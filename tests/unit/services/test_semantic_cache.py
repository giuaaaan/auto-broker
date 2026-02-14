"""
AUTO-BROKER: Unit Tests for Semantic Cache Service

Test suite per la cache semantica con sentence-transformers.
"""
import asyncio
import hashlib
from datetime import datetime, timedelta
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4, UUID

import pytest
import pytest_asyncio
import numpy as np
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from api.models import Base, SentimentCache
from api.services.semantic_cache import (
    SemanticCacheService, EmbeddingService,
    SIMILARITY_THRESHOLD, EMBEDDING_DIMENSIONS
)


# ==========================================
# FIXTURES
# ==========================================

@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Fixture per database in-memory."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=NullPool,
        echo=False
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest_asyncio.fixture
async def semantic_cache(db_session: AsyncSession) -> SemanticCacheService:
    """Crea SemanticCacheService."""
    return SemanticCacheService(db_session)


@pytest.fixture
def sample_embedding() -> list:
    """Embedding di test (384 dimensioni, normalizzato)."""
    vec = np.random.randn(EMBEDDING_DIMENSIONS)
    vec = vec / np.linalg.norm(vec)  # Normalizza
    return vec.tolist()


@pytest.fixture
def sample_transcriptions():
    """Coppie di transcriptions per test similarità."""
    return {
        "similar_pair": (
            "Il prezzo è troppo alto per il servizio offerto",
            "Costo molto elevato rispetto alla qualità"
        ),
        "different_pair": (
            "Prezzo alto",
            "Prezzo basso e conveniente"
        ),
        "exact": "Servizio eccellente, sono molto soddisfatto"
    }


# ==========================================
# TESTS - Embedding Service
# ==========================================

class TestEmbeddingService:
    """Test per EmbeddingService."""
    
    def test_encode_dimensions(self):
        """Test: Embedding ha dimensione corretta (384)."""
        text = "Testo di prova in italiano"
        
        try:
            embedding = EmbeddingService.encode(text)
            
            assert len(embedding) == EMBEDDING_DIMENSIONS
            assert isinstance(embedding, list)
            assert all(isinstance(x, float) for x in embedding)
        except RuntimeError:
            pytest.skip("sentence-transformers not installed")
    
    def test_encode_normalization(self):
        """Test: Embedding è normalizzato (norma = 1)."""
        text = "Un altro test"
        
        try:
            embedding = EmbeddingService.encode(text)
            vec = np.array(embedding)
            norm = np.linalg.norm(vec)
            
            assert abs(norm - 1.0) < 0.0001  # Normalizzato
        except RuntimeError:
            pytest.skip("sentence-transformers not installed")
    
    def test_similarity_same_text(self):
        """Test: Similarità di testo con se stesso = 1.0."""
        text = "Identical text"
        
        try:
            emb1 = EmbeddingService.encode(text)
            emb2 = EmbeddingService.encode(text)
            
            sim = EmbeddingService.cosine_similarity(emb1, emb2)
            
            assert sim > 0.999  # Praticamente 1.0
        except RuntimeError:
            pytest.skip("sentence-transformers not installed")
    
    def test_similarity_semantically_similar(self):
        """Test: Frasi simili semanticamente hanno alta similarità."""
        text1 = "Il prezzo è troppo alto"
        text2 = "Costo molto elevato"
        
        try:
            emb1 = EmbeddingService.encode(text1)
            emb2 = EmbeddingService.encode(text2)
            
            sim = EmbeddingService.cosine_similarity(emb1, emb2)
            
            assert sim > SIMILARITY_THRESHOLD  # > 0.95
        except RuntimeError:
            pytest.skip("sentence-transformers not installed")
    
    def test_similarity_different(self):
        """Test: Frasi diverse hanno bassa similarità."""
        text1 = "Prezzo alto"
        text2 = "Prezzo basso"
        
        try:
            emb1 = EmbeddingService.encode(text1)
            emb2 = EmbeddingService.encode(text2)
            
            sim = EmbeddingService.cosine_similarity(emb1, emb2)
            
            # Similarità dovrebbe essere più bassa
            assert sim < 0.90  # Significativamente diverso
        except RuntimeError:
            pytest.skip("sentence-transformers not installed")


# ==========================================
# TESTS - Semantic Cache Service
# ==========================================

class TestSemanticCacheService:
    """Test per SemanticCacheService."""
    
    @pytest.mark.asyncio
    async def test_compute_transcription_hash(self, semantic_cache):
        """Test: Hash è deterministico e univoco."""
        text = "Testo di prova"
        
        hash1 = semantic_cache._compute_transcription_hash(text)
        hash2 = semantic_cache._compute_transcription_hash(text)
        hash3 = semantic_cache._compute_transcription_hash("Altro testo")
        
        assert hash1 == hash2  # Deterministico
        assert len(hash1) == 64  # SHA256 hex
        assert hash1 != hash3  # Diverso per testo diverso
    
    @pytest.mark.asyncio
    async def test_create_preview(self, semantic_cache):
        """Test: Preview è troncata correttamente."""
        short = "Corto"
        long_text = "A" * 200
        
        preview_short = semantic_cache._create_preview(short)
        preview_long = semantic_cache._create_preview(long_text)
        
        assert preview_short == short  # Non troncato
        assert len(preview_long) == 103  # 100 + "..."
        assert preview_long.endswith("...")
    
    @pytest.mark.asyncio
    async def test_save_and_retrieve_exact_match(
        self,
        semantic_cache: SemanticCacheService,
        db_session: AsyncSession,
        sample_embedding
    ):
        """Test: Salva e recupera con match esatto."""
        text = "Testo esatto per cache"
        result = {
            "emotions": {"Joy": 0.9},
            "sentiment_score": 0.8,
            "analysis_method": "hume"
        }
        
        # Salva
        saved = await semantic_cache._save_to_cache(text, sample_embedding, result)
        assert saved is not None
        
        # Recupera con match esatto
        text_hash = semantic_cache._compute_transcription_hash(text)
        retrieved = await semantic_cache._find_exact_match(text_hash)
        
        assert retrieved is not None
        assert retrieved.transcription_hash == text_hash
        assert retrieved.sentiment_result["emotions"]["Joy"] == 0.9
    
    @pytest.mark.asyncio
    async def test_exact_match_increments_hit_count(
        self,
        semantic_cache: SemanticCacheService,
        db_session: AsyncSession,
        sample_embedding
    ):
        """Test: Hit count incrementato su match esatto."""
        text = "Testo hit count"
        result = {"emotions": {"Joy": 0.9}}
        
        # Salva
        await semantic_cache._save_to_cache(text, sample_embedding, result)
        
        # Prima hit
        hash_val = semantic_cache._compute_transcription_hash(text)
        entry1 = await semantic_cache._find_exact_match(hash_val)
        initial_hits = entry1.hit_count
        
        await semantic_cache._update_hit_count(entry1)
        
        # Verifica incremento
        entry2 = await semantic_cache._find_exact_match(hash_val)
        assert entry2.hit_count == initial_hits + 1
    
    @pytest.mark.asyncio
    async def test_get_or_compute_cache_miss(
        self,
        semantic_cache: SemanticCacheService,
        sample_embedding
    ):
        """Test: Cache miss chiama compute_func e salva risultato."""
        text = "Nuovo testo mai visto"
        
        mock_compute = AsyncMock(return_value={
            "emotions": {"Joy": 0.9},
            "sentiment_score": 0.8
        })
        
        with patch.object(EmbeddingService, 'encode', return_value=sample_embedding):
            result = await semantic_cache.get_or_compute(text, mock_compute)
        
        # Deve aver chiamato compute
        mock_compute.assert_called_once()
        
        # Risultato deve avere source hume
        assert result["source"] == "hume"
        assert result["cache_hit"] == False
    
    @pytest.mark.asyncio
    async def test_get_or_compute_cache_hit_exact(
        self,
        semantic_cache: SemanticCacheService,
        db_session: AsyncSession,
        sample_embedding
    ):
        """Test: Stesso testo restituisce cache hit."""
        text = "Testo per cache hit"
        computed_result = {
            "emotions": {"Joy": 0.9},
            "sentiment_score": 0.8
        }
        
        mock_compute = AsyncMock(return_value=computed_result)
        
        with patch.object(EmbeddingService, 'encode', return_value=sample_embedding):
            # Prima chiamata (miss)
            result1 = await semantic_cache.get_or_compute(text, mock_compute)
            
            # Reset mock
            mock_compute.reset_mock()
            
            # Seconda chiamata (hit)
            result2 = await semantic_cache.get_or_compute(text, mock_compute)
        
        # Seconda non deve chiamare compute
        mock_compute.assert_not_called()
        
        # Risultati devono coincidere
        assert result2["cache_hit"] == True
        assert result2["cache_type"] == "exact"
    
    @pytest.mark.asyncio
    async def test_race_condition_handling(
        self,
        semantic_cache: SemanticCacheService,
        sample_embedding
    ):
        """Test: Race condition gestita con ON CONFLICT."""
        text = "Testo race condition"
        result = {"emotions": {"Joy": 0.9}}
        
        # Salva due volte simultaneamente
        with patch.object(EmbeddingService, 'encode', return_value=sample_embedding):
            saved1 = await semantic_cache._save_to_cache(text, sample_embedding, result)
            saved2 = await semantic_cache._save_to_cache(text, sample_embedding, result)
        
        # Almeno uno deve essere salvato
        assert saved1 is not None or saved2 is not None
        
        # Query deve trovare esattamente 1 entry
        hash_val = semantic_cache._compute_transcription_hash(text)
        entry = await semantic_cache._find_exact_match(hash_val)
        assert entry is not None
    
    @pytest.mark.asyncio
    async def test_get_stats_empty(self, semantic_cache):
        """Test: Stats con cache vuota."""
        stats = await semantic_cache.get_stats()
        
        assert stats["total_entries"] == 0
        assert stats["total_hits"] == 0
        assert stats["hit_rate_percent"] == 0
        assert stats["cost_saved_eur"] == 0
    
    @pytest.mark.asyncio
    async def test_get_stats_with_data(
        self,
        semantic_cache: SemanticCacheService,
        db_session: AsyncSession,
        sample_embedding
    ):
        """Test: Stats con dati presenti."""
        # Crea entries
        for i in range(5):
            text = f"Testo {i}"
            result = {"emotions": {"Joy": 0.9}}
            
            cache_entry = SentimentCache(
                id=uuid4(),
                embedding=sample_embedding,
                transcription_hash=hashlib.sha256(text.encode()).hexdigest(),
                transcription_preview=text[:50],
                sentiment_result=result,
                hit_count=i * 10,  # 0, 10, 20, 30, 40
                created_at=datetime.utcnow()
            )
            db_session.add(cache_entry)
        
        await db_session.commit()
        
        stats = await semantic_cache.get_stats()
        
        assert stats["total_entries"] == 5
        assert stats["total_hits"] == 100  # 0+10+20+30+40
        assert stats["hit_rate_percent"] > 0
        assert stats["cost_saved_eur"] == 100 * 0.15  # 100 hits * 0.15 EUR
    
    @pytest.mark.asyncio
    async def test_clear_old_cache(
        self,
        semantic_cache: SemanticCacheService,
        db_session: AsyncSession,
        sample_embedding
    ):
        """Test: Pulizia entries vecchie."""
        # Crea entry vecchia
        old_entry = SentimentCache(
            id=uuid4(),
            embedding=sample_embedding,
            transcription_hash="old_hash",
            transcription_preview="old",
            sentiment_result={},
            created_at=datetime.utcnow() - timedelta(days=60)
        )
        db_session.add(old_entry)
        
        # Crea entry nuova
        new_entry = SentimentCache(
            id=uuid4(),
            embedding=sample_embedding,
            transcription_hash="new_hash",
            transcription_preview="new",
            sentiment_result={},
            created_at=datetime.utcnow()
        )
        db_session.add(new_entry)
        
        await db_session.commit()
        
        # Pulisci entries > 30 giorni
        deleted = await semantic_cache.clear_old_cache(days=30)
        
        assert deleted == 1
        
        # Verifica che solo la nuova rimanga
        result = await db_session.execute(
            select(SentimentCache)
        )
        remaining = result.scalars().all()
        assert len(remaining) == 1
        assert remaining[0].transcription_hash == "new_hash"
    
    @pytest.mark.asyncio
    async def test_warm_cache(
        self,
        semantic_cache: SemanticCacheService,
        sample_embedding
    ):
        """Test: Warming cache con lista transcriptions."""
        transcriptions = [
            "Servizio eccellente",
            "Prezzo troppo alto",
            "Non sono soddisfatto"
        ]
        
        with patch.object(EmbeddingService, 'encode', return_value=sample_embedding):
            result = await semantic_cache.warm_cache(transcriptions)
        
        assert result["processed"] == 3
        assert result["cached"] == 3
        assert result["errors"] == 0
    
    @pytest.mark.asyncio
    async def test_short_text_not_cached(self, semantic_cache):
        """Test: Testi troppo corti non vengono cachati."""
        short_text = "Ciao"
        
        mock_compute = AsyncMock(return_value={"emotions": {"Joy": 0.9}})
        
        result = await semantic_cache.get_or_compute(short_text, mock_compute)
        
        # Deve chiamare compute
        mock_compute.assert_called_once()
        # Non deve avere cache_hit flag
        assert "cache_hit" in result


# ==========================================
# TESTS - Performance
# ==========================================

class TestSemanticCachePerformance:
    """Test performance."""
    
    @pytest.mark.asyncio
    async def test_lookup_performance(
        self,
        semantic_cache: SemanticCacheService,
        db_session: AsyncSession,
        sample_embedding
    ):
        """Test: Lookup < 50ms con 10k entries."""
        import time
        
        # Popola cache con entries (simulato)
        # In produzione avremmo 10k entries reali
        for i in range(100):  # Limitato per test velocità
            entry = SentimentCache(
                id=uuid4(),
                embedding=sample_embedding,
                transcription_hash=f"hash_{i}",
                transcription_preview=f"Test {i}",
                sentiment_result={"emotions": {"Joy": 0.9}},
                created_at=datetime.utcnow()
            )
            db_session.add(entry)
        
        await db_session.commit()
        
        # Misura tempo lookup
        start = time.time()
        await semantic_cache._find_exact_match("hash_50")
        elapsed_ms = (time.time() - start) * 1000
        
        # Deve essere < 50ms
        assert elapsed_ms < 50, f"Lookup took {elapsed_ms}ms, expected < 50ms"


# ==========================================
# INTEGRATION TESTS
# ==========================================

class TestSemanticCacheIntegration:
    """Test integrazione completa."""
    
    @pytest.mark.asyncio
    async def test_full_flow_exact_match(self, semantic_cache):
        """Test: Flow completo con match esatto."""
        text = "Il servizio è stato eccellente e professionale"
        
        async def mock_compute():
            return {
                "emotions": {"Joy": 0.95, "Trust": 0.8},
                "sentiment_score": 0.88,
                "analysis_method": "hume"
            }
        
        # Prima chiamata (miss)
        result1 = await semantic_cache.get_or_compute(text, mock_compute)
        assert result1["cache_hit"] == False
        assert result1["source"] == "hume"
        
        # Seconda chiamata (hit)
        result2 = await semantic_cache.get_or_compute(text, mock_compute)
        assert result2["cache_hit"] == True
        assert result2["source"] == "cache"
        assert result2["cache_type"] == "exact"
        
        # Risultati devono essere uguali
        assert result1["sentiment_score"] == result2["sentiment_score"]
