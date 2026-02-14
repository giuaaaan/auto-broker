"""
AUTO-BROKER 3.0 - Persuasive Engine
Milton Model linguistic patterns for adaptive selling
Architecture: Neuro-Linguistic Programming + Meta AI Agents 2025
"""

import json
import logging
import random
from typing import Dict, List, Literal, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

ProfileType = Literal['velocity', 'analyst', 'social', 'security']


@dataclass
class ScriptTemplate:
    """Template for persuasive script generation."""
    name: str
    profile_type: ProfileType
    template: str
    milton_patterns: List[str]
    required_vars: List[str]
    success_rate: float


class PersuasiveEngine:
    """
    Engine for generating adaptive persuasive scripts using Milton Model patterns.
    
    Features:
    - Profile-based script adaptation
    - Milton Model linguistic patterns
    - Objection handling
    - A/B testing support
    """
    
    # Profile-specific communication styles
    PROFILE_STYLES = {
        "velocity": {
            "pace": "fast",
            "focus": "time_saved",
            "tone": "direct",
            "triggers": ["immediatamente", "ora", "subito", "veloce", "rapido", "in 24 ore"],
            "template": "{benefit} subito, senza attese. {action} in 2 minuti. {urgency}",
            "opening": "Vado dritto al punto:",
            "closing": "Decidiamo ora?",
            "objection_handlers": {
                "too_expensive": "Con questo volume, il ROI è in 3 settimane. Firmiamo subito?",
                "need_to_think": "Capisco, ma le migliori opportunità vanno prese subito. Possiamo chiudere ora?",
                "competitor": "La velocità fa la differenza. Partiamo oggi e siamo operativi domani.",
                "timing": "Il momento migliore è ora. Ogni giorno di ritardo costa {daily_cost}€."
            }
        },
        "analyst": {
            "pace": "measured",
            "focus": "data_proof",
            "tone": "professional",
            "triggers": ["statistiche", "dati", "confronto", "analisi", "ROI", "efficienza", "report"],
            "template": "I dati mostrano che il 98% dei clienti {benefit}. Ecco il confronto: {data}",
            "opening": "Le presento l'analisi:",
            "closing": "Ha tutti i dati per decidere. Ha domande?",
            "objection_handlers": {
                "too_expensive": "Ecco il confronto costi-benefici dettagliato. Il break-even è a {break_even} giorni.",
                "need_to_think": "Prenda il tempo necessario. Intanto le invio l'analisi comparativa e i case study.",
                "competitor": "Ecco il confronto oggettivo. I nostri numeri parlano chiaro: {comparison_data}",
                "timing": "Analizziamo il momento ottimale insieme. Ecco i dati stagionali: {seasonal_data}"
            }
        },
        "social": {
            "pace": "warm",
            "focus": "relationship",
            "tone": "friendly",
            "triggers": ["fiducia", "collaborazione", "clienti", "insieme", "partnership", "soddisfatti"],
            "template": "I nostri clienti ci scelgono perché {benefit}. Come {reference}, anche lei...",
            "opening": "Grazie per il tempo che ci dedica:",
            "closing": "Siamo qui per accompagnarla. Iniziamo insieme?",
            "objection_handlers": {
                "too_expensive": "I nostri clienti {reference} hanno avuto lo stesso dubbio. Oggi sono soddisfatti. Possiamo farlo anche per lei.",
                "need_to_think": "Certo, rifletta. Nel frattempo, posso metterla in contatto con {reference} per un parere?",
                "competitor": "Capisco abbia altre opzioni. I nostri clienti sono passati a noi per {differentiator}.",
                "timing": "Molti clienti hanno iniziato proprio in questo periodo. {reference} ha visto risultati immediati."
            }
        },
        "security": {
            "pace": "reassuring",
            "focus": "safety_guarantee",
            "tone": "confident",
            "triggers": ["garantito", "sicuro", "proteggere", "tranquillità", "assicurato", "certezza"],
            "template": "La sua {asset} sarà protetta. Garantiamo {guarantee} per la sua tranquillità.",
            "opening": "La sua tranquillità è la nostra priorità:",
            "closing": "Con queste garanzie, può procedere in sicurezza?",
            "objection_handlers": {
                "too_expensive": "La tranquillità non ha prezzo. Con {guarantee}, il suo investimento è protetto.",
                "need_to_think": "Decida con calma. Offriamo {trial_period} giorni di prova con garanzia soddisfatti o rimborsati.",
                "competitor": "Capisco la cautela. Ecco le nostre certificazioni e garanzie che {competitor} non offre.",
                "timing": "La sicurezza non aspetta. Ogni giorno di ritardo espone a rischi. Proteggiamola ora."
            }
        }
    }
    
    # Milton Model linguistic patterns
    MILTON_PATTERNS = {
        "embedded_command": {
            "description": "Hide commands within seemingly innocent statements",
            "examples": [
                "Può {action} quando è pronto",
                "Immagini di {benefit} già da domani",
                "Si chieda quanto {benefit} potrà ottenere"
            ],
            "markers": ["può", "immagini", "si chieda", "consideri"]
        },
        "presupposition": {
            "description": "Assume the outcome is already decided",
            "examples": [
                "Quando sarà operativo con noi...",
                "Dopo che avrà visto i risultati...",
                "Mentre lei godrà dei benefici..."
            ],
            "markers": ["quando", "dopo", "mentre", "prima di"]
        },
        "tag_question": {
            "description": "Add question at end to elicit agreement",
            "examples": [
                "Il risparmio è significativo, non trova?",
                "Ha senso procedere, vero?",
                "Le conviene, no?"
            ],
            "markers": ["non trova?", "vero?", "no?", "giusto?"]
        },
        "universal_quantifier": {
            "description": "Use all/none/every to create sense of inevitability",
            "examples": [
                "Tutti i nostri clienti hanno visto risultati",
                "Ogni azienda ha bisogno di questa soluzione",
                "Sempre più imprese scelgono noi"
            ],
            "markers": ["tutti", "ogni", "sempre", "mai", "nessuno"]
        },
        "nominalization": {
            "description": "Turn verbs into nouns to soften impact",
            "examples": [
                "La decisione è semplice",
                "Il successo arriva con la qualità",
                "La fiducia si costruisce nel tempo"
            ],
            "markers": ["zione", "mento", "ità", "anza"]
        },
        "lack_of_referential_index": {
            "description": "Vague references that allow personal interpretation",
            "examples": [
                "Certe persone hanno notato...",
                "Molti dicono che...",
                "Si sa che..."
            ],
            "markers": ["certe persone", "molti", "si sa", "si dice"]
        },
        "time_distortion": {
            "description": "Compress or expand time perception",
            "examples": [
                "Ricorda quando ha iniziato l'azienda? Quella stessa energia...",
                "Tra un anno si chiederà perché non ha iniziato prima",
                "In un attimo sarà operativo"
            ],
            "markers": ["quando", "tra", "prima", "dopo", "in un attimo"]
        }
    }
    
    def __init__(self):
        """Initialize PersuasiveEngine with strategy templates."""
        self.templates = self._load_templates()
        logger.info("PersuasiveEngine initialized")
    
    def _load_templates(self) -> List[ScriptTemplate]:
        """Load A/B tested script templates."""
        return [
            ScriptTemplate(
                name="fast_close_velocity",
                profile_type="velocity",
                template="{benefit} subito, senza attese. {action} in 2 minuti. Non perda tempo, {urgency}",
                milton_patterns=["embedded_command", "time_distortion"],
                required_vars=["benefit", "action", "urgency"],
                success_rate=0.78
            ),
            ScriptTemplate(
                name="data_driven_analyst",
                profile_type="analyst",
                template="I dati mostrano che il 98% dei clienti simili al suo profilo ha {benefit}. Ecco il confronto: {data}. Ha senso, {tag_question}",
                milton_patterns=["universal_quantifier", "tag_question"],
                required_vars=["benefit", "data", "tag_question"],
                success_rate=0.82
            ),
            ScriptTemplate(
                name="social_proof_warm",
                profile_type="social",
                template="Come {reference}, anche lei può {benefit}. I nostri clienti ci scelgono perché {differentiator}. Iniziamo insieme?",
                milton_patterns=["embedded_command", "presupposition"],
                required_vars=["reference", "benefit", "differentiator"],
                success_rate=0.75
            ),
            ScriptTemplate(
                name="security_guarantee",
                profile_type="security",
                template="La sua {asset} sarà protetta. Garantiamo {guarantee} per la sua tranquillità. Può fidarsi, {tag_question}",
                milton_patterns=["nominalization", "tag_question"],
                required_vars=["asset", "guarantee", "tag_question"],
                success_rate=0.71
            )
        ]
    
    def generate_adaptive_script(
        self,
        profile_type: ProfileType,
        context: Dict[str, Any],
        include_milton: bool = True,
        objection: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Generate adaptive sales script based on psychological profile.
        
        Args:
            profile_type: Psychological profile type
            context: Context variables (benefit, price, timeframe, etc.)
            include_milton: Whether to apply Milton Model patterns
            objection: Optional objection to handle
            
        Returns:
            Dict with script sections
        """
        style = self.PROFILE_STYLES.get(profile_type, self.PROFILE_STYLES["analyst"])
        
        # Generate base script
        script = self._build_script_sections(style, context, objection)
        
        # Apply Milton Model patterns if enabled
        if include_milton:
            script["opening"] = self._apply_milton_patterns(script["opening"], profile_type)
            script["body"] = self._apply_milton_patterns(script["body"], profile_type)
            script["closing"] = self._apply_milton_patterns(script["closing"], profile_type)
        
        # Add metadata
        script["profile_type"] = profile_type
        script["pace"] = style["pace"]
        script["tone"] = style["tone"]
        script["focus"] = style["focus"]
        script["patterns_used"] = style["triggers"][:3]
        
        return script
    
    def _build_script_sections(
        self,
        style: Dict[str, Any],
        context: Dict[str, Any],
        objection: Optional[str] = None
    ) -> Dict[str, str]:
        """Build script sections based on style and context."""
        
        # Opening
        opening = f"{style['opening']} {context.get('benefit_statement', '')}"
        
        # Body - main value proposition
        if objection and objection in style["objection_handlers"]:
            body_template = style["objection_handlers"][objection]
            body = body_template.format(
                break_even=context.get("break_even_days", "30"),
                daily_cost=context.get("daily_cost", "100"),
                comparison_data=context.get("comparison_data", "i nostri dati sono superiori"),
                reference=context.get("reference_customer", "i nostri clienti"),
                differentiator=context.get("differentiator", "la nostra qualità"),
                seasonal_data=context.get("seasonal_data", "ottimo momento"),
                guarantee=context.get("guarantee", "soddisfatto o rimborsato"),
                trial_period=context.get("trial_period", "14")
            )
        else:
            body_template = style["template"]
            body = body_template.format(
                benefit=context.get("benefit", "migliorare i risultati"),
                action=context.get("action", "iniziare"),
                urgency=context.get("urgency", "le poste si riempiono"),
                data=context.get("data", "riduzione del 23% dei costi"),
                reference=context.get("reference", "altre aziende del suo settore"),
                asset=context.get("asset", "mercè"),
                guarantee=context.get("guarantee", "consegna puntuale")
            )
        
        # Closing
        closing = style["closing"]
        
        # Add objection prevention
        prevention = self._generate_objection_prevention(style["focus"])
        
        return {
            "opening": opening,
            "body": body,
            "prevention": prevention,
            "closing": closing,
            "full_script": f"{opening}\n\n{body}\n\n{prevention}\n\n{closing}"
        }
    
    def _apply_milton_patterns(self, text: str, profile_type: ProfileType) -> str:
        """Apply Milton Model linguistic patterns to text."""
        
        # Select patterns based on profile
        if profile_type == "velocity":
            patterns = ["embedded_command", "time_distortion"]
        elif profile_type == "analyst":
            patterns = ["universal_quantifier", "lack_of_referential_index"]
        elif profile_type == "social":
            patterns = ["presupposition", "lack_of_referential_index"]
        else:  # security
            patterns = ["nominalization", "universal_quantifier"]
        
        # Apply transformations
        result = text
        
        # Embedded commands
        if "embedded_command" in patterns:
            transformations = [
                ("può vedere", "veda"),
                ("può considerare", "consideri"),
                ("può iniziare", "inizi ora"),
            ]
            for old, new in transformations:
                result = result.replace(old, new)
        
        # Presuppositions
        if "presupposition" in patterns and "quando" not in result.lower():
            result = f"Quando sarà pronto, {result.lower()}"
        
        # Tag questions
        if "tag_question" in patterns and not any(marker in result for marker in ["vero?", "giusto?", "no?"]):
            if profile_type == "analyst":
                result += ", corretto?"
            elif profile_type == "social":
                result += ", non trova?"
            else:
                result += ", vero?"
        
        return result
    
    def _generate_objection_prevention(self, focus: str) -> str:
        """Generate objection prevention statement."""
        preventions = {
            "time_saved": "So che il tempo è prezioso. Ecco perché abbiamo semplificato ogni passaggio.",
            "data_proof": "Ho tutti i dati per rispondere ad ogni sua domanda. Mi chieda pure.",
            "relationship": "La sua fiducia è importante. Prendiamo tutto il tempo necessario.",
            "safety_guarantee": "Ogni dubbio è legittimo. Ecco le garanzie che offriamo."
        }
        return preventions.get(focus, "")
    
    def handle_objection(
        self,
        objection: str,
        profile_type: ProfileType,
        context: Dict[str, Any]
    ) -> str:
        """
        Generate objection handling response.
        
        Args:
            objection: Objection type or text
            profile_type: Psychological profile
            context: Context variables
            
        Returns:
            Objection handling response
        """
        style = self.PROFILE_STYLES.get(profile_type, self.PROFILE_STYLES["analyst"])
        
        # Map objection to handler
        objection_key = self._classify_objection(objection)
        
        if objection_key in style["objection_handlers"]:
            handler_template = style["objection_handlers"][objection_key]
            response = handler_template.format(
                break_even=context.get("break_even_days", "30"),
                daily_cost=context.get("daily_cost", "100"),
                comparison_data=context.get("comparison_data", "i nostri dati sono superiori"),
                reference=context.get("reference_customer", "i nostri clienti"),
                differentiator=context.get("differentiator", "la nostra qualità"),
                guarantee=context.get("guarantee", "soddisfatto o rimborsato"),
                trial_period=context.get("trial_period", "14")
            )
        else:
            # Generic acknowledgment
            response = f"Capisco la sua preoccupazione. {context.get('benefit', 'Vediamo insieme come possiamo risolverla')}."
        
        # Apply Milton patterns
        response = self._apply_milton_patterns(response, profile_type)
        
        return response
    
    def _classify_objection(self, objection: str) -> str:
        """Classify objection text to known type."""
        objection_lower = objection.lower()
        
        if any(word in objection_lower for word in ["caro", "costoso", "prezzo", "troppo", "euro"]):
            return "too_expensive"
        elif any(word in objection_lower for word in ["pensare", "riflettere", "tempo", "decidere"]):
            return "need_to_think"
        elif any(word in objection_lower for word in ["concorrente", "altri", "preventivo", "offerta"]):
            return "competitor"
        elif any(word in objection_lower for word in ["momento", "tempismo", "adesso", "troppo presto"]):
            return "timing"
        else:
            return "generic"
    
    def get_next_best_action(
        self,
        profile_type: ProfileType,
        interaction_history: List[Dict[str, Any]],
        current_stage: str
    ) -> Dict[str, Any]:
        """
        Determine next best action based on profile and history.
        
        Args:
            profile_type: Psychological profile
            interaction_history: Previous interactions
            current_stage: Current sales stage
            
        Returns:
            Recommended next action
        """
        style = self.PROFILE_STYLES.get(profile_type, self.PROFILE_STYLES["analyst"])
        
        # Analyze interaction count
        interaction_count = len(interaction_history)
        
        # Determine urgency based on profile and stage
        if profile_type == "velocity":
            urgency = "high"
            follow_up_hours = 2
        elif profile_type == "security":
            urgency = "low"
            follow_up_hours = 48
        else:
            urgency = "medium"
            follow_up_hours = 24
        
        # Generate action recommendations
        if current_stage == "initial_contact":
            if profile_type == "velocity":
                action = "Schedule immediate call within 2 hours"
            elif profile_type == "analyst":
                action = "Send detailed proposal with data sheets"
            elif profile_type == "social":
                action = "Request reference call with existing client"
            else:
                action = "Provide guarantees and certifications"
        
        elif current_stage == "proposal_sent":
            if profile_type == "velocity":
                action = "Follow up with urgency: 'Limited spots available'"
            elif profile_type == "analyst":
                action = "Offer data review session"
            elif profile_type == "social":
                action = "Share testimonial video from similar client"
            else:
                action = "Extend guarantee terms"
        
        elif current_stage == "objection_raised":
            action = f"Apply {profile_type}-specific objection handler"
        
        else:
            action = "Standard follow-up"
        
        return {
            "action": action,
            "urgency": urgency,
            "follow_up_hours": follow_up_hours,
            "recommended_channel": style["triggers"][0] if style["triggers"] else "email",
            "message_tone": style["tone"],
            "key_phrases": style["triggers"][:3]
        }
    
    def analyze_script_effectiveness(
        self,
        script_text: str,
        profile_type: ProfileType
    ) -> Dict[str, Any]:
        """
        Analyze script for effectiveness markers.
        
        Args:
            script_text: Script text to analyze
            profile_type: Target profile type
            
        Returns:
            Effectiveness analysis
        """
        style = self.PROFILE_STYLES.get(profile_type, self.PROFILE_STYLES["analyst"])
        
        # Check for profile-specific triggers
        trigger_count = sum(1 for trigger in style["triggers"] if trigger.lower() in script_text.lower())
        
        # Check for Milton patterns
        pattern_count = 0
        patterns_found = []
        for pattern_name, pattern_data in self.MILTON_PATTERNS.items():
            for marker in pattern_data["markers"]:
                if marker.lower() in script_text.lower():
                    pattern_count += 1
                    patterns_found.append(pattern_name)
                    break
        
        # Calculate effectiveness score
        base_score = 0.5
        trigger_bonus = min(0.3, trigger_count * 0.1)
        pattern_bonus = min(0.2, pattern_count * 0.05)
        
        effectiveness_score = base_score + trigger_bonus + pattern_bonus
        
        # Recommendations
        recommendations = []
        if trigger_count < 2:
            recommendations.append(f"Add more {profile_type}-specific triggers: {style['triggers'][:2]}")
        if pattern_count < 2:
            recommendations.append("Include Milton Model patterns for better persuasion")
        
        return {
            "effectiveness_score": round(effectiveness_score, 2),
            "trigger_count": trigger_count,
            "pattern_count": pattern_count,
            "patterns_found": list(set(patterns_found)),
            "recommendations": recommendations,
            "estimated_success_rate": min(0.95, effectiveness_score)
        }


# Singleton instance
_persuasive_engine: Optional[PersuasiveEngine] = None


def get_persuasive_engine() -> PersuasiveEngine:
    """Get or create singleton PersuasiveEngine instance."""
    global _persuasive_engine
    if _persuasive_engine is None:
        _persuasive_engine = PersuasiveEngine()
    return _persuasive_engine
