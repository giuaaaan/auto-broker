"""
AUTO-BROKER: Pricing Engine V2

Pricing engine con supporto Zero-Knowledge per verifica fair pricing.
Integra calcolo prezzi con generazione proof ZK.
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Dict, Any
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from api.services.zk_pricing_service import ZeroKnowledgePricing, ZKCommitment

logger = structlog.get_logger()


class PricingEngineV2:
    """
    Pricing Engine V2 con supporto Zero-Knowledge.
    
    Features:
    - Calcolo prezzi base + markup
    - Generazione commitment ZK (opzionale)
    - Verifica on-chain readiness
    """
    
    DEFAULT_MARKUP_PERCENT = Decimal("25.00")  # 25% default
    MAX_MARKUP_PERCENT = Decimal("30.00")      # 30% massimo (regola ZK)
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self.zk_service = ZeroKnowledgePricing(db_session)
    
    async def calculate_quote(
        self,
        quote_id: UUID,
        base_cost: Decimal,
        markup_percent: Optional[Decimal] = None,
        zk_mode: bool = False
    ) -> Dict[str, Any]:
        """
        Calcola preventivo con opzione ZK.
        
        Args:
            quote_id: UUID preventivo
            base_cost: Costo base (corriere + operativi)
            markup_percent: Markup % (default 25%, max 30%)
            zk_mode: Se True, genera commitment ZK
            
        Returns:
            Dict con prezzo e opzionalmente commitment ZK
        """
        # Validazione markup
        markup = markup_percent or self.DEFAULT_MARKUP_PERCENT
        if markup > self.MAX_MARKUP_PERCENT:
            markup = self.MAX_MARKUP_PERCENT
            logger.warning(
                "markup_capped_to_30",
                quote_id=str(quote_id),
                requested=float(markup_percent or 0)
            )
        
        # Calcolo prezzo
        multiplier = Decimal("1") + (markup / Decimal("100"))
        selling_price = (base_cost * multiplier).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )
        
        result = {
            "quote_id": str(quote_id),
            "base_cost": float(base_cost),
            "markup_percent": float(markup),
            "selling_price": float(selling_price),
            "zk_mode": zk_mode
        }
        
        # Modalità Zero-Knowledge
        if zk_mode:
            try:
                commitment = await self.zk_service.generate_price_commitment(
                    quote_id=quote_id,
                    base_cost=base_cost,
                    selling_price=selling_price,
                    markup_percent=markup
                )
                
                result["zk_commitment"] = {
                    "commitment": commitment.commitment,
                    "proof": commitment.proof,
                    "public_inputs": commitment.public_inputs,
                    "salt_hash": commitment.salt_hash
                }
                
                logger.info(
                    "quote_calculated_with_zk",
                    quote_id=str(quote_id),
                    commitment=commitment.commitment[:16]
                )
                
            except Exception as e:
                logger.error(
                    "zk_commitment_failed",
                    quote_id=str(quote_id),
                    error=str(e)
                )
                # Non fallisce, ma logga errore
                result["zk_error"] = str(e)
        else:
            logger.info(
                "quote_calculated",
                quote_id=str(quote_id),
                selling_price=float(selling_price)
            )
        
        return result
    
    async def verify_quote(
        self,
        commitment_hash: str
    ) -> Optional[Dict[str, Any]]:
        """
        Verifica un preventivo ZK esistente.
        
        Args:
            commitment_hash: Hash del commitment
            
        Returns:
            Dict con risultato verifica o None
        """
        try:
            is_valid = await self.zk_service.verify_fair_pricing(
                commitment=commitment_hash,
                proof=None,  # Recupera da DB
                public_inputs=None
            )
            
            commitment_data = await self.zk_service.get_commitment_by_quote(
                UUID(commitment_hash) if len(commitment_hash) == 36 else None
            )
            
            return {
                "commitment": commitment_hash,
                "is_valid": is_valid,
                "selling_price": float(commitment_data.selling_price) if commitment_data else None
            }
            
        except Exception as e:
            logger.error(
                "quote_verification_failed",
                commitment=commitment_hash[:16],
                error=str(e)
            )
            return None


# Funzione helper per compatibilità
def calculate_price_with_markup(
    base_cost: Decimal,
    markup_percent: Decimal = Decimal("25.00")
) -> Decimal:
    """
    Calcola prezzo con markup semplice.
    
    Args:
        base_cost: Costo base
        markup_percent: Percentuale markup
        
    Returns:
        Prezzo vendita
    """
    multiplier = Decimal("1") + (markup_percent / Decimal("100"))
    return (base_cost * multiplier).quantize(Decimal("0.01"))