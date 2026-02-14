"""
EQ Sentiment Service Test Suite
Target: 100% Coverage for Quota Management, Circuit Breaker, Fallback
"""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from datetime import datetime

import httpx
import respx
from httpx import Response

from api.services.circuit_breaker import CircuitBreaker, CircuitState
from api.services.eq_sentiment_service import SentimentService, EQSettings


# ============= Circuit Breaker Tests =============

class TestCircuitBreaker:
    """Tests for Circuit Breaker implementation."""
    
    @pytest.mark.asyncio
    async def test_initial_state_is_closed(self):
        """Test circuit starts in CLOSED state."""
        cb = CircuitBreaker("test")
        assert cb.state == CircuitState.CLOSED
    
    @pytest.mark.asyncio
    async def test_opens_after_failures(self):
        """Test circuit opens after threshold failures."""
        cb = CircuitBreaker("test", failure_threshold=3)
        
        # Simulate 3 failures
        for _ in range(3):
            try:
                await cb.call(lambda: (_ for _ in ()).throw(Exception("Fail")))
            except Exception:
                pass
        
        assert cb.state == CircuitState.OPEN
        assert cb._failure_count == 3
    
    @pytest.mark.asyncio
    async def test_closed_allows_execution(self):
        """Test CLOSED state allows normal execution."""
        cb = CircuitBreaker("test")
        
        async def success_func():
            return "success"
        
        result = await cb.call(success_func)
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_open_rejects_execution(self):
        """Test OPEN state rejects execution."""
        cb = CircuitBreaker("test", failure_threshold=1)
        
        # Open the circuit
        try:
            await cb.call(lambda: (_ for _ in ()).throw(Exception("Fail")))
        except Exception:
            pass
        
        assert cb.state == CircuitState.OPEN
        
        # Next call should fail fast
        with pytest.raises(Exception) as exc_info:
            await cb.call(lambda: "should not execute")
        
        assert "OPEN" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_half_open_after_timeout(self):
        """Test circuit enters HALF_OPEN after recovery timeout."""
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.1)
        
        # Open the circuit
        try:
            await cb.call(lambda: (_ for _ in ()).throw(Exception("Fail")))
        except Exception:
            pass
        
        assert cb.state == CircuitState.OPEN
        
        # Wait for timeout
        await asyncio.sleep(0.15)
        
        # State should now be HALF_OPEN
        assert cb.state == CircuitState.HALF_OPEN
    
    @pytest.mark.asyncio
    async def test_closes_after_success_in_half_open(self):
        """Test circuit closes after successful calls in HALF_OPEN."""
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.1)
        
        # Open -> half-open
        try:
            await cb.call(lambda: (_ for _ in ()).throw(Exception("Fail")))
        except Exception:
            pass
        
        await asyncio.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN
        
        # Success calls should close circuit
        async def success():
            return "ok"
        
        await cb.call(success)
        await cb.call(success)
        
        assert cb.state == CircuitState.CLOSED
    
    @pytest.mark.asyncio
    async def test_reopens_on_failure_in_half_open(self):
        """Test circuit reopens if failure occurs in HALF_OPEN."""
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.1)
        
        # Open -> half-open
        try:
            await cb.call(lambda: (_ for _ in ()).throw(Exception("Fail")))
        except Exception:
            pass
        
        await asyncio.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN
        
        # Failure should reopen
        try:
            await cb.call(lambda: (_ for _ in ()).throw(Exception("Fail again")))
        except Exception:
            pass
        
        assert cb.state == CircuitState.OPEN
    
    @pytest.mark.asyncio
    async def test_reset_manual(self):
        """Test manual circuit reset."""
        cb = CircuitBreaker("test", failure_threshold=1)
        
        # Open the circuit
        try:
            await cb.call(lambda: (_ for _ in ()).throw(Exception("Fail")))
        except Exception:
            pass
        
        assert cb.state == CircuitState.OPEN
        
        # Reset
        await cb.reset()
        
        assert cb.state == CircuitState.CLOSED
        assert cb._failure_count == 0
    
    @pytest.mark.asyncio
    async def test_success_resets_failure_count(self):
        """Test success in CLOSED state reduces failure count."""
        cb = CircuitBreaker("test", failure_threshold=5)
        
        # Add some failures
        for _ in range(2):
            try:
                await cb.call(lambda: (_ for _ in ()).throw(Exception("Fail")))
            except Exception:
                pass
        
        assert cb._failure_count == 2
        
        # Success should reduce count
        async def success():
            return "ok"
        
        await cb.call(success)
        
        # Should be reduced (or 0 depending on implementation)
        assert cb._failure_count < 2
    
    @pytest.mark.asyncio
    async def test_get_state_dict(self):
        """Test state dict returns correct structure."""
        cb = CircuitBreaker("test")
        
        state = cb.get_state_dict()
        
        assert "state" in state
        assert "failure_count" in state
        assert state["state"] == "closed"
    
    @pytest.mark.asyncio
    async def test_sync_function_support(self):
        """Test circuit breaker works with sync functions."""
        cb = CircuitBreaker("test")
        
        def sync_success():
            return "sync result"
        
        result = await cb.call(sync_success)
        assert result == "sync result"
    
    @pytest.mark.asyncio
    async def test_half_open_max_calls_limit(self):
        """Test HALF_OPEN closes circuit after 2 consecutive successes."""
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.1, half_open_max_calls=2)
        
        # Open -> half-open
        try:
            await cb.call(lambda: (_ for _ in ()).throw(Exception("Fail")))
        except Exception:
            pass
        
        await asyncio.sleep(0.15)
        
        # First call in half-open should work
        assert cb.state == CircuitState.HALF_OPEN
        await cb.call(lambda: "success1")
        assert cb.state == CircuitState.HALF_OPEN  # Still half-open after 1 success
        
        # Second call should close circuit
        await cb.call(lambda: "success2")
        assert cb.state == CircuitState.CLOSED  # Circuit closed after 2 successes
        
        # Third call should work normally (circuit closed)
        result = await cb.call(lambda: "success3")
        assert result == "success3"


# ============= Sentiment Service Tests =============

class TestSentimentService:
    """Tests for SentimentService."""
    
    @pytest.fixture
    def service(self):
        """Create SentimentService instance."""
        return SentimentService()
    
    @pytest.mark.asyncio
    async def test_analyze_empty_transcription(self, service):
        """Test handling of empty transcription."""
        result = await service.analyze(None, "", 123)
        
        assert result["analysis_method"] == "empty"
        assert result["sentiment_score"] == 0.0
    
    @pytest.mark.asyncio
    async def test_analyze_short_transcription(self, service):
        """Test handling of very short transcription."""
        result = await service.analyze(None, "ab", 123)
        
        assert result["analysis_method"] == "empty"
    
    @pytest.mark.asyncio
    async def test_keyword_analysis_positive(self, service):
        """Test keyword analysis detects positive sentiment."""
        result = service._analyze_keywords("Sono felice e contento", 123)
        
        assert result["analysis_method"] == "keyword"
        assert result["emotions"]["Joy"] > 0
        assert result["confidence"] == 0.5
    
    @pytest.mark.asyncio
    async def test_keyword_analysis_negative(self, service):
        """Test keyword analysis detects negative sentiment."""
        result = service._analyze_keywords("Sono arrabbiato e furioso", 123)
        
        assert result["analysis_method"] == "keyword"
        assert result["emotions"]["Anger"] > 0
        assert result["sentiment_score"] < 0
    
    @pytest.mark.asyncio
    async def test_keyword_escalation_anger(self, service):
        """Test keyword analysis triggers escalation on anger."""
        result = service._analyze_keywords("Sono arrabbiato!", 123)
        
        assert result["requires_escalation"] is True
        assert result["dominant_emotion"] == "Anger"
    
    @pytest.mark.asyncio
    async def test_keyword_escalation_legal(self, service):
        """Test keyword analysis triggers escalation on legal terms."""
        result = service._analyze_keywords("Chiamerò il mio avvocato!", 123)
        
        assert result["requires_escalation"] is True
    
    @pytest.mark.asyncio
    async def test_calc_score_positive(self, service):
        """Test sentiment score calculation for positive emotions."""
        emotions = {"Joy": 0.8, "Trust": 0.6, "Anxiety": 0.1}
        score = service._calc_score(emotions)
        
        assert score > 0
    
    @pytest.mark.asyncio
    async def test_calc_score_negative(self, service):
        """Test sentiment score calculation for negative emotions."""
        emotions = {"Anger": 0.8, "Anxiety": 0.6, "Joy": 0.1}
        score = service._calc_score(emotions)
        
        assert score < 0
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_hume_quota_check_success(self, service):
        """Test Hume quota check with successful API response."""
        # Mock the usage endpoint
        route = respx.get("https://api.hume.ai/v0/account/usage").mock(
            return_value=Response(200, json={"minutes_used": 500, "minutes_limit": 1000})
        )
        
        with patch.object(EQSettings, "HUME_API_KEY", "test-key"):
            result = await service.check_hume_quota()
        
        assert result["status"] == "ok"
        assert result["usage_percent"] == 50.0
        assert result["fallback_required"] is False
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_hume_quota_check_exceeded(self, service):
        """Test Hume quota check when quota exceeded."""
        route = respx.get("https://api.hume.ai/v0/account/usage").mock(
            return_value=Response(200, json={"minutes_used": 950, "minutes_limit": 1000})
        )
        
        with patch.object(EQSettings, "HUME_API_KEY", "test-key"):
            result = await service.check_hume_quota()
        
        assert result["fallback_required"] is True
        assert result["usage_percent"] == 95.0
    
    @pytest.mark.asyncio
    async def test_hume_quota_check_api_failure(self, service):
        """Test Hume quota check handles API failure gracefully."""
        with respx.mock:
            respx.get("https://api.hume.ai/v0/account/usage").mock(
                return_value=Response(500)
            )
            
            result = await service.check_hume_quota()
        
        assert result["status"] == "error"
        assert result["fallback_required"] is True
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_hume_analysis_success(self, service):
        """Test Hume analysis with successful response."""
        # Mock job creation
        respx.post("https://api.hume.ai/v0/batch/jobs").mock(
            return_value=Response(200, json={"job_id": "job-123"})
        )
        
        # Mock job polling
        respx.get("https://api.hume.ai/v0/batch/jobs/job-123").mock(
            return_value=Response(200, json={
                "status": "completed",
                "predictions": [{
                    "emotions": [
                        {"name": "Joy", "score": 0.8},
                        {"name": "Anger", "score": 0.1}
                    ]
                }]
            })
        )
        
        with patch.object(EQSettings, "HUME_API_KEY", "test-key"):
            result = await service._analyze_hume("http://recording.mp3", "test", 123)
        
        assert result["analysis_method"] == "hume"
        assert "emotions" in result
    
    @pytest.mark.asyncio
    @respx.mock
    async def test_ollama_analysis_success(self, service):
        """Test Ollama analysis with successful response."""
        respx.post("http://ollama:11434/api/generate").mock(
            return_value=Response(200, json={
                "response": json.dumps({
                    "emotions": {"Joy": 0.7, "Anxiety": 0.2},
                    "dominant": "Joy",
                    "requires_escalation": False
                })
            })
        )
        
        result = await service._analyze_ollama("Sono felice", 123)
        
        assert result["analysis_method"] == "ollama"
        assert result["dominant_emotion"] == "Joy"
    
    @pytest.mark.asyncio
    async def test_three_tier_fallback(self, service):
        """Test three-tier fallback: Hume -> Ollama -> Keywords."""
        # Mock quota to require fallback
        with patch.object(service, "check_hume_quota", new_callable=AsyncMock) as mock_quota:
            mock_quota.return_value = {"fallback_required": True}
            
            # Mock Ollama to fail
            with patch.object(service, "_analyze_ollama", new_callable=AsyncMock) as mock_ollama:
                mock_ollama.side_effect = Exception("Ollama down")
                
                result = await service.analyze(None, "Testo di prova", 123)
                
                # Should fall back to keywords
                assert result["analysis_method"] == "keyword"
    
    @pytest.mark.asyncio
    async def test_trigger_escalation_logs(self, service, caplog):
        """Test escalation triggers critical log."""
        with caplog.at_level("CRITICAL"):
            await service.trigger_escalation(123, "Anger")
        
        assert "ESCALATION" in caplog.text
        assert "123" in caplog.text


# ============= Database Integrity Tests =============

@pytest.mark.skip(reason="Requires actual database - run integration test")
class TestDatabaseIntegrity:
    """Tests for database CASCADE and referential integrity."""
    
    async def test_cascade_delete_lead_removes_sentiment(self, db_session):
        """Test CASCADE delete removes sentiment when lead is deleted."""
        # This would require actual database setup
        pass
    
    async def test_set_null_on_sentiment_delete(self, db_session):
        """Test SET NULL on interaction history when sentiment deleted."""
        pass


# ============= Edge Case Tests =============

class TestEdgeCases:
    """Edge case tests."""
    
    @pytest.mark.asyncio
    async def test_very_long_transcription(self):
        """Test handling of very long transcription."""
        service = SentimentService()
        long_text = "Parola " * 10000
        
        result = service._analyze_keywords(long_text, 123)
        
        assert result["analysis_method"] == "keyword"
    
    @pytest.mark.asyncio
    async def test_special_characters(self):
        """Test handling of special characters."""
        service = SentimentService()
        text = "Ciao! Come stai? 😊 @#$%"
        
        result = service._analyze_keywords(text, 123)
        
        assert result["analysis_method"] == "keyword"
    
    @pytest.mark.asyncio
    async def test_mixed_emotions(self):
        """Test handling of mixed emotions."""
        service = SentimentService()
        text = "Sono felice ma anche preoccupato"
        
        result = service._analyze_keywords(text, 123)
        
        assert result["emotions"]["Joy"] > 0
        assert result["emotions"]["Anxiety"] > 0


# Run with: pytest tests/unit/test_eq_sentiment_quota.py -v --cov=api --cov-report=term-missing --cov-fail-under=100
