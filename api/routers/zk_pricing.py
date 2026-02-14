"""
AUTO-BROKER: Zero-Knowledge Pricing Router

Endpoint per gestione pricing privato con Zero-Knowledge Proofs.
"""
from decimal import Decimal
from typing import Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status, Header
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.services.database import get_db
from api.services.zk_pricing_service import ZeroKnowledgePricing, ZKCommitment

logger = structlog.get_logger()

router = APIRouter(prefix="/pricing/zk", tags=["Zero-Knowledge Pricing"])


# ==========================================
# SCHEMAS
# ==========================================

class ZKCommitRequest(BaseModel):
    """Request per generazione commitment ZK."""
    quote_id: UUID = Field(..., description="ID del preventivo")
    base_cost: Decimal = Field(..., ge=0, decimal_places=2, description="Costo base privato (EUR)")
    selling_price: Decimal = Field(..., ge=0, decimal_places=2, description="Prezzo vendita pubblico (EUR)")
    markup_percent: Decimal = Field(..., ge=0, le=30, decimal_places=2, description="Markup % (max 30%)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "quote_id": "550e8400-e29b-41d4-a716-446655440000",
                "base_cost": 1000.00,
                "selling_price": 1250.00,
                "markup_percent": 25.00
            }
        }


class ZKCommitResponse(BaseModel):
    """Response con commitment ZK."""
    quote_id: UUID
    commitment: str = Field(..., description="Hash commitment (pubblico)")
    proof: str = Field(..., description="Proof ZK (pubblica)")
    public_inputs: str = Field(..., description="Input pubblici per verifica")
    selling_price: Decimal
    salt_hash: str = Field(..., description="Hash del salt (per integrità)")
    message: str


class ZKVerifyRequest(BaseModel):
    """Request per verifica proof ZK."""
    commitment: str = Field(..., description="Commitment da verificare")
    proof: Optional[str] = Field(None, description="Proof ZK (opzionale, recupera da DB)")
    public_inputs: Optional[str] = Field(None, description="Input pubblici (opzionale)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "commitment": "a1b2c3d4e5f6...",
                "proof": None,  # Recuperato automaticamente da DB
                "public_inputs": None
            }
        }


class ZKVerifyResponse(BaseModel):
    """Response verifica ZK."""
    commitment: str
    is_valid: bool
    selling_price: Optional[Decimal]
    message: str
    verified_at: str


class ZKRevealRequest(BaseModel):
    """Request per reveal condizionale (solo admin)."""
    quote_id: UUID
    base_cost: Decimal = Field(..., description="Costo base rivelato")
    salt: str = Field(..., description="Salt usato per commitment")
    
    class Config:
        json_schema_extra = {
            "example": {
                "quote_id": "550e8400-e29b-41d4-a716-446655440000",
                "base_cost": 1000.00,
                "salt": "a1b2c3d4e5f6..."
            }
        }


class ZKRevealResponse(BaseModel):
    """Response reveal ZK."""
    quote_id: UUID
    verified: bool
    commitment_match: bool
    base_cost: Decimal
    selling_price: Optional[Decimal]
    markup_percent: Optional[Decimal]
    message: str
    audit_logged: bool


class ZKAuditResponse(BaseModel):
    """Response audit ZK commitment."""
    quote_id: UUID
    commitment: str
    proof_available: bool
    selling_price: Decimal
    created_at: str
    revealed: bool
    revealed_at: Optional[str]
    revealed_by: Optional[str]


# ==========================================
# AUTH DEPENDENCIES
# ==========================================

async def get_current_user(authorization: Optional[str] = Header(None)) -> str:
    """Verifica autenticazione base."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization"
        )
    token = authorization.replace("Bearer ", "")
    # Semplificato: in produzione validare JWT
    return token.split(":")[0] if ":" in token else "user"


async def verify_admin(authorization: Optional[str] = Header(None)) -> str:
    """Verifica admin per operazioni sensibili."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization"
        )
    token = authorization.replace("Bearer ", "")
    # Semplificato: verifica admin token
    if not token.startswith("admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return token


# ==========================================
# ENDPOINTS
# ==========================================

@router.post(
    "/commit",
    response_model=ZKCommitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Genera commitment ZK",
    description="""
    Cliente genera commitment del proprio costo base.
    
    Il cliente fornisce:
    - base_cost: Costo base (privato, non salvato in chiaro)
    - selling_price: Prezzo vendita (pubblico)
    - markup_percent: Markup % (deve essere <= 30%)
    
    Il sistema:
    - Genera salt casuale
    - Calcola commitment = hash(base_cost + salt)
    - Genera proof ZK che markup <= 30%
    - Salva commitment, proof, salt_hash (NON base_cost o salt!)
    """
)
async def create_zk_commitment(
    request: ZKCommitRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Crea commitment ZK per un preventivo.
    
    Il costo base rimane privato al cliente.
    Solo il commitment e la proof vengono salvati.
    """
    try:
        zk_service = ZeroKnowledgePricing(db)
        
        commitment = await zk_service.generate_price_commitment(
            quote_id=request.quote_id,
            base_cost=request.base_cost,
            selling_price=request.selling_price,
            markup_percent=request.markup_percent
        )
        
        logger.info(
            "zk_commitment_created",
            quote_id=str(request.quote_id),
            user_id=user_id,
            commitment=commitment.commitment[:16]
        )
        
        return ZKCommitResponse(
            quote_id=commitment.quote_id,
            commitment=commitment.commitment,
            proof=commitment.proof,
            public_inputs=commitment.public_inputs,
            selling_price=commitment.selling_price,
            salt_hash=commitment.salt_hash,
            message="Zero-knowledge commitment generated successfully"
        )
        
    except ValueError as e:
        logger.warning(
            "zk_commitment_validation_failed",
            quote_id=str(request.quote_id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(
            "zk_commitment_failed",
            quote_id=str(request.quote_id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate commitment: {str(e)}"
        )


@router.post(
    "/verify",
    response_model=ZKVerifyResponse,
    summary="Verifica proof ZK",
    description="""
    Verifica che il markup sia <= 30% senza conoscere base_cost.
    
    Il broker (o chiunque) può verificare la fairness del pricing
    usando solo il commitment e la proof pubblica.
    """
)
async def verify_zk_proof(
    request: ZKVerifyRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Verifica proof Zero-Knowledge.
    
    Non richiede autenticazione: chiunque può verificare
    che il pricing sia fair.
    """
    try:
        zk_service = ZeroKnowledgePricing(db)
        
        # Recupera commitment se esiste
        commitment_data = await zk_service.get_commitment_by_quote(
            quote_id=UUID(request.commitment) if len(request.commitment) == 36 else None
        )
        
        # Se trovato per quote_id, usa i dati da DB
        if commitment_data:
            proof = request.proof or commitment_data.proof
            public_inputs = request.public_inputs or commitment_data.public_inputs
            selling_price = commitment_data.selling_price
        else:
            # Altrimenti usa dati forniti nella request
            proof = request.proof
            public_inputs = request.public_inputs
            selling_price = None
        
        if not proof:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Proof not found"
            )
        
        is_valid = await zk_service.verify_fair_pricing(
            commitment=request.commitment,
            proof=proof,
            public_inputs=public_inputs
        )
        
        logger.info(
            "zk_proof_verified" if is_valid else "zk_proof_rejected",
            commitment=request.commitment[:16],
            is_valid=is_valid
        )
        
        return ZKVerifyResponse(
            commitment=request.commitment,
            is_valid=is_valid,
            selling_price=selling_price,
            message=(
                "Proof verified: markup is within 30% limit"
                if is_valid else
                "Proof rejected: potential fraud detected"
            ),
            verified_at=datetime.utcnow().isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "zk_verify_failed",
            commitment=request.commitment[:16],
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Verification failed: {str(e)}"
        )


@router.post(
    "/reveal",
    response_model=ZKRevealResponse,
    summary="Rivela prezzo (solo admin)",
    description="""
    Rivelazione condizionale del costo base per dispute resolution.
    
    SOLO admin possono chiamare questo endpoint.
    Ogni accesso è loggato per audit GDPR.
    """
)
async def reveal_zk_price(
    request: ZKRevealRequest,
    admin_id: str = Depends(verify_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Rivela costo base per dispute resolution.
    
    Requisiti:
    - Admin authentication
    - Salt corretto
    - Audit logging attivo
    """
    try:
        zk_service = ZeroKnowledgePricing(db)
        
        # Esegui reveal
        verified = await zk_service.reveal_price(
            quote_id=request.quote_id,
            base_cost=request.base_cost,
            salt=request.salt,
            admin_id=admin_id
        )
        
        if not verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Commitment verification failed: invalid base_cost or salt"
            )
        
        # Recupera selling price per calcolo markup
        commitment_data = await zk_service.get_commitment_by_quote(request.quote_id)
        selling_price = commitment_data.selling_price if commitment_data else None
        
        # Calcola markup
        markup_percent = None
        if selling_price and request.base_cost > 0:
            markup_percent = ((selling_price - request.base_cost) / request.base_cost) * 100
        
        logger.critical(
            "zk_price_revealed_api",
            quote_id=str(request.quote_id),
            admin_id=admin_id,
            verified=verified
        )
        
        return ZKRevealResponse(
            quote_id=request.quote_id,
            verified=verified,
            commitment_match=verified,
            base_cost=request.base_cost,
            selling_price=selling_price,
            markup_percent=markup_percent,
            message="Price revealed successfully. Access logged for GDPR audit.",
            audit_logged=True
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "zk_reveal_failed",
            quote_id=str(request.quote_id),
            admin_id=admin_id,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Reveal failed: {str(e)}"
        )


@router.get(
    "/audit/{quote_id}",
    response_model=ZKAuditResponse,
    summary="Audit ZK commitment",
    description="""
    Recupera informazioni audit per un commitment ZK.
    
    Mostra se il prezzo è stato rivelato e da chi (GDPR audit trail).
    """
)
async def audit_zk_commitment(
    quote_id: UUID,
    admin_id: str = Depends(verify_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Audit trail per commitment ZK.
    """
    try:
        zk_service = ZeroKnowledgePricing(db)
        
        commitment_data = await zk_service.get_commitment_by_quote(quote_id)
        
        if not commitment_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Commitment not found"
            )
        
        # Recupera dati reveal se presenti nel DB
        result = await db.execute(
            select(ZKPriceCommitment).where(ZKPriceCommitment.quote_id == quote_id)
        )
        db_record = result.scalar_one_or_none()
        
        logger.info(
            "zk_audit_accessed",
            quote_id=str(quote_id),
            admin_id=admin_id
        )
        
        return ZKAuditResponse(
            quote_id=quote_id,
            commitment=commitment_data.commitment,
            proof_available=bool(commitment_data.proof),
            selling_price=commitment_data.selling_price,
            created_at=commitment_data.created_at or "",
            revealed=db_record.revealed_at is not None if db_record else False,
            revealed_at=str(db_record.revealed_at) if db_record and db_record.revealed_at else None,
            revealed_by=db_record.revealed_by if db_record else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "zk_audit_failed",
            quote_id=str(quote_id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Audit failed: {str(e)}"
        )


@router.get(
    "/stats",
    summary="Statistiche ZK Pricing",
    description="Statistiche sull'uso del sistema ZK Pricing"
)
async def zk_stats(
    admin_id: str = Depends(verify_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Statistiche ZK Pricing.
    """
    from sqlalchemy import func
    from api.models import ZKPriceCommitment
    
    try:
        # Totale commitments
        result = await db.execute(select(func.count(ZKPriceCommitment.id)))
        total_commitments = result.scalar()
        
        # Revealed
        result = await db.execute(
            select(func.count(ZKPriceCommitment.id)).where(
                ZKPriceCommitment.revealed_at.isnot(None)
            )
        )
        revealed_count = result.scalar()
        
        return {
            "total_commitments": total_commitments,
            "revealed_count": revealed_count,
            "active_commitments": total_commitments - revealed_count,
            "reveal_rate": (revealed_count / total_commitments * 100) if total_commitments > 0 else 0
        }
        
    except Exception as e:
        logger.error("zk_stats_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Stats failed: {str(e)}"
        )


# Import per timestamp
from datetime import datetime