"""
AUTO-BROKER: Stripe Service
"""
import os
from typing import Optional, Dict, Any
from decimal import Decimal
import stripe as stripe_lib
import structlog

logger = structlog.get_logger()

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

stripe_lib.api_key = STRIPE_SECRET_KEY


class StripeService:
    def __init__(self):
        self.stripe = stripe_lib
        self.webhook_secret = STRIPE_WEBHOOK_SECRET
    
    async def create_checkout_session(
        self,
        amount: Decimal,
        success_url: str,
        cancel_url: str,
        customer_email: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if not STRIPE_SECRET_KEY:
            session_id = f"cs_mock_{hash(str(metadata))}"
            return {"id": session_id, "url": f"https://checkout.stripe.com/mock/{session_id}", "mock": True}
        
        amount_cents = int(amount * 100)
        
        session = self.stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "eur",
                    "product_data": {
                        "name": "Servizi di Spedizione Logistik AI",
                    },
                    "unit_amount": amount_cents,
                },
                "quantity": 1,
            }],
            mode="payment",
            success_url=success_url,
            cancel_url=cancel_url,
            customer_email=customer_email,
            metadata=metadata or {}
        )
        
        return {"id": session.id, "url": session.url, "amount": amount_cents}
    
    async def calculate_fees(self, amount: Decimal) -> Dict[str, Decimal]:
        fee_percentage = Decimal("0.015")
        fixed_fee = Decimal("0.25")
        fees = (amount * fee_percentage) + fixed_fee
        net = amount - fees
        return {
            "gross_amount": amount,
            "stripe_fees": fees.quantize(Decimal("0.01")),
            "net_amount": net.quantize(Decimal("0.01"))
        }


stripe_service = StripeService()
