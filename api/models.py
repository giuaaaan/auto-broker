"""
AUTO-BROKER: SQLAlchemy Models
Database models for the logistics broker platform
"""
from datetime import datetime
from typing import Optional, List
from uuid import UUID as PyUUID
import uuid

from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, Text, 
    Numeric, ForeignKey, CheckConstraint, Index, ARRAY, JSON, Float
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

Base = declarative_base()


class Lead(Base):
    __tablename__ = "leads"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome = Column(String(100), nullable=False)
    cognome = Column(String(100))
    azienda = Column(String(200), nullable=False)
    telefono = Column(String(50), nullable=False)
    email = Column(String(200), nullable=False)
    settore = Column(String(100))
    indirizzo = Column(String(300))
    citta = Column(String(100))
    provincia = Column(String(10))
    cap = Column(String(10))
    status = Column(String(50), default='nuovo')
    fonte = Column(String(100), default='csv')
    note = Column(Text)
    retell_call_id = Column(String(100))
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    follow_up_date = Column(DateTime(timezone=True))
    
    qualificazioni = relationship("Qualificazione", back_populates="lead", cascade="all, delete-orphan")
    preventivi = relationship("Preventivo", back_populates="lead")
    contratti = relationship("Contratto", back_populates="lead")
    spedizioni = relationship("Spedizione", back_populates="lead")


class Qualificazione(Base):
    __tablename__ = "qualificazioni"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)
    volume_kg_mensile = Column(Numeric(10, 2))
    lane_origine = Column(String(200))
    lane_destinazione = Column(String(200))
    frequenza = Column(String(50))
    prezzo_attuale_kg = Column(Numeric(8, 2))
    tipo_merce = Column(String(100))
    esigenze_speciali = Column(Text)
    credit_score = Column(Integer)
    credit_check_note = Column(Text)
    partita_iva = Column(String(20))
    status = Column(String(50), default='in_corso')
    agente = Column(String(50), default='marco')
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True))
    
    lead = relationship("Lead", back_populates="qualificazioni")
    preventivi = relationship("Preventivo", back_populates="qualificazione", cascade="all, delete-orphan")


class Corriere(Base):
    __tablename__ = "corrieri"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome = Column(String(100), nullable=False)
    codice = Column(String(20), unique=True, nullable=False)
    tipo = Column(String(50))
    api_endpoint = Column(String(500))
    api_key = Column(String(500))
    email_preventivi = Column(String(200))
    telefono = Column(String(50))
    rating_ontime = Column(Numeric(5, 2), default=95.00)
    costo_per_kg_nazionale = Column(Numeric(8, 4))
    costo_per_kg_internazionale = Column(Numeric(8, 4))
    tempi_consegna_giorni = Column(Integer)
    aree_copertura = Column(ARRAY(String))
    requisiti_speciali = Column(Text)
    attivo = Column(Boolean, default=True)
    priorita = Column(Integer, default=0)
    note = Column(Text)
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    
    preventivi = relationship("Preventivo", back_populates="corriere")
    spedizioni = relationship("Spedizione", back_populates="corriere")


class Preventivo(Base):
    __tablename__ = "preventivi"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    qualifica_id = Column(UUID(as_uuid=True), ForeignKey("qualificazioni.id", ondelete="CASCADE"), nullable=False)
    corriere_id = Column(UUID(as_uuid=True), ForeignKey("corrieri.id"), nullable=False)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id"))
    peso_kg = Column(Numeric(10, 2))
    lane_origine = Column(String(200))
    lane_destinazione = Column(String(200))
    costo_corriere = Column(Numeric(10, 2))
    markup_percentuale = Column(Numeric(5, 2), default=30.00)
    prezzo_vendita = Column(Numeric(10, 2))
    margine_netto = Column(Numeric(10, 2))
    tempi_stimati_giorni = Column(Integer)
    valuta = Column(String(3), default='EUR')
    condizioni = Column(Text)
    valido_fino = Column(DateTime(timezone=True))
    status = Column(String(50), default='bozza')
    pdf_url = Column(String(500))
    email_aperta = Column(Boolean, default=False)
    email_aperta_at = Column(DateTime(timezone=True))
    email_click_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    inviato_at = Column(DateTime(timezone=True))
    accettato_at = Column(DateTime(timezone=True))
    
    qualificazione = relationship("Qualificazione", back_populates="preventivi")
    corriere = relationship("Corriere", back_populates="preventivi")
    lead = relationship("Lead", back_populates="preventivi")
    contratti = relationship("Contratto", back_populates="preventivo", cascade="all, delete-orphan")


class Contratto(Base):
    __tablename__ = "contratti"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    preventivo_id = Column(UUID(as_uuid=True), ForeignKey("preventivi.id", ondelete="CASCADE"), nullable=False)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id"))
    numero_contratto = Column(String(50), unique=True, nullable=False)
    docusign_envelope_id = Column(String(100))
    docusign_url = Column(String(500))
    status = Column(String(50), default='bozza')
    importo_totale = Column(Numeric(12, 2))
    durata_mesi = Column(Integer, default=12)
    condizioni_generali = Column(Text)
    note = Column(Text)
    firmato_cliente_at = Column(DateTime(timezone=True))
    firmato_broker_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    completato_at = Column(DateTime(timezone=True))
    
    preventivo = relationship("Preventivo", back_populates="contratti")
    lead = relationship("Lead", back_populates="contratti")
    pagamenti = relationship("Pagamento", back_populates="contratto", cascade="all, delete-orphan")
    spedizioni = relationship("Spedizione", back_populates="contratto")


class Pagamento(Base):
    __tablename__ = "pagamenti"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contratto_id = Column(UUID(as_uuid=True), ForeignKey("contratti.id", ondelete="CASCADE"), nullable=False)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id"))
    stripe_payment_intent_id = Column(String(100))
    stripe_checkout_url = Column(String(500))
    stripe_payment_status = Column(String(50), default='pending')
    importo_cliente = Column(Numeric(12, 2), nullable=False)
    importo_corriere = Column(Numeric(12, 2))
    commissioni_stripe = Column(Numeric(10, 2), default=0)
    altre_commissioni = Column(Numeric(10, 2), default=0)
    netto_broker = Column(Numeric(12, 2))
    costi_fissi = Column(Numeric(10, 2), default=0)
    profitto_finale = Column(Numeric(12, 2))
    pagato_cliente_at = Column(DateTime(timezone=True))
    pagato_corriere_at = Column(DateTime(timezone=True))
    wise_transfer_id = Column(String(100))
    fattura_numero = Column(String(50))
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    
    contratto = relationship("Contratto", back_populates="pagamenti")
    spedizioni = relationship("Spedizione", back_populates="pagamento")


class Spedizione(Base):
    __tablename__ = "spedizioni"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contratto_id = Column(UUID(as_uuid=True), ForeignKey("contratti.id"))
    pagamento_id = Column(UUID(as_uuid=True), ForeignKey("pagamenti.id"))
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id"))
    corriere_id = Column(UUID(as_uuid=True), ForeignKey("corrieri.id"))
    numero_spedizione = Column(String(50), unique=True, nullable=False)
    tracking_number = Column(String(100))
    tracking_url = Column(String(500))
    aftership_tracking_id = Column(String(100))
    riferimento_cliente = Column(String(100))
    peso_effettivo_kg = Column(Numeric(10, 2))
    dimensioni_cm = Column(String(50))
    lane_origine = Column(String(200))
    lane_destinazione = Column(String(200))
    indirizzo_destinatario = Column(Text)
    nome_destinatario = Column(String(200))
    telefono_destinatario = Column(String(50))
    note_consegna = Column(Text)
    costo_corriere_effettivo = Column(Numeric(10, 2))
    prezzo_vendita_effettivo = Column(Numeric(10, 2))
    status = Column(String(50), default='in_preparazione')
    data_ritiro = Column(DateTime(timezone=True))
    data_consegna_prevista = Column(DateTime(timezone=True))
    data_consegna_effettiva = Column(DateTime(timezone=True))
    ritardo_ore = Column(Integer, default=0)
    alert_ritardo_inviato = Column(Boolean, default=False)
    email_conferma_inviata = Column(Boolean, default=False)
    email_consegnata_inviata = Column(Boolean, default=False)
    recensione_richiesta = Column(Boolean, default=False)
    cmr_url = Column(String(500))
    etichette_urls = Column(ARRAY(String))
    documenti_urls = Column(ARRAY(String))
    eventi_tracking = Column(JSONB, default=list)
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    
    contratto = relationship("Contratto", back_populates="spedizioni")
    pagamento = relationship("Pagamento", back_populates="spedizioni")
    lead = relationship("Lead", back_populates="spedizioni")
    corriere = relationship("Corriere", back_populates="spedizioni")


class LogAttivita(Base):
    __tablename__ = "log_attivita"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entita_tipo = Column(String(50), nullable=False)
    entita_id = Column(UUID(as_uuid=True), nullable=False)
    azione = Column(String(100), nullable=False)
    dettagli = Column(JSONB)
    agente = Column(String(50))
    ip_address = Column(INET)
    created_at = Column(DateTime(timezone=True), default=func.now())


class EmailInviata(Base):
    __tablename__ = "email_inviate"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id"))
    preventivo_id = Column(UUID(as_uuid=True), ForeignKey("preventivi.id"))
    tipo_email = Column(String(100), nullable=False)
    oggetto = Column(String(300))
    mittente = Column(String(200))
    destinatario = Column(String(200))
    resend_id = Column(String(100))
    status = Column(String(50), default='inviata')
    aperta_at = Column(DateTime(timezone=True))
    cliccata_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=func.now())


class ChiamataRetell(Base):
    __tablename__ = "chiamate_retell"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id"))
    call_id = Column(String(100), unique=True, nullable=False)
    agent_id = Column(String(100))
    agente_nome = Column(String(50))
    status = Column(String(50))
    durata_secondi = Column(Integer)
    recording_url = Column(String(500))
    transcript = Column(Text)
    outcome = Column(String(100))
    note = Column(Text)
    created_at = Column(DateTime(timezone=True), default=func.now())
    completed_at = Column(DateTime(timezone=True))
