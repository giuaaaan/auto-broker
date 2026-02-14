-- AUTO-BROKER 3.0 - Emotional Intelligence Schema
-- Production-Grade with Referential Integrity
-- Architecture: Meta AI Agents 2025, Google Affective Computing

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable vector extension for ChromaDB compatibility
CREATE EXTENSION IF NOT EXISTS vector;

-- ==========================================
-- SENTIMENT ANALYSIS TABLE
-- Stores voice sentiment from Hume AI or fallback
-- ==========================================
CREATE TABLE IF NOT EXISTS sentiment_analysis (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    call_id VARCHAR(255) UNIQUE NOT NULL,
    lead_id UUID REFERENCES leads(id) ON DELETE CASCADE,
    sentiment_score DECIMAL(3,2) CHECK (sentiment_score BETWEEN -1.0 AND 1.0),
    emotions JSONB NOT NULL DEFAULT '{}',
    dominant_emotion VARCHAR(50),
    confidence DECIMAL(3,2) CHECK (confidence BETWEEN 0.0 AND 1.0),
    prosody_raw JSONB,
    requires_escalation BOOLEAN DEFAULT FALSE,
    escalation_reason VARCHAR(255),
    analyzed_at TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sentiment_lead ON sentiment_analysis(lead_id, analyzed_at DESC);
CREATE INDEX IF NOT EXISTS idx_sentiment_call_id ON sentiment_analysis(call_id);
CREATE INDEX IF NOT EXISTS idx_sentiment_escalation ON sentiment_analysis(requires_escalation) WHERE requires_escalation = TRUE;
CREATE INDEX IF NOT EXISTS idx_sentiment_emotions ON sentiment_analysis USING GIN (emotions);

COMMENT ON TABLE sentiment_analysis IS 'Voice sentiment analysis from Hume AI Prosody or fallback local analysis';

-- ==========================================
-- PSYCHOLOGICAL PROFILES TABLE
-- Psychological profiling with vector embedding for similarity
-- ==========================================
CREATE TABLE IF NOT EXISTS psychological_profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    lead_id UUID REFERENCES leads(id) ON DELETE CASCADE,
    profile_type VARCHAR(20) CHECK (profile_type IN ('velocity', 'analyst', 'social', 'security')),
    decision_speed INT CHECK (decision_speed BETWEEN 1 AND 10),
    risk_tolerance INT CHECK (risk_tolerance BETWEEN 1 AND 10),
    price_sensitivity INT CHECK (price_sensitivity BETWEEN 1 AND 10),
    communication_pref VARCHAR(20) CHECK (communication_pref IN ('phone', 'email', 'whatsapp', 'sms')),
    pain_points TEXT[],
    core_values TEXT[],
    profile_embedding VECTOR(1536),
    churn_risk_score DECIMAL(3,2),
    profile_metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT unique_lead_profile UNIQUE (lead_id)
);

CREATE INDEX IF NOT EXISTS idx_profile_type ON psychological_profiles(profile_type);
CREATE INDEX IF NOT EXISTS idx_profile_churn ON psychological_profiles(churn_risk_score) WHERE churn_risk_score > 0.7;
CREATE INDEX IF NOT EXISTS idx_profile_embedding ON psychological_profiles USING ivfflat (profile_embedding vector_cosine_ops);

COMMENT ON TABLE psychological_profiles IS 'Psychological profiles based on BANT-C+Emotion framework';

-- ==========================================
-- INTERACTION HISTORY TABLE
-- Memory system for agent continuity
-- ==========================================
CREATE TABLE IF NOT EXISTS interaction_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    lead_id UUID NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    agent_name VARCHAR(50) NOT NULL,
    channel VARCHAR(20) NOT NULL,
    interaction_type VARCHAR(30) CHECK (interaction_type IN ('call', 'email', 'sms', 'whatsapp', 'meeting')),
    interaction_vector VECTOR(1536),
    sentiment_id UUID REFERENCES sentiment_analysis(id) ON DELETE SET NULL,
    transcription_text TEXT,
    strategy_applied VARCHAR(50),
    persuasion_techniques TEXT[],
    conversion_value DECIMAL(10,2),
    outcome VARCHAR(20) CHECK (outcome IN ('converted', 'rejected', 'nurture', 'escalated', 'pending')),
    outcome_notes TEXT,
    next_best_action VARCHAR(100),
    context_data JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_interaction_lead ON interaction_history(lead_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_interaction_agent ON interaction_history(agent_name, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_interaction_outcome ON interaction_history(outcome);
CREATE INDEX IF NOT EXISTS idx_interaction_vector ON interaction_history USING ivfflat (interaction_vector vector_cosine_ops);

COMMENT ON TABLE interaction_history IS 'Interaction memory for agent continuity and personalization';

-- ==========================================
-- NURTURING SEQUENCES TABLE
-- Adaptive nurturing based on psychological profile
-- ==========================================
CREATE TABLE IF NOT EXISTS nurturing_sequences (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    lead_id UUID NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    sequence_type VARCHAR(20) CHECK (sequence_type IN ('post_rejection', 'long_term', 'reactivation', 'activation', 'objection_handling')),
    step_number INT NOT NULL,
    content_template TEXT NOT NULL,
    personalization_vars JSONB DEFAULT '{}',
    channel VARCHAR(20) NOT NULL,
    scheduled_at TIMESTAMP NOT NULL,
    executed_at TIMESTAMP,
    opened BOOLEAN DEFAULT FALSE,
    clicked BOOLEAN DEFAULT FALSE,
    replied BOOLEAN DEFAULT FALSE,
    converted BOOLEAN DEFAULT FALSE,
    engagement_score DECIMAL(3,2) DEFAULT 0.0,
    ai_optimized BOOLEAN DEFAULT FALSE,
    optimization_notes TEXT,
    CONSTRAINT unique_sequence_step UNIQUE (lead_id, sequence_type, step_number)
);

CREATE INDEX IF NOT EXISTS idx_nurturing_lead ON nurturing_sequences(lead_id, sequence_type, step_number);
CREATE INDEX IF NOT EXISTS idx_nurturing_scheduled ON nurturing_sequences(scheduled_at) WHERE executed_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_nurturing_pending ON nurturing_sequences(lead_id, executed_at) WHERE executed_at IS NULL;

COMMENT ON TABLE nurturing_sequences IS 'Adaptive nurturing sequences based on psychological profile and engagement';

-- ==========================================
-- PERSUASION STRATEGIES TABLE
-- A/B tested persuasion strategies per profile type
-- ==========================================
CREATE TABLE IF NOT EXISTS persuasion_strategies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    strategy_name VARCHAR(100) NOT NULL,
    profile_type VARCHAR(20) CHECK (profile_type IN ('velocity', 'analyst', 'social', 'security')),
    trigger_condition VARCHAR(255),
    script_template TEXT NOT NULL,
    milton_patterns TEXT[],
    objection_handlers JSONB DEFAULT '{}',
    success_rate DECIMAL(3,2),
    usage_count INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_strategy_profile ON persuasion_strategies(profile_type, success_rate DESC);

COMMENT ON TABLE persuasion_strategies IS 'A/B tested persuasion strategies per psychological profile type';

-- ==========================================
-- EQ HEALTH MONITORING TABLE
-- Tracks Hume AI quota and system health
-- ==========================================
CREATE TABLE IF NOT EXISTS eq_health_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    metric_type VARCHAR(50) NOT NULL,
    metric_value DECIMAL(10,2),
    metric_metadata JSONB DEFAULT '{}',
    recorded_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_eq_health_type ON eq_health_metrics(metric_type, recorded_at DESC);

COMMENT ON TABLE eq_health_metrics IS 'Health metrics for Emotional Intelligence systems including API quotas';

-- ==========================================
-- TRIGGER FUNCTIONS FOR UPDATED_AT
-- ==========================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply triggers
DROP TRIGGER IF EXISTS update_sentiment_updated_at ON sentiment_analysis;
CREATE TRIGGER update_sentiment_updated_at
    BEFORE UPDATE ON sentiment_analysis
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_profile_updated_at ON psychological_profiles;
CREATE TRIGGER update_profile_updated_at
    BEFORE UPDATE ON psychological_profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_strategies_updated_at ON persuasion_strategies;
CREATE TRIGGER update_strategies_updated_at
    BEFORE UPDATE ON persuasion_strategies
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ==========================================
-- SEED DATA: Persuasion Strategies
-- ==========================================
INSERT INTO persuasion_strategies (strategy_name, profile_type, trigger_condition, script_template, milton_patterns, objection_handlers, success_rate) VALUES
('velocity_fast_close', 'velocity', 'price_objection_minor', 'Perfetto, possiamo chiudere subito! {benefit} è garantito. Mi serve solo il suo OK e partiamo entro 24 ore.', ARRAY['embedded_command', 'time_pressure'], '{"too_expensive": "Con questo volume, il ROI è in 3 settimane. Firmiamo?"}', 0.78),

('analyst_data_driven', 'analyst', 'needs_validation', 'I dati del nostro ultimo trimestre mostrano che il 94% dei clienti simili al suo profilo ha ridotto i costi del 23% in media. Ecco il confronto dettagliato: {comparison_data}', ARRAY['authority_reference', 'presupposition'], '{"need_to_think": "Prenda il tempo necessario. Intanto le invio l''analisi comparativa."}', 0.82),

('social_proof_warm', 'social', 'trust_building', 'Come {reference_customer}, anche lei ha bisogno di {pain_point}. I nostri clienti ci scelgono perché {benefit}. Possiamo fare lo stesso per lei?', ARRAY['social_proof', 'similarity'], '{"not_trusted": "Capisco la sua cautela. Parli con {reference_customer}, le darà il suo feedback diretto."}', 0.75),

('security_guarantee', 'security', 'risk_concern', 'La sua merce è coperta da assicurazione integrale fino a {coverage_amount}. Inoltre, garantiamo {guarantee_terms}. La sua tranquillità è la nostra priorità.', ARRAY['certainty_words', 'risk_reversal'], '{"too_risky": "Le offro la prima spedizione con pagamento alla consegna. Così valuta senza rischi."}', 0.71);

-- ==========================================
-- VIEWS FOR COMMON QUERIES
-- ==========================================

-- View: Leads requiring escalation
CREATE OR REPLACE VIEW leads_requiring_escalation AS
SELECT 
    l.id as lead_id,
    l.nome,
    l.cognome,
    l.azienda,
    s.dominant_emotion,
    s.sentiment_score,
    s.requires_escalation,
    s.escalation_reason,
    s.analyzed_at
FROM leads l
JOIN sentiment_analysis s ON l.id = s.lead_id
WHERE s.requires_escalation = TRUE
AND s.analyzed_at > NOW() - INTERVAL '24 hours';

-- View: Profile-based lead scoring
CREATE OR REPLACE VIEW lead_psychological_scores AS
SELECT 
    l.id as lead_id,
    l.nome,
    l.cognome,
    p.profile_type,
    p.decision_speed,
    p.risk_tolerance,
    p.price_sensitivity,
    p.churn_risk_score,
    CASE 
        WHEN p.profile_type = 'velocity' THEN p.decision_speed * 10
        WHEN p.profile_type = 'analyst' THEN (p.risk_tolerance + p.decision_speed) * 5
        WHEN p.profile_type = 'social' THEN 70 - (p.price_sensitivity * 5)
        WHEN p.profile_type = 'security' THEN p.risk_tolerance * 8
        ELSE 50
    END as conversion_probability
FROM leads l
LEFT JOIN psychological_profiles p ON l.id = p.lead_id;

COMMIT;
