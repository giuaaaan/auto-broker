-- ==========================================
-- AUTO-BROKER: Database Schema
-- ==========================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable Vector extension for ChromaDB
CREATE EXTENSION IF NOT EXISTS "vector";

-- ==========================================
-- LEADS TABLE
-- ==========================================
CREATE TABLE IF NOT EXISTS leads (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    nome VARCHAR(100) NOT NULL,
    cognome VARCHAR(100),
    azienda VARCHAR(200) NOT NULL,
    telefono VARCHAR(50) NOT NULL,
    email VARCHAR(200) NOT NULL,
    settore VARCHAR(100),
    indirizzo VARCHAR(300),
    citta VARCHAR(100),
    provincia VARCHAR(10),
    cap VARCHAR(10),
    status VARCHAR(50) DEFAULT 'nuovo' CHECK (status IN ('nuovo', 'contattato', 'qualificato', 'sospeso', 'rifiutato', 'convertito')),
    fonte VARCHAR(100) DEFAULT 'csv',
    note TEXT,
    retell_call_id VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    follow_up_date TIMESTAMP WITH TIME ZONE,
    UNIQUE(email, telefono)
);

CREATE INDEX idx_leads_status ON leads(status);
CREATE INDEX idx_leads_created_at ON leads(created_at);
CREATE INDEX idx_leads_follow_up ON leads(follow_up_date) WHERE follow_up_date IS NOT NULL;

-- ==========================================
-- QUALIFICAZIONI TABLE
-- ==========================================
CREATE TABLE IF NOT EXISTS qualificazioni (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    lead_id UUID NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    volume_kg_mensile DECIMAL(10,2),
    lane_origine VARCHAR(200),
    lane_destinazione VARCHAR(200),
    frequenza VARCHAR(50) CHECK (frequenza IN ('giornaliera', 'settimanale', 'mensile', 'occasionale')),
    prezzo_attuale_kg DECIMAL(8,2),
    tipo_merce VARCHAR(100),
    esigenze_speciali TEXT,
    credit_score INTEGER CHECK (credit_score >= 0 AND credit_score <= 100),
    credit_check_note TEXT,
    partita_iva VARCHAR(20),
    status VARCHAR(50) DEFAULT 'in_corso' CHECK (status IN ('in_corso', 'approvato', 'rifiutato', 'revisione')),
    agente VARCHAR(50) DEFAULT 'marco',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_qualificazioni_lead_id ON qualificazioni(lead_id);
CREATE INDEX idx_qualificazioni_status ON qualificazioni(status);

-- ==========================================
-- CORRIERI TABLE
-- ==========================================
CREATE TABLE IF NOT EXISTS corrieri (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    nome VARCHAR(100) NOT NULL,
    codice VARCHAR(20) UNIQUE NOT NULL,
    tipo VARCHAR(50) CHECK (tipo IN ('nazionale', 'internazionale', 'locale', 'express')),
    api_endpoint VARCHAR(500),
    api_key VARCHAR(500),
    email_preventivi VARCHAR(200),
    telefono VARCHAR(50),
    rating_ontime DECIMAL(5,2) DEFAULT 95.00,
    costo_per_kg_nazionale DECIMAL(8,4),
    costo_per_kg_internazionale DECIMAL(8,4),
    tempi_consegna_giorni INTEGER,
    aree_copertura TEXT[],
    requisiti_speciali TEXT,
    attivo BOOLEAN DEFAULT true,
    priorita INTEGER DEFAULT 0,
    note TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_corrieri_attivo ON corrieri(attivo);
CREATE INDEX idx_corrieri_tipo ON corrieri(tipo);

-- ==========================================
-- PREVENTIVI TABLE
-- ==========================================
CREATE TABLE IF NOT EXISTS preventivi (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    qualifica_id UUID NOT NULL REFERENCES qualificazioni(id) ON DELETE CASCADE,
    corriere_id UUID NOT NULL REFERENCES corrieri(id),
    lead_id UUID REFERENCES leads(id),
    peso_kg DECIMAL(10,2),
    lane_origine VARCHAR(200),
    lane_destinazione VARCHAR(200),
    costo_corriere DECIMAL(10,2),
    markup_percentuale DECIMAL(5,2) DEFAULT 30.00,
    prezzo_vendita DECIMAL(10,2),
    margine_netto DECIMAL(10,2),
    tempi_stimati_giorni INTEGER,
    valuta VARCHAR(3) DEFAULT 'EUR',
    condizioni TEXT,
    valido_fino TIMESTAMP WITH TIME ZONE,
    status VARCHAR(50) DEFAULT 'bozza' CHECK (status IN ('bozza', 'inviato', 'visionato', 'accettato', 'rifiutato', 'scaduto')),
    pdf_url VARCHAR(500),
    email_aperta BOOLEAN DEFAULT false,
    email_aperta_at TIMESTAMP WITH TIME ZONE,
    email_click_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    inviato_at TIMESTAMP WITH TIME ZONE,
    accettato_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_preventivi_qualifica_id ON preventivi(qualifica_id);
CREATE INDEX idx_preventivi_status ON preventivi(status);
CREATE INDEX idx_preventivi_email_aperta ON preventivi(email_aperta) WHERE email_aperta = true;

-- ==========================================
-- CONTRATTI TABLE
-- ==========================================
CREATE TABLE IF NOT EXISTS contratti (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    preventivo_id UUID NOT NULL REFERENCES preventivi(id) ON DELETE CASCADE,
    lead_id UUID REFERENCES leads(id),
    numero_contratto VARCHAR(50) UNIQUE NOT NULL,
    docusign_envelope_id VARCHAR(100),
    docusign_url VARCHAR(500),
    status VARCHAR(50) DEFAULT 'bozza' CHECK (status IN ('bozza', 'inviato', 'visionato', 'firmato_cliente', 'firmato_entrambi', 'completato', 'annullato')),
    importo_totale DECIMAL(12,2),
    durata_mesi INTEGER DEFAULT 12,
    condizioni_generali TEXT,
    note TEXT,
    firmato_cliente_at TIMESTAMP WITH TIME ZONE,
    firmato_broker_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completato_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_contratti_preventivo_id ON contratti(preventivo_id);
CREATE INDEX idx_contratti_status ON contratti(status);
CREATE INDEX idx_contratti_docusign ON contratti(docusign_envelope_id);

-- ==========================================
-- PAGAMENTI TABLE
-- ==========================================
CREATE TABLE IF NOT EXISTS pagamenti (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    contratto_id UUID NOT NULL REFERENCES contratti(id) ON DELETE CASCADE,
    lead_id UUID REFERENCES leads(id),
    stripe_payment_intent_id VARCHAR(100),
    stripe_checkout_url VARCHAR(500),
    stripe_payment_status VARCHAR(50) DEFAULT 'pending' CHECK (stripe_payment_status IN ('pending', 'processing', 'succeeded', 'failed', 'refunded', 'disputed')),
    importo_cliente DECIMAL(12,2) NOT NULL,
    importo_corriere DECIMAL(12,2),
    commissioni_stripe DECIMAL(10,2) DEFAULT 0,
    altre_commissioni DECIMAL(10,2) DEFAULT 0,
    netto_broker DECIMAL(12,2),
    costi_fissi DECIMAL(10,2) DEFAULT 0,
    profitto_finale DECIMAL(12,2),
    pagato_cliente_at TIMESTAMP WITH TIME ZONE,
    pagato_corriere_at TIMESTAMP WITH TIME ZONE,
    wise_transfer_id VARCHAR(100),
    fattura_numero VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_pagamenti_contratto_id ON pagamenti(contratto_id);
CREATE INDEX idx_pagamenti_stripe_id ON pagamenti(stripe_payment_intent_id);
CREATE INDEX idx_pagamenti_status ON pagamenti(stripe_payment_status);

-- ==========================================
-- SPEDIZIONI TABLE
-- ==========================================
CREATE TABLE IF NOT EXISTS spedizioni (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    contratto_id UUID REFERENCES contratti(id),
    pagamento_id UUID REFERENCES pagamenti(id),
    lead_id UUID REFERENCES leads(id),
    corriere_id UUID REFERENCES corrieri(id),
    numero_spedizione VARCHAR(50) UNIQUE NOT NULL,
    tracking_number VARCHAR(100),
    tracking_url VARCHAR(500),
    aftership_tracking_id VARCHAR(100),
    riferimento_cliente VARCHAR(100),
    peso_effettivo_kg DECIMAL(10,2),
    dimensioni_cm VARCHAR(50),
    lane_origine VARCHAR(200),
    lane_destinazione VARCHAR(200),
    indirizzo_destinatario TEXT,
    nome_destinatario VARCHAR(200),
    telefono_destinatario VARCHAR(50),
    note_consegna TEXT,
    costo_corriere_effettivo DECIMAL(10,2),
    prezzo_vendita_effettivo DECIMAL(10,2),
    status VARCHAR(50) DEFAULT 'in_preparazione' CHECK (status IN ('in_preparazione', 'ritirata', 'in_transito', 'in_consegna', 'consegnata', 'fallita', 'ritornata')),
    data_ritiro TIMESTAMP WITH TIME ZONE,
    data_consegna_prevista TIMESTAMP WITH TIME ZONE,
    data_consegna_effettiva TIMESTAMP WITH TIME ZONE,
    ritardo_ore INTEGER DEFAULT 0,
    alert_ritardo_inviato BOOLEAN DEFAULT false,
    email_conferma_inviata BOOLEAN DEFAULT false,
    email_consegnata_inviata BOOLEAN DEFAULT false,
    recensione_richiesta BOOLEAN DEFAULT false,
    cmr_url VARCHAR(500),
    etichette_urls TEXT[],
    documenti_urls TEXT[],
    eventi_tracking JSONB DEFAULT '[]',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_spedizioni_contratto_id ON spedizioni(contratto_id);
CREATE INDEX idx_spedizioni_tracking ON spedizioni(tracking_number);
CREATE INDEX idx_spedizioni_status ON spedizioni(status);
CREATE INDEX idx_spedizioni_corriere ON spedizioni(corriere_id);
CREATE INDEX idx_spedizioni_data_consegna ON spedizioni(data_consegna_prevista);

-- ==========================================
-- LOG ATTIVITA TABLE (Audit Trail)
-- ==========================================
CREATE TABLE IF NOT EXISTS log_attivita (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entita_tipo VARCHAR(50) NOT NULL,
    entita_id UUID NOT NULL,
    azione VARCHAR(100) NOT NULL,
    dettagli JSONB,
    agente VARCHAR(50),
    ip_address INET,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_log_attivita_entita ON log_attivita(entita_tipo, entita_id);
CREATE INDEX idx_log_attivita_created ON log_attivita(created_at);

-- ==========================================
-- EMAIL INViate TABLE
-- ==========================================
CREATE TABLE IF NOT EXISTS email_inviate (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    lead_id UUID REFERENCES leads(id),
    preventivo_id UUID REFERENCES preventivi(id),
    tipo_email VARCHAR(100) NOT NULL,
    oggetto VARCHAR(300),
    mittente VARCHAR(200),
    destinatario VARCHAR(200),
    resend_id VARCHAR(100),
    status VARCHAR(50) DEFAULT 'inviata' CHECK (status IN ('inviata', 'consegnata', 'aperta', 'cliccata', 'rimbalzata', 'spam')),
    aperta_at TIMESTAMP WITH TIME ZONE,
    cliccata_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_email_inviate_lead ON email_inviate(lead_id);
CREATE INDEX idx_email_inviate_resend ON email_inviate(resend_id);

-- ==========================================
-- CHIAMATE RETELL TABLE
-- ==========================================
CREATE TABLE IF NOT EXISTS chiamate_retell (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    lead_id UUID REFERENCES leads(id),
    call_id VARCHAR(100) UNIQUE NOT NULL,
    agent_id VARCHAR(100),
    agente_nome VARCHAR(50),
    status VARCHAR(50),
    durata_secondi INTEGER,
    recording_url VARCHAR(500),
    transcript TEXT,
    outcome VARCHAR(100),
    note TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_chiamate_retell_lead ON chiamate_retell(lead_id);
CREATE INDEX idx_chiamate_retell_call ON chiamate_retell(call_id);

-- ==========================================
-- FUNCTIONS AND TRIGGERS
-- ==========================================

-- Update timestamp function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for all tables with updated_at
CREATE TRIGGER update_leads_updated_at BEFORE UPDATE ON leads
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_qualificazioni_updated_at BEFORE UPDATE ON qualificazioni
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_corrieri_updated_at BEFORE UPDATE ON corrieri
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_preventivi_updated_at BEFORE UPDATE ON preventivi
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_contratti_updated_at BEFORE UPDATE ON contratti
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_pagamenti_updated_at BEFORE UPDATE ON pagamenti
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_spedizioni_updated_at BEFORE UPDATE ON spedizioni
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ==========================================
-- SEED DATA
-- ==========================================

-- Insert sample carriers
INSERT INTO corrieri (nome, codice, tipo, api_endpoint, email_preventivi, telefono, rating_ontime, costo_per_kg_nazionale, costo_per_kg_internazionale, tempi_consegna_giorni, aree_copertura, attivo, priorita) VALUES
('Bartolini (BRT)', 'BRT', 'nazionale', NULL, 'preventivi@brt.it', '+39 02 39661', 96.50, 0.85, NULL, 1, ARRAY['Italia'], true, 1),
('GLS Italy', 'GLS', 'nazionale', NULL, 'commerciale@gls-italy.com', '+39 02 396661', 94.20, 0.78, NULL, 1, ARRAY['Italia'], true, 2),
('SDA (Poste Italiane)', 'SDA', 'nazionale', NULL, 'preventivi@sda.it', '+39 199 113366', 92.80, 0.72, NULL, 2, ARRAY['Italia'], true, 3),
('DHL Express', 'DHLE', 'internazionale', 'https://api-eu.dhl.com/track/shipments', 'italy.sales@dhl.com', '+39 199 199345', 98.30, 1.45, 4.50, 2, ARRAY['Europa', 'USA', 'Asia'], true, 1),
('FedEx', 'FEDEX', 'internazionale', 'https://apis.fedex.com/ship/v1', 'sales@fedex.com', '+39 199 151188', 97.50, 1.55, 4.80, 2, ARRAY['Europa', 'USA', 'Asia'], true, 2),
('TNT (FedEx)', 'TNT', 'internazionale', NULL, 'sales@tnt.com', '+39 02 362151', 95.40, 1.35, 4.20, 2, ARRAY['Europa'], true, 3),
('UPS', 'UPS', 'internazionale', 'https://onlinetools.ups.com/api/track/v1', 'sales@ups.com', '+39 02 30303039', 96.80, 1.48, 4.60, 2, ARRAY['Europa', 'USA', 'Asia'], true, 4),
('Nexive', 'NEXIVE', 'locale', NULL, 'preventivi@nexive.it', '+39 02 8412301', 91.50, 0.68, NULL, 3, ARRAY['Nord Italia', 'Centro Italia'], true, 5),
('Amazon Logistics (Partner)', 'AMZL', 'locale', NULL, 'logistics@amazon.it', NULL, 93.20, 0.95, NULL, 1, ARRAY['Italia'], true, 6),
('DB Schenker', 'DBS', 'internazionale', NULL, 'italy@dbschenker.com', '+39 02 486941', 94.60, 1.25, 3.80, 3, ARRAY['Europa'], true, 7)
ON CONFLICT (codice) DO NOTHING;

-- Insert sample leads for testing
INSERT INTO leads (nome, cognome, azienda, telefono, email, settore, indirizzo, citta, provincia, cap, status, fonte) VALUES
('Mario', 'Rossi', 'Rossi Srl', '+39 333 1234567', 'mario.rossi@rossisrl.it', 'E-commerce', 'Via Milano 10', 'Milano', 'MI', '20121', 'nuovo', 'csv'),
('Giuseppe', 'Bianchi', 'Bianchi Trasporti', '+39 347 9876543', 'info@bianchitrasporti.com', 'Trasporto Merci', 'Via Roma 25', 'Roma', 'RM', '00185', 'nuovo', 'csv'),
('Laura', 'Verdi', 'Verdi Fashion', '+39 338 4567890', 'laura@verdifashion.it', 'Abbigliamento', 'Corso Italia 5', 'Firenze', 'FI', '50123', 'nuovo', 'csv'),
('Antonio', 'Neri', 'Neri Elettronica', '+39 320 1112233', 'antonio@nerielettronica.it', 'Elettronica', 'Via Torino 15', 'Torino', 'TO', '10100', 'nuovo', 'csv'),
('Francesca', 'Ferrari', 'Ferrari Componenti', '+39 334 5556677', 'francesca@ferraricomp.it', 'Componenti Auto', 'Via Bologna 8', 'Bologna', 'BO', '40126', 'nuovo', 'csv')
ON CONFLICT (email, telefono) DO NOTHING;

-- Insert sample qualificazione for testing
INSERT INTO qualificazioni (lead_id, volume_kg_mensile, lane_origine, lane_destinazione, frequenza, prezzo_attuale_kg, tipo_merce, credit_score, partita_iva, status)
SELECT 
    l.id,
    500.00,
    'Milano, Italia',
    'Roma, Italia',
    'settimanale',
    1.20,
    'Abbigliamento',
    85,
    'IT12345678901',
    'approvato'
FROM leads l WHERE l.email = 'mario.rossi@rossisrl.it'
ON CONFLICT DO NOTHING;
