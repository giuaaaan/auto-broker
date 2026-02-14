"""
AUTO-BROKER: Governance Models

Database models per l'architettura decisionale asimmetrica:
- VetoSession: Gestione stato veto window
- DecisionAudit: Tracciamento GDPR-compliant
- OperatorPresence: Heartbeat operatori
- GovernanceConfig: Soglie configurabili
"""
from datetime import datetime
from decimal import Decimal
from enum import Enum as PyEnum
from typing import Optional, Dict, Any
from uuid import uuid4

from sqlalchemy import (
    Column, String, DateTime, Numeric, Integer, 
    ForeignKey, Text, Boolean, JSON, Index, Enum
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from api.models import Base


class VetoStatus(str, PyEnum):
    """Stati possibili di una sessione veto."""
    RESERVED = "reserved"       # Soft lock attivo, timer in corso
    COMMITTING = "committing"   # Transizione a committed
    COMMITTED = "committed"     # Operazione eseguita, irreversibile
    VETOED = "vetoed"           # Veto esercitato, compensation pending
    EXPIRED = "expired"         # Timer scaduto, auto-committed
    CANCELLED = "cancelled"     # Cancellata (errore o manuale)


class DecisionMode(str, PyEnum):
    """Modalità decisionale."""
    FULL_AUTO = "full_auto"           # Nessuna supervisione
    HUMAN_ON_THE_LOOP = "human_on_the_loop"  # Veto window (PAOLO)
    HUMAN_IN_THE_LOOP = "human_in_the_loop"  # Pre-auth (GIULIA)
    DUAL_CONTROL = "dual_control"     # Four-eyes principle


class AgentType(str, PyEnum):
    """Tipi di agenti."""
    PAOLO = "paolo"    # Carrier Failover
    GIULIA = "giulia"  # Dispute Resolution


class VetoSession(Base):
    """
    Sessione veto per human-on-the-loop governance.
    
    Traccia lo stato di una decisione in veto window,
    con timer e gestione stato.
    """
    __tablename__ = "veto_sessions"
    
    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Identificazione
    agent_type = Column(Enum(AgentType), nullable=False, index=True)
    operation_type = Column(String(50), nullable=False)  # carrier_failover, dispute_resolution
    
    # Riferimenti business
    shipment_id = Column(UUID(as_uuid=True), ForeignKey("spedizioni.id"), nullable=True)
    carrier_id = Column(UUID(as_uuid=True), ForeignKey("corrieri.id"), nullable=True)
    dispute_id = Column(UUID(as_uuid=True), nullable=True)
    
    # Contesto decisionale
    amount_eur = Column(Numeric(10, 2), nullable=False)
    confidence_score = Column(Numeric(3, 2), nullable=True)  # 0.00 - 1.00
    
    # Stato
    status = Column(
        Enum(VetoStatus), 
        nullable=False, 
        default=VetoStatus.RESERVED,
        index=True
    )
    
    # Timer configurazione
    timeout_seconds = Column(Integer, nullable=False, default=60)
    opened_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    
    # Risultato
    committed_at = Column(DateTime(timezone=True), nullable=True)
    vetoed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Operatore (se veto o approval)
    operator_id = Column(UUID(as_uuid=True), ForeignKey("operatori.id"), nullable=True)
    operator_rationale = Column(Text, nullable=True)
    
    # Blockchain reference
    blockchain_tx_hash = Column(String(66), nullable=True)
    compensation_tx_hash = Column(String(66), nullable=True)
    
    # Metadata
    context = Column(JSONB, default=dict)  # JSON arbitrario per contesto
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    
    # Indici
    __table_args__ = (
        Index('idx_veto_status_expires', 'status', 'expires_at'),
        Index('idx_veto_shipment', 'shipment_id', 'created_at'),
        Index('idx_veto_agent_status', 'agent_type', 'status'),
    )
    
    @property
    def time_remaining_seconds(self) -> float:
        """Calcola secondi rimanenti per veto."""
        if self.status != VetoStatus.RESERVED:
            return 0.0
        
        now = datetime.utcnow()
        if now >= self.expires_at:
            return 0.0
        
        return (self.expires_at - now).total_seconds()
    
    @property
    def is_expired(self) -> bool:
        """Verifica se la sessione è scaduta."""
        return datetime.utcnow() >= self.expires_at
    
    @property
    def can_be_vetoed(self) -> bool:
        """Verifica se è ancora possibile esercitare veto."""
        return (
            self.status == VetoStatus.RESERVED and 
            not self.is_expired
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Serializza sessione per API."""
        return {
            "id": str(self.id),
            "agent_type": self.agent_type.value if self.agent_type else None,
            "operation_type": self.operation_type,
            "shipment_id": str(self.shipment_id) if self.shipment_id else None,
            "amount_eur": str(self.amount_eur),
            "confidence_score": float(self.confidence_score) if self.confidence_score else None,
            "status": self.status.value if self.status else None,
            "time_remaining_seconds": self.time_remaining_seconds,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "operator_id": str(self.operator_id) if self.operator_id else None,
            "operator_rationale": self.operator_rationale,
            "can_be_vetoed": self.can_be_vetoed
        }


class DecisionAudit(Base):
    """
    Audit trail immutabile per GDPR compliance.
    
    Registra ogni interazione con il sistema di governance,
    inclusi AI rationale e human decisions.
    """
    __tablename__ = "decision_audit"
    
    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Riferimento veto session
    veto_session_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("veto_sessions.id"), 
        nullable=False,
        index=True
    )
    
    # Timestamp
    timestamp = Column(DateTime(timezone=True), nullable=False, default=func.now())
    
    # Evento
    event_type = Column(String(50), nullable=False)  # window_opened, veto_exerted, committed, etc
    
    # Contesto AI (GDPR Art. 22 - spiegazione decisione)
    ai_rationale = Column(JSONB, nullable=True)
    ai_model_version = Column(String(50), nullable=True)
    ai_confidence = Column(Numeric(3, 2), nullable=True)
    evidence_hashes = Column(JSONB, default=list)  # Array di hash IPFS
    
    # Interazione umana
    operator_id = Column(UUID(as_uuid=True), ForeignKey("operatori.id"), nullable=True)
    operator_action = Column(String(20), nullable=True)  # veto, approve, extend
    operator_rationale = Column(Text, nullable=True)
    time_to_decision_ms = Column(Integer, nullable=True)
    
    # Outcome
    final_state = Column(String(20), nullable=True)
    blockchain_tx_hash = Column(String(66), nullable=True)
    
    # GDPR compliance
    gdpr_article22_compliant = Column(Boolean, default=False)
    human_supervised = Column(Boolean, default=False)
    right_to_contest_noted = Column(Boolean, default=False)
    
    # Immutable data (non modificabile)
    ipfs_audit_hash = Column(String(64), nullable=True)  # Hash su IPFS per immutabilità
    
    # Indici
    __table_args__ = (
        Index('idx_audit_session_time', 'veto_session_id', 'timestamp'),
        Index('idx_audit_operator', 'operator_id', 'timestamp'),
        Index('idx_audit_event', 'event_type', 'timestamp'),
    )


class OperatorPresence(Base):
    """
    Tracciamento presenza e heartbeat operatori.
    
    Usato per determinare se operatori sono disponibili
    per supervisione in tempo reale.
    """
    __tablename__ = "operator_presence"
    
    # Primary Key
    operator_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("operatori.id"), 
        primary_key=True
    )
    
    # Stato
    is_online = Column(Boolean, default=False, index=True)
    last_heartbeat = Column(DateTime(timezone=True), nullable=True)
    
    # Contesto
    dashboard_url = Column(String(500), nullable=True)  # URL sessione attiva
    current_session_id = Column(UUID(as_uuid=True), ForeignKey("veto_sessions.id"), nullable=True)
    
    # Capability
    can_receive_urgent = Column(Boolean, default=True)
    can_receive_standard = Column(Boolean, default=True)
    
    # Metadata
    user_agent = Column(String(200), nullable=True)
    ip_address = Column(String(45), nullable=True)  # IPv6 compatible
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    
    @property
    def seconds_since_heartbeat(self) -> float:
        """Secondi dall'ultimo heartbeat."""
        if not self.last_heartbeat:
            return float('inf')
        return (datetime.utcnow() - self.last_heartbeat).total_seconds()
    
    @property
    def is_available(self) -> bool:
        """Verifica se operatore è disponibile per supervisione."""
        return (
            self.is_online and 
            self.seconds_since_heartbeat < 30  # 30s timeout
        )


class GovernanceConfig(Base):
    """
    Configurazione dinamica governance.
    
    Soglie e policy configurabili runtime.
    """
    __tablename__ = "governance_config"
    
    # Primary Key (singleton pattern - una riga per environment)
    id = Column(Integer, primary_key=True, default=1)
    environment = Column(String(20), nullable=False, unique=True, default="production")
    
    # Feature flags
    governance_enabled = Column(Boolean, default=False)
    
    # PAOLO thresholds
    paolo_full_auto_max_eur = Column(Numeric(10, 2), default=Decimal("5000.00"))
    paolo_hot_standby_max_eur = Column(Numeric(10, 2), default=Decimal("10000.00"))
    paolo_human_in_loop_max_eur = Column(Numeric(10, 2), default=Decimal("50000.00"))
    paolo_dual_control_min_eur = Column(Numeric(10, 2), default=Decimal("50000.00"))
    
    # PAOLO timeouts
    paolo_veto_window_seconds = Column(Integer, default=60)
    paolo_escalation_first_reminder_seconds = Column(Integer, default=15)
    paolo_escalation_backup_seconds = Column(Integer, default=30)
    
    # GIULIA thresholds
    giulia_full_auto_max_eur = Column(Numeric(10, 2), default=Decimal("1000.00"))
    giulia_fast_track_confidence_min = Column(Numeric(3, 2), default=Decimal("0.95"))
    giulia_fast_track_max_eur = Column(Numeric(10, 2), default=Decimal("3000.00"))
    giulia_human_in_loop_max_eur = Column(Numeric(10, 2), default=Decimal("10000.00"))
    
    # GIULIA timeouts
    giulia_standard_approval_hours = Column(Integer, default=4)
    giulia_escalation_senior_hours = Column(Integer, default=24)
    
    # Business hours
    business_hours_start = Column(String(5), default="09:00")
    business_hours_end = Column(String(5), default="18:00")
    weekend_policy = Column(String(20), default="emergency_only")  # emergency_only, full_auto_restricted
    holidays_policy = Column(String(20), default="human_in_loop_for_all")
    
    # Health check
    max_dashboard_downtime_seconds = Column(Integer, default=30)
    max_notification_downtime_seconds = Column(Integer, default=60)
    
    # Audit
    updated_by = Column(UUID(as_uuid=True), ForeignKey("operatori.id"), nullable=True)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    
    def get_threshold_for_agent(self, agent_type: str, amount: Decimal) -> str:
        """
        Determina modalità decisionale per agente e importo.
        
        Args:
            agent_type: 'paolo' o 'giulia'
            amount: Importo in EUR
            
        Returns:
            DecisionMode appropriata come stringa
        """
        agent = agent_type.lower()
        
        if agent == "paolo":
            if amount <= self.paolo_full_auto_max_eur:
                return DecisionMode.FULL_AUTO
            elif amount <= self.paolo_hot_standby_max_eur:
                return DecisionMode.HUMAN_ON_THE_LOOP
            elif amount < self.paolo_dual_control_min_eur:
                return DecisionMode.HUMAN_IN_THE_LOOP
            else:
                return DecisionMode.DUAL_CONTROL
        else:  # giulia
            if amount <= self.giulia_full_auto_max_eur:
                return DecisionMode.FULL_AUTO
            elif amount <= self.giulia_fast_track_max_eur:
                return DecisionMode.HUMAN_ON_THE_LOOP
            else:
                return DecisionMode.HUMAN_IN_THE_LOOP
    
    def to_dict(self) -> Dict[str, Any]:
        """Esporta configurazione come dizionario."""
        return {
            "governance_enabled": self.governance_enabled,
            "paolo": {
                "thresholds": {
                    "full_auto_max_eur": str(self.paolo_full_auto_max_eur),
                    "hot_standby_max_eur": str(self.paolo_hot_standby_max_eur),
                    "human_in_loop_max_eur": str(self.paolo_human_in_loop_max_eur),
                    "dual_control_min_eur": str(self.paolo_dual_control_min_eur)
                },
                "timeouts": {
                    "veto_window_seconds": self.paolo_veto_window_seconds,
                    "escalation_first_reminder_seconds": self.paolo_escalation_first_reminder_seconds,
                    "escalation_backup_seconds": self.paolo_escalation_backup_seconds
                }
            },
            "giulia": {
                "thresholds": {
                    "full_auto_max_eur": str(self.giulia_full_auto_max_eur),
                    "fast_track_confidence_min": float(self.giulia_fast_track_confidence_min),
                    "fast_track_max_eur": str(self.giulia_fast_track_max_eur),
                    "human_in_loop_max_eur": str(self.giulia_human_in_loop_max_eur)
                },
                "timeouts": {
                    "standard_approval_hours": self.giulia_standard_approval_hours,
                    "escalation_senior_hours": self.giulia_escalation_senior_hours
                }
            },
            "business_hours": {
                "start": self.business_hours_start,
                "end": self.business_hours_end,
                "weekend_policy": self.weekend_policy,
                "holidays_policy": self.holidays_policy
            }
        }


# Tabella placeholder per Operatori (se non esiste)
# In produzione questa tabella esiste già nel sistema
class Operatore(Base):
    """Operatore umano (placeholder - usa tabella esistente in produzione)."""
    __tablename__ = "operatori"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    email = Column(String(200), nullable=False, unique=True)
    name = Column(String(200), nullable=False)
    role = Column(String(50), nullable=False)  # operator, senior, admin
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=func.now())