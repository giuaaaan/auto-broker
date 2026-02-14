"""
EQ API Routes - FastAPI router with rate limiting
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from typing import Dict, Optional, Any
import logging

from api.services.eq_sentiment_service import SentimentService
from api.services.eq_profiling_service import ProfilingService
from api.services.eq_persuasive_service import PersuasiveEngine
from api.services.circuit_breaker import HUME_CIRCUIT, OLLAMA_CIRCUIT

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/eq", tags=["Emotional Intelligence"])

# Simple rate limiting storage (use Redis in production)
_request_counts: Dict[str, Dict[str, Any]] = {}


async def rate_limit_check(request: Request, max_requests: int = 10, window: int = 60) -> bool:
    """
    Check if request is within rate limit.
    
    Args:
        request: FastAPI request
        max_requests: Max requests per window
        window: Time window in seconds
    
    Returns:
        True if allowed, False if rate limited
    """
    client_ip = request.client.host if request.client else "unknown"
    key = f"{client_ip}:{request.url.path}"
    
    import time
    now = time.time()
    
    if key not in _request_counts:
        _request_counts[key] = {"count": 1, "reset_time": now + window}
        return True
    
    data = _request_counts[key]
    
    if now > data["reset_time"]:
        data["count"] = 1
        data["reset_time"] = now + window
        return True
    
    if data["count"] >= max_requests:
        return False
    
    data["count"] += 1
    return True


@router.get("/health")
async def eq_health():
    """
    Health check endpoint.
    
    Returns circuit breaker status and service health.
    """
    return {
        "status": "ok",
        "circuit_breaker": {
            "hume_api": HUME_CIRCUIT.get_state_dict(),
            "ollama": OLLAMA_CIRCUIT.get_state_dict()
        },
        "version": "3.0.0"
    }


@router.post("/analyze-sentiment")
async def analyze_sentiment(
    request: Request,
    recording_url: Optional[str] = None,
    transcription: str = "",
    lead_id: int = 0
):
    """
    Analyze sentiment of call/message.
    
    Three-tier cascade: Hume AI -> Ollama -> Keywords
    Rate limited to 10 requests per minute.
    
    Args:
        recording_url: URL to voice recording (optional)
        transcription: Call transcription or message text
        lead_id: Lead ID
    
    Returns:
        Sentiment analysis with escalation flags
    """
    # Rate limiting
    if not await rate_limit_check(request, max_requests=10, window=60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Max 10 requests per minute."
        )
    
    if not recording_url and not transcription:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide recording_url or transcription"
        )
    
    service = SentimentService()
    
    try:
        result = await service.analyze(recording_url, transcription, lead_id)
        
        # Trigger escalation if needed
        if result.get("requires_escalation"):
            await service.trigger_escalation(
                lead_id,
                result.get("dominant_emotion", "unknown")
            )
        
        return result
    
    except Exception as e:
        logger.error(f"Sentiment analysis failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis failed: {str(e)}"
        )


@router.post("/psychological-profile")
async def create_profile(
    lead_id: int,
    answers: Dict[str, str]
):
    """
    Create psychological profile from survey answers.
    
    Uses BANT-C+Emotion framework to determine profile type.
    
    Args:
        lead_id: Lead ID
        answers: Survey answers (q1, q2, q3)
    
    Returns:
        Profile with dimensions and embedding
    """
    if not answers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Answers required"
        )
    
    service = ProfilingService()
    
    try:
        profile_type = service.determine_profile(answers)
        dimensions = service.calculate_dimensions(profile_type, answers)
        pain_points = service.extract_pain_points(answers)
        core_values = service.extract_core_values(answers)
        
        # Create full profile
        profile = {
            "lead_id": lead_id,
            "profile_type": profile_type,
            **dimensions,
            "pain_points": pain_points,
            "core_values": core_values
        }
        
        # Generate embedding
        embedding = service.create_embedding(profile)
        profile["embedding_dims"] = len(embedding)
        
        return profile
    
    except Exception as e:
        logger.error(f"Profile creation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Profile creation failed: {str(e)}"
        )


@router.get("/adaptive-script/{agent}/{lead_id}")
async def get_adaptive_script(
    agent: str,
    lead_id: int,
    profile: str,
    sentiment: float = 0.0,
    stage: str = "opening",
    context: Optional[str] = None
):
    """
    Get real-time adaptive script for agent.
    
    Adapts base script using Milton Model patterns
    based on psychological profile and current sentiment.
    
    Args:
        agent: Agent name (SARA, MARCO, etc.)
        lead_id: Lead ID
        profile: Psychological profile type
        sentiment: Current sentiment score (-1 to 1)
        stage: Interaction stage
        context: JSON string with context variables
    
    Returns:
        Adapted script
    """
    valid_profiles = ["velocity", "analyst", "social", "security"]
    if profile not in valid_profiles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid profile. Must be one of: {valid_profiles}"
        )
    
    engine = PersuasiveEngine()
    
    try:
        # Get base template
        base = engine.get_script_template(profile, stage)
        
        # Parse context
        ctx = {}
        if context:
            import json
            try:
                ctx = json.loads(context)
            except json.JSONDecodeError:
                pass
        
        ctx.update({
            "nome": ctx.get("nome", "Cliente"),
            "azienda": ctx.get("azienda", "la sua azienda"),
            "agent": agent
        })
        
        # Adapt script
        adapted = engine.adapt_script(base, profile, sentiment, ctx)
        
        return {
            "script": adapted,
            "profile": profile,
            "sentiment": sentiment,
            "stage": stage
        }
    
    except Exception as e:
        logger.error(f"Script adaptation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Script adaptation failed: {str(e)}"
        )


@router.post("/handle-objection")
async def handle_objection(
    objection: str,
    profile: str,
    context: Optional[Dict[str, Any]] = None
):
    """
    Handle customer objection with profile-specific response.
    
    Args:
        objection: Objection text
        profile: Psychological profile type
        context: Context variables
    
    Returns:
        Profile-specific objection handler
    """
    valid_profiles = ["velocity", "analyst", "social", "security"]
    if profile not in valid_profiles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid profile. Must be one of: {valid_profiles}"
        )
    
    engine = PersuasiveEngine()
    
    try:
        result = engine.handle_objection(objection, profile, context)
        return result
    
    except Exception as e:
        logger.error(f"Objection handling failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Objection handling failed: {str(e)}"
        )


@router.post("/circuit-reset/{circuit_name}")
async def reset_circuit(
    circuit_name: str,
    admin_token: str
):
    """
    Manually reset a circuit breaker.
    
    Args:
        circuit_name: Name of circuit (hume_api, ollama, chroma_db)
        admin_token: Admin authentication token
    """
    # Validate admin token (simplified)
    if admin_token != "admin-secret-token":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin token"
        )
    
    from api.services.circuit_breaker import CHROMA_CIRCUIT
    
    circuits = {
        "hume_api": HUME_CIRCUIT,
        "ollama": OLLAMA_CIRCUIT,
        "chroma_db": CHROMA_CIRCUIT
    }
    
    if circuit_name not in circuits:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Circuit {circuit_name} not found"
        )
    
    await circuits[circuit_name].reset()
    
    return {
        "message": f"Circuit {circuit_name} reset successfully",
        "state": circuits[circuit_name].state.value
    }
