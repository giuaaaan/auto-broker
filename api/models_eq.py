"""
AUTO-BROKER 3.0 - Emotional Intelligence Models
Database models for EQ layer with proper foreign key constraints
Architecture: Meta AI Agents 2025, Google Affective Computing
"""

from datetime import datetime
from uuid import UUID as PyUUID
import uuid

from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, Text, 
    Numeric, ForeignKey, CheckConstraint, Index, ARRAY, JSON, Float
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from models import Base, Lead


class SentimentAnalysis(Base):
    """
    Voice sentiment analysis from Hume AI Prosody or fallback local analysis.
    Stores emotional state detected during calls for adaptive agent response.
    """
    __tablename__ = "sentiment_analysis"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    call_id = Column(String(255), unique=True, nullable=False, index=True)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), index=True)
    sentiment_score = Column(Numeric(3, 2), CheckConstraint('sentiment_score BETWEEN -1.0 AND 1.0'))
    emotions = Column(JSONB, nullable=False, default={})
    dominant_emotion = Column(String(50))
    confidence = Column(Numeric(3, 2), CheckConstraint('confidence BETWEEN 0.0 AND 1.0'))
    prosody_raw = Column(JSONB)  # Raw Hume AI response
    requires_escalation = Column(Boolean, default=False)
    escalation_reason = Column(String(255))
    analyzed_at = Column(DateTime(timezone=True), default=func.now())
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    
    # Relationships
    lead = relationship("Lead", backref="sentiment_analyses")
    
    __table_args__ = (
        Index('idx_sentiment_lead_date', 'lead_id', 'analyzed_at', postgresql_using='btree'),
        Index('idx_sentiment_escalation', 'requires_escalation', postgresql_where=(requires_escalation == True)),
        Index('idx_sentiment_emotions', 'emotions', postgresql_using='gin'),
    )


class PsychologicalProfile(Base):
    """
    Psychological profiles based on BANT-C+Emotion framework.
    Used for adaptive selling and personalization.
    """
    __tablename__ = "psychological_profiles"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), unique=True, nullable=False)
    profile_type = Column(String(20), CheckConstraint("profile_type IN ('velocity', 'analyst', 'social', 'security')"))
    decision_speed = Column(Integer, CheckConstraint('decision_speed BETWEEN 1 AND 10'))
    risk_tolerance = Column(Integer, CheckConstraint('risk_tolerance BETWEEN 1 AND 10'))
    price_sensitivity = Column(Integer, CheckConstraint('price_sensitivity BETWEEN 1 AND 10'))
    communication_pref = Column(String(20), CheckConstraint("communication_pref IN ('phone', 'email', 'whatsapp', 'sms')"))
    pain_points = Column(ARRAY(String))
    core_values = Column(ARRAY(String))
    # Note: profile_embedding is stored in ChromaDB, not PostgreSQL
    churn_risk_score = Column(Numeric(3, 2))
    profile_metadata = Column(JSONB, default={})
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    
    # Relationships
    lead = relationship("Lead", backref="psychological_profile", uselist=False)
    
    __table_args__ = (
        Index('idx_profile_type', 'profile_type'),
        Index('idx_profile_churn', 'churn_risk_score', postgresql_where=(churn_risk_score > 0.7)),
    )


class InteractionHistory(Base):
    """
    Interaction memory for agent continuity and personalization.
    Tracks all touchpoints with sentiment and strategy information.
    """
    __tablename__ = "interaction_history"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_name = Column(String(50), nullable=False)
    channel = Column(String(20), nullable=False)  # call, email, sms, whatsapp, meeting
    interaction_type = Column(String(30), CheckConstraint("interaction_type IN ('call', 'email', 'sms', 'whatsapp', 'meeting')"))
    # Note: interaction_vector stored in ChromaDB
    sentiment_id = Column(UUID(as_uuid=True), ForeignKey("sentiment_analysis.id", ondelete="SET NULL"))
    transcription_text = Column(Text)
    strategy_applied = Column(String(50))  # Which persuasion strategy was used
    persuasion_techniques = Column(ARRAY(String))  # List of techniques used
    conversion_value = Column(Numeric(10, 2))
    outcome = Column(String(20), CheckConstraint("outcome IN ('converted', 'rejected', 'nurture', 'escalated', 'pending')"))
    outcome_notes = Column(Text)
    next_best_action = Column(String(100))
    context_data = Column(JSONB, default={})
    created_at = Column(DateTime(timezone=True), default=func.now())
    
    # Relationships
    lead = relationship("Lead", backref="interactions")
    sentiment = relationship("SentimentAnalysis", backref="interactions")
    
    __table_args__ = (
        Index('idx_interaction_lead_date', 'lead_id', 'created_at', postgresql_using='btree'),
        Index('idx_interaction_agent', 'agent_name', 'created_at'),
        Index('idx_interaction_outcome', 'outcome'),
    )


class NurturingSequence(Base):
    """
    Adaptive nurturing sequences based on psychological profile and engagement.
    Automated follow-up sequences with personalization.
    """
    __tablename__ = "nurturing_sequences"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)
    sequence_type = Column(String(20), CheckConstraint("sequence_type IN ('post_rejection', 'long_term', 'reactivation', 'activation', 'objection_handling')"))
    step_number = Column(Integer, nullable=False)
    content_template = Column(Text, nullable=False)
    personalization_vars = Column(JSONB, default={})
    channel = Column(String(20), nullable=False)
    scheduled_at = Column(DateTime(timezone=True), nullable=False)
    executed_at = Column(DateTime(timezone=True))
    opened = Column(Boolean, default=False)
    clicked = Column(Boolean, default=False)
    replied = Column(Boolean, default=False)
    converted = Column(Boolean, default=False)
    engagement_score = Column(Numeric(3, 2), default=0.0)
    ai_optimized = Column(Boolean, default=False)
    optimization_notes = Column(Text)
    created_at = Column(DateTime(timezone=True), default=func.now())
    
    # Relationships
    lead = relationship("Lead", backref="nurturing_sequences")
    
    __table_args__ = (
        Index('idx_nurturing_lead_type', 'lead_id', 'sequence_type', 'step_number', unique=True),
        Index('idx_nurturing_scheduled', 'scheduled_at', postgresql_where=(executed_at == None)),
    )


class PersuasionStrategy(Base):
    """
    A/B tested persuasion strategies per profile type.
    Stores successful strategies for reuse.
    """
    __tablename__ = "persuasion_strategies"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    strategy_name = Column(String(100), nullable=False)
    profile_type = Column(String(20), CheckConstraint("profile_type IN ('velocity', 'analyst', 'social', 'security')"))
    trigger_condition = Column(String(255))
    script_template = Column(Text, nullable=False)
    milton_patterns = Column(ARRAY(String))
    objection_handlers = Column(JSONB, default={})
    success_rate = Column(Numeric(3, 2))
    usage_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        Index('idx_strategy_profile_success', 'profile_type', 'success_rate', postgresql_using='btree'),
    )


class EQHealthMetric(Base):
    """
    Health metrics for Emotional Intelligence systems.
    Tracks Hume API quota and system performance.
    """
    __tablename__ = "eq_health_metrics"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    metric_type = Column(String(50), nullable=False)  # quota_usage, fallback_activations, etc.
    metric_value = Column(Numeric(10, 2))
    metric_metadata = Column(JSONB, default={})
    recorded_at = Column(DateTime(timezone=True), default=func.now())
    
    __table_args__ = (
        Index('idx_eq_health_type_date', 'metric_type', 'recorded_at', postgresql_using='btree'),
    )


# Views for common queries
# Note: Views are created in init_eq.sql, not here
