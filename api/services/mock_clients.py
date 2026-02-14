# =============================================================================
# Auto-Broker Mock Clients - Demo Mode
# Simula API esterne senza costi (Hume AI, Insighto, Blockchain)
# =============================================================================

import asyncio
import random
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)


class MockHumeClient:
    """
    Mock client per Hume AI - Emotional Intelligence
    Simula analisi emotiva e generazione voce senza chiamate API
    """
    
    EMOTIONS = ["joy", "sadness", "anger", "fear", "surprise", "neutral", "excitement"]
    
    def __init__(self):
        self.call_count = 0
        logger.info("🎭 MockHumeClient initialized (Demo Mode)")
    
    async def analyze_emotion(self, audio_data: bytes = None, text: str = None) -> Dict[str, Any]:
        """Simula analisi emotiva"""
        await asyncio.sleep(0.5)  # Simula latenza rete
        
        self.call_count += 1
        
        # Genera punteggi emotivi casuali ma realistici
        emotions = {emotion: round(random.uniform(0.0, 1.0), 3) for emotion in self.EMOTIONS}
        
        # Normalizza a somma 1.0
        total = sum(emotions.values())
        emotions = {k: round(v/total, 3) for k, v in emotions.items()}
        
        dominant_emotion = max(emotions, key=emotions.get)
        
        result = {
            "emotions": emotions,
            "dominant_emotion": dominant_emotion,
            "confidence": round(random.uniform(0.75, 0.98), 3),
            "timestamp": datetime.utcnow().isoformat(),
            "request_id": str(uuid.uuid4()),
            "mock": True
        }
        
        logger.info(f"🎭 [MOCK Hume] Emotion analysis: {dominant_emotion} ({result['confidence']})")
        return result
    
    async def generate_speech(self, text: str, voice_id: str = "default") -> Dict[str, Any]:
        """Simula generazione audio - ritorna placeholder"""
        await asyncio.sleep(0.3)
        
        self.call_count += 1
        
        # In demo mode, ritorna un URL placeholder che il frontend gestisce
        result = {
            "audio_url": f"/demo/audio/placeholder_{uuid.uuid4().hex[:8]}.mp3",
            "duration_seconds": round(len(text) * 0.08, 2),  # ~120 parole/min
            "text": text,
            "voice_id": voice_id,
            "mock": True,
            "note": "Audio simulato - nessuna chiamata API reale"
        }
        
        logger.info(f"🎭 [MOCK Hume] Speech generated: {result['duration_seconds']}s")
        return result
    
    async def analyze_conversation(self, transcript: str) -> Dict[str, Any]:
        """Analizza una conversazione e ritorna insight emotivi"""
        await asyncio.sleep(0.4)
        
        self.call_count += 1
        
        # Simula sentiment analysis
        positive_words = ["ottimo", "perfetto", "interessante", "sì", "accordo", "buono", "grande"]
        negative_words = ["no", "troppo", "caro", "problema", "male", "peccato"]
        
        text_lower = transcript.lower()
        positive_count = sum(1 for w in positive_words if w in text_lower)
        negative_count = sum(1 for w in negative_words if w in text_lower)
        
        sentiment = "positive" if positive_count > negative_count else "neutral" if positive_count == negative_count else "negative"
        
        result = {
            "sentiment": sentiment,
            "engagement_score": round(random.uniform(0.6, 0.95), 2),
            "talk_ratio": {"agent": 0.45, "customer": 0.55},
            "key_moments": [
                {"timestamp": "00:15", "type": "interest_peak", "confidence": 0.85},
                {"timestamp": "01:23", "type": "objection", "confidence": 0.72},
            ],
            "mock": True
        }
        
        logger.info(f"🎭 [MOCK Hume] Conversation analysis: {sentiment}")
        return result


class MockInsightoClient:
    """
    Mock client per Insighto AI - Carrier Intelligence
    Simula telefonate e qualifica carrier
    """
    
    CARRIER_RESPONSES = [
        {"status": "available", "price_factor": 0.85, "eta_hours": 24},
        {"status": "available", "price_factor": 1.0, "eta_hours": 18},
        {"status": "busy", "price_factor": 1.15, "eta_hours": 48, "reason": "high_demand"},
        {"status": "available", "price_factor": 0.92, "eta_hours": 20},
        {"status": "limited", "price_factor": 1.05, "eta_hours": 36, "capacity": "80%"},
    ]
    
    def __init__(self):
        self.call_count = 0
        logger.info("📞 MockInsightoClient initialized (Demo Mode)")
    
    async def make_call(self, phone_number: str, script: str, agent_voice: str = "marco") -> Dict[str, Any]:
        """Simula una telefonata completa"""
        
        logger.info(f"📞 [MOCK Insighto] Calling {phone_number}...")
        
        # Simula durata chiamata (2-5 secondi invece di minuti reali)
        duration = random.randint(2, 5)
        await asyncio.sleep(duration)
        
        self.call_count += 1
        
        # Simula risultato chiamata (80% successo)
        success = random.random() < 0.8
        
        result = {
            "call_id": str(uuid.uuid4()),
            "status": "completed" if success else "no_answer",
            "duration_seconds": random.randint(120, 360) if success else 15,
            "outcome": "interested" if success else "no_response",
            "transcript": self._generate_mock_transcript(success),
            "recording_url": f"/demo/recordings/call_{uuid.uuid4().hex[:8]}.mp3" if success else None,
            "timestamp": datetime.utcnow().isoformat(),
            "mock": True,
            "cost_saved": "€0.15"  # Quanto avrebbe costato realmente
        }
        
        logger.info(f"📞 [MOCK Insighto] Call completed: {result['status']} ({result['duration_seconds']}s)")
        return result
    
    async def check_carrier_availability(self, carrier_id: str, lane: str) -> Dict[str, Any]:
        """Verifica disponibilità carrier"""
        await asyncio.sleep(0.3)
        
        self.call_count += 1
        
        response = random.choice(self.CARRIER_RESPONSES)
        
        result = {
            "carrier_id": carrier_id,
            "lane": lane,
            "available": response["status"] in ["available", "limited"],
            "status": response["status"],
            "estimated_price_factor": response["price_factor"],
            "eta_hours": response["eta_hours"],
            "mock": True,
            "checked_at": datetime.utcnow().isoformat()
        }
        
        if "capacity" in response:
            result["current_capacity"] = response["capacity"]
        
        logger.info(f"📞 [MOCK Insighto] Carrier {carrier_id}: {response['status']}")
        return result
    
    async def qualify_lead(self, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        """Qualifica un lead"""
        await asyncio.sleep(0.5)
        
        self.call_count += 1
        
        # Simula scoring (0-100)
        base_score = random.randint(50, 85)
        
        # Aumenta score se dati completi
        if lead_data.get("company_name") and lead_data.get("monthly_volume_kg"):
            base_score += 10
        
        result = {
            "lead_id": lead_data.get("id", str(uuid.uuid4())),
            "qualification_score": min(base_score, 100),
            "qualified": base_score >= 70,
            "monthly_volume_estimate_kg": random.randint(500, 5000),
            "preferred_lanes": ["MI-RO", "TO-BO", "NA-GE"],
            "price_sensitivity": random.choice(["low", "medium", "high"]),
            "decision_timeline_days": random.randint(7, 30),
            "mock": True,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        logger.info(f"📞 [MOCK Insighto] Lead qualified: {result['qualification_score']}/100")
        return result
    
    def _generate_mock_transcript(self, success: bool) -> str:
        """Genera transcript fittizio"""
        if success:
            transcripts = [
                "Agent: Buongiorno, sono Marco di Logistik AI.\nCliente: Buongiorno Marco, mi dica.\nAgent: Aiutiamo aziende come la vostra a ridurre i costi di spedizione del 20-30%.\nCliente: Interessante, quanti kg spedite al mese?\nAgent: Circa 2000 kg.\nCliente: Perfetto, mi mandi una proposta.\nAgent: Certo, la preparo subito!",
                "Agent: Ciao, sono Marco.\nCliente: Ciao!\nAgent: Vorrei parlare dei vostri costi di spedizione.\nCliente: Attualmente spendiamo troppo.\nAgent: Possiamo aiutarvi, facciamo una qualifica veloce?\nCliente: Sì, procediamo."
            ]
        else:
            transcripts = [
                "Agent: Buongiorno...\n[Segreteria telefonica]\n[Chiamata terminata]",
                "Agent: Pronto?\nCliente: Non sono interessato.\n[Chiamata terminata]"
            ]
        
        return random.choice(transcripts)


class MockBlockchainClient:
    """
    Mock client per Blockchain (Polygon)
    Simula transazioni senza gas cost
    """
    
    def __init__(self):
        self.tx_count = 0
        self.mock_block_number = 45000000
        logger.info("⛓️  MockBlockchainClient initialized (Demo Mode)")
    
    async def deploy_contract(self, contract_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Simula deploy smart contract"""
        await asyncio.sleep(0.2)
        
        self.tx_count += 1
        self.mock_block_number += 1
        
        contract_address = f"0x{uuid.uuid4().hex[:40]}"
        
        result = {
            "contract_address": contract_address,
            "transaction_hash": f"0x{uuid.uuid4().hex}",
            "block_number": self.mock_block_number,
            "gas_used": random.randint(80000, 150000),
            "gas_cost_eth": "0.0",
            "gas_cost_usd": "$0.00 (Demo Mode)",
            "status": "confirmed",
            "confirmations": 12,
            "mock": True,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        logger.info(f"⛓️  [MOCK Blockchain] Contract deployed: {contract_address[:20]}...")
        return result
    
    async def send_transaction(self, to: str, value_eth: float, data: str = None) -> Dict[str, Any]:
        """Simula invio transazione"""
        await asyncio.sleep(0.3)
        
        self.tx_count += 1
        self.mock_block_number += 1
        
        result = {
            "transaction_hash": f"0x{uuid.uuid4().hex}",
            "from": f"0x{uuid.uuid4().hex[:40]}",
            "to": to,
            "value_eth": value_eth,
            "value_usd": f"${value_eth * 2500:.2f}",
            "gas_used": random.randint(21000, 65000),
            "gas_cost_eth": "0.0",
            "gas_cost_usd": "$0.00 (Demo Mode)",
            "block_number": self.mock_block_number,
            "status": "confirmed",
            "confirmations": random.randint(5, 20),
            "mock": True,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        logger.info(f"⛓️  [MOCK Blockchain] TX sent: {value_eth} ETH to {to[:20]}...")
        return result
    
    async def escrow_deposit(self, shipment_id: str, amount: float, carrier_address: str) -> Dict[str, Any]:
        """Simula deposito in escrow"""
        await asyncio.sleep(0.25)
        
        self.tx_count += 1
        
        result = {
            "escrow_id": str(uuid.uuid4()),
            "shipment_id": shipment_id,
            "carrier": carrier_address,
            "amount_locked": amount,
            "amount_usd": f"${amount:.2f}",
            "status": "locked",
            "release_conditions": ["pod_signed", "delivery_confirmed"],
            "transaction_hash": f"0x{uuid.uuid4().hex}",
            "mock": True,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        logger.info(f"⛓️  [MOCK Blockchain] Escrow created: €{amount:.2f} for shipment {shipment_id}")
        return result
    
    async def escrow_release(self, escrow_id: str) -> Dict[str, Any]:
        """Simula rilascio escrow"""
        await asyncio.sleep(0.2)
        
        self.tx_count += 1
        
        result = {
            "escrow_id": escrow_id,
            "status": "released",
            "released_to": f"0x{uuid.uuid4().hex[:40]}",
            "transaction_hash": f"0x{uuid.uuid4().hex}",
            "mock": True,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        logger.info(f"⛓️  [MOCK Blockchain] Escrow released: {escrow_id[:20]}...")
        return result
    
    async def get_balance(self, address: str) -> Dict[str, Any]:
        """Ritorna balance fittizio"""
        return {
            "address": address,
            "balance_eth": round(random.uniform(0.5, 5.0), 4),
            "balance_usd": f"${random.uniform(1250, 12500):.2f}",
            "mock": True
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Ritorna statistiche mock"""
        return {
            "total_transactions": self.tx_count,
            "current_block": self.mock_block_number,
            "gas_saved_eth": self.tx_count * 0.001,
            "gas_saved_usd": f"${self.tx_count * 2.5:.2f}",
            "mock": True
        }


# Singleton instances
_mock_hume = None
_mock_insighto = None
_mock_blockchain = None


def get_mock_hume() -> MockHumeClient:
    global _mock_hume
    if _mock_hume is None:
        _mock_hume = MockHumeClient()
    return _mock_hume


def get_mock_insighto() -> MockInsightoClient:
    global _mock_insighto
    if _mock_insighto is None:
        _mock_insighto = MockInsightoClient()
    return _mock_insighto


def get_mock_blockchain() -> MockBlockchainClient:
    global _mock_blockchain
    if _mock_blockchain is None:
        _mock_blockchain = MockBlockchainClient()
    return _mock_blockchain
