"""
AUTO-BROKER AI Audit Logger
GDPR Article 22 - Right to explanation
Immutable append-only log for AI decisions
Regulatory Compliance - P0 Critical
"""

import hashlib
import json
import logging
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum

from sqlalchemy import (
    Column, String, DateTime, JSON, Boolean, Text, Numeric,
    create_engine, Index, event
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)
Base = declarative_base()


class DecisionType(str, Enum):
    """Types of AI decisions to audit."""
    PRICING = "pricing"
    ROUTING = "routing"
    CARRIER_SELECTION = "carrier_selection"
    LEAD_SCORING = "lead_scoring"
    SENTIMENT_ANALYSIS = "sentiment_analysis"
    AGENT_RESPONSE = "agent_response"


class DecisionOutcome(str, Enum):
    """Outcome of AI decision."""
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    MODIFIED = "modified"  # Human override
    PENDING = "pending"


class AIDecisionLog(Base):
    """
    Immutable audit log for AI decisions.
    
    GDPR Article 22 requires:
    - Input data used
    - Logic applied
    - Feature importance
    - Human override capability
    
    This table is APPEND-ONLY. No UPDATE/DELETE allowed.
    """
    
    __tablename__ = "ai_decisions"
    
    # Primary key
    decision_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Decision metadata
    decision_type = Column(String(50), nullable=False, index=True)
    model_version = Column(String(50), nullable=False)
    model_name = Column(String(100), nullable=False)
    
    # Input/Output hashes for integrity verification
    input_hash = Column(String(64), nullable=False)  # SHA256
    output_hash = Column(String(64), nullable=False)  # SHA256
    input_data = Column(JSON, nullable=False)  # Full input (may be masked)
    output_data = Column(JSON, nullable=False)  # Full output
    
    # Explainability (GDPR Article 22)
    feature_importance = Column(JSON, nullable=False)  # SHAP values or similar
    decision_logic = Column(Text, nullable=False)  # Human-readable explanation
    confidence_score = Column(Numeric(5, 4), nullable=True)  # 0.0000 - 1.0000
    
    # Context
    organization_id = Column(String(50), nullable=False, index=True)
    user_id = Column(String(50), nullable=True, index=True)  # Broker who triggered
    lead_id = Column(String(50), nullable=True, index=True)
    shipment_id = Column(String(50), nullable=True, index=True)
    
    # Human override (HITL)
    human_override = Column(Boolean, default=False, nullable=False)
    override_reason = Column(Text, nullable=True)
    overridden_by = Column(String(50), nullable=True)
    overridden_at = Column(DateTime, nullable=True)
    original_decision_id = Column(UUID(as_uuid=True), nullable=True)  # Link to original
    
    # Timestamps (immutable)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Compliance metadata
    retention_until = Column(DateTime, nullable=False)  # GDPR: 5 years
    archived = Column(Boolean, default=False, nullable=False)
    archive_location = Column(String(500), nullable=True)  # S3 path after 5 years
    
    __table_args__ = (
        Index('idx_decisions_org_type', 'organization_id', 'decision_type'),
        Index('idx_decisions_created', 'created_at'),
        Index('idx_decisions_override', 'human_override', 'created_at'),
    )


# Prevent UPDATE and DELETE at database level
def _prevent_update_delete(mapper, connection, target):
    """Raise error if attempt to update or delete audit log."""
    raise Exception(
        "AI_DECISIONS table is IMMUTABLE. "
        "Updates and deletes are prohibited for compliance."
    )


event.listen(AIDecisionLog, 'before_update', _prevent_update_delete)
event.listen(AIDecisionLog, 'before_delete', _prevent_update_delete)


@dataclass
class DecisionInput:
    """Input data for AI decision."""
    features: Dict[str, Any]
    context: Dict[str, Any]
    timestamp: datetime


@dataclass
class DecisionOutput:
    """Output from AI decision."""
    decision: str
    confidence: float
    alternatives: List[Dict[str, Any]]
    raw_scores: Dict[str, float]


@dataclass
class FeatureImportance:
    """SHAP-style feature importance."""
    feature_name: str
    importance_score: float  # SHAP value
    direction: str  # "positive" or "negative"
    description: str


class AuditLogger:
    """
    Immutable audit logger for AI decisions.
    
    All AI decisions MUST be logged through this class.
    Supports GDPR Article 22 right to explanation.
    """
    
    RETENTION_YEARS = 5  # Legal requirement for transport
    
    def __init__(self, db_session_factory):
        """Initialize with database session factory."""
        self.session_factory = db_session_factory
    
    @staticmethod
    def _compute_hash(data: Dict[str, Any]) -> str:
        """Compute SHA256 hash of data for integrity."""
        canonical = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()
    
    def log_decision(
        self,
        decision_type: DecisionType,
        model_name: str,
        model_version: str,
        input_data: Dict[str, Any],
        output_data: Dict[str, Any],
        feature_importance: List[FeatureImportance],
        decision_logic: str,
        organization_id: str,
        user_id: Optional[str] = None,
        lead_id: Optional[str] = None,
        shipment_id: Optional[str] = None,
        confidence_score: Optional[float] = None
    ) -> uuid.UUID:
        """
        Log an AI decision to immutable audit trail.
        
        Args:
            decision_type: Type of decision (pricing, routing, etc.)
            model_name: Name of model used
            model_version: Model version (semver)
            input_data: Input features and context
            output_data: Model output
            feature_importance: List of feature importance scores
            decision_logic: Human-readable explanation
            organization_id: Organization ID
            user_id: User who triggered decision
            lead_id: Related lead ID
            shipment_id: Related shipment ID
            confidence_score: Model confidence (0-1)
        
        Returns:
            decision_id: UUID of logged decision
        """
        session = self.session_factory()
        
        try:
            # Compute hashes for integrity
            input_hash = self._compute_hash(input_data)
            output_hash = self._compute_hash(output_data)
            
            # Calculate retention date (5 years)
            retention_until = datetime.utcnow().replace(year=datetime.utcnow().year + self.RETENTION_YEARS)
            
            # Create log entry
            decision = AIDecisionLog(
                decision_id=uuid.uuid4(),
                decision_type=decision_type.value,
                model_name=model_name,
                model_version=model_version,
                input_hash=input_hash,
                output_hash=output_hash,
                input_data=input_data,
                output_data=output_data,
                feature_importance=[asdict(f) for f in feature_importance],
                decision_logic=decision_logic,
                confidence_score=confidence_score,
                organization_id=organization_id,
                user_id=user_id,
                lead_id=lead_id,
                shipment_id=shipment_id,
                human_override=False,
                created_at=datetime.utcnow(),
                retention_until=retention_until,
                archived=False
            )
            
            session.add(decision)
            session.commit()
            
            logger.info(
                f"AI decision logged: {decision_type.value}",
                extra={
                    "decision_id": str(decision.decision_id),
                    "decision_type": decision_type.value,
                    "model": model_name,
                    "version": model_version,
                    "org": organization_id
                }
            )
            
            return decision.decision_id
            
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to log AI decision: {e}")
            raise
        finally:
            session.close()
    
    def log_human_override(
        self,
        original_decision_id: uuid.UUID,
        new_decision: Dict[str, Any],
        override_reason: str,
        overridden_by: str,
        input_data: Optional[Dict[str, Any]] = None
    ) -> uuid.UUID:
        """
        Log human override of AI decision.
        
        Creates new audit entry linked to original.
        Required for HITL compliance.
        """
        session = self.session_factory()
        
        try:
            # Fetch original decision
            original = session.query(AIDecisionLog).filter_by(
                decision_id=original_decision_id
            ).first()
            
            if not original:
                raise ValueError(f"Original decision {original_decision_id} not found")
            
            # Compute new hashes
            input_data = input_data or original.input_data
            input_hash = self._compute_hash(input_data)
            output_hash = self._compute_hash(new_decision)
            
            # Create override entry
            override = AIDecisionLog(
                decision_id=uuid.uuid4(),
                decision_type=original.decision_type,
                model_name=original.model_name,
                model_version=original.model_version + "-OVERRIDE",
                input_hash=input_hash,
                output_hash=output_hash,
                input_data=input_data,
                output_data=new_decision,
                feature_importance=original.feature_importance,
                decision_logic=f"HUMAN OVERRIDE: {override_reason}",
                confidence_score=None,
                organization_id=original.organization_id,
                user_id=original.user_id,
                lead_id=original.lead_id,
                shipment_id=original.shipment_id,
                human_override=True,
                override_reason=override_reason,
                overridden_by=overridden_by,
                overridden_at=datetime.utcnow(),
                original_decision_id=original_decision_id,
                created_at=datetime.utcnow(),
                retention_until=original.retention_until,
                archived=False
            )
            
            session.add(override)
            session.commit()
            
            logger.info(
                f"Human override logged for decision {original_decision_id}",
                extra={
                    "override_decision_id": str(override.decision_id),
                    "original_decision_id": str(original_decision_id),
                    "overridden_by": overridden_by
                }
            )
            
            return override.decision_id
            
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to log human override: {e}")
            raise
        finally:
            session.close()
    
    def get_decision_explanation(self, decision_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """
        Get full explanation for a decision (GDPR Article 22).
        
        Returns:
            Dict with all information needed to explain decision
        """
        session = self.session_factory()
        
        try:
            decision = session.query(AIDecisionLog).filter_by(
                decision_id=decision_id
            ).first()
            
            if not decision:
                return None
            
            return {
                "decision_id": str(decision.decision_id),
                "decision_type": decision.decision_type,
                "model": {
                    "name": decision.model_name,
                    "version": decision.model_version
                },
                "input_data": decision.input_data,
                "output_data": decision.output_data,
                "feature_importance": decision.feature_importance,
                "decision_logic": decision.decision_logic,
                "confidence_score": float(decision.confidence_score) if decision.confidence_score else None,
                "human_override": decision.human_override,
                "override_reason": decision.override_reason if decision.human_override else None,
                "created_at": decision.created_at.isoformat(),
                "integrity": {
                    "input_hash": decision.input_hash,
                    "output_hash": decision.output_hash,
                    "verified": self._verify_integrity(decision)
                }
            }
            
        finally:
            session.close()
    
    def _verify_integrity(self, decision: AIDecisionLog) -> bool:
        """Verify data integrity using hashes."""
        input_hash = self._compute_hash(decision.input_data)
        output_hash = self._compute_hash(decision.output_data)
        
        return (
            input_hash == decision.input_hash and
            output_hash == decision.output_hash
        )
    
    def get_decisions_for_user(
        self,
        user_id: str,
        organization_id: str,
        decision_type: Optional[DecisionType] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get all decisions for a user (GDPR data portability).
        """
        session = self.session_factory()
        
        try:
            query = session.query(AIDecisionLog).filter(
                AIDecisionLog.user_id == user_id,
                AIDecisionLog.organization_id == organization_id
            )
            
            if decision_type:
                query = query.filter(AIDecisionLog.decision_type == decision_type.value)
            
            decisions = query.order_by(AIDecisionLog.created_at.desc()).limit(limit).all()
            
            return [
                {
                    "decision_id": str(d.decision_id),
                    "decision_type": d.decision_type,
                    "created_at": d.created_at.isoformat(),
                    "decision_logic": d.decision_logic,
                    "human_override": d.human_override
                }
                for d in decisions
            ]
            
        finally:
            session.close()


# Archive old decisions to cold storage
def archive_old_decisions(db_session_factory, s3_client, bucket: str):
    """
    Archive decisions older than 5 years to S3 Glacier.
    
    Called by nightly cron job.
    """
    session = db_session_factory()
    
    try:
        cutoff_date = datetime.utcnow().replace(year=datetime.utcnow().year - 5)
        
        old_decisions = session.query(AIDecisionLog).filter(
            AIDecisionLog.created_at < cutoff_date,
            AIDecisionLog.archived == False
        ).all()
        
        for decision in old_decisions:
            # Serialize to JSON
            data = {
                "decision_id": str(decision.decision_id),
                "decision_type": decision.decision_type,
                "model_name": decision.model_name,
                "model_version": decision.model_version,
                "input_hash": decision.input_hash,
                "output_hash": decision.output_hash,
                "input_data": decision.input_data,
                "output_data": decision.output_data,
                "feature_importance": decision.feature_importance,
                "decision_logic": decision.decision_logic,
                "created_at": decision.created_at.isoformat()
            }
            
            # Upload to S3 Glacier
            key = f"ai-decisions/{decision.organization_id}/{decision.decision_id}.json"
            s3_client.put_object(
                Bucket=bucket,
                Key=key,
                Body=json.dumps(data).encode(),
                StorageClass="GLACIER"
            )
            
            # Mark as archived
            decision.archived = True
            decision.archive_location = f"s3://{bucket}/{key}"
        
        session.commit()
        logger.info(f"Archived {len(old_decisions)} old decisions to Glacier")
        
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to archive decisions: {e}")
        raise
    finally:
        session.close()
