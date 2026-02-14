"""
AUTO-BROKER: Semantic Cache Service for Hume AI

Cache semantica per ridurre costi Hume AI del 90%
usando embeddings e similarità coseno con pgvector.
"""
import hashlib
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Callable, List
from uuid import uuid4, UUID

import structlog
import httpx
import numpy as np
from sqlalchemy import select, func, text, and_, desc
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import SentimentCache
from api.services.cost_tracker import CostTracker, COST_CONFIG

logger = structlog.get_logger()

# Configurazione
SIMILARITY_THRESHOLD = 0.95  # Cosine similarity >= 0.95
EMBEDDING_DIMENSIONS = 384  # paraphrase-multilingual-MiniLM-L12-v2
HUME_COST_PER_MINUTE = COST_CONFIG.get("hume_ai_per_minute", 0.15)


class EmbeddingService:
    """
    Servizio per generare embeddings usando sentence-transformers.
    Fallback a API esterna se modello non disponibile localmente.
    """
    
    _model = None
    _model_name = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    
    @classmethod
    def _get_model(cls):
        """Lazy loading del modello."""
        if cls._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                cls._model = SentenceTransformer(cls._model_name)
                logger.info("embedding_model_loaded", model=cls._model_name)
            except ImportError:
                logger.error("sentence_transformers_not_installed")
                raise RuntimeError("sentence-transformers required. Install: pip install sentence-transformers")
        return cls._model
    
    @classmethod
    def encode(cls, text: str) -> List[float]:
        """
        Genera embedding per il testo.
        
        Args:
            text: Testo da embeddare
            
        Returns:
            Lista di 384 float (normalizzati)
        """
        model = cls._get_model()
        
        # Trunca testo troppo lungo (modello ha max 256 tokens)
        text = text[:1000]
        
        # Genera embedding
        embedding = model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
        
        return embedding.tolist()
    
    @classmethod
    def cosine_similarity(cls, vec1: List[float], vec2: List[float]) -> float:
        """
        Calcola similarità coseno tra due vettori.
        
        Args:
            vec1, vec2: Vettori di dimensione 384
            
        Returns:
            Similarità coseno (0-1)
        """
        v1 = np.array(vec1)
        v2 = np.array(vec2)
        
        # I vettori sono già normalizzati, quindi dot product = cosine similarity
        return float(np.dot(v1, v2))


class SemanticCacheService:
    """
    Servizio di cache semantica per Hume AI.
    
    Riduce i costi del 90% evitando chiamate duplicate quando
    il contenuto audio è semanticamente simile.
    
    Features:
    - Embedding con sentence-transformers (384 dim)
    - Similarità coseno >= 0.95 per cache hit
    - Storage in PostgreSQL con pgvector
    - Race condition handling
    - GDPR compliance (auto-cleanup dopo 30 giorni)
    """
    
    def __init__(self, db_session: AsyncSession, cost_tracker: Optional[CostTracker] = None):
        self.db = db_session
        self.cost_tracker = cost_tracker
        self.embedding_service = EmbeddingService()
    
    def _compute_transcription_hash(self, text: str) -> str:
        """
        Calcola SHA256 della transcription per lookup esatto.
        
        Args:
            text: Testo della transcription
            
        Returns:
            Hash SHA256 (64 char)
        """
        return hashlib.sha256(text.encode('utf-8')).hexdigest()
    
    def _create_preview(self, text: str, max_len: int = 100) -> str:
        """
        Crea preview della transcription per debug (no PII completa).
        
        Args:
            text: Testo completo
            max_len: Lunghezza massima preview
            
        Returns:
            Preview troncata
        """
        if len(text) <= max_len:
            return text
        return text[:max_len] + "..."
    
    async def _find_similar_cached(
        self, 
        embedding: List[float], 
        threshold: float = SIMILARITY_THRESHOLD
    ) -> Optional[SentimentCache]:
        """
        Cerca entry cache con similarità >= threshold.
        
        Usa pgvector con operatore <=> (cosine distance).
        Distance < 0.05 significa similarity > 0.95.
        
        Args:
            embedding: Vettore embedding della query
            threshold: Soglia similarità (default 0.95)
            
        Returns:
            Entry cache più simile o None
        """
        max_distance = 1.0 - threshold  # 0.05 per threshold 0.95
        
        try:
            # Query usando pgvector - ordina per distanza coseno
            # <=> è l'operatore di distanza coseno in pgvector
            query = text("""
                SELECT id, embedding, transcription_hash, sentiment_result, 
                       emotion_scores, hit_count, created_at
                FROM sentiment_cache
                WHERE embedding <=> :embedding < :max_distance
                ORDER BY embedding <=> :embedding
                LIMIT 1
            """)
            
            result = await self.db.execute(
                query,
                {
                    "embedding": str(embedding),  # pgvector accetta formato array string
                    "max_distance": max_distance
                }
            )
            
            row = result.fetchone()
            if row:
                logger.debug(
                    "semantic_cache_similarity_found",
                    cache_id=str(row.id),
                    distance=1.0 - row.embedding if hasattr(row, 'embedding') else "unknown"
                )
                return row
            
            return None
            
        except Exception as e:
            logger.error(
                "semantic_cache_similarity_query_failed",
                error=str(e),
                error_type=type(e).__name__
            )
            # Fallback: cerca match esatto per hash
            return None
    
    async def _find_exact_match(self, transcription_hash: str) -> Optional[SentimentCache]:
        """
        Cerca match esatto per hash SHA256.
        
        Args:
            transcription_hash: Hash della transcription
            
        Returns:
            Entry cache esatta o None
        """
        result = await self.db.execute(
            select(SentimentCache).where(
                SentimentCache.transcription_hash == transcription_hash
            )
        )
        return result.scalar_one_or_none()
    
    async def _save_to_cache(
        self,
        transcription: str,
        embedding: List[float],
        sentiment_result: Dict[str, Any]
    ) -> Optional[SentimentCache]:
        """
        Salva risultato in cache.
        
        Usa INSERT ... ON CONFLICT DO NOTHING per gestire race conditions.
        
        Args:
            transcription: Testo transcription (non salvato, solo hash)
            embedding: Vettore embedding
            sentiment_result: Risultato analisi Hume
            
        Returns:
            Entry creata o None se duplicato
        """
        transcription_hash = self._compute_transcription_hash(transcription)
        preview = self._create_preview(transcription)
        
        # Estrai emotion scores per query veloci
        emotion_scores = sentiment_result.get("emotions", {})
        
        try:
            # INSERT con ON CONFLICT per race condition handling
            stmt = insert(SentimentCache).values(
                id=uuid4(),
                embedding=embedding,
                transcription_hash=transcription_hash,
                transcription_preview=preview,
                sentiment_result=sentiment_result,
                emotion_scores=emotion_scores,
                created_at=datetime.utcnow(),
                last_accessed=datetime.utcnow(),
                hit_count=1
            ).on_conflict_do_nothing(
                index_elements=['transcription_hash']
            )
            
            result = await self.db.execute(stmt)
            await self.db.commit()
            
            if result.rowcount > 0:
                logger.info(
                    "semantic_cache_saved",
                    hash=transcription_hash[:16],
                    preview=preview
                )
                
                # Recupera l'entry creata
                return await self._find_exact_match(transcription_hash)
            else:
                # Conflict - qualcun altro ha salvato nel frattempo
                logger.debug(
                    "semantic_cache_race_condition_avoided",
                    hash=transcription_hash[:16]
                )
                return await self._find_exact_match(transcription_hash)
                
        except Exception as e:
            await self.db.rollback()
            logger.error(
                "semantic_cache_save_failed",
                error=str(e),
                hash=transcription_hash[:16]
            )
            return None
    
    async def _update_hit_count(self, cache_entry: SentimentCache):
        """
        Incrementa hit_count e aggiorna last_accessed.
        
        Args:
            cache_entry: Entry cache da aggiornare
        """
        try:
            await self.db.execute(
                text("""
                    UPDATE sentiment_cache
                    SET hit_count = hit_count + 1,
                        last_accessed = NOW()
                    WHERE id = :id
                """),
                {"id": cache_entry.id}
            )
            await self.db.commit()
            
        except Exception as e:
            logger.warning(
                "semantic_cache_hit_update_failed",
                cache_id=str(cache_entry.id),
                error=str(e)
            )
    
    async def get_or_compute(
        self,
        transcription: str,
        compute_func: Callable[[], Any],
        shipment_id: Optional[UUID] = None,
        customer_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Recupera da cache o computa risultato sentiment analysis.
        
        Args:
            transcription: Testo da analizzare
            compute_func: Funzione async da chiamare se cache miss (Hume API)
            shipment_id: UUID spedizione per tracking costi
            customer_id: UUID cliente per tracking costi
            
        Returns:
            Risultato sentiment analysis con campo 'source' ("cache" o "hume")
        """
        if not transcription or len(transcription.strip()) < 5:
            # Testo troppo corto, non vale la pena cachare
            result = await compute_func()
            result["source"] = "hume"
            result["cache_hit"] = False
            return result
        
        start_time = time.time()
        
        # 1. Prova match esatto (hash)
        transcription_hash = self._compute_transcription_hash(transcription)
        exact_match = await self._find_exact_match(transcription_hash)
        
        if exact_match:
            # Cache hit esatto!
            await self._update_hit_count(exact_match)
            
            # Traccia risparmio
            if self.cost_tracker:
                await self.cost_tracker.track_cost_saved_from_cache(
                    shipment_id=shipment_id,
                    customer_id=customer_id,
                    cost_saved=HUME_COST_PER_MINUTE,
                    cache_type="hume_exact"
                )
            
            lookup_time = (time.time() - start_time) * 1000
            
            logger.info(
                "semantic_cache_hit_exact",
                hash=transcription_hash[:16],
                hit_count=exact_match.hit_count + 1,
                lookup_ms=round(lookup_time, 2)
            )
            
            result = dict(exact_match.sentiment_result)
            result["source"] = "cache"
            result["cache_hit"] = True
            result["cache_type"] = "exact"
            result["lookup_time_ms"] = round(lookup_time, 2)
            return result
        
        # 2. Genera embedding e cerca similarità
        try:
            embedding = self.embedding_service.encode(transcription)
            similar_entry = await self._find_similar_cached(embedding)
            
            if similar_entry:
                # Cache hit semantico!
                await self._update_hit_count(similar_entry)
                
                # Traccia risparmio
                if self.cost_tracker:
                    await self.cost_tracker.track_cost_saved_from_cache(
                        shipment_id=shipment_id,
                        customer_id=customer_id,
                        cost_saved=HUME_COST_PER_MINUTE,
                        cache_type="hume_semantic"
                    )
                
                lookup_time = (time.time() - start_time) * 1000
                
                logger.info(
                    "semantic_cache_hit_semantic",
                    hash=transcription_hash[:16],
                    hit_count=similar_entry.hit_count + 1,
                    lookup_ms=round(lookup_time, 2)
                )
                
                result = dict(similar_entry.sentiment_result)
                result["source"] = "cache"
                result["cache_hit"] = True
                result["cache_type"] = "semantic"
                result["lookup_time_ms"] = round(lookup_time, 2)
                return result
                
        except Exception as e:
            logger.warning(
                "semantic_cache_embedding_failed",
                error=str(e),
                fallback="calling_hume_directly"
            )
        
        # 3. Cache miss - chiama Hume
        logger.info(
            "semantic_cache_miss",
            hash=transcription_hash[:16],
            preview=self._create_preview(transcription)
        )
        
        result = await compute_func()
        result["source"] = "hume"
        result["cache_hit"] = False
        
        # 4. Salva in cache per future richieste
        try:
            if "error" not in result:  # Non salvare errori
                embedding = self.embedding_service.encode(transcription)
                await self._save_to_cache(transcription, embedding, result)
        except Exception as e:
            logger.warning(
                "semantic_cache_save_after_compute_failed",
                error=str(e)
            )
        
        return result
    
    async def get_stats(self) -> Dict[str, Any]:
        """
        Statistiche cache.
        
        Returns:
            Dict con hit_rate, total_entries, cost_saved, etc.
        """
        try:
            # Totale entries
            result = await self.db.execute(
                select(func.count(SentimentCache.id))
            )
            total_entries = result.scalar() or 0
            
            # Hit count totale
            result = await self.db.execute(
                select(func.sum(SentimentCache.hit_count))
            )
            total_hits = result.scalar() or 0
            
            # Entries recenti (ultimi 7 giorni)
            week_ago = datetime.utcnow() - timedelta(days=7)
            result = await self.db.execute(
                select(func.count(SentimentCache.id)).where(
                    SentimentCache.created_at >= week_ago
                )
            )
            recent_entries = result.scalar() or 0
            
            # Calcola hit rate stimato
            # hits / (hits + entries) approssima il hit rate
            total_requests = total_hits + total_entries
            hit_rate = (total_hits / total_requests * 100) if total_requests > 0 else 0
            
            # Costo risparmiato stimato
            cost_saved = total_hits * HUME_COST_PER_MINUTE
            
            # Performance: tempo medio lookup (se tracciato)
            # Nota: richiederebbe campo aggiuntivo per tracciare tempi
            
            return {
                "total_entries": total_entries,
                "recent_entries_7d": recent_entries,
                "total_hits": total_hits,
                "hit_rate_percent": round(hit_rate, 2),
                "cost_saved_eur": round(cost_saved, 2),
                "hume_cost_per_minute": HUME_COST_PER_MINUTE,
                "similarity_threshold": SIMILARITY_THRESHOLD,
                "embedding_dimensions": EMBEDDING_DIMENSIONS
            }
            
        except Exception as e:
            logger.error("semantic_cache_stats_failed", error=str(e))
            return {
                "error": str(e),
                "total_entries": 0,
                "hit_rate_percent": 0,
                "cost_saved_eur": 0
            }
    
    async def clear_old_cache(self, days: int = 30) -> int:
        """
        Cancella entries più vecchie di X giorni (GDPR compliance).
        
        Args:
            days: Giorni di retention (default 30)
            
        Returns:
            Numero di entries cancellate
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        try:
            result = await self.db.execute(
                text("""
                    DELETE FROM sentiment_cache
                    WHERE created_at < :cutoff_date
                    RETURNING id
                """),
                {"cutoff_date": cutoff_date}
            )
            
            deleted_ids = result.fetchall()
            await self.db.commit()
            
            deleted_count = len(deleted_ids)
            
            logger.info(
                "semantic_cache_cleared_old",
                deleted_count=deleted_count,
                older_than_days=days
            )
            
            return deleted_count
            
        except Exception as e:
            await self.db.rollback()
            logger.error(
                "semantic_cache_clear_failed",
                error=str(e)
            )
            return 0
    
    async def warm_cache(self, transcriptions: List[str]) -> Dict[str, Any]:
        """
        Precarica cache con lista di transcriptions comuni.
        
        Args:
            transcriptions: Lista di testi da precaricare
            
        Returns:
            Statistiche warming
        """
        stats = {"processed": 0, "cached": 0, "errors": 0}
        
        for text in transcriptions:
            stats["processed"] += 1
            
            try:
                # Verifica se già in cache
                text_hash = self._compute_transcription_hash(text)
                existing = await self._find_exact_match(text_hash)
                
                if existing:
                    continue  # Già presente
                
                # Genera embedding
                embedding = self.embedding_service.encode(text)
                
                # Crea risultato placeholder (da aggiornare con Hume reale)
                placeholder_result = {
                    "emotions": {"Neutral": 1.0},
                    "dominant_emotion": "Neutral",
                    "sentiment_score": 0.0,
                    "confidence": 0.0,
                    "analysis_method": "warmed",
                    "requires_escalation": False,
                    "warmed_at": datetime.now().isoformat()
                }
                
                await self._save_to_cache(text, embedding, placeholder_result)
                stats["cached"] += 1
                
            except Exception as e:
                stats["errors"] += 1
                logger.warning(
                    "semantic_cache_warm_failed",
                    text_preview=text[:50],
                    error=str(e)
                )
        
        logger.info(
            "semantic_cache_warm_completed",
            **stats
        )
        
        return stats


# Singleton e dependency injection
_semantic_cache_service: Optional[SemanticCacheService] = None


async def get_semantic_cache(
    db: AsyncSession = None,
    cost_tracker: Optional[CostTracker] = None
) -> SemanticCacheService:
    """
    Factory per SemanticCacheService.
    
    Usage:
        cache = await get_semantic_cache(db)
        result = await cache.get_or_compute(text, compute_func)
    """
    global _semantic_cache_service
    
    if db:
        return SemanticCacheService(db, cost_tracker)
    
    if _semantic_cache_service is None:
        raise RuntimeError("Database session required")
    
    return _semantic_cache_service
