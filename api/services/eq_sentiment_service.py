"""
EQ Sentiment Service - Three-tier cascade implementation with Semantic Cache
Hume AI -> Ollama -> Keywords (guaranteed)

Aggiunta cache semantica per riduzione costi 90%
"""

import httpx
import json
import asyncio
import re
import os
from typing import Dict, Optional, Any
from datetime import datetime
import logging
from uuid import UUID

from api.services.circuit_breaker import CircuitBreaker, HUME_CIRCUIT, OLLAMA_CIRCUIT
from api.services.semantic_cache import SemanticCacheService, get_semantic_cache

logger = logging.getLogger(__name__)


class EQSettings:
    """Settings loaded from environment."""
    HUME_API_KEY = os.getenv("HUME_API_KEY", "")
    HUME_API_URL = "https://api.hume.ai/v0/batch/jobs"
    HUME_USAGE_URL = "https://api.hume.ai/v0/account/usage"
    HUME_QUOTA_LIMIT = 1000
    HUME_QUOTA_THRESHOLD = 0.9
    OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")
    DEFAULT_LLM_MODEL = "llama3.2:3b"
    REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
    SEMANTIC_CACHE_ENABLED = os.getenv("SEMANTIC_CACHE_ENABLED", "true").lower() == "true"


class SentimentService:
    """
    Three-tier sentiment analysis service with semantic caching.
    
    Tier 0: Semantic Cache (90% cost reduction)
    Tier 1: Hume AI (cloud, highest accuracy)
    Tier 2: Ollama local LLM (on-premise fallback)
    Tier 3: Keyword extraction (guaranteed, no external deps)
    """
    
    def __init__(self, redis_client=None, db_session=None):
        self.redis = redis_client
        self.db = db_session
        self.hume_breaker = HUME_CIRCUIT
        self.ollama_breaker = OLLAMA_CIRCUIT
        self._quota_cache_key = "hume:quota:status"
        self._semantic_cache = None
    
    async def _get_semantic_cache(self) -> Optional[SemanticCacheService]:
        """Lazy initialization della cache semantica."""
        if not EQSettings.SEMANTIC_CACHE_ENABLED:
            return None
        
        if self._semantic_cache is None and self.db:
            try:
                self._semantic_cache = await get_semantic_cache(self.db)
            except Exception as e:
                logger.warning(f"Semantic cache initialization failed: {e}")
                return None
        
        return self._semantic_cache
    
    async def check_hume_quota(self) -> Dict[str, Any]:
        """Check Hume quota with Redis caching (TTL 300s)."""
        # Try cache first
        if self.redis:
            try:
                cached = await self.redis.get(self._quota_cache_key)
                if cached:
                    return json.loads(cached)
            except Exception as e:
                logger.warning(f"Redis cache read failed: {e}")
        
        # Fetch from API
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    EQSettings.HUME_USAGE_URL,
                    headers={"Authorization": f"Bearer {EQSettings.HUME_API_KEY}"}
                )
                response.raise_for_status()
                data = response.json()
                
                minutes_used = data.get("minutes_used", 0)
                usage_percent = minutes_used / EQSettings.HUME_QUOTA_LIMIT
                
                result = {
                    "minutes_used": minutes_used,
                    "usage_percent": round(usage_percent * 100, 2),
                    "fallback_required": usage_percent >= EQSettings.HUME_QUOTA_THRESHOLD,
                    "status": "ok"
                }
                
                # Cache for 5 minutes
                if self.redis:
                    try:
                        await self.redis.setex(self._quota_cache_key, 300, json.dumps(result))
                    except Exception as e:
                        logger.warning(f"Redis cache write failed: {e}")
                
                return result
        except Exception as e:
            logger.error(f"Quota check failed: {e}")
            # Conservative fallback
            return {
                "status": "error",
                "usage_percent": 100.0,
                "fallback_required": True,
                "error": str(e)
            }
    
    async def analyze(
        self,
        recording_url: Optional[str],
        transcription: str,
        lead_id: int,
        use_cache: bool = True,
        shipment_id: Optional[UUID] = None,
        customer_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Three-tier cascade: Cache -> Hume -> Ollama -> Keywords.
        
        Args:
            recording_url: URL to audio recording (for Hume)
            transcription: Text transcription
            lead_id: Lead identifier
            use_cache: Whether to use semantic cache (default True)
            shipment_id: Shipment UUID for cost tracking
            customer_id: Customer UUID for cost tracking
            
        Returns sentiment analysis with escalation flags and cache metadata.
        """
        # Validate input
        if not transcription or len(transcription.strip()) < 3:
            return self._create_empty_result(lead_id)
        
        # Tier 0: Semantic Cache (if enabled and text available)
        if use_cache and transcription and self.db:
            try:
                semantic_cache = await self._get_semantic_cache()
                if semantic_cache:
                    return await semantic_cache.get_or_compute(
                        transcription=transcription,
                        compute_func=lambda: self._call_hume_api(
                            recording_url, transcription, lead_id
                        ),
                        shipment_id=shipment_id,
                        customer_id=customer_id
                    )
            except Exception as e:
                logger.warning(f"Semantic cache lookup failed: {e}, falling back to direct Hume")
        
        # Tier 1-3: Direct cascade (no cache or cache disabled)
        return await self._call_hume_api(recording_url, transcription, lead_id)
    
    async def _call_hume_api(
        self,
        recording_url: Optional[str],
        transcription: str,
        lead_id: int
    ) -> Dict[str, Any]:
        """
        Chiama Hume API o fallback (metodo privato estratto).
        
        Questo metodo è il compute_func passato alla semantic cache.
        """
        quota = await self.check_hume_quota()
        
        # Tier 1: Hume AI (if available and quota OK)
        if (recording_url and 
            not quota.get("fallback_required") and 
            self.hume_breaker.state == CircuitState.CLOSED):
            try:
                result = await self.hume_breaker.call(
                    self._analyze_hume,
                    recording_url,
                    transcription,
                    lead_id
                )
                result["cache_hit"] = False
                result["source"] = result.get("source", "hume")
                return result
            except Exception as e:
                logger.warning(f"Hume analysis failed: {e}, trying Ollama")
        
        # Tier 2: Ollama Local (if available)
        if transcription and self.ollama_breaker.state == CircuitState.CLOSED:
            try:
                result = await self.ollama_breaker.call(
                    self._analyze_ollama,
                    transcription,
                    lead_id
                )
                result["cache_hit"] = False
                result["source"] = result.get("source", "ollama")
                return result
            except Exception as e:
                logger.warning(f"Ollama analysis failed: {e}, using keywords")
        
        # Tier 3: Guaranteed fallback
        result = self._analyze_keywords(transcription, lead_id)
        result["cache_hit"] = False
        result["source"] = result.get("source", "keyword")
        return result
    
    async def _analyze_hume(
        self,
        recording_url: str,
        transcription: str,
        lead_id: int
    ) -> Dict[str, Any]:
        """Analyze with Hume AI Prosody API."""
        payload = {
            "urls": [recording_url],
            "models": {"prosody": {}},
            "notify": False
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                EQSettings.HUME_API_URL,
                json=payload,
                headers={"Authorization": f"Bearer {EQSettings.HUME_API_KEY}"}
            )
            response.raise_for_status()
            job_data = response.json()
            job_id = job_data.get("job_id")
            
            # Poll for result (max 30s)
            for attempt in range(15):
                await asyncio.sleep(2)
                result_resp = await client.get(
                    f"{EQSettings.HUME_API_URL}/{job_id}",
                    headers={"Authorization": f"Bearer {EQSettings.HUME_API_KEY}"}
                )
                result_data = result_resp.json()
                
                if result_data.get("status") == "completed":
                    return self._parse_hume_result(result_data, lead_id, transcription, "hume")
                elif result_data.get("status") == "failed":
                    raise Exception(f"Hume job failed: {result_data.get('error')}")
            
            raise Exception("Hume polling timeout")
    
    async def _analyze_ollama(
        self,
        transcription: str,
        lead_id: int
    ) -> Dict[str, Any]:
        """Fallback to local Ollama LLM."""
        prompt = f"""Analyze the sentiment of this Italian text.
Return ONLY JSON in this exact format:
{{"emotions": {{"Anxiety": 0.0, "Joy": 0.0, "Anger": 0.0}}, "dominant": "Joy", "requires_escalation": false}}

Text: {transcription[:500]}"""
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{EQSettings.OLLAMA_HOST}/api/generate",
                json={
                    "model": EQSettings.DEFAULT_LLM_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json"
                }
            )
            response.raise_for_status()
            data = response.json()
            
            try:
                result = json.loads(data["response"])
            except (json.JSONDecodeError, KeyError) as e:
                logger.error(f"Ollama returned invalid JSON: {e}")
                raise Exception("Invalid Ollama response format")
            
            emotions = result.get("emotions", {})
            dominant = result.get("dominant", "Neutral")
            
            return {
                "lead_id": lead_id,
                "transcription": transcription,
                "emotions": emotions,
                "dominant_emotion": dominant,
                "sentiment_score": self._calc_score(emotions),
                "requires_escalation": result.get("requires_escalation", False) or 
                                       emotions.get("Anger", 0) > 0.7,
                "confidence": 0.7,
                "analysis_method": "ollama",
                "analyzed_at": datetime.now().isoformat()
            }
    
    def _analyze_keywords(self, transcription: str, lead_id: int) -> Dict[str, Any]:
        """Guaranteed local analysis - zero external dependencies."""
        text = transcription.lower()
        emotions = {
            "Anxiety": 0.0,
            "Anger": 0.0,
            "Joy": 0.0,
            "Trust": 0.0,
            "Neutral": 0.5
        }
        
        # Italian emotion patterns
        patterns = {
            "Anxiety": ["preoccupato", "stress", "urgente", "temo", "paura", "ansia", 
                       "timore", "incerto", "dubbioso", "nervoso"],
            "Anger": ["arrabbiato", "furioso", "inaccettabile", "schifo", "odio",
                     "furiosa", "rabbia", "incazzato", "stuf", "bast"],
            "Joy": ["felice", "ottimo", "perfetto", "grazie", "bene", "contento",
                   "soddisfatto", "fantastico", "bello", "brav"],
            "Trust": ["fiducia", "sicuro", "certo", "garantito", "affidabile",
                     "professional", "esperto", "onesto"]
        }
        
        for emotion, keywords in patterns.items():
            for kw in keywords:
                if kw in text:
                    emotions[emotion] = min(1.0, emotions[emotion] + 0.3)
        
        # Determine dominant
        dominant = max(emotions, key=emotions.get)
        if emotions[dominant] < 0.3:
            dominant = "Neutral"
        
        # Calculate overall score (-1 to 1)
        positive = emotions["Joy"] + emotions["Trust"]
        negative = emotions["Anxiety"] + emotions["Anger"]
        sentiment_score = (positive - negative) / 2
        
        # Escalation triggers
        requires_escalation = (
            emotions["Anger"] > 0.5 or
            "avvocato" in text or
            "denuncia" in text or
            "responsabile" in text or
            sentiment_score < -0.7
        )
        
        return {
            "lead_id": lead_id,
            "transcription": transcription,
            "emotions": emotions,
            "dominant_emotion": dominant,
            "sentiment_score": round(sentiment_score, 2),
            "requires_escalation": requires_escalation,
            "confidence": 0.5,
            "analysis_method": "keyword",
            "analyzed_at": datetime.now().isoformat()
        }
    
    def _parse_hume_result(
        self,
        data: Dict,
        lead_id: int,
        transcription: str,
        method: str
    ) -> Dict[str, Any]:
        """Parse Hume API response."""
        predictions = data.get("predictions", [{}])[0]
        emotions_list = predictions.get("emotions", [])
        
        # Convert to dict
        emotion_dict = {e["name"]: e["score"] for e in emotions_list}
        
        # Find dominant
        if emotions_list:
            dominant = max(emotions_list, key=lambda x: x["score"])
            dominant_name = dominant["name"]
            dominant_score = dominant["score"]
        else:
            dominant_name = "Neutral"
            dominant_score = 0
        
        # Calculate sentiment score
        negative = sum([
            emotion_dict.get(e, 0) 
            for e in ["Anxiety", "Anger", "Frustration", "Distress"]
        ])
        positive = sum([
            emotion_dict.get(e, 0)
            for e in ["Joy", "Satisfaction", "Trust", "Excitement"]
        ])
        sentiment_score = (positive - negative) / 2
        sentiment_score = max(-1.0, min(1.0, sentiment_score))
        
        # Escalation check
        requires_escalation = (
            dominant_name in ["Anger", "Frustration"] and dominant_score > 0.7 or
            sentiment_score < -0.7
        )
        
        # Average confidence
        confidence = sum(e["score"] for e in emotions_list) / len(emotions_list) if emotions_list else 0
        
        return {
            "lead_id": lead_id,
            "transcription": transcription,
            "emotions": emotion_dict,
            "dominant_emotion": dominant_name,
            "sentiment_score": round(sentiment_score, 2),
            "requires_escalation": requires_escalation,
            "confidence": round(confidence, 2),
            "analysis_method": method,
            "analyzed_at": datetime.now().isoformat()
        }
    
    def _calc_score(self, emotions: Dict[str, float]) -> float:
        """Calculate sentiment score from emotions dict."""
        negative = emotions.get("Anxiety", 0) + emotions.get("Anger", 0) + emotions.get("Frustration", 0)
        positive = emotions.get("Joy", 0) + emotions.get("Trust", 0) + emotions.get("Satisfaction", 0)
        return round((positive - negative) / 2, 2)
    
    def _create_empty_result(self, lead_id: int) -> Dict[str, Any]:
        """Create result for empty/invalid input."""
        return {
            "lead_id": lead_id,
            "transcription": "",
            "emotions": {"Neutral": 1.0},
            "dominant_emotion": "Neutral",
            "sentiment_score": 0.0,
            "requires_escalation": False,
            "confidence": 0.0,
            "analysis_method": "empty",
            "analyzed_at": datetime.now().isoformat(),
            "cache_hit": False,
            "source": "empty"
        }
    
    async def trigger_escalation(self, lead_id: int, reason: str):
        """Send escalation notification."""
        logger.critical(f"🚨 ESCALATION: Lead {lead_id}, Reason: {reason}")
        # Implement Slack webhook here
        # await send_slack_alert(f"Lead {lead_id} requires escalation: {reason}")


# Import CircuitState here to avoid circular import issues
from api.services.circuit_breaker import CircuitState
