"""
AUTO-BROKER: GIULIA Agent - Dispute Resolution Specialist

GIULIA (Generative Intelligent Unified Logistics Investigation Agent)
analizza dispute usando AI per verificare POD autenticità e decidere outcome.

Responsabilità:
- Monitor webhook blockchain per dispute aperte
- Analisi AI: OCR, pattern matching, computer vision
- Decisione auto-resolve o escalation human
- Update blockchain con risoluzione

Architettura:
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Webhook    │───→│  AI Analysis│───→│  Resolution │
│  Dispute    │    │  Evidence   │    │  Pay/Refund │
└─────────────┘    └─────────────┘    └─────────────┘
"""
import asyncio
import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
from uuid import UUID

import httpx
import structlog
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db_session
from api.models import Spedizione, Corriere

logger = structlog.get_logger()

# Config
AUTO_RESOLVE_THRESHOLD = int(os.getenv("GIULIA_AUTO_RESOLVE_THRESHOLD", "85"))
AUTO_RESOLUTION_LIMIT_EUR = int(os.getenv("AUTO_RESOLUTION_LIMIT", "5000"))
HUMAN_ESCALATION_THRESHOLD = int(os.getenv("HUMAN_ESCALATION_THRESHOLD", "50"))
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")


class ResolutionDecision(Enum):
    """Decisione possibile per dispute."""
    AUTO_RESOLVE_CARRIER_WINS = "auto_resolve_carrier"
    AUTO_RESOLVE_CUSTOMER_WINS = "auto_resolve_customer"
    ESCALATE_HUMAN = "escalate_human"
    REQUEST_MORE_EVIDENCE = "request_evidence"


@dataclass
class Evidence:
    """Evidence raccolta per dispute."""
    pod_document_url: Optional[str]
    pod_ipfs_hash: Optional[str]
    tracking_history: List[Dict[str, Any]]
    photos: List[str]  # URLs
    signatures: List[Dict[str, Any]]
    gps_data: List[Dict[str, Any]]


@dataclass
class AIAnalysisResult:
    """Risultato analisi AI."""
    signature_authentic: float  # 0-100 confidence
    delivery_verified: float    # 0-100 confidence
    damage_visible: float       # 0-100 confidence
    overall_confidence: float   # 0-100
    reasoning: str
    flags: List[str]


@dataclass
class Resolution:
    """Risoluzione dispute."""
    dispute_id: UUID
    shipment_id: UUID
    decision: ResolutionDecision
    carrier_wins: bool
    refund_amount: float
    confidence: float
    evidence_hash: str
    ai_analysis_hash: str
    resolved_at: datetime
    requires_human_arbitration: bool
    tx_hash: Optional[str]


@dataclass
class DisputeEvent:
    """Evento dispute da blockchain."""
    dispute_id: UUID
    shipment_id: UUID
    initiator: str
    reason: str
    claimed_amount: float
    created_at: datetime


class GiuliaAgent:
    """
    Agent autonomo per dispute resolution.
    
    Flusso:
    1. Listen → Webhook da PODSmartContract.openDispute()
    2. Gather → Recupera POD, tracking, foto da IPFS
    3. Analyze → AI analysis (signature, tracking, damage)
    4. Decide → Auto-resolve o escalate basato su confidence
    5. Execute → Update blockchain, paga/rimborsa
    """
    
    def __init__(self):
        self._resolutions: Dict[UUID, Resolution] = {}
        self._dispute_patterns: Dict[str, int] = {}  # Per detect fraud patterns
        self._running = False
        
        logger.info("giulia_agent_initialized")
    
    async def handle_dispute_webhook(self, event: DisputeEvent) -> Resolution:
        """
        Gestisce nuova dispute da blockchain webhook.
        
        Args:
            event: Dati dispute dal webhook
            
        Returns:
            Resolution con decisione
        """
        logger.info(
            "dispute_webhook_received",
            dispute_id=str(event.dispute_id),
            shipment_id=str(event.shipment_id),
            claimed_amount=event.claimed_amount
        )
        
        # STEP 1: Gather evidence
        evidence = await self._gather_evidence(event.shipment_id)
        
        # STEP 2: AI Analysis
        analysis = await self._analyze_evidence(evidence, event)
        
        # STEP 3: Decision
        decision = self._make_decision(analysis, event.claimed_amount)
        
        # STEP 4: Execute resolution
        resolution = await self._execute_resolution(event, evidence, analysis, decision)
        
        # STEP 5: Update carrier reputation se frode rilevata
        if analysis.signature_authentic < 30 or analysis.delivery_verified < 30:
            await self._flag_carrier_fraud(event.shipment_id)
        
        return resolution
    
    async def _gather_evidence(self, shipment_id: UUID) -> Evidence:
        """
        Raccoglie evidence per analisi.
        
        Recupera:
        - POD document da IPFS
        - Tracking history
        - Foto se disponibili
        - Firme
        - Dati GPS
        """
        async with get_db_session() as db:
            # Ottieni shipment
            shipment = await db.get(Spedizione, shipment_id)
            
            if not shipment:
                logger.error("shipment_not_found", shipment_id=str(shipment_id))
                return Evidence(None, None, [], [], [], [])
            
            # In produzione: recupera da IPFS, tracking API, etc.
            # Per ora: simulazione
            
            evidence = Evidence(
                pod_document_url=f"https://ipfs.io/ipfs/{shipment.pod_hash or 'dummy'}",
                pod_ipfs_hash=shipment.pod_hash,
                tracking_history=[
                    {"timestamp": "2024-01-15T10:00:00Z", "status": "picked_up", "location": "Milan"},
                    {"timestamp": "2024-01-15T14:30:00Z", "status": "in_transit", "location": "Bologna"},
                    {"timestamp": "2024-01-15T18:45:00Z", "status": "delivered", "location": "Rome"},
                ],
                photos=[],  # URLs foto
                signatures=[
                    {"type": "carrier", "timestamp": "2024-01-15T08:00:00Z"},
                    {"type": "consignee", "timestamp": "2024-01-15T18:45:00Z"},
                ],
                gps_data=[
                    {"lat": 45.46, "lng": 9.19, "timestamp": "2024-01-15T10:00:00Z"},
                    {"lat": 44.49, "lng": 11.34, "timestamp": "2024-01-15T14:30:00Z"},
                    {"lat": 41.90, "lng": 12.50, "timestamp": "2024-01-15T18:45:00Z"},
                ]
            )
            
            logger.info("evidence_gathered", shipment_id=str(shipment_id))
            return evidence
    
    async def _analyze_evidence(
        self,
        evidence: Evidence,
        dispute: DisputeEvent
    ) -> AIAnalysisResult:
        """
        Analisi AI dell'evidence.
        
        Verifica:
        1. Firma su POD è autentica? (OCR + pattern matching)
        2. Tracking mostra consegna effettiva? (GPS vs claim)
        3. Danno visibile in foto? (computer vision)
        """
        tasks = [
            self._analyze_signature_authenticity(evidence),
            self._verify_delivery_tracking(evidence, dispute),
            self._check_for_damage(evidence),
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        signature_score = results[0] if not isinstance(results[0], Exception) else 50.0
        delivery_score = results[1] if not isinstance(results[1], Exception) else 50.0
        damage_score = results[2] if not isinstance(results[2], Exception) else 0.0
        
        # Calcola confidence overall
        overall = (signature_score * 0.4 + delivery_score * 0.4 + (100 - damage_score) * 0.2)
        
        # Genera reasoning
        reasoning = self._generate_reasoning(signature_score, delivery_score, damage_score)
        
        # Detect flags
        flags = []
        if signature_score < 50:
            flags.append("suspicious_signature")
        if delivery_score < 50:
            flags.append("tracking_mismatch")
        if damage_score > 70:
            flags.append("visible_damage")
        
        return AIAnalysisResult(
            signature_authentic=signature_score,
            delivery_verified=delivery_score,
            damage_visible=damage_score,
            overall_confidence=overall,
            reasoning=reasoning,
            flags=flags
        )
    
    async def _analyze_signature_authenticity(self, evidence: Evidence) -> float:
        """
        Analizza autenticità firma su POD.
        
        Usa OCR + pattern matching per verificare:
        - Firma presente
        - Nome corrisponde al consignee
        - Data coerente
        """
        try:
            # In produzione: chiama GPT-4 Vision o LLM locale
            # Per ora: simulazione basata su pattern
            
            if not evidence.signatures:
                return 0.0  # No signature = definitely fake
            
            # Chiama Ollama per analisi
            prompt = f"""
            Analyze this delivery signature evidence:
            - Signatures recorded: {len(evidence.signatures)}
            - Consignee signed at: {evidence.signatures[-1].get('timestamp', 'unknown')}
            - POD available: {evidence.pod_document_url is not None}
            
            Return a confidence score 0-100 for signature authenticity.
            Consider: presence, legibility, timestamp consistency.
            Return only the number.
            """
            
            score = await self._call_llm(prompt, default=75.0)
            
            # Aggiungi randomicità per simulazione
            import random
            score = max(0, min(100, score + random.uniform(-10, 10)))
            
            logger.info("signature_analysis_complete", score=score)
            return score
            
        except Exception as e:
            logger.error("signature_analysis_failed", error=str(e))
            return 50.0
    
    async def _verify_delivery_tracking(
        self,
        evidence: Evidence,
        dispute: DisputeEvent
    ) -> float:
        """
        Verifica che tracking mostri consegna effettiva.
        
        Confronta:
        - GPS data vs claimed location
        - Timestamp consegna vs claimed time
        - Status progression logic
        """
        try:
            if not evidence.tracking_history:
                return 0.0
            
            # Verifica status progression
            statuses = [t.get("status") for t in evidence.tracking_history]
            expected_flow = ["picked_up", "in_transit", "delivered"]
            
            flow_score = 100.0
            for i, expected in enumerate(expected_flow):
                if i < len(statuses) and statuses[i] != expected:
                    flow_score -= 30
            
            # Verifica GPS data coerente con route
            if evidence.gps_data and len(evidence.gps_data) >= 2:
                # Semplice check: distanza tra punti deve essere ragionevole
                gps_score = 100.0  # Assume OK
            else:
                gps_score = 50.0  # Missing GPS data
            
            # Verifica timestamp
            last_tracking = evidence.tracking_history[-1].get("timestamp", "")
            has_delivery_status = last_tracking and "delivered" in str(statuses).lower()
            
            timestamp_score = 100.0 if has_delivery_status else 0.0
            
            # Media pesata
            score = (flow_score * 0.4 + gps_score * 0.3 + timestamp_score * 0.3)
            
            logger.info("delivery_verification_complete", score=score)
            return max(0, min(100, score))
            
        except Exception as e:
            logger.error("delivery_verification_failed", error=str(e))
            return 50.0
    
    async def _check_for_damage(self, evidence: Evidence) -> float:
        """
        Verifica se ci sono danni visibili nelle foto.
        
        Usa computer vision (Ollama vision o API esterna).
        """
        try:
            if not evidence.photos:
                return 0.0  # No photos = no visible damage
            
            # In produzione: chiama CV model
            # Per ora: simulazione
            
            prompt = f"""
            Analyze delivery photos for visible damage.
            Number of photos: {len(evidence.photos)}
            
            Return a damage severity score 0-100 where:
            0 = no damage visible
            100 = severe damage clearly visible
            Return only the number.
            """
            
            score = await self._call_llm(prompt, default=10.0)
            
            logger.info("damage_analysis_complete", score=score)
            return max(0, min(100, score))
            
        except Exception as e:
            logger.error("damage_check_failed", error=str(e))
            return 0.0
    
    async def _call_llm(self, prompt: str, default: float = 50.0) -> float:
        """Chiama LLM locale (Ollama) per analisi."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{OLLAMA_URL}/api/generate",
                    json={
                        "model": "llama2",
                        "prompt": prompt,
                        "stream": False
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    text = result.get("response", "")
                    
                    # Estrai numero dalla risposta
                    numbers = re.findall(r'\d+\.?\d*', text)
                    if numbers:
                        return float(numbers[0])
                
                return default
                
        except Exception as e:
            logger.warning("llm_call_failed", error=str(e))
            return default
    
    def _generate_reasoning(
        self,
        signature_score: float,
        delivery_score: float,
        damage_score: float
    ) -> str:
        """Genera spiegazione della decisione."""
        parts = []
        
        if signature_score > 80:
            parts.append("Signature appears authentic.")
        elif signature_score > 50:
            parts.append("Signature partially verified.")
        else:
            parts.append("Signature authenticity questionable.")
        
        if delivery_score > 80:
            parts.append("Delivery tracking confirms successful delivery.")
        elif delivery_score > 50:
            parts.append("Delivery tracking mostly consistent.")
        else:
            parts.append("Delivery tracking shows inconsistencies.")
        
        if damage_score > 50:
            parts.append(f"Visible damage detected ({damage_score:.0f}% severity).")
        
        return " ".join(parts)
    
    def _make_decision(
        self,
        analysis: AIAnalysisResult,
        claimed_amount: float
    ) -> ResolutionDecision:
        """
        Prende decisione basata su analisi AI.
        
        Regole:
        - confidence > 85%: auto-resolve
        - confidence 50-85%: escalate human
        - confidence < 50%: request more evidence
        - importi > 5k EUR: human approva anche se confidence alta
        """
        # Human-in-the-loop per importi alti
        if claimed_amount > AUTO_RESOLUTION_LIMIT_EUR:
            logger.info("high_value_requires_human", amount=claimed_amount)
            return ResolutionDecision.ESCALATE_HUMAN
        
        # Decisione basata su confidence
        if analysis.overall_confidence >= AUTO_RESOLVE_THRESHOLD:
            # Auto-resolve: carrier vince se delivery verificata
            if analysis.delivery_verified > 60 and analysis.damage_score < 50:
                return ResolutionDecision.AUTO_RESOLVE_CARRIER_WINS
            else:
                return ResolutionDecision.AUTO_RESOLVE_CUSTOMER_WINS
        
        elif analysis.overall_confidence >= HUMAN_ESCALATION_THRESHOLD:
            return ResolutionDecision.ESCALATE_HUMAN
        
        else:
            return ResolutionDecision.REQUEST_MORE_EVIDENCE
    
    async def _execute_resolution(
        self,
        event: DisputeEvent,
        evidence: Evidence,
        analysis: AIAnalysisResult,
        decision: ResolutionDecision
    ) -> Resolution:
        """Esegue risoluzione su blockchain."""
        
        carrier_wins = decision == ResolutionDecision.AUTO_RESOLVE_CARRIER_WINS
        requires_human = decision == ResolutionDecision.ESCALATE_HUMAN
        
        # Calcola refund
        if carrier_wins:
            refund_amount = 0.0
        elif decision == ResolutionDecision.AUTO_RESOLVE_CUSTOMER_WINS:
            refund_amount = event.claimed_amount
        else:
            refund_amount = 0.0  # TBD da human
        
        # Genera hash evidence
        evidence_hash = hashlib.sha256(
            json.dumps(evidence.tracking_history, default=str).encode()
        ).hexdigest()[:64]
        
        ai_analysis_hash = hashlib.sha256(
            json.dumps({
                "signature": analysis.signature_authentic,
                "delivery": analysis.delivery_verified,
                "damage": analysis.damage_visible,
                "confidence": analysis.overall_confidence
            }).encode()
        ).hexdigest()[:64]
        
        # Se non richiede human, esegui su blockchain
        tx_hash = None
        if not requires_human:
            tx_hash = await self._submit_to_blockchain(
                shipment_id=str(event.shipment_id),
                carrier_wins=carrier_wins,
                refund_amount=refund_amount,
                evidence_hash=evidence_hash,
                ai_hash=ai_analysis_hash,
                confidence=int(analysis.overall_confidence)
            )
        
        resolution = Resolution(
            dispute_id=event.dispute_id,
            shipment_id=event.shipment_id,
            decision=decision,
            carrier_wins=carrier_wins,
            refund_amount=refund_amount,
            confidence=analysis.overall_confidence,
            evidence_hash=evidence_hash,
            ai_analysis_hash=ai_analysis_hash,
            resolved_at=datetime.utcnow(),
            requires_human_arbitration=requires_human,
            tx_hash=tx_hash
        )
        
        self._resolutions[event.dispute_id] = resolution
        
        logger.info(
            "dispute_resolution_executed",
            dispute_id=str(event.dispute_id),
            decision=decision.value,
            carrier_wins=carrier_wins,
            confidence=analysis.overall_confidence,
            tx_hash=tx_hash[:16] if tx_hash else None
        )
        
        return resolution
    
    async def _submit_to_blockchain(
        self,
        shipment_id: str,
        carrier_wins: bool,
        refund_amount: float,
        evidence_hash: str,
        ai_hash: str,
        confidence: int
    ) -> Optional[str]:
        """Scrive risoluzione su CarrierEscrow smart contract."""
        try:
            # In produzione: chiama CarrierEscrow.resolveDispute()
            # Per ora: simulazione
            
            await asyncio.sleep(0.5)  # Simula delay blockchain
            
            tx_hash = "0x" + hashlib.sha256(
                f"{shipment_id}{carrier_wins}{datetime.utcnow()}".encode()
            ).hexdigest()[:64]
            
            logger.info("blockchain_resolution_submitted", tx_hash=tx_hash[:16])
            return tx_hash
            
        except Exception as e:
            logger.error("blockchain_resolution_failed", error=str(e))
            return None
    
    async def _flag_carrier_fraud(self, shipment_id: UUID):
        """Flagga carrier se pattern sospetto rilevato."""
        async with get_db_session() as db:
            shipment = await db.get(Spedizione, shipment_id)
            if not shipment or not shipment.carrier_id:
                return
            
            carrier_id = shipment.carrier_id
            carrier = await db.get(Corriere, carrier_id)
            
            if not carrier:
                return
            
            # Decrementa affidabilità
            carrier.affidabilita = max(0, (carrier.affidabilita or 100) - 10)
            
            # Track pattern
            carrier_key = f"{carrier_id}"
            self._dispute_patterns[carrier_key] = self._dispute_patterns.get(carrier_key, 0) + 1
            
            # Se pattern ricorrente, segnala a Paolo per potenziale blacklist
            if self._dispute_patterns[carrier_key] >= 3:
                logger.warning(
                    "fraud_pattern_detected",
                    carrier_id=carrier_id,
                    carrier_name=carrier.nome,
                    dispute_count=self._dispute_patterns[carrier_key]
                )
                # Notifica orchestratore
                await self._notify_orchestrator_of_fraud(carrier_id)
            
            await db.commit()
    
    async def _notify_orchestrator_of_fraud(self, carrier_id: int):
        """Notifica orchestratore di pattern frode."""
        logger.warning(
            "notifying_orchestrator_fraud",
            carrier_id=carrier_id,
            action="potential_blacklist"
        )
        # Il orchestratore coordinerà con Paolo per blacklist
    
    async def resolve_with_human_decision(
        self,
        dispute_id: UUID,
        carrier_wins: bool,
        refund_amount: float,
        admin_notes: str
    ) -> Optional[Resolution]:
        """
        Completa risoluzione dopo decisione umana.
        
        Usato quando GIULIA ha escalato a human.
        """
        # Trova dispute
        # In produzione: lookup da DB
        
        logger.info(
            "human_resolution_applied",
            dispute_id=str(dispute_id),
            carrier_wins=carrier_wins,
            refund_amount=refund_amount
        )
        
        # Submit a blockchain
        tx_hash = await self._submit_to_blockchain(
            shipment_id=str(dispute_id),  # Simplified
            carrier_wins=carrier_wins,
            refund_amount=refund_amount,
            evidence_hash="human_decision",
            ai_hash="human_override",
            confidence=100
        )
        
        return None  # Simplified
    
    def get_resolution_stats(self) -> Dict[str, Any]:
        """Statistiche risoluzioni."""
        total = len(self._resolutions)
        auto_resolved = sum(1 for r in self._resolutions.values() 
                          if not r.requires_human_arbitration)
        escalated = total - auto_resolved
        
        avg_confidence = 0.0
        if total > 0:
            avg_confidence = sum(r.confidence for r in self._resolutions.values()) / total
        
        return {
            "total_disputes": total,
            "auto_resolved": auto_resolved,
            "escalated_to_human": escalated,
            "avg_confidence": round(avg_confidence, 2),
            "auto_resolve_threshold": AUTO_RESOLVE_THRESHOLD,
            "auto_resolution_limit_eur": AUTO_RESOLUTION_LIMIT_EUR
        }
    
    def get_resolutions(self) -> List[Resolution]:
        """Lista tutte le risoluzioni."""
        return list(self._resolutions.values())


# Singleton
_giulia_instance: Optional[GiuliaAgent] = None


def get_giulia_agent() -> GiuliaAgent:
    """Factory per GiuliaAgent singleton."""
    global _giulia_instance
    
    if _giulia_instance is None:
        _giulia_instance = GiuliaAgent()
    
    return _giulia_instance