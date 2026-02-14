-- AUTO-BROKER 3.0 - Emotional Intelligence Schema
-- Production Ticket: EQ-2026-001
-- Zero errors tolerated

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
-- Note: pgvector is optional. If not available, embeddings stored as JSONB
DO $$
BEGIN
    CREATE EXTENSION IF NOT EXISTS vector;
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'pgvector not available - will use JSONB for embeddings';
END $$;

-- 1. SENTIMENT ANALYSIS (Core)
CREATE TABLE IF NOT EXISTS sentiment_analysis (
    id SERIAL PRIMARY KEY,
    call_id VARCHAR(255) UNIQUE NOT NULL,
    lead_id INT REFERENCES leads(id) ON DELETE CASCADE,
    transcription TEXT NOT NULL,
    sentiment_score DECIMAL(3,2) CHECK (sentiment_score BETWEEN -1.0 AND 1.0),
    emotions JSONB NOT NULL DEFAULT '{}',
    dominant_emotion VARCHAR(50),
    confidence DECIMAL(3,2) CHECK (confidence BETWEEN 0.0 AND 1.0),
    prosody_raw JSONB,
    requires_escalation BOOLEAN DEFAULT FALSE,
    analysis_method VARCHAR(20) DEFAULT 'hume',
    analyzed_at TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sentiment_lead ON sentiment_analysis(lead_id, analyzed_at DESC);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sentiment_escalation ON sentiment_analysis(requires_escalation) WHERE requires_escalation = TRUE;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sentiment_method ON sentiment_analysis(analysis_method, created_at DESC);

-- 2. PSYCHOLOGICAL PROFILES
CREATE TABLE IF NOT EXISTS psychological_profiles (
    id SERIAL PRIMARY KEY,
    lead_id INT REFERENCES leads(id) ON DELETE CASCADE,
    profile_type VARCHAR(20) CHECK (profile_type IN ('velocity', 'analyst', 'social', 'security')),
    decision_speed INT CHECK (decision_speed BETWEEN 1 AND 10),
    risk_tolerance INT CHECK (risk_tolerance BETWEEN 1 AND 10),
    price_sensitivity INT CHECK (price_sensitivity BETWEEN 1 AND 10),
    communication_pref VARCHAR(20) CHECK (communication_pref IN ('phone', 'email', 'whatsapp', 'sms')),
    pain_points TEXT[],
    core_values TEXT[],
    profile_embedding VECTOR(1536),
    churn_risk_score DECIMAL(3,2),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT unique_lead_profile UNIQUE (lead_id)
);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_profile_type ON psychological_profiles(profile_type);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_profile_lead ON psychological_profiles(lead_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_profile_embedding ON psychological_profiles USING ivfflat (profile_embedding vector_cosine_ops);

-- 3. INTERACTION HISTORY (Event Sourcing)
CREATE TABLE IF NOT EXISTS interaction_history (
    id SERIAL PRIMARY KEY,
    lead_id INT NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    agent_name VARCHAR(50) NOT NULL,
    channel VARCHAR(20) NOT NULL,
    interaction_text TEXT,
    interaction_vector VECTOR(1536),
    sentiment_id INT REFERENCES sentiment_analysis(id) ON DELETE SET NULL,
    strategy_applied VARCHAR(50),
    conversion_value DECIMAL(10,2),
    outcome VARCHAR(20) CHECK (outcome IN ('converted', 'rejected', 'nurture', 'escalated')),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_interaction_lead ON interaction_history(lead_id, created_at DESC);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_interaction_agent ON interaction_history(agent_name, created_at DESC);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_interaction_sentiment ON interaction_history(sentiment_id) WHERE sentiment_id IS NOT NULL;

-- 4. NURTURING SEQUENCES
CREATE TABLE IF NOT EXISTS nurturing_sequences (
    id SERIAL PRIMARY KEY,
    lead_id INT NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    sequence_type VARCHAR(20) CHECK (sequence_type IN ('post_rejection', 'long_term', 'reactivation')),
    step_number INT NOT NULL,
    content_template TEXT NOT NULL,
    personalization_vars JSONB,
    channel VARCHAR(20) NOT NULL,
    scheduled_at TIMESTAMP NOT NULL,
    executed_at TIMESTAMP,
    opened BOOLEAN DEFAULT FALSE,
    clicked BOOLEAN DEFAULT FALSE,
    replied BOOLEAN DEFAULT FALSE,
    CONSTRAINT unique_sequence_step UNIQUE (lead_id, sequence_type, step_number)
);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_nurturing_scheduled ON nurturing_sequences(scheduled_at) WHERE executed_at IS NULL;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_nurturing_lead ON nurturing_sequences(lead_id, sequence_type);

-- 5. PERSUASION STRATEGIES (A/B Testing)
CREATE TABLE IF NOT EXISTS persuasion_strategies (
    id SERIAL PRIMARY KEY,
    profile_type VARCHAR(20),
    strategy_name VARCHAR(50),
    script_template TEXT,
    milton_patterns JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    traffic_allocation INT DEFAULT 50 CHECK (traffic_allocation BETWEEN 0 AND 100),
    success_count INT DEFAULT 0,
    test_count INT DEFAULT 0,
    success_rate DECIMAL(5,2) GENERATED ALWAYS AS (CASE WHEN test_count > 0 THEN (success_count::DECIMAL / test_count) * 100 ELSE 0 END) STORED,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_strategy_profile ON persuasion_strategies(profile_type, is_active) WHERE is_active = TRUE;

-- Seed initial strategies
INSERT INTO persuasion_strategies (profile_type, strategy_name, script_template, milton_patterns) VALUES
('velocity', 'urgency_close', 'Possiamo chiudere subito. Immagini il beneficio immediato.', '["embedded_command", "time_pressure"]'),
('analyst', 'data_driven', 'I dati mostrano un ROI del 150%. Analizziamo insieme.', '["authority", "presupposition"]'),
('social', 'testimonial', 'I nostri clienti sono soddisfatti. Anche lei lo sarà.', '["social_proof", "future_pacing"]'),
('security', 'guarantee', 'È tutto garantito. Zero rischi per lei.', '["certainty", "risk_reversal"]')
ON CONFLICT DO NOTHING;

-- Verify tables created
DO $$
DECLARE
    table_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO table_count
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_name IN ('sentiment_analysis', 'psychological_profiles', 'interaction_history', 'nurturing_sequences', 'persuasion_strategies');
    
    IF table_count = 5 THEN
        RAISE NOTICE '✅ All EQ tables created successfully';
    ELSE
        RAISE EXCEPTION '❌ Expected 5 tables, found %', table_count;
    END IF;
END $$;
