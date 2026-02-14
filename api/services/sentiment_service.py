"""
AUTO-BROKER 3.0 - Emotional Intelligence Sentiment Service
Production-grade with Hume AI quota management and graceful fallback
Architecture: Meta AI Agents 2025, Google Affective Computing
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

import httpx
import redis.asyncio as redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import SentimentAnalysis
from services.database import get_db

logger = logging.getLogger(__name__)


class SentimentService:
    """
    Service for voice sentiment analysis with Hume AI Prosody API.
    
    Features:
    - Quota management (1000 min/month free tier)
    - Graceful degradation to local Ollama fallback
    - Redis caching for quota checks
    - Cascade handling for database operations
    """
    
    HUME_API_URL = "https://api.hume.ai/v0/batch/jobs"
    HUME_USAGE_URL = "https://api.hume.ai/v0/account/usage"
    QUOTA_LIMIT = 1000  # minutes per month (free tier)
    QUOTA_THRESHOLD = 0.9  # 90% threshold for fallback activation
    
    def __init__(self, hume_api_key: Optional[str] = None, redis_client: Optional[redis.Redis] = None):
        """
        Initialize SentimentService.
        
        Args:
            hume_api_key: Hume AI API key (optional, can use env var)
            redis_client: Redis client for caching (optional)
        """
        self.hume_api_key = hume_api_key or self._get_api_key_from_env()
        self.redis = redis_client or redis.Redis(
            host='localhost', 
            port=6380, 
            decode_responses=True
        )
        self.use_fallback = False
        self._quota_checked_at: Optional[datetime] = None
    
    def _get_api_key_from_env(self) -> str:
        """Get Hume API key from environment."""
        import os
        api_key = os.getenv('HUME_API_KEY')
        if not api_key:
            logger.warning("HUME_API_KEY not set, will use fallback mode")
            self.use_fallback = True
        return api_key or ""
    
    async def check_hume_quota(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Check Hume API usage. If > 90% (900 min), activate fallback mode.
        
        Caches result in Redis for 5 minutes to avoid rate limiting.
        
        Args:
            force_refresh: Force refresh cache even if recent check exists
            
        Returns:
            Dict with quota status including:
            - minutes_used: float
            - minutes_remaining: float  
            - usage_percent: float
            - quota_exceeded: bool
            - near_limit: bool
        """
        cache_key = "hume:quota:check"
        
        if not force_refresh:
            cached = await self.redis.get(cache_key)
            if cached:
                try:
                    return json.loads(cached)
                except json.JSONDecodeError:
                    logger.warning("Invalid quota cache, refreshing")
        
        # If no API key, immediately return fallback state
        if not self.hume_api_key:
            result = {
                "minutes_used": 0,
                "minutes_remaining": 0,
                "usage_percent": 1.0,
                "quota_exceeded": True,
                "near_limit": True,
                "fallback_activated": True,
                "reason": "no_api_key"
            }
            self.use_fallback = True
            return result
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.HUME_USAGE_URL,
                    headers={"Authorization": f"Bearer {self.hume_api_key}"},
                    timeout=10.0
                )
                response.raise_for_status()
                data = response.json()
                
                minutes_used = float(data.get("minutes_used", 0))
                minutes_limit = float(data.get("minutes_limit", self.QUOTA_LIMIT))
                usage_percent = minutes_used / minutes_limit if minutes_limit > 0 else 1.0
                
                result = {
                    "minutes_used": minutes_used,
                    "minutes_remaining": max(0, minutes_limit - minutes_used),
                    "usage_percent": usage_percent,
                    "quota_exceeded": usage_percent >= 1.0,
                    "near_limit": usage_percent >= self.QUOTA_THRESHOLD,
                    "fallback_activated": False,
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                # Cache for 5 minutes
                await self.redis.setex(cache_key, 300, json.dumps(result))
                
                # Activate fallback if above threshold
                if result["near_limit"] or result["quota_exceeded"]:
                    self.use_fallback = True
                    logger.warning(
                        f"Hume API quota at {usage_percent:.1%}. "
                        f"Switching to fallback mode. Used: {minutes_used}/{minutes_limit} min"
                    )
                else:
                    self.use_fallback = False
                
                self._quota_checked_at = datetime.utcnow()
                return result
                
        except httpx.HTTPStatusError as e:
            logger.error(f"Hume API error checking quota: {e}")
            # On 429 (rate limit), assume near limit
            if e.response.status_code == 429:
                self.use_fallback = True
                return {
                    "minutes_used": 900,
                    "minutes_remaining": 100,
                    "usage_percent": 0.9,
                    "quota_exceeded": False,
                    "near_limit": True,
                    "fallback_activated": True,
                    "reason": "rate_limited"
                }
            raise
        except Exception as e:
            logger.error(f"Failed to check Hume quota: {e}")
            # On any error, activate fallback for safety
            self.use_fallback = True
            return {
                "error": str(e),
                "near_limit": True,
                "fallback_activated": True,
                "reason": "error"
            }
    
    async def analyze_call_audio(
        self, 
        recording_url: str, 
        lead_id: str,
        call_id: Optional[str] = None,
        transcription: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze call audio for sentiment.
        
        If Hume quota > 90% or error, uses fallback local analysis.
        
        Args:
            recording_url: URL to audio file
            lead_id: UUID of lead
            call_id: Optional call identifier
            transcription: Optional transcript for fallback analysis
            
        Returns:
            Dict with analysis results
        """
        # Check quota before proceeding
        quota_status = await self.check_hume_quota()
        
        if self.use_fallback or quota_status.get("near_limit"):
            logger.info(f"Using fallback analysis for lead {lead_id} (Hume quota limit)")
            if transcription:
                result = await self.fallback_text_analysis(transcription)
            else:
                result = self._default_sentiment()
                result["note"] = "No transcription available for fallback"
            
            result.update({
                "method": "fallback",
                "status": "completed",
                "lead_id": lead_id,
                "call_id": call_id,
                "quota_status": quota_status
            })
            return result
        
        # Proceed with Hume if quota available
        return await self._analyze_with_hume(recording_url, lead_id, call_id)
    
    async def _analyze_with_hume(
        self, 
        recording_url: str, 
        lead_id: str,
        call_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Submit audio to Hume AI for analysis."""
        payload = {
            "urls": [recording_url],
            "models": {"prosody": {}},
            "notify": True
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.HUME_API_URL,
                    json=payload,
                    headers={"Authorization": f"Bearer {self.hume_api_key}"},
                    timeout=30.0
                )
                response.raise_for_status()
                job_data = response.json()
                
                # Estimate quota usage (will be refined by webhook callback)
                await self._estimate_quota_usage(recording_url, 5.0)  # Assume 5 min default
                
                return {
                    "job_id": job_data.get("job_id"),
                    "status": "processing",
                    "lead_id": lead_id,
                    "call_id": call_id,
                    "method": "hume_ai",
                    "message": "Analysis submitted, awaiting webhook callback"
                }
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:  # Rate limit
                logger.warning("Hume rate limit hit, activating fallback")
                self.use_fallback = True
                # Force cache refresh on next check
                await self.redis.delete("hume:quota:check")
                raise Exception("Hume rate limit exceeded, fallback activated")
            raise
    
    async def _estimate_quota_usage(self, recording_url: str, estimated_minutes: float = 5.0):
        """
        Estimate minutes used and update counter in Redis.
        
        Args:
            recording_url: URL (used for tracking, not actual duration extraction)
            estimated_minutes: Estimated call duration
        """
        current = await self.redis.get("hume:quota:estimated")
        if current:
            try:
                current = float(current)
            except ValueError:
                current = 0
        else:
            current = 0
        
        new_total = current + estimated_minutes
        await self.redis.setex("hume:quota:estimated", 3600, str(new_total))
        
        # If estimate exceeds 900 (90%), force refresh of actual quota check
        if new_total > (self.QUOTA_LIMIT * self.QUOTA_THRESHOLD):
            logger.info(f"Estimated quota at {new_total} min, forcing quota refresh")
            await self.redis.delete("hume:quota:check")
    
    def parse_hume_emotions(self, hume_response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse Hume API response and extract dominant emotion and sentiment.
        
        Args:
            hume_response: Raw response from Hume webhook
            
        Returns:
            Parsed sentiment data
        """
        predictions = hume_response.get("predictions", [{}])[0]
        emotions = predictions.get("emotions", [])
        
        if not emotions:
            return self._default_sentiment()
        
        # Find dominant emotion
        dominant = max(emotions, key=lambda x: x.get("score", 0))
        
        # Calculate negative emotion aggregate
        negative_emotions = ["Anxiety", "Anger", "Frustration", "Disappointment", "Sadness", "Distress"]
        negative_score = sum([
            e.get("score", 0) for e in emotions 
            if e.get("name") in negative_emotions
        ])
        
        # Determine escalation need
        requires_escalation = (
            dominant.get("name") in ["Anger", "Frustration"] and dominant.get("score", 0) > 0.7
        ) or negative_score > 1.5
        
        escalation_reason = None
        if requires_escalation:
            if dominant.get("name") in ["Anger", "Frustration"]:
                escalation_reason = f"High {dominant['name']} detected ({dominant['score']:.2f})"
            else:
                escalation_reason = f"Aggregate negative sentiment ({negative_score:.2f})"
        
        # Calculate confidence
        total_score = sum(e.get("score", 0) for e in emotions)
        confidence = total_score / len(emotions) if emotions else 0
        
        # Calculate overall sentiment score (-1 to 1)
        positive_emotions = ["Joy", "Excitement", "Interest", "Satisfaction"]
        positive_score = sum([
            e.get("score", 0) for e in emotions 
            if e.get("name") in positive_emotions
        ])
        sentiment_score = (positive_score - negative_score) / max(positive_score + negative_score, 1)
        sentiment_score = max(-1.0, min(1.0, sentiment_score))  # Clamp to [-1, 1]
        
        return {
            "dominant_emotion": dominant.get("name", "Neutral"),
            "dominant_score": round(dominant.get("score", 0), 2),
            "sentiment_score": round(sentiment_score, 2),
            "emotions": {e.get("name", "Unknown"): round(e.get("score", 0), 2) for e in emotions},
            "requires_escalation": requires_escalation,
            "escalation_reason": escalation_reason,
            "confidence": round(confidence, 2),
            "prosody_raw": hume_response
        }
    
    async def fallback_text_analysis(self, transcription: str) -> Dict[str, Any]:
        """
        Local analysis when Hume is not available (quota or error).
        
        Uses keyword matching + Ollama local LLM if available.
        
        Args:
            transcription: Call transcript text
            
        Returns:
            Sentiment analysis result
        """
        text_lower = transcription.lower()
        
        emotion_scores = {
            "Anxiety": 0.0, 
            "Joy": 0.0, 
            "Anger": 0.0, 
            "Frustration": 0.0,
            "Interest": 0.0,
            "Neutral": 0.5
        }
        
        # Italian keyword patterns
        anxiety_keywords = [
            "preoccupato", "stress", "urgente", "temo", "paura", "ansia", 
            "non so", "incerto", "dubbio", "rischio", "problema"
        ]
        anger_keywords = [
            "arrabbiato", "furioso", "inaccettabile", "schifo", "odio", 
            "maledetti", "assurdo", "ridicolo", "basta", "non accetto"
        ]
        joy_keywords = [
            "felice", "ottimo", "perfetto", "grazie", "bene", "ottima",
            "contento", "soddisfatto", "eccellente", "fantastico"
        ]
        frustration_keywords = [
            "deluso", "frustrato", "aspettavo di più", "non funziona",
            "delusione", "promesso", "non rispettato"
        ]
        interest_keywords = [
            "interessato", "vorrei sapere", "mi informo", "curioso",
            "opportunità", "valutare", "considerare"
        ]
        
        # Score based on keyword presence
        for kw in anxiety_keywords:
            if kw in text_lower:
                emotion_scores["Anxiety"] = min(1.0, emotion_scores["Anxiety"] + 0.25)
                emotion_scores["Neutral"] = 0
                
        for kw in anger_keywords:
            if kw in text_lower:
                emotion_scores["Anger"] = min(1.0, emotion_scores["Anger"] + 0.4)
                emotion_scores["Neutral"] = 0
                
        for kw in joy_keywords:
            if kw in text_lower:
                emotion_scores["Joy"] = min(1.0, emotion_scores["Joy"] + 0.3)
                emotion_scores["Neutral"] = 0
                
        for kw in frustration_keywords:
            if kw in text_lower:
                emotion_scores["Frustration"] = min(1.0, emotion_scores["Frustration"] + 0.3)
                emotion_scores["Neutral"] = 0
                
        for kw in interest_keywords:
            if kw in text_lower:
                emotion_scores["Interest"] = min(1.0, emotion_scores["Interest"] + 0.2)
        
        # Try Ollama for enhanced analysis if available
        try:
            ollama_result = await self._ollama_sentiment_analysis(transcription)
            if ollama_result:
                # Blend Ollama results with keyword (weighted average)
                for emotion, score in ollama_result.items():
                    if emotion in emotion_scores:
                        emotion_scores[emotion] = (emotion_scores[emotion] * 0.6) + (score * 0.4)
        except Exception as e:
            logger.debug(f"Ollama analysis failed (expected if not running): {e}")
        
        # Determine dominant emotion
        dominant = max(emotion_scores, key=emotion_scores.get)
        
        # Calculate sentiment score
        positive = emotion_scores["Joy"] + emotion_scores["Interest"]
        negative = emotion_scores["Anxiety"] + emotion_scores["Anger"] + emotion_scores["Frustration"]
        sentiment_score = (positive - negative) / max(positive + negative, 0.5)
        
        # Determine escalation
        requires_escalation = (
            emotion_scores["Anger"] > 0.5 or 
            emotion_scores["Frustration"] > 0.6 or
            (emotion_scores["Anxiety"] > 0.7 and negative > positive)
        )
        
        return {
            "dominant_emotion": dominant,
            "dominant_score": round(emotion_scores[dominant], 2),
            "emotions": {k: round(v, 2) for k, v in emotion_scores.items()},
            "sentiment_score": round(sentiment_score, 2),
            "requires_escalation": requires_escalation,
            "escalation_reason": "High negative emotion detected" if requires_escalation else None,
            "confidence": 0.6,  # Lower confidence for fallback
            "method": "fallback_local",
            "keyword_matched": True
        }
    
    async def _ollama_sentiment_analysis(self, text: str) -> Optional[Dict[str, float]]:
        """
        Advanced fallback using Ollama local LLM.
        
        Args:
            text: Text to analyze
            
        Returns:
            Dict of emotion scores or None if Ollama unavailable
        """
        import os
        
        ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        model = os.getenv("DEFAULT_LLM_MODEL", "llama3.2:3b")
        
        try:
            async with httpx.AsyncClient() as client:
                prompt = f"""Analyze the sentiment of this Italian text. 
                Reply ONLY with valid JSON format like {{"emotion_name": score, ...}} 
                where emotion_name is one of: Joy, Anxiety, Anger, Frustration, Interest, Neutral
                and score is 0.0 to 1.0.
                
                Text: {text[:500]}"""
                
                response = await client.post(
                    f"{ollama_host}/api/generate",
                    json={
                        "model": model,
                        "prompt": prompt,
                        "stream": False,
                        "format": "json"
                    },
                    timeout=10.0
                )
                response.raise_for_status()
                
                result = response.json()
                response_text = result.get("response", "")
                
                # Parse JSON from response
                try:
                    emotions = json.loads(response_text)
                    # Normalize to expected emotions
                    normalized = {}
                    for emotion, score in emotions.items():
                        emotion_cap = emotion.capitalize()
                        if emotion_cap in ["Joy", "Anxiety", "Anger", "Frustration", "Interest", "Neutral"]:
                            normalized[emotion_cap] = float(score)
                    return normalized if normalized else None
                except json.JSONDecodeError:
                    logger.warning(f"Could not parse Ollama response: {response_text[:100]}")
                    return None
                    
        except Exception as e:
            logger.debug(f"Ollama not available: {e}")
            return None
    
    def _default_sentiment(self) -> Dict[str, Any]:
        """Default neutral sentiment."""
        return {
            "dominant_emotion": "Neutral",
            "dominant_score": 0.5,
            "sentiment_score": 0.0,
            "emotions": {"Neutral": 0.5},
            "requires_escalation": False,
            "escalation_reason": None,
            "confidence": 0.0,
            "method": "default",
            "note": "No analysis performed"
        }
    
    async def store_sentiment_analysis(
        self, 
        db: AsyncSession,
        call_id: str,
        lead_id: str,
        analysis_result: Dict[str, Any]
    ) -> SentimentAnalysis:
        """
        Store sentiment analysis result in database.
        
        Args:
            db: Database session
            call_id: Call identifier
            lead_id: Lead UUID
            analysis_result: Parsed analysis result
            
        Returns:
            Created SentimentAnalysis record
        """
        sentiment = SentimentAnalysis(
            call_id=call_id,
            lead_id=lead_id,
            sentiment_score=analysis_result.get("sentiment_score", 0),
            emotions=analysis_result.get("emotions", {}),
            dominant_emotion=analysis_result.get("dominant_emotion", "Neutral"),
            confidence=analysis_result.get("confidence", 0),
            prosody_raw=analysis_result.get("prosody_raw"),
            requires_escalation=analysis_result.get("requires_escalation", False),
            escalation_reason=analysis_result.get("escalation_reason"),
            analyzed_at=datetime.utcnow()
        )
        
        db.add(sentiment)
        await db.commit()
        await db.refresh(sentiment)
        
        logger.info(f"Stored sentiment analysis for call {call_id}, lead {lead_id}")
        return sentiment
    
    async def get_lead_sentiment_history(
        self, 
        db: AsyncSession, 
        lead_id: str,
        limit: int = 10
    ) -> List[SentimentAnalysis]:
        """
        Get sentiment history for a lead.
        
        Args:
            db: Database session
            lead_id: Lead UUID
            limit: Max records to return
            
        Returns:
            List of sentiment analysis records
        """
        result = await db.execute(
            select(SentimentAnalysis)
            .where(SentimentAnalysis.lead_id == lead_id)
            .order_by(SentimentAnalysis.analyzed_at.desc())
            .limit(limit)
        )
        return result.scalars().all()


# Singleton instance for application use
_sentiment_service: Optional[SentimentService] = None


def get_sentiment_service() -> SentimentService:
    """Get or create singleton SentimentService instance."""
    global _sentiment_service
    if _sentiment_service is None:
        _sentiment_service = SentimentService()
    return _sentiment_service
