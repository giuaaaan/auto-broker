"""
AUTO-BROKER: Pydantic Schemas
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from uuid import UUID
from enum import Enum

from pydantic import BaseModel, Field, EmailStr


class LeadStatus(str, Enum):
    NUOVO = "nuovo"
    CONTATTATO = "contattato"
    QUALIFICATO = "qualificato"
    SOSPESO = "sospeso"
    RIFIUTATO = "rifiutato"
    CONVERTITO = "convertito"


class FrequenzaSpedizione(str, Enum):
    GIORNALIERA = "giornaliera"
    SETTIMANALE = "settimanale"
    MENSILE = "mensile"
    OCCASIONALE = "occasionale"


# ==========================================
# LEAD SCHEMAS
# ==========================================
class LeadBase(BaseModel):
    nome: str = Field(..., min_length=1, max_length=100)
    cognome: Optional[str] = Field(None, max_length=100)
    azienda: str = Field(..., min_length=1, max_length=200)
    telefono: str = Field(..., min_length=5, max_length=50)
    email: EmailStr
    settore: Optional[str] = Field(None, max_length=100)
    indirizzo: Optional[str] = Field(None, max_length=300)
    citta: Optional[str] = Field(None, max_length=100)
    provincia: Optional[str] = Field(None, max_length=10)
    cap: Optional[str] = Field(None, max_length=10)
    fonte: str = Field(default="csv", max_length=100)
    note: Optional[str] = None


class LeadCreate(LeadBase):
    pass


class LeadUpdate(BaseModel):
    nome: Optional[str] = Field(None, max_length=100)
    cognome: Optional[str] = Field(None, max_length=100)
    azienda: Optional[str] = Field(None, max_length=200)
    telefono: Optional[str] = Field(None, max_length=50)
    email: Optional[EmailStr] = None
    settore: Optional[str] = Field(None, max_length=100)
    status: Optional[LeadStatus] = None
    note: Optional[str] = None
    follow_up_date: Optional[datetime] = None


class LeadResponse(LeadBase):
    id: UUID
    status: LeadStatus
    retell_call_id: Optional[str]
    created_at: datetime
    updated_at: datetime
    follow_up_date: Optional[datetime]
    
    class Config:
        from_attributes = True


# ==========================================
# QUALIFICAZIONE SCHEMAS
# ==========================================
class QualificazioneBase(BaseModel):
    volume_kg_mensile: Optional[Decimal] = None
    lane_origine: Optional[str] = Field(None, max_length=200)
    lane_destinazione: Optional[str] = Field(None, max_length=200)
    frequenza: Optional[FrequenzaSpedizione] = None
    prezzo_attuale_kg: Optional[Decimal] = None
    tipo_merce: Optional[str] = Field(None, max_length=100)
    esigenze_speciali: Optional[str] = None
    partita_iva: Optional[str] = Field(None, max_length=20)


class QualificazioneCreate(QualificazioneBase):
    lead_id: UUID


class QualificazioneResponse(QualificazioneBase):
    id: UUID
    lead_id: UUID
    credit_score: Optional[int]
    credit_check_note: Optional[str]
    status: str
    agente: str
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class QualifyLeadRequest(BaseModel):
    lead_id: UUID
    volume_kg_mensile: Decimal
    lane_origine: str
    lane_destinazione: str
    frequenza: FrequenzaSpedizione
    prezzo_attuale_kg: Decimal
    tipo_merce: str
    partita_iva: str
    esigenze_speciali: Optional[str] = None


# ==========================================
# CARRIER SCHEMAS
# ==========================================
class CorriereResponse(BaseModel):
    id: UUID
    nome: str
    codice: str
    tipo: Optional[str]
    rating_ontime: Decimal
    costo_per_kg_nazionale: Optional[Decimal]
    costo_per_kg_internazionale: Optional[Decimal]
    tempi_consegna_giorni: Optional[int]
    attivo: bool
    
    class Config:
        from_attributes = True


class CarrierQuote(BaseModel):
    corriere_id: UUID
    corriere_nome: str
    corriere_codice: str
    costo_per_kg: Decimal
    costo_totale: Decimal
    tempi_consegna_giorni: int
    rating_ontime: Decimal
    fonte: str = "database"


class SourceCarriersRequest(BaseModel):
    lane_origine: str
    lane_destinazione: str
    peso_kg: Decimal
    tipo_merce: Optional[str] = None


class SourceCarriersResponse(BaseModel):
    lane_origine: str
    lane_destinazione: str
    peso_kg: Decimal
    quotes: List[CarrierQuote]
    miglior_prezzo: Optional[CarrierQuote] = None


class CalculatePriceRequest(BaseModel):
    lane_origine: str
    lane_destinazione: str
    peso_kg: Decimal
    dimensioni: Optional[Dict[str, Any]] = None


class CalculatePriceResponse(BaseModel):
    lane_origine: str
    lane_destinazione: str
    peso_kg: Decimal
    corriere_id: UUID
    corriere_nome: str
    costo_corriere: Decimal
    markup_percentuale: Decimal
    prezzo_vendita: Decimal
    margine_netto: Decimal
    tempi_stimati_giorni: int
    valuta: str = "EUR"


# ==========================================
# PROPOSAL SCHEMAS
# ==========================================
class CreateProposalRequest(BaseModel):
    qualifica_id: UUID
    corriere_id: UUID
    markup_percentuale: Optional[Decimal] = Decimal("30.00")
    note: Optional[str] = None


class CreateProposalResponse(BaseModel):
    preventivo_id: UUID
    pdf_url: str
    email_inviata: bool
    email_id: Optional[str]
    tracking_id: str


class PreventivoResponse(BaseModel):
    id: UUID
    qualifica_id: UUID
    corriere_id: UUID
    lead_id: Optional[UUID]
    prezzo_vendita: Optional[Decimal]
    margine_netto: Optional[Decimal]
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True


# ==========================================
# WEBHOOK SCHEMAS
# ==========================================
class RetellWebhookRequest(BaseModel):
    call_id: str
    lead_id: Optional[UUID]
    agent_id: str
    agent_name: str
    status: str
    duration_seconds: Optional[int]
    outcome: Optional[str]
    transcript: Optional[str]


class DocuSignWebhookRequest(BaseModel):
    event: str
    envelope_id: str
    status: str
    recipient_email: Optional[str]
    recipient_name: Optional[str]
    completed_at: Optional[datetime]


class DisruptionAlertRequest(BaseModel):
    spedizione_id: UUID
    tipo_ritardo: str
    ore_ritardo: int
    nuova_eta: Optional[datetime] = None
    motivo: Optional[str] = None


# ==========================================
# IMPORT SCHEMAS
# ==========================================
class ImportResult(BaseModel):
    totali: int
    importati: int
    errori: int
    errori_dettaglio: List[Dict[str, Any]]


# ==========================================
# RESPONSE SCHEMAS
# ==========================================
class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
    version: str = "1.0.0"
    database: str
    redis: str


class SuccessResponse(BaseModel):
    success: bool = True
    message: str
    data: Optional[Dict[str, Any]] = None
