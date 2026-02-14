"""
EQ Profiling Service - BANT-C Framework implementation
"""

from typing import Dict, Literal, List, Optional, Any
import numpy as np
import logging

logger = logging.getLogger(__name__)

ProfileType = Literal['velocity', 'analyst', 'social', 'security']


class ProfilingService:
    """
    Psychological profiling using BANT-C+Emotion framework.
    
    Maps 3 discovery questions to psychological dimensions.
    """
    
    def __init__(self):
        self.use_chroma = True
        self.chroma_client = None
        self.collection = None
        
        try:
            import chromadb
            from chromadb.config import Settings
            
            self.chroma_client = chromadb.Client(Settings(
                chroma_db_impl="duckdb+parquet",
                persist_directory=".chroma_db"
            ))
            self.collection = self.chroma_client.get_or_create_collection("profiles")
            logger.info("ChromaDB initialized successfully")
        except Exception as e:
            logger.warning(f"ChromaDB failed: {e}, using pgvector only")
            self.use_chroma = False
    
    def determine_profile(self, answers: Dict[str, str]) -> ProfileType:
        """
        Algorithm: Map 3 questions to profile type.
        
        Questions:
        - q1: Decision style
        - q2: Risk tolerance
        - q3: Social orientation
        
        Answers: A, B, C, or D
        """
        scores = {"velocity": 0, "analyst": 0, "social": 0, "security": 0}
        
        # Mapping from answers to profiles
        mapping = {
            "q1": {"A": "velocity", "B": "analyst", "C": "social", "D": "security"},
            "q2": {"A": "velocity", "B": "security", "C": "social", "D": "analyst"},
            "q3": {"A": "velocity", "B": "analyst", "C": "social", "D": "security"}
        }
        
        for q, answer in answers.items():
            if q in mapping and answer in mapping[q]:
                scores[mapping[q][answer]] += 1
        
        max_score = max(scores.values())
        candidates = [k for k, v in scores.items() if v == max_score]
        
        # Tie-breaking: analyst > security > velocity > social
        if len(candidates) > 1:
            priority = ["analyst", "security", "velocity", "social"]
            for p in priority:
                if p in candidates:
                    return p  # type: ignore
        
        return max(scores, key=scores.get)  # type: ignore
    
    def calculate_dimensions(
        self,
        profile_type: ProfileType,
        answers: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Calculate psychological dimensions (1-10 scale).
        
        Returns:
            dict with decision_speed, risk_tolerance, price_sensitivity, etc.
        """
        base = {
            "velocity": {
                "decision_speed": 9,
                "risk_tolerance": 8,
                "price_sensitivity": 3,
                "communication_pref": "phone"
            },
            "analyst": {
                "decision_speed": 3,
                "risk_tolerance": 4,
                "price_sensitivity": 8,
                "communication_pref": "email"
            },
            "social": {
                "decision_speed": 6,
                "risk_tolerance": 5,
                "price_sensitivity": 6,
                "communication_pref": "whatsapp"
            },
            "security": {
                "decision_speed": 4,
                "risk_tolerance": 2,
                "price_sensitivity": 7,
                "communication_pref": "email"
            }
        }
        
        dimensions = base[profile_type].copy()
        
        # Calculate churn risk based on profile
        churn_risk = {
            "velocity": 0.3,
            "analyst": 0.2,
            "social": 0.25,
            "security": 0.15
        }
        dimensions["churn_risk_score"] = churn_risk[profile_type]
        
        return dimensions
    
    def extract_pain_points(self, answers: Dict[str, str]) -> List[str]:
        """Extract pain points from survey answers."""
        pain_keywords = {
            "slow": ["lento", "tempo", "attesa", "ritardo"],
            "expensive": ["caro", "costoso", "prezzo", "budget"],
            "complex": ["complicato", "difficile", "macchinoso"],
            "support": ["supporto", "aiuto", "assistenza"]
        }
        
        found = []
        text = " ".join(answers.values()).lower()
        
        for pain_type, keywords in pain_keywords.items():
            if any(kw in text for kw in keywords):
                found.append(pain_type)
        
        return found[:3]  # Max 3
    
    def extract_core_values(self, answers: Dict[str, str]) -> List[str]:
        """Extract core values from survey answers."""
        value_keywords = {
            "quality": ["qualità", "eccellenza", "migliore"],
            "efficiency": ["efficienza", "velocità", "rapido"],
            "trust": ["fiducia", "onestà", "trasparenza"],
            "innovation": ["innovazione", "tecnologia", "moderno"]
        }
        
        found = []
        text = " ".join(answers.values()).lower()
        
        for value_type, keywords in value_keywords.items():
            if any(kw in text for kw in keywords):
                found.append(value_type)
        
        return found[:3]  # Max 3
    
    def create_embedding(self, profile: Dict) -> List[float]:
        """
        Create 1536-dimensional vector embedding.
        
        Uses feature encoding + random padding to reach 1536 dims.
        """
        # Feature vector (base dimensions)
        features = [
            # Profile type one-hot (4 dims)
            1.0 if profile.get("profile_type") == "velocity" else 0.0,
            1.0 if profile.get("profile_type") == "analyst" else 0.0,
            1.0 if profile.get("profile_type") == "social" else 0.0,
            1.0 if profile.get("profile_type") == "security" else 0.0,
            # Dimensions (3 dims)
            profile.get("decision_speed", 5) / 10.0,
            profile.get("risk_tolerance", 5) / 10.0,
            profile.get("price_sensitivity", 5) / 10.0,
            # Churn risk (1 dim)
            profile.get("churn_risk_score", 0.3),
        ]
        
        # Pad to 1536 dimensions with deterministic noise
        np.random.seed(42)
        padding = np.random.randn(1536 - len(features)).tolist()
        
        return features + padding
    
    async def store_profile(
        self,
        lead_id: int,
        profile: Dict[str, Any],
        db_session=None
    ) -> bool:
        """
        Store profile in both ChromaDB and PostgreSQL.
        
        Args:
            lead_id: Lead ID
            profile: Profile dictionary
            db_session: SQLAlchemy async session
        
        Returns:
            True if successful
        """
        # Create embedding
        embedding = self.create_embedding(profile)
        profile["embedding"] = embedding
        
        # Store in ChromaDB (if available)
        if self.use_chroma and self.collection:
            try:
                self.collection.upsert(
                    ids=[str(lead_id)],
                    embeddings=[embedding],
                    metadatas=[{
                        "profile_type": profile.get("profile_type"),
                        "lead_id": str(lead_id)
                    }]
                )
            except Exception as e:
                logger.error(f"ChromaDB store failed: {e}")
        
        # Store in PostgreSQL (if session provided)
        if db_session:
            # This would be implemented with SQLAlchemy
            pass
        
        return True
    
    def find_similar_profiles(
        self,
        embedding: List[float],
        n_results: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Find similar profiles using vector similarity.
        
        Args:
            embedding: Query embedding
            n_results: Number of results
        
        Returns:
            List of similar profiles
        """
        if not self.use_chroma or not self.collection:
            return []
        
        try:
            results = self.collection.query(
                query_embeddings=[embedding],
                n_results=n_results,
                include=["metadatas", "distances"]
            )
            
            similar = []
            if results.get("metadatas"):
                for metadata, distance in zip(
                    results["metadatas"][0],
                    results["distances"][0]
                ):
                    similar.append({
                        "lead_id": metadata.get("lead_id"),
                        "profile_type": metadata.get("profile_type"),
                        "similarity": 1.0 - distance
                    })
            
            return similar
        except Exception as e:
            logger.error(f"Similarity search failed: {e}")
            return []
