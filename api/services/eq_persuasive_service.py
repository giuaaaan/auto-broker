"""
EQ Persuasive Engine - Milton Model implementation
"""

from typing import Dict, Literal, Optional, Any, List
import re
import random

ProfileType = Literal['velocity', 'analyst', 'social', 'security']


class PersuasiveEngine:
    """
    Adaptive persuasion using Milton Model patterns.
    
    The Milton Model uses vague, metaphorical language to bypass
    conscious resistance and speak to the unconscious mind.
    """
    
    # Profile-specific configurations
    CONFIG = {
        "velocity": {
            "triggers": ["subito", "immediatamente", "veloce", "ora", "rapido"],
            "pace": "fast",
            "sentence_length": "short",
            "focus": "action",
            "urgency_phrases": [
                "Lo facciamo subito",
                "Risultati immediati",
                "Zero tempo perso",
                "Oggi stesso"
            ]
        },
        "analyst": {
            "triggers": ["dati", "analisi", "confronto", "numeri", "statistiche"],
            "pace": "slow",
            "sentence_length": "medium",
            "focus": "data",
            "proof_phrases": [
                "I dati mostrano",
                "Come dimostrato da",
                "L'analisi conferma",
                "Secondo le ricerche"
            ]
        },
        "social": {
            "triggers": ["fiducia", "insieme", "clienti", "rapporto", "parlato"],
            "pace": "warm",
            "sentence_length": "conversational",
            "focus": "relationship",
            "social_phrases": [
                "I nostri clienti",
                "Insieme possiamo",
                "Come lei",
                "La community"
            ]
        },
        "security": {
            "triggers": ["garantito", "sicuro", "proteggere", "tutelare", "coperto"],
            "pace": "calm",
            "sentence_length": "detailed",
            "focus": "safety",
            "safety_phrases": [
                "È tutto garantito",
                "Zero rischi",
                "Protezione completa",
                "Sicurezza totale"
            ]
        }
    }
    
    # Milton Model linguistic patterns
    # Format: (regex_pattern, replacement)
    PATTERNS = [
        # Embedded commands - hide commands in larger sentences
        (r"\bconsegneremo\b", "immagini la soddisfazione di vedere arrivare"),
        (r"\bcosta\b", "investire solo"),
        (r"\bse firma\b", "quando sarà pronto per sentirsi"),
        (r"\bdevi decidere\b", "puoi iniziare a sentirti pronto per"),
        (r"\bcomprare\b", "prendere la decisione giusta di avere"),
        # Presuppositions - assume the outcome
        (r"\bquando\b", "quando (e non se)"),
        # Modal operators - possibility and necessity
        (r"\bpuoi\b", "puoi naturalmente"),
        (r"\bdevi\b", "è importante che"),
        # Universal quantifiers - generalizations
        (r"\btutti\b", "tutti sanno che"),
        (r"\bogni\b", "ogni persona intelligente sa"),
    ]
    
    # Objection handlers by profile type
    OBJECTION_HANDLERS = {
        "costo": {
            "velocity": {
                "reframe": "Non un costo, ma un investimento che si ripaga in {roi_time}.",
                "technique": "time_value"
            },
            "analyst": {
                "reframe": "Ecco l'analisi: costo {cost}, beneficio {benefit}, ROI {roi}%.",
                "technique": "roi_calculation"
            },
            "social": {
                "reframe": "I nostri clienti scoprono che il vero costo è non averlo.",
                "technique": "social_proof"
            },
            "security": {
                "reframe": "Capisco la sua cautela. Ecco la garanzia: {guarantee}.",
                "technique": "guarantee"
            }
        },
        "tempo": {
            "velocity": {
                "reframe": "Proprio perché non ha tempo, questa soluzione le fa risparmiare ore.",
                "technique": "efficiency"
            },
            "analyst": {
                "reframe": "Analizziamo: ora spende X ore, con noi Y. Risparmio: Z%.",
                "technique": "time_analysis"
            },
            "social": {
                "reframe": "Più tempo per ciò che conta. I clienti ne parlano.",
                "technique": "lifestyle"
            },
            "security": {
                "reframe": "Il tempo è sicurezza. Implementazione in {timeframe}.",
                "technique": "timeline_guarantee"
            }
        },
        "fiducia": {
            "velocity": {
                "reframe": "Provi 30 giorni, senza impegno. Se non funziona, arrivederci.",
                "technique": "trial"
            },
            "analyst": {
                "reframe": "Ecco i dati: {n} clienti, {satisfaction}% soddisfazione.",
                "technique": "statistics"
            },
            "social": {
                "reframe": "Parli con {reference}, le dica che l'ho mandato io.",
                "technique": "reference_call"
            },
            "security": {
                "reframe": "Fiducia protetta da contratto: {guarantee_terms}.",
                "technique": "contract"
            }
        }
    }
    
    def adapt_script(
        self,
        text: str,
        profile: ProfileType,
        sentiment_score: float = 0.0,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Adapt script using Milton Model patterns.
        
        Args:
            text: Base script text
            profile: Target psychological profile
            sentiment_score: Current sentiment (-1 to 1)
            context: Additional context variables
        
        Returns:
            Adapted script
        """
        context = context or {}
        adapted = text
        
        # 1. Apply Milton Model linguistic patterns
        for pattern, replacement in self.PATTERNS:
            adapted = re.sub(pattern, replacement, adapted, flags=re.IGNORECASE)
        
        # 2. Add profile-specific phrases
        config = self.CONFIG.get(profile, {})
        if sentiment_score < -0.3:
            # Add reassurance for negative sentiment
            if profile == "security":
                adapted = f"Capisco la sua cautela. {adapted}"
            elif profile == "analyst":
                adapted = f"Prendo nota delle sue preoccupazioni. {adapted}"
            elif profile == "social":
                adapted = f"Capisco come si sente. {adapted}"
            else:  # velocity
                adapted = f"Risolviamo subito. {adapted}"
        
        # 3. Add profile-specific power phrases
        if random.random() > 0.5:  # 50% chance
            phrases = config.get("urgency_phrases", []) if profile == "velocity" else \
                     config.get("proof_phrases", []) if profile == "analyst" else \
                     config.get("social_phrases", []) if profile == "social" else \
                     config.get("safety_phrases", [])
            if phrases:
                phrase = random.choice(phrases)
                adapted = f"{adapted} {phrase}."
        
        # 4. Personalize with context
        for key, value in context.items():
            adapted = adapted.replace(f"{{{key}}}", str(value))
        
        return adapted.strip()
    
    def handle_objection(
        self,
        objection: str,
        profile: ProfileType,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, str]:
        """
        Generate profile-specific objection handler.
        
        Args:
            objection: Objection text (e.g., "costo", "tempo", "fiducia")
            profile: Psychological profile
            context: Context variables for template
        
        Returns:
            Dict with response and technique
        """
        context = context or {}
        
        # Normalize objection type
        objection_type = self._classify_objection(objection)
        
        # Get handler
        handlers = self.OBJECTION_HANDLERS.get(objection_type, {})
        handler = handlers.get(profile, {
            "reframe": "Capisco la sua posizione. Possiamo trovare una soluzione.",
            "technique": "generic"
        })
        
        # Format response with context
        try:
            response = handler["reframe"].format(**context)
        except KeyError:
            response = handler["reframe"]
        
        return {
            "response": response,
            "technique": handler["technique"],
            "objection_type": objection_type
        }
    
    def _classify_objection(self, objection: str) -> str:
        """Classify objection type from text."""
        text = objection.lower()
        
        if any(word in text for word in ["costo", "prezzo", "caro", "soldi", "budget"]):
            return "costo"
        elif any(word in text for word in ["tempo", "tardi", "aspettare", "mese", "settimana"]):
            return "tempo"
        elif any(word in text for word in ["fiducia", "fido", "scettico", "sicuro", "garanzia"]):
            return "fiducia"
        elif any(word in text for word in ["bisogno", "serve", "necessario", "utile"]):
            return "bisogno"
        elif any(word in text for word in ["concorrenza", "altri", "competitor"]):
            return "concorrenza"
        else:
            return "other"
    
    def get_script_template(
        self,
        profile: ProfileType,
        stage: str = "opening"
    ) -> str:
        """
        Get base script template for profile and stage.
        
        Args:
            profile: Psychological profile
            stage: Interaction stage (opening, qualification, closing)
        
        Returns:
            Base script template
        """
        templates = {
            "velocity": {
                "opening": "{nome}, ho una soluzione che risolve {problem} in {timeframe}. Posso mostrarle subito?",
                "qualification": "Quanto tempo sta perdendo con {current_solution}? Immagini di risparmiare {time_saved} subito.",
                "proposal": "Ecco il piano: {solution} operativo in {setup_time}. Risultati da {day_one}.",
                "closing": "Procediamo ora? In 5 minuti è tutto attivo. Oggi, non domani."
            },
            "analyst": {
                "opening": "{nome}, ho analizzato la situazione di {azienda}. I dati mostrano {opportunity}.",
                "qualification": "Mi aiuti a capire: qual è il costo attuale di {problem} in termini di {metrics}?",
                "proposal": "Ecco l'analisi comparativa. Soluzione A: {option_a}. Soluzione B (nostra): {option_b}. Vantaggio netto: {advantage}.",
                "closing": "I numeri parlano chiaro: ROI del {roi}% nel primo anno. Posso preparare l'analisi dettagliata?"
            },
            "social": {
                "opening": "{nome}, sono contento di conoscerla. {reference} mi ha parlato molto bene di {azienda}.",
                "qualification": "Quali sfide sta affrontando il team in questo momento? Voglio capire come possiamo aiutarvi insieme.",
                "proposal": "Ho pensato a una soluzione su misura per {azienda}. {reference} ha avuto risultati simili.",
                "closing": "Sono convinto che sia l'inizio di una grande collaborazione. Iniziamo insieme?"
            },
            "security": {
                "opening": "{nome}, capisco l'importanza della sicurezza per {azienda}. Proteggiamo il suo business.",
                "qualification": "Quali rischi sta correndo attualmente con {current_approach}? Come li mitiga oggi?",
                "proposal": "Ecco il piano di protezione completo: {solution}. Garanzia: {guarantee}. Supporto: {support_terms}.",
                "closing": "La sua sicurezza è garantita. Proteggiamo il suo investimento da subito. Pronto per iniziare?"
            }
        }
        
        profile_templates = templates.get(profile, templates["analyst"])
        return profile_templates.get(stage, profile_templates["opening"])
