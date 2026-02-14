"""
AUTO-BROKER 3.0 - Psychological Profiling Service
Production-grade with ChromaDB vector storage
Architecture: Meta AI Agents 2025, BANT-C+Emotion Framework
"""

import json
import logging
from typing import Dict, List, Literal, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime

import numpy as np
import chromadb
from chromadb.config import Settings
from chromadb.api.types import EmbeddingFunction, Documents, Embeddings
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models import PsychologicalProfile, InteractionHistory

logger = logging.getLogger(__name__)

ProfileType = Literal['velocity', 'analyst', 'social', 'security']
CommunicationPref = Literal['phone', 'email', 'whatsapp', 'sms']


@dataclass
class ProfileDimensions:
    """Dimensions for psychological profile."""
    decision_speed: int  # 1-10
    risk_tolerance: int  # 1-10
    price_sensitivity: int  # 1-10
    communication_pref: CommunicationPref
    pain_points: List[str]
    core_values: List[str]


class PsychologicalProfileService:
    """
    Service for psychological profiling and vector-based similarity search.
    
    Features:
    - Profile type determination via BANT-C+Emotion questions
    - Vector storage in ChromaDB for similarity search
    - Embedding generation for personality dimensions
    - Churn risk prediction based on profile + sentiment
    """
    
    # Profile type definitions with characteristics
    PROFILE_DEFINITIONS = {
        "velocity": {
            "name": "Velocity Seeker",
            "characteristics": [
                "Fast decision maker",
                "Time-sensitive",
                "Results-oriented",
                "Impatient with details"
            ],
            "optimal_approach": "Fast, direct, emphasize speed and efficiency",
            "key_triggers": ["immediately", "now", "quickly", "save time", "fast delivery"],
            "avoid": [" lengthy explanations", "too many options", "delays"]
        },
        "analyst": {
            "name": "Data Analyst",
            "characteristics": [
                "Evidence-based decision maker",
                "Detail-oriented",
                "Risk-averse without data",
                "Needs validation"
            ],
            "optimal_approach": "Provide data, comparisons, case studies, ROI calculations",
            "key_triggers": ["statistics", "data shows", "comparison", "ROI", "evidence"],
            "avoid": ["vague claims", "pressure tactics", "missing data"]
        },
        "social": {
            "name": "Relationship Builder",
            "characteristics": [
                "Trust-based decision maker",
                "Values relationships",
                "Social proof oriented",
                "Emotionally driven"
            ],
            "optimal_approach": "Build rapport, use testimonials, emphasize partnership",
            "key_triggers": ["trusted by", "partnership", "together", "relationship", "clients like you"],
            "avoid": ["impersonal approach", "purely transactional", "ignoring concerns"]
        },
        "security": {
            "name": "Risk Minimizer",
            "characteristics": [
                "Safety-first decision maker",
                "Needs guarantees",
                "Conservative",
                "Long-term thinker"
            ],
            "optimal_approach": "Emphasize guarantees, insurance, safety, risk mitigation",
            "key_triggers": ["guaranteed", "safe", "protected", "insured", "no risk", "peace of mind"],
            "avoid": ["uncertainty", "risky propositions", "lack of guarantees"]
        }
    }
    
    def __init__(self, chroma_persist_dir: str = ".chroma_db"):
        """
        Initialize ProfilingService.
        
        Args:
            chroma_persist_dir: Directory for ChromaDB persistence
        """
        self.chroma_client = chromadb.Client(Settings(
            chroma_db_impl="duckdb+parquet",
            persist_directory=chroma_persist_dir,
            anonymized_telemetry=False
        ))
        
        # Get or create collections
        self.profiles_collection = self.chroma_client.get_or_create_collection(
            name="psychological_profiles",
            metadata={"hnsw:space": "cosine"},
            embedding_function=SimpleEmbeddingFunction()
        )
        
        self.interactions_collection = self.chroma_client.get_or_create_collection(
            name="interaction_history",
            metadata={"hnsw:space": "cosine"},
            embedding_function=SimpleEmbeddingFunction()
        )
        
        logger.info(f"ProfilingService initialized with ChromaDB at {chroma_persist_dir}")
    
    def determine_profile_type(self, answers: Dict[str, str]) -> ProfileType:
        """
        Determine psychological profile type based on questionnaire answers.
        
        Algorithm:
        1. Score each profile type based on answer mappings
        2. Handle ties using priority order
        3. Return winning profile type
        
        Expected questions:
        - q1_speed: How do you typically make business decisions? (A=Quickly, B=Analyze data, C=Consult others, D=Carefully)
        - q2_risk: How do you feel about business risks? (A=Take calculated risks, B=Avoid if possible, C=Depends on team input, D=Minimize always)
        - q3_communication: Preferred communication? (A=Phone/direct, B=Email/detailed, C=WhatsApp/casual)
        - q4_price: Price vs quality priority? (A=Speed of delivery, B=Detailed specs, C=Referrals, D=Warranty terms)
        
        Args:
            answers: Dict mapping question IDs to answers (A, B, C, D)
            
        Returns:
            Profile type: velocity, analyst, social, or security
        """
        scores = {"velocity": 0, "analyst": 0, "social": 0, "security": 0}
        
        # Question-to-profile mappings
        mappings = {
            "q1_speed": {"A": "velocity", "B": "analyst", "C": "social", "D": "security"},
            "q2_risk": {"A": "velocity", "B": "security", "C": "social", "D": "analyst"},
            "q3_communication": {"A": "velocity", "B": "analyst", "C": "social"},
            "q4_price": {"A": "velocity", "B": "analyst", "C": "social", "D": "security"}
        }
        
        # Score each answer
        for question, answer in answers.items():
            if question in mappings and answer in mappings[question]:
                profile = mappings[question][answer]
                scores[profile] += 1
                logger.debug(f"Question {question} answer {answer} -> {profile} (+1)")
        
        # Find highest score
        max_score = max(scores.values())
        candidates = [k for k, v in scores.items() if v == max_score]
        
        logger.info(f"Profile scores: {scores}, candidates: {candidates}")
        
        # Tie-breaking logic: analyst > security > velocity > social
        if len(candidates) > 1:
            priority = ["analyst", "security", "velocity", "social"]
            for p in priority:
                if p in candidates:
                    logger.info(f"Tie-breaker selected: {p}")
                    return p
        
        winner = max(scores, key=scores.get)
        logger.info(f"Determined profile type: {winner} (score: {max_score})")
        return winner
    
    def calculate_dimension_scores(
        self, 
        profile_type: ProfileType,
        custom_scores: Optional[Dict[str, int]] = None
    ) -> Dict[str, int]:
        """
        Calculate dimension scores (1-10) based on profile type.
        
        Args:
            profile_type: The determined profile type
            custom_scores: Optional override scores
            
        Returns:
            Dict with decision_speed, risk_tolerance, price_sensitivity
        """
        # Base scores per profile type
        base_scores = {
            "velocity": {
                "decision_speed": 9,
                "risk_tolerance": 7,
                "price_sensitivity": 4
            },
            "analyst": {
                "decision_speed": 4,
                "risk_tolerance": 5,
                "price_sensitivity": 6
            },
            "social": {
                "decision_speed": 6,
                "risk_tolerance": 5,
                "price_sensitivity": 7
            },
            "security": {
                "decision_speed": 3,
                "risk_tolerance": 2,
                "price_sensitivity": 8
            }
        }
        
        scores = base_scores.get(profile_type, base_scores["analyst"]).copy()
        
        # Apply custom overrides
        if custom_scores:
            for key in ["decision_speed", "risk_tolerance", "price_sensitivity"]:
                if key in custom_scores:
                    scores[key] = max(1, min(10, custom_scores[key]))
        
        return scores
    
    def predict_churn_risk(
        self,
        profile_type: ProfileType,
        recent_sentiment: Optional[Dict[str, Any]] = None,
        interaction_count: int = 0
    ) -> float:
        """
        Predict churn risk score (0.0 to 1.0) based on profile and sentiment.
        
        Args:
            profile_type: Psychological profile type
            recent_sentiment: Recent sentiment analysis result
            interaction_count: Number of interactions
            
        Returns:
            Churn risk score (0.0 = low risk, 1.0 = high risk)
        """
        base_risk = {
            "velocity": 0.3,    # Quick to decide, quick to leave
            "analyst": 0.2,     # Loyal if data supports
            "social": 0.25,     # Loyal if relationship good
            "security": 0.15    # Most loyal, hates change
        }.get(profile_type, 0.3)
        
        # Adjust based on sentiment
        if recent_sentiment:
            sentiment_score = recent_sentiment.get("sentiment_score", 0)
            negative_emotions = ["Anger", "Frustration", "Disappointment"]
            dominant = recent_sentiment.get("dominant_emotion", "Neutral")
            
            # Increase risk for negative sentiment
            if sentiment_score < -0.3:
                base_risk += 0.2
            if dominant in negative_emotions:
                base_risk += 0.15
            if recent_sentiment.get("requires_escalation"):
                base_risk += 0.1
        
        # Adjust based on interaction count
        if interaction_count < 2:
            base_risk += 0.1  # New leads more likely to churn
        elif interaction_count > 10:
            base_risk -= 0.1  # Engaged leads less likely to churn
        
        return min(1.0, max(0.0, base_risk))
    
    def create_profile_embedding(self, profile_data: Dict[str, Any]) -> np.ndarray:
        """
        Create vector embedding from profile dimensions.
        
        Creates a normalized vector representing the profile for similarity search.
        Dimensions: profile_type (one-hot), decision_speed, risk_tolerance, 
                   price_sensitivity, communication_pref (one-hot)
        
        Args:
            profile_data: Profile data dict
            
        Returns:
            1536-dimensional numpy array (padded)
        """
        # One-hot encode profile type (4 dimensions)
        profile_types = ["velocity", "analyst", "social", "security"]
        profile_type = profile_data.get("profile_type", "analyst")
        type_vector = [1.0 if t == profile_type else 0.0 for t in profile_types]
        
        # Normalize dimension scores to 0-1
        decision_speed = profile_data.get("decision_speed", 5) / 10.0
        risk_tolerance = profile_data.get("risk_tolerance", 5) / 10.0
        price_sensitivity = profile_data.get("price_sensitivity", 5) / 10.0
        
        # One-hot encode communication preference (4 dimensions)
        comm_prefs = ["phone", "email", "whatsapp", "sms"]
        comm_pref = profile_data.get("communication_pref", "email")
        comm_vector = [1.0 if c == comm_pref else 0.0 for c in comm_prefs]
        
        # Combine into feature vector
        feature_vector = (
            type_vector + 
            [decision_speed, risk_tolerance, price_sensitivity] + 
            comm_vector
        )
        
        # Pad to 1536 dimensions with zeros for future expansion
        target_dim = 1536
        if len(feature_vector) < target_dim:
            padding = [0.0] * (target_dim - len(feature_vector))
            feature_vector.extend(padding)
        
        return np.array(feature_vector[:target_dim], dtype=np.float32)
    
    def store_profile_vector(
        self, 
        lead_id: str, 
        profile_data: Dict[str, Any],
        outcome: Optional[str] = None
    ) -> None:
        """
        Store profile in ChromaDB for similarity search.
        
        Args:
            lead_id: Lead UUID
            profile_data: Profile data dict
            outcome: Optional conversion outcome for learning
        """
        embedding = self.create_profile_embedding(profile_data)
        
        metadata = {
            "profile_type": profile_data.get("profile_type", "analyst"),
            "decision_speed": profile_data.get("decision_speed", 5),
            "risk_tolerance": profile_data.get("risk_tolerance", 5),
            "price_sensitivity": profile_data.get("price_sensitivity", 5),
            "communication_pref": profile_data.get("communication_pref", "email"),
            "outcome": outcome or "unknown",
            "stored_at": datetime.utcnow().isoformat()
        }
        
        self.profiles_collection.upsert(
            ids=[str(lead_id)],
            embeddings=[embedding.tolist()],
            metadatas=[metadata]
        )
        
        logger.info(f"Stored profile vector for lead {lead_id}")
    
    def find_similar_profiles(
        self, 
        profile_data: Dict[str, Any], 
        n_results: int = 5,
        min_similarity: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Find similar profiles based on vector similarity.
        
        Args:
            profile_data: Profile to compare against
            n_results: Number of similar profiles to return
            min_similarity: Minimum similarity threshold (cosine)
            
        Returns:
            List of similar profiles with metadata
        """
        embedding = self.create_profile_embedding(profile_data)
        
        results = self.profiles_collection.query(
            query_embeddings=[embedding.tolist()],
            n_results=n_results,
            include=["metadatas", "distances"]
        )
        
        similar_profiles = []
        if results and results["ids"]:
            for i, profile_id in enumerate(results["ids"][0]):
                distance = results["distances"][0][i]
                # Convert cosine distance to similarity (1 - distance)
                similarity = 1 - distance
                
                if similarity >= min_similarity:
                    similar_profiles.append({
                        "lead_id": profile_id,
                        "similarity": round(similarity, 3),
                        "metadata": results["metadatas"][0][i]
                    })
        
        return sorted(similar_profiles, key=lambda x: x["similarity"], reverse=True)
    
    def store_interaction_vector(
        self,
        interaction_id: str,
        lead_id: str,
        agent_name: str,
        interaction_text: str,
        outcome: Optional[str] = None
    ) -> None:
        """
        Store interaction in vector DB for memory and pattern learning.
        
        Args:
            interaction_id: Unique interaction ID
            lead_id: Lead UUID
            agent_name: Name of agent handling interaction
            interaction_text: Text representation of interaction
            outcome: Optional outcome (converted, rejected, etc.)
        """
        # Create simple embedding from text (in production, use sentence-transformers)
        # Here we use a hash-based embedding as placeholder
        words = interaction_text.lower().split()
        word_hash = sum(hash(w) % 1000 for w in words[:50]) / 50000
        embedding = np.array([word_hash] * 1536, dtype=np.float32)
        
        metadata = {
            "lead_id": lead_id,
            "agent_name": agent_name,
            "outcome": outcome or "unknown",
            "word_count": len(words),
            "stored_at": datetime.utcnow().isoformat()
        }
        
        self.interactions_collection.add(
            ids=[interaction_id],
            embeddings=[embedding.tolist()],
            metadatas=[metadata]
        )
        
        logger.info(f"Stored interaction vector {interaction_id}")
    
    async def create_or_update_profile(
        self,
        db: AsyncSession,
        lead_id: str,
        profile_type: ProfileType,
        dimensions: ProfileDimensions,
        churn_risk: Optional[float] = None
    ) -> PsychologicalProfile:
        """
        Create or update psychological profile in database and vector store.
        
        Args:
            db: Database session
            lead_id: Lead UUID
            profile_type: Determined profile type
            dimensions: Profile dimension scores
            churn_risk: Optional pre-calculated churn risk
            
        Returns:
            Created/updated PsychologicalProfile
        """
        # Calculate churn risk if not provided
        if churn_risk is None:
            churn_risk = self.predict_churn_risk(profile_type)
        
        # Prepare profile data
        profile_data = {
            "lead_id": lead_id,
            "profile_type": profile_type,
            "decision_speed": dimensions.decision_speed,
            "risk_tolerance": dimensions.risk_tolerance,
            "price_sensitivity": dimensions.price_sensitivity,
            "communication_pref": dimensions.communication_pref,
            "pain_points": dimensions.pain_points,
            "core_values": dimensions.core_values,
            "churn_risk_score": churn_risk
        }
        
        # Check if profile exists
        result = await db.execute(
            select(PsychologicalProfile).where(PsychologicalProfile.lead_id == lead_id)
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            # Update existing
            for key, value in profile_data.items():
                if hasattr(existing, key):
                    setattr(existing, key, value)
            existing.updated_at = datetime.utcnow()
            await db.commit()
            await db.refresh(existing)
            profile = existing
            logger.info(f"Updated profile for lead {lead_id}")
        else:
            # Create new
            profile = PsychologicalProfile(**profile_data)
            db.add(profile)
            await db.commit()
            await db.refresh(profile)
            logger.info(f"Created new profile for lead {lead_id}")
        
        # Store in vector DB
        self.store_profile_vector(lead_id, profile_data)
        
        return profile
    
    def get_profile_strategy_recommendations(self, profile_type: ProfileType) -> Dict[str, Any]:
        """
        Get persuasion strategy recommendations for a profile type.
        
        Args:
            profile_type: Profile type
            
        Returns:
            Strategy recommendations
        """
        profile_def = self.PROFILE_DEFINITIONS.get(profile_type, self.PROFILE_DEFINITIONS["analyst"])
        
        return {
            "profile_type": profile_type,
            "profile_name": profile_def["name"],
            "characteristics": profile_def["characteristics"],
            "optimal_approach": profile_def["optimal_approach"],
            "key_triggers": profile_def["key_triggers"],
            "avoid": profile_def["avoid"],
            "recommended_pace": "fast" if profile_type == "velocity" else "measured",
            "follow_up_frequency": "high" if profile_type == "velocity" else "moderate"
        }


class SimpleEmbeddingFunction(EmbeddingFunction):
    """Simple embedding function for ChromaDB (placeholder for sentence-transformers)."""
    
    def __call__(self, texts: Documents) -> Embeddings:
        """Generate simple embeddings (in production, use proper model)."""
        embeddings = []
        for text in texts:
            # Simple hash-based embedding as placeholder
            words = text.lower().split()[:100]
            vec = [hash(w) % 1000 / 1000 for w in words]
            # Pad to 1536
            if len(vec) < 1536:
                vec.extend([0.0] * (1536 - len(vec)))
            embeddings.append(vec[:1536])
        return embeddings


# Singleton instance
_profiling_service: Optional[PsychologicalProfileService] = None


def get_profiling_service() -> PsychologicalProfileService:
    """Get or create singleton ProfilingService instance."""
    global _profiling_service
    if _profiling_service is None:
        _profiling_service = PsychologicalProfileService()
    return _profiling_service
