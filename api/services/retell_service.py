"""
AUTO-BROKER: Retell AI Service
"""
import os
from typing import Optional, Dict, Any
import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

logger = structlog.get_logger()

RETELL_API_KEY = os.getenv("RETELL_API_KEY", "")
RETELL_API_URL = "https://api.retellai.com"
AGENT_SARA = os.getenv("RETELL_AGENT_ID_SARA", "agent_sara")
AGENT_MARCO = os.getenv("RETELL_AGENT_ID_MARCO", "agent_marco")
AGENT_LUIGI = os.getenv("RETELL_AGENT_ID_LUIGI", "agent_luigi")


class RetellService:
    def __init__(self):
        self.api_key = RETELL_API_KEY
        self.base_url = RETELL_API_URL
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    async def create_call(self, phone_number: str, agent_id: str, 
                         lead_id: Optional[str] = None,
                         metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self.api_key:
            return {
                "call_id": f"mock_call_{lead_id}",
                "status": "queued",
                "agent_id": agent_id,
                "mock": True
            }
        
        payload = {
            "from_number": "+1234567890",
            "to_number": phone_number,
            "agent_id": agent_id,
            "retell_llm_dynamic_variables": {
                "lead_id": str(lead_id) if lead_id else "",
                **(metadata or {})
            }
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/v2/create-phone-call",
                headers=self.headers,
                json=payload
            )
            response.raise_for_status()
            return response.json()
    
    async def call_sara(self, phone_number: str, lead_id: str,
                        azienda: str, nome: str) -> Dict[str, Any]:
        return await self.create_call(
            phone_number=phone_number,
            agent_id=AGENT_SARA,
            lead_id=lead_id,
            metadata={"azienda": azienda, "nome": nome, "agent_name": "Sara"}
        )
    
    async def call_marco(self, phone_number: str, lead_id: str,
                         azienda: str, nome: str) -> Dict[str, Any]:
        return await self.create_call(
            phone_number=phone_number,
            agent_id=AGENT_MARCO,
            lead_id=lead_id,
            metadata={"azienda": azienda, "nome": nome, "agent_name": "Marco"}
        )
    
    async def call_luigi(self, phone_number: str, lead_id: str,
                         azienda: str, nome: str, preventivo_id: str) -> Dict[str, Any]:
        return await self.create_call(
            phone_number=phone_number,
            agent_id=AGENT_LUIGI,
            lead_id=lead_id,
            metadata={"azienda": azienda, "nome": nome, "preventivo_id": preventivo_id, "agent_name": "Luigi"}
        )


retell_service = RetellService()
