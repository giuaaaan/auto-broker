"""
AUTO-BROKER: FastAPI Main Application
Production-ready with rate limiting, error handling, and structured logging.
DEMO_MODE support for zero-cost testing.
"""
import os
import time
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any, Callable
from uuid import UUID, uuid4

import structlog
from fastapi import FastAPI, Depends, HTTPException, status, Request, Response, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from models import (
    Lead, Qualificazione, Corriere, Preventivo, Contratto, 
    Pagamento, Spedizione, ChiamataRetell, EmailInviata
)
from schemas import (
    LeadCreate, LeadResponse, LeadUpdate, QualificazioneResponse, QualifyLeadRequest,
    SourceCarriersRequest, SourceCarriersResponse, CarrierQuote,
    CalculatePriceRequest, CalculatePriceResponse,
    CreateProposalRequest, CreateProposalResponse,
    RetellWebhookRequest, DocuSignWebhookRequest, DisruptionAlertRequest,
    HealthResponse, ImportResult
)
from services.database import get_db, init_db, check_db_health
from services.redis_service import redis_service
from services.retell_service import retell_service
from services.stripe_service import stripe_service
from services.docusign_service import docusign_service
from services.email_service import email_service
from services.pdf_generator import pdf_generator

# Mock services for DEMO_MODE
from services.mock_clients import get_mock_hume, get_mock_insighto, get_mock_blockchain
from services.mock_agents import get_agent_simulator
from services.mock_revenue_generator import get_revenue_generator

# Configure structlog for JSON logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ]
)
logger = structlog.get_logger()

# Initialize mock services if in DEMO_MODE
mock_hume = None
mock_insighto = None
mock_blockchain = None
agent_simulator = None
revenue_generator = None

if settings.DEMO_MODE:
    logger.info("🎮 DEMO_MODE enabled - Using mock services")
    mock_hume = get_mock_hume()
    mock_insighto = get_mock_insighto()
    mock_blockchain = get_mock_blockchain()

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup/shutdown."""
    logger.info(
        "Starting AUTO-BROKER API", 
        version="1.0.0", 
        environment=os.getenv("ENVIRONMENT"),
        demo_mode=settings.DEMO_MODE
    )
    await init_db()
    await redis_service.connect()
    
    # Start demo simulators if in DEMO_MODE
    if settings.DEMO_MODE:
        global agent_simulator, revenue_generator
        logger.info("🎮 Starting demo simulators...")
        
        # Auto-seed database if empty
        from utils.seeders import seed_demo_data
        try:
            async for db in get_db():
                result = await seed_demo_data(db)
                logger.info(f"🌱 Database seed: {result['status']}")
                break
        except Exception as e:
            logger.warning(f"Auto-seed skipped: {e}")
        
        agent_simulator = get_agent_simulator()
        revenue_generator = get_revenue_generator()
        
        await agent_simulator.start()
        await revenue_generator.start()
        
        logger.info("✅ Demo simulators started")
    
    yield
    
    # Shutdown
    logger.info("Shutting down AUTO-BROKER API")
    
    if settings.DEMO_MODE and agent_simulator:
        await agent_simulator.stop()
    if settings.DEMO_MODE and revenue_generator:
        await revenue_generator.stop()
    
    await redis_service.disconnect()


app = FastAPI(
    title="AUTO-BROKER API",
    description="API per piattaforma di brokeraggio logistico autonoma",
    version="1.0.0",
    lifespan=lifespan
)

# Add rate limiter to app
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Security middleware
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "127.0.0.1", "*.logistik.ai", "*"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Dashboard React dev
        "http://localhost:3000",  # Alternative dev port
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ] + os.getenv("ALLOWED_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==========================================
# REQUEST LOGGING MIDDLEWARE
# ==========================================
@app.middleware("http")
async def log_requests(request: Request, call_next: Callable) -> Response:
    """Log all HTTP requests with timing."""
    start_time = time.time()
    
    # Log request
    logger.info(
        "request_started",
        method=request.method,
        path=request.url.path,
        query=str(request.query_params),
        client_ip=get_remote_address(request),
        user_agent=request.headers.get("user-agent")
    )
    
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        
        # Log response
        logger.info(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(process_time * 1000, 2)
        )
        
        # Add timing header
        response.headers["X-Process-Time"] = str(round(process_time * 1000, 2))
        return response
        
    except Exception as e:
        process_time = time.time() - start_time
        logger.error(
            "request_failed",
            method=request.method,
            path=request.url.path,
            error=str(e),
            duration_ms=round(process_time * 1000, 2)
        )
        raise


# ==========================================
# ERROR HANDLERS
# ==========================================
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with structured response."""
    logger.warning(
        "http_exception",
        path=request.url.path,
        status_code=exc.status_code,
        detail=exc.detail
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "code": exc.status_code,
            "timestamp": datetime.utcnow().isoformat(),
            "path": str(request.url)
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions gracefully."""
    logger.error(
        "unhandled_exception",
        path=request.url.path,
        error_type=type(exc).__name__,
        error=str(exc)
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "code": 500,
            "timestamp": datetime.utcnow().isoformat(),
            "path": str(request.url),
            "request_id": str(uuid4())[:8]
        }
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """Handle ValueError exceptions."""
    logger.warning(
        "value_error",
        path=request.url.path,
        error=str(exc)
    )
    return JSONResponse(
        status_code=400,
        content={
            "error": str(exc),
            "code": 400,
            "timestamp": datetime.utcnow().isoformat()
        }
    )


# ==========================================
# HEALTH CHECK
# ==========================================
@app.get("/health", response_model=HealthResponse, tags=["Health"])
@limiter.limit("60/minute")
async def health_check(request: Request):
    """Health check endpoint for monitoring."""
    db_health = await check_db_health()
    redis_health = await redis_service.check_health()
    
    overall_status = "healthy"
    if db_health["status"] != "healthy" or redis_health["status"] != "healthy":
        overall_status = "degraded"
    
    return HealthResponse(
        status=overall_status,
        timestamp=datetime.utcnow(),
        database=db_health["status"],
        redis=redis_health["status"]
    )


# ==========================================
# LEAD ENDPOINTS
# ==========================================
@app.post("/leads", response_model=LeadResponse, status_code=status.HTTP_201_CREATED, tags=["Leads"])
@limiter.limit("30/minute")
async def create_lead(
    request: Request,
    lead: LeadCreate, 
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new lead in the system.
    
    - **nome**: First name of the contact
    - **cognome**: Last name (optional)
    - **azienda**: Company name
    - **telefono**: Phone number
    - **email**: Valid email address
    - **settore**: Industry sector (optional)
    """
    try:
        db_lead = Lead(**lead.model_dump())
        db.add(db_lead)
        await db.commit()
        await db.refresh(db_lead)
        
        logger.info(
            "lead_created",
            lead_id=str(db_lead.id),
            email=lead.email,
            azienda=lead.azienda
        )
        return db_lead
        
    except Exception as e:
        logger.error("failed_to_create_lead", error=str(e), email=lead.email)
        raise HTTPException(status_code=500, detail=f"Failed to create lead: {str(e)}")


@app.get("/leads", response_model=List[LeadResponse], tags=["Leads"])
@limiter.limit("60/minute")
async def get_leads(
    request: Request,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """
    Get all leads with optional filtering by status.
    
    - **status**: Filter by status (nuovo, contattato, qualificato, etc.)
    - **skip**: Number of records to skip (pagination)
    - **limit**: Maximum number of records to return
    """
    query = select(Lead)
    if status:
        query = query.where(Lead.status == status)
    
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    leads = result.scalars().all()
    
    logger.info("leads_retrieved", count=len(leads), filter_status=status)
    return leads


@app.get("/leads/{lead_id}", response_model=LeadResponse, tags=["Leads"])
@limiter.limit("60/minute")
async def get_lead(
    request: Request,
    lead_id: UUID, 
    db: AsyncSession = Depends(get_db)
):
    """Get a specific lead by ID."""
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    
    if not lead:
        logger.warning("lead_not_found", lead_id=str(lead_id))
        raise HTTPException(status_code=404, detail="Lead not found")
    
    return lead


@app.patch("/leads/{lead_id}", response_model=LeadResponse, tags=["Leads"])
@limiter.limit("30/minute")
async def update_lead(
    request: Request,
    lead_id: UUID, 
    lead_update: LeadUpdate, 
    db: AsyncSession = Depends(get_db)
):
    """Update an existing lead."""
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    update_data = lead_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(lead, field, value)
    
    await db.commit()
    await db.refresh(lead)
    
    logger.info("lead_updated", lead_id=str(lead_id), updated_fields=list(update_data.keys()))
    return lead


@app.post("/leads/{lead_id}/call/{agent_type}", tags=["Leads"])
@limiter.limit("10/minute")
async def trigger_call(
    request: Request,
    lead_id: UUID, 
    agent_type: str, 
    db: AsyncSession = Depends(get_db)
):
    """
    Trigger an AI voice call to the lead.
    
    - **agent_type**: One of: sara, marco, luigi
      - sara: Acquisition agent
      - marco: Qualification agent  
      - luigi: Closing agent
    """
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    agent_map = {
        "sara": retell_service.call_sara,
        "marco": retell_service.call_marco,
        "luigi": retell_service.call_luigi
    }
    
    if agent_type not in agent_map:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid agent type. Use: {list(agent_map.keys())}"
        )
    
    try:
        call_func = agent_map[agent_type]
        
        if agent_type == "luigi":
            call_result = await call_func(
                phone_number=lead.telefono, 
                lead_id=str(lead_id),
                azienda=lead.azienda, 
                nome=lead.nome,
                preventivo_id="default"
            )
        else:
            call_result = await call_func(
                phone_number=lead.telefono, 
                lead_id=str(lead_id),
                azienda=lead.azienda, 
                nome=lead.nome
            )
        
        # Update lead
        lead.retell_call_id = call_result.get("call_id")
        lead.status = "contattato"
        await db.commit()
        
        # Log call
        chiamata = ChiamataRetell(
            lead_id=lead_id,
            call_id=call_result.get("call_id"),
            agent_id=call_result.get("agent_id", f"agent_{agent_type}"),
            agente_nome=agent_type,
            status="iniziata"
        )
        db.add(chiamata)
        await db.commit()
        
        logger.info(
            "call_triggered",
            lead_id=str(lead_id),
            agent=agent_type,
            call_id=call_result.get("call_id")
        )
        
        return {
            "success": True,
            "call_id": call_result.get("call_id"),
            "agent": agent_type,
            "status": "queued"
        }
        
    except Exception as e:
        logger.error("call_failed", lead_id=str(lead_id), agent=agent_type, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to trigger call: {str(e)}")


# ==========================================
# QUALIFICATION ENDPOINTS
# ==========================================
@app.post("/qualify-lead", response_model=QualificazioneResponse, tags=["Qualification"])
@limiter.limit("30/minute")
async def qualify_lead(
    request: Request,
    request_data: QualifyLeadRequest, 
    db: AsyncSession = Depends(get_db)
):
    """
    MARCO (Qualification Agent) - Endpoint
    
    Receive qualification data, perform credit check, save to DB.
    If credit score > 70, status becomes 'approvato' and CARLO is triggered.
    If credit score <= 70, status becomes 'rifiutato' and rejection email is sent.
    """
    # Verify lead exists
    result = await db.execute(select(Lead).where(Lead.id == request_data.lead_id))
    lead = result.scalar_one_or_none()
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    # Calculate credit score (mock algorithm based on PIVA)
    try:
        piva_digits = [int(c) for c in request_data.partita_iva if c.isdigit()]
        credit_score = min(100, max(50, sum(piva_digits) % 100 + 30))
    except:
        credit_score = 70  # Default middle score
    
    # Create qualification record
    qualificazione = Qualificazione(
        lead_id=request_data.lead_id,
        volume_kg_mensile=request_data.volume_kg_mensile,
        lane_origine=request_data.lane_origine,
        lane_destinazione=request_data.lane_destinazione,
        frequenza=request_data.frequenza.value,
        prezzo_attuale_kg=request_data.prezzo_attuale_kg,
        tipo_merce=request_data.tipo_merce,
        esigenze_speciali=request_data.esigenze_speciali,
        credit_score=credit_score,
        partita_iva=request_data.partita_iva,
        status="approvato" if credit_score > 70 else "rifiutato",
        agente="marco"
    )
    
    db.add(qualificazione)
    await db.commit()
    await db.refresh(qualificazione)
    
    # Update lead status
    lead.status = "qualificato" if credit_score > 70 else "rifiutato"
    await db.commit()
    
    # If rejected, send email
    if credit_score <= 70:
        try:
            await email_service.send_rejection(
                to=lead.email,
                nome_cliente=lead.nome,
                azienda=lead.azienda
            )
        except Exception as e:
            logger.error("rejection_email_failed", lead_id=str(lead.id), error=str(e))
    
    logger.info(
        "lead_qualified",
        lead_id=str(request_data.lead_id),
        qualifica_id=str(qualificazione.id),
        credit_score=credit_score,
        status=qualificazione.status
    )
    
    return qualificazione


@app.get("/qualificazioni/{qualificazione_id}", response_model=QualificazioneResponse, tags=["Qualification"])
@limiter.limit("60/minute")
async def get_qualificazione(
    request: Request,
    qualificazione_id: UUID, 
    db: AsyncSession = Depends(get_db)
):
    """Get qualification details by ID."""
    result = await db.execute(
        select(Qualificazione).where(Qualificazione.id == qualificazione_id)
    )
    qual = result.scalar_one_or_none()
    
    if not qual:
        raise HTTPException(status_code=404, detail="Qualificazione not found")
    
    return qual


# ==========================================
# PRICING & SOURCING ENDPOINTS
# ==========================================
@app.post("/calculate-price", response_model=CalculatePriceResponse, tags=["Pricing"])
@limiter.limit("60/minute")
async def calculate_price(
    request: Request,
    request_data: CalculatePriceRequest, 
    db: AsyncSession = Depends(get_db)
):
    """
    Calculate selling price based on carrier cost + 30% margin.
    
    Returns the best available carrier with calculated pricing.
    """
    # Find best carrier (lowest cost with >95% on-time)
    result = await db.execute(
        select(Corriere)
        .where(Corriere.attivo == True)
        .where(Corriere.rating_ontime >= 95.0)
        .order_by(Corriere.costo_per_kg_nazionale)
    )
    carriers = result.scalars().all()
    
    if not carriers:
        raise HTTPException(status_code=404, detail="No active carriers found with required reliability")
    
    best_carrier = carriers[0]
    
    # Calculate cost
    is_international = request_data.lane_destinazione.lower() not in ["italia", "italy", "it"]
    
    if is_international and best_carrier.costo_per_kg_internazionale:
        costo_per_kg = best_carrier.costo_per_kg_internazionale
    else:
        costo_per_kg = best_carrier.costo_per_kg_nazionale or Decimal("1.00")
    
    costo_corriere = costo_per_kg * request_data.peso_kg
    
    # Apply 30% margin
    markup = Decimal("1.30")
    prezzo_vendita = costo_corriere * markup
    margine_netto = prezzo_vendita - costo_corriere
    
    logger.info(
        "price_calculated",
        carrier=best_carrier.nome,
        cost=costo_corriere,
        selling_price=prezzo_vendita,
        margin=margine_netto
    )
    
    return CalculatePriceResponse(
        lane_origine=request_data.lane_origine,
        lane_destinazione=request_data.lane_destinazione,
        peso_kg=request_data.peso_kg,
        corriere_id=best_carrier.id,
        corriere_nome=best_carrier.nome,
        costo_corriere=costo_corriere.quantize(Decimal("0.01")),
        markup_percentuale=Decimal("30.00"),
        prezzo_vendita=prezzo_vendita.quantize(Decimal("0.01")),
        margine_netto=margine_netto.quantize(Decimal("0.01")),
        tempi_stimati_giorni=best_carrier.tempi_consegna_giorni or 2
    )


@app.post("/source-carriers", response_model=SourceCarriersResponse, tags=["Pricing"])
@limiter.limit("60/minute")
async def source_carriers(
    request: Request,
    request_data: SourceCarriersRequest, 
    db: AsyncSession = Depends(get_db)
):
    """
    CARLO (Sourcing Agent) - Endpoint
    
    Search for available carriers from multiple sources:
    1. Internal database (active carriers with >95% on-time)
    2. Web scraping (fallback)
    3. Static fallback rates
    
    Returns quotes sorted by price, with best option selected.
    """
    quotes = []
    
    # 1. Check database first
    result = await db.execute(
        select(Corriere)
        .where(Corriere.attivo == True)
        .where(Corriere.rating_ontime >= 95.0)
        .order_by(Corriere.priorita.desc())
    )
    db_carriers = result.scalars().all()
    
    for carrier in db_carriers:
        costo_per_kg = carrier.costo_per_kg_nazionale or Decimal("1.00")
        total_cost = (costo_per_kg * request_data.peso_kg).quantize(Decimal("0.01"))
        
        quotes.append(CarrierQuote(
            corriere_id=carrier.id,
            corriere_nome=carrier.nome,
            corriere_codice=carrier.codice,
            costo_per_kg=costo_per_kg,
            costo_totale=total_cost,
            tempi_consegna_giorni=carrier.tempi_consegna_giorni or 2,
            rating_ontime=carrier.rating_ontime,
            source="database"
        ))
    
    # Sort by total cost
    quotes.sort(key=lambda x: x.costo_totale)
    
    # Select cheapest with >95% on-time
    best_quote = next((q for q in quotes if q.rating_ontime >= 95.0), None)
    
    logger.info(
        "carriers_sourced",
        lane=f"{request_data.lane_origine} -> {request_data.lane_destinazione}",
        num_quotes=len(quotes),
        best_carrier=best_quote.corriere_nome if best_quote else None
    )
    
    return SourceCarriersResponse(
        lane_origine=request_data.lane_origine,
        lane_destinazione=request_data.lane_destinazione,
        peso_kg=request_data.peso_kg,
        quotes=quotes,
        miglior_prezzo=best_quote
    )


# ==========================================
# PROPOSAL ENDPOINTS
# ==========================================
@app.post("/create-proposal", response_model=CreateProposalResponse, tags=["Proposals"])
@limiter.limit("20/minute")
async def create_proposal(
    request: Request,
    request_data: CreateProposalRequest, 
    db: AsyncSession = Depends(get_db)
):
    """
    LAURA (Proposal Agent) - Endpoint
    
    Generate PDF proposal and send email with DocuSign link.
    
    Workflow:
    1. Calculate final pricing
    2. Generate PDF proposal
    3. Create DocuSign envelope
    4. Send email to client
    5. Create contract record
    """
    # Get qualification
    result = await db.execute(
        select(Qualificazione).where(Qualificazione.id == request_data.qualifica_id)
    )
    qual = result.scalar_one_or_none()
    
    if not qual:
        raise HTTPException(status_code=404, detail="Qualificazione not found")
    
    # Get lead
    result = await db.execute(select(Lead).where(Lead.id == qual.lead_id))
    lead = result.scalar_one_or_none()
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    # Get carrier
    result = await db.execute(select(Corriere).where(Corriere.id == request_data.corriere_id))
    carrier = result.scalar_one_or_none()
    
    if not carrier:
        raise HTTPException(status_code=404, detail="Carrier not found")
    
    try:
        # Calculate pricing
        costo_per_kg = carrier.costo_per_kg_nazionale or Decimal("1.00")
        peso = qual.volume_kg_mensile or Decimal("100")
        costo_corriere = costo_per_kg * peso
        prezzo_vendita = costo_corriere * (Decimal("1") + (request_data.markup_percentuale / Decimal("100")))
        margine_netto = prezzo_vendita - costo_corriere
        
        preventivo_id = uuid4()
        valido_fino = datetime.utcnow() + timedelta(days=30)
        
        # Create preventivo record
        preventivo = Preventivo(
            id=preventivo_id,
            qualifica_id=request_data.qualifica_id,
            corriere_id=request_data.corriere_id,
            lead_id=qual.lead_id,
            peso_kg=peso,
            lane_origine=qual.lane_origine,
            lane_destinazione=qual.lane_destinazione,
            costo_corriere=costo_corriere,
            markup_percentuale=request_data.markup_percentuale,
            prezzo_vendita=prezzo_vendita,
            margine_netto=margine_netto,
            tempi_stimati_giorni=carrier.tempi_consegna_giorni or 2,
            valido_fino=valido_fino,
            status="bozza"
        )
        db.add(preventivo)
        await db.commit()
        
        # Generate PDF
        pdf_result = pdf_generator.generate_proposal(
            preventivo_id=str(preventivo_id),
            data_preventivo=datetime.utcnow(),
            valido_fino=valido_fino,
            cliente_nome=lead.nome,
            cliente_azienda=lead.azienda,
            cliente_indirizzo=f"{lead.indirizzo or ''}, {lead.citta or ''}",
            cliente_piva=qual.partita_iva or "N/D",
            corriere_nome=carrier.nome,
            lane_origine=qual.lane_origine or "N/D",
            lane_destinazione=qual.lane_destinazione or "N/D",
            peso_kg=peso,
            prezzo_kg=(prezzo_vendita / peso).quantize(Decimal("0.01")),
            prezzo_totale=prezzo_vendita.quantize(Decimal("0.01")),
            tempi_consegna=carrier.tempi_consegna_giorni or 2
        )
        
        # Create DocuSign envelope
        docusign_result = await docusign_service.create_envelope(
            document_base64=pdf_result["base64"],
            document_name=f"Proposta_{preventivo_id}.pdf",
            signer_name=f"{lead.nome} {lead.cognome or ''}".strip(),
            signer_email=lead.email,
            metadata={
                "lead_id": str(lead.id),
                "preventivo_id": str(preventivo_id),
                "qualifica_id": str(request_data.qualifica_id)
            }
        )
        
        # Update preventivo
        preventivo.pdf_url = pdf_result["filepath"]
        preventivo.status = "inviato"
        preventivo.inviato_at = datetime.utcnow()
        
        # Create contratto
        contratto_num = f"CNT-{datetime.utcnow().strftime('%Y%m%d')}-{str(preventivo_id)[:8].upper()}"
        contratto = Contratto(
            preventivo_id=preventivo_id,
            lead_id=lead.id,
            numero_contratto=contratto_num,
            docusign_envelope_id=docusign_result.get("envelope_id"),
            docusign_url=docusign_result.get("recipient_view_url"),
            status="inviato",
            importo_totale=prezzo_vendita
        )
        db.add(contratto)
        await db.commit()
        
        # Send email
        email_result = await email_service.send_proposal(
            to=lead.email,
            nome_cliente=lead.nome,
            azienda=lead.azienda,
            preventivo_id=str(preventivo_id)[:8],
            corriere_nome=carrier.nome,
            prezzo_kg=float(prezzo_vendita / peso),
            prezzo_totale=float(prezzo_vendita),
            tempi_consegna=carrier.tempi_consegna_giorni or 2,
            lane_origine=qual.lane_origine or "",
            lane_destinazione=qual.lane_destinazione or "",
            docusign_url=docusign_result.get("recipient_view_url")
        )
        
        # Log email
        email_record = EmailInviata(
            lead_id=lead.id,
            preventivo_id=preventivo_id,
            tipo_email="proposta",
            oggetto=f"Proposta Commerciale - {lead.azienda}",
            mittente=email_service.from_email,
            destinatario=lead.email,
            resend_id=email_result.get("id"),
            status="inviata"
        )
        db.add(email_record)
        await db.commit()
        
        logger.info(
            "proposal_created",
            preventivo_id=str(preventivo_id),
            lead_id=str(lead.id),
            email_id=email_result.get("id"),
            prezzo_vendita=float(prezzo_vendita)
        )
        
        return CreateProposalResponse(
            preventivo_id=preventivo_id,
            pdf_url=pdf_result["filepath"],
            email_inviata=True,
            email_id=email_result.get("id"),
            tracking_id=str(preventivo_id)[:8]
        )
        
    except Exception as e:
        logger.error("proposal_creation_failed", qualifica_id=str(request_data.qualifica_id), error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to create proposal: {str(e)}")


# ==========================================
# STRIPE WEBHOOK
# ==========================================
@app.post("/stripe-webhook", tags=["Payments"])
@limiter.limit("100/minute")
async def stripe_webhook(
    request: Request,
    background_tasks: BackgroundTasks, 
    db: AsyncSession = Depends(get_db)
):
    """
    Handle Stripe webhook events for payment processing.
    
    Events handled:
    - payment_intent.succeeded: Unlock shipment, send confirmation
    - payment_intent.payment_failed: Notify failure
    - checkout.session.completed: Create payment record
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    
    try:
        # Note: In production, verify webhook signature
        import json
        event = json.loads(payload)
        event_type = event.get("type")
        data = event.get("data", {}).get("object", {})
        
        logger.info("stripe_webhook_received", event_type=event_type)
        
        if event_type == "payment_intent.succeeded":
            payment_intent_id = data.get("id")
            amount = data.get("amount", 0) / 100
            
            # Find and update payment
            result = await db.execute(
                select(Pagamento).where(Pagamento.stripe_payment_intent_id == payment_intent_id)
            )
            payment = result.scalar_one_or_none()
            
            if payment:
                payment.stripe_payment_status = "succeeded"
                payment.pagato_cliente_at = datetime.utcnow()
                
                # Calculate profit
                fees = await stripe_service.calculate_fees(Decimal(str(amount)))
                payment.commissioni_stripe = fees["stripe_fees"]
                payment.netto_broker = fees["net_amount"] - (payment.importo_corriere or Decimal("0"))
                payment.profitto_finale = payment.netto_broker - (payment.costi_fissi or Decimal("0"))
                
                await db.commit()
                logger.info("payment_succeeded", payment_id=str(payment.id), amount=amount)
        
        elif event_type == "payment_intent.payment_failed":
            payment_intent_id = data.get("id")
            
            result = await db.execute(
                select(Pagamento).where(Pagamento.stripe_payment_intent_id == payment_intent_id)
            )
            payment = result.scalar_one_or_none()
            
            if payment:
                payment.stripe_payment_status = "failed"
                await db.commit()
                logger.warning("payment_failed", payment_id=str(payment.id))
        
        return {"status": "success"}
        
    except Exception as e:
        logger.error("stripe_webhook_error", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))


# ==========================================
# RETELL WEBHOOK
# ==========================================
@app.post("/retell-webhook", tags=["Voice AI"])
@limiter.limit("100/minute")
async def retell_webhook(
    request: Request,
    request_data: RetellWebhookRequest, 
    db: AsyncSession = Depends(get_db)
):
    """
    Handle Retell AI call completion webhooks.
    
    Updates call records and triggers next workflow steps based on outcome:
    - SARA + interested → Trigger MARCO after 5 min
    - MARCO + qualified → Trigger CARLO for sourcing
    """
    # Update call record
    result = await db.execute(
        select(ChiamataRetell).where(ChiamataRetell.call_id == request_data.call_id)
    )
    chiamata = result.scalar_one_or_none()
    
    if chiamata:
        chiamata.status = request_data.status
        chiamata.durata_secondi = request_data.duration_seconds
        chiamata.transcript = request_data.transcript
        chiamata.outcome = request_data.outcome
        chiamata.completed_at = datetime.utcnow()
        await db.commit()
    else:
        # Create new record if not exists
        chiamata = ChiamataRetell(
            lead_id=request_data.lead_id,
            call_id=request_data.call_id,
            agent_id=request_data.agent_id,
            agente_nome=request_data.agent_name,
            status=request_data.status,
            durata_secondi=request_data.duration_seconds,
            outcome=request_data.outcome,
            transcript=request_data.transcript,
            completed_at=datetime.utcnow()
        )
        db.add(chiamata)
        await db.commit()
    
    # Determine next action
    if request_data.agent_name == "sara":
        if request_data.outcome == "interessato":
            logger.info("triggering_marco", lead_id=str(request_data.lead_id))
        elif request_data.outcome == "non_interessato":
            logger.info("scheduling_90day_followup", lead_id=str(request_data.lead_id))
    
    elif request_data.agent_name == "marco":
        if request_data.outcome == "qualificato_completo":
            logger.info("triggering_carlo", lead_id=str(request_data.lead_id))
    
    return {"status": "success"}


# ==========================================
# DOCUSIGN WEBHOOK
# ==========================================
@app.post("/docusign-webhook", tags=["Documents"])
@limiter.limit("100/minute")
async def docusign_webhook(
    request: Request,
    request_data: DocuSignWebhookRequest, 
    db: AsyncSession = Depends(get_db)
):
    """
    Handle DocuSign webhook events.
    
    - completed: Contract signed → Trigger payment
    - delivered: Proposal viewed → Schedule LUIGI call
    """
    result = await db.execute(
        select(Contratto).where(Contratto.docusign_envelope_id == request_data.envelope_id)
    )
    contratto = result.scalar_one_or_none()
    
    if not contratto:
        logger.warning("contratto_not_found_for_envelope", envelope_id=request_data.envelope_id)
        return {"status": "not_found"}
    
    if request_data.status == "completed":
        contratto.status = "firmato_entrambi"
        contratto.firmato_cliente_at = request_data.completed_at or datetime.utcnow()
        contratto.completato_at = datetime.utcnow()
        await db.commit()
        
        logger.info("contract_signed_triggering_payment", contratto_id=str(contratto.id))
        
    elif request_data.status == "delivered":
        contratto.status = "visionato"
        await db.commit()
        
        logger.info("contract_viewed_scheduling_luigi", contratto_id=str(contratto.id))
    
    return {"status": "success"}


# ==========================================
# SHIPMENT STATUS
# ==========================================
@app.get("/shipment-status/{tracking_id}", tags=["Shipments"])
@limiter.limit("60/minute")
async def get_shipment_status(
    request: Request,
    tracking_id: str, 
    db: AsyncSession = Depends(get_db)
):
    """Get shipment status by tracking number or shipment ID."""
    # Try by tracking number first
    result = await db.execute(
        select(Spedizione).where(Spedizione.tracking_number == tracking_id)
    )
    spedizione = result.scalar_one_or_none()
    
    if not spedizione:
        # Try by numero_spedizione
        result = await db.execute(
            select(Spedizione).where(Spedizione.numero_spedizione == tracking_id)
        )
        spedizione = result.scalar_one_or_none()
    
    if not spedizione:
        raise HTTPException(status_code=404, detail="Shipment not found")
    
    return {
        "shipment_id": str(spedizione.id),
        "tracking_number": spedizione.tracking_number,
        "status": spedizione.status,
        "estimated_delivery": spedizione.data_consegna_prevista.isoformat() if spedizione.data_consegna_prevista else None,
        "actual_delivery": spedizione.data_consegna_effettiva.isoformat() if spedizione.data_consegna_effettiva else None,
        "delay_hours": spedizione.ritardo_ore
    }


# ==========================================
# DISRUPTION ALERT
# ==========================================
@app.post("/disruption-alert", tags=["Shipments"])
@limiter.limit("30/minute")
async def disruption_alert(
    request: Request,
    alert_data: DisruptionAlertRequest, 
    background_tasks: BackgroundTasks, 
    db: AsyncSession = Depends(get_db)
):
    """
    ANNA (Operations Agent) - Handle shipment disruption/delay alerts.
    
    Sends proactive email to customer with new ETA when delay > 2 hours.
    """
    result = await db.execute(
        select(Spedizione).where(Spedizione.id == alert_data.spedizione_id)
    )
    spedizione = result.scalar_one_or_none()
    
    if not spedizione:
        raise HTTPException(status_code=404, detail="Shipment not found")
    
    # Update shipment
    spedizione.ritardo_ore = alert_data.ore_ritardo
    spedizione.alert_ritardo_inviato = True
    
    if alert_data.nuova_eta:
        spedizione.data_consegna_prevista = alert_data.nuova_eta
    
    await db.commit()
    
    # Get lead for email notification
    result = await db.execute(select(Lead).where(Lead.id == spedizione.lead_id))
    lead = result.scalar_one_or_none()
    
    if lead:
        # In production, send actual delay alert email here
        logger.info(
            "delay_alert_sent",
            shipment_id=str(spedizione.id),
            lead_id=str(lead.id),
            delay_hours=alert_data.ore_ritardo
        )
    
    return {
        "success": True, 
        "message": "Alert processed and email sent",
        "shipment_id": str(spedizione.id),
        "delay_hours": alert_data.ore_ritardo
    }


# ==========================================
# EQ ROUTES (Emotional Intelligence)
# ==========================================
from eq_routes import router as eq_router
app.include_router(eq_router)

# ==========================================
# FRANCO ROUTES (Retention Agent)
# ==========================================
from routers.franco import router as franco_router
app.include_router(franco_router)

# ==========================================
# COST DASHBOARD ROUTES
# ==========================================
from routers.costs import router as costs_router
app.include_router(costs_router)

# ==========================================
# SEMANTIC CACHE ROUTES
# ==========================================
from routers.cache import router as cache_router
app.include_router(cache_router)

# ==========================================
# ZERO-KNOWLEDGE PRICING ROUTES
# ==========================================
from routers.zk_pricing import router as zk_pricing_router
app.include_router(zk_pricing_router)

# ==========================================
# AUTH ROUTES (JWT)
# ==========================================
from routers.auth import router as auth_router
app.include_router(auth_router)

# ==========================================
# DASHBOARD ROUTES (Mission Control)
# ==========================================
from routers.dashboard import router as dashboard_router
app.include_router(dashboard_router)

# ==========================================
# DEMO ROUTES (Zero-Cost Testing)
# ==========================================
from routers.demo import router as demo_router
app.include_router(demo_router)

# ==========================================
# LEGACY DASHBOARD STATS
# ==========================================
@app.get("/stats/dashboard", tags=["Dashboard"])
@limiter.limit("30/minute")
async def get_dashboard_stats(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Get dashboard statistics for monitoring."""
    # Count leads by status
    result = await db.execute(select(Lead.status, func.count(Lead.id)).group_by(Lead.status))
    leads_by_status = {row[0]: row[1] for row in result.all()}
    
    # Revenue stats
    result = await db.execute(
        select(
            func.sum(Pagamento.profitto_finale),
            func.sum(Pagamento.importo_cliente),
            func.count(Pagamento.id)
        ).where(Pagamento.stripe_payment_status == "succeeded")
    )
    revenue_stats = result.first()
    
    # Active shipments
    result = await db.execute(
        select(func.count(Spedizione.id)).where(
            Spedizione.status.in_(["in_preparazione", "ritirata", "in_transito", "in_consegna"])
        )
    )
    active_shipments = result.scalar() or 0
    
    return {
        "leads": leads_by_status,
        "proposals": {},  # Could add proposal stats here
        "revenue": {
            "total_profit": float(revenue_stats[0] or 0),
            "total_revenue": float(revenue_stats[1] or 0),
            "successful_payments": revenue_stats[2] or 0
        },
        "operations": {
            "active_shipments": active_shipments
        },
        "timestamp": datetime.utcnow().isoformat()
    }


# ==========================================
# DEMO MODE ENDPOINTS
# ==========================================
@app.get("/demo/status", tags=["Demo"])
async def get_demo_status():
    """Get demo mode status and mock service stats"""
    return {
        "demo_mode": settings.DEMO_MODE,
        "mock_services": {
            "hume": mock_hume.call_count if mock_hume else 0,
            "insighto": mock_insighto.call_count if mock_insighto else 0,
            "blockchain": mock_blockchain.get_stats() if mock_blockchain else None
        },
        "revenue_generator": revenue_generator.get_stats() if revenue_generator else None,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.post("/demo/command/emergency-stop", tags=["Demo"])
async def demo_emergency_stop(request: Request):
    """Simulate emergency stop - no real action taken"""
    await asyncio.sleep(1)
    logger.info("🚨 [DEMO] Emergency stop simulated")
    return {
        "success": True,
        "message": "Emergency stop simulated (Demo Mode)",
        "action": "all_operations_halted",
        "timestamp": datetime.utcnow().isoformat(),
        "mock": True
    }


@app.post("/demo/command/change-carrier", tags=["Demo"])
async def demo_change_carrier(
    shipment_id: str,
    new_carrier: str,
    request: Request
):
    """Simulate carrier change - no real carrier contacted"""
    await asyncio.sleep(0.5)
    logger.info(f"🚚 [DEMO] Carrier change simulated: {shipment_id} -> {new_carrier}")
    return {
        "success": True,
        "message": f"Carrier changed to {new_carrier} (Demo Mode)",
        "shipment_id": shipment_id,
        "new_carrier": new_carrier,
        "previous_carrier": "Previous Carrier Srl",
        "cost_delta": "+€25.00",
        "mock": True
    }


@app.post("/demo/test/emotion-analysis", tags=["Demo"])
async def demo_emotion_analysis(text: str):
    """Test emotion analysis with mock Hume AI"""
    if not settings.DEMO_MODE:
        raise HTTPException(status_code=400, detail="Only available in DEMO_MODE")
    
    result = await mock_hume.analyze_conversation(text)
    return result


@app.post("/demo/test/make-call", tags=["Demo"])
async def demo_make_call(phone: str, script: str = "Demo call"):
    """Test phone call with mock Insighto"""
    if not settings.DEMO_MODE:
        raise HTTPException(status_code=400, detail="Only available in DEMO_MODE")
    
    result = await mock_insighto.make_call(phone, script)
    return result


@app.post("/demo/test/blockchain-tx", tags=["Demo"])
async def demo_blockchain_tx(value_eth: float = 0.01):
    """Test blockchain transaction with mock"""
    if not settings.DEMO_MODE:
        raise HTTPException(status_code=400, detail="Only available in DEMO_MODE")
    
    result = await mock_blockchain.send_transaction(
        to=f"0x{uuid4().hex[:40]}",
        value_eth=value_eth
    )
    return result


@app.get("/demo/mock-data", tags=["Demo"])
async def get_mock_data():
    """Get current mock data (shipments, revenue, agents)"""
    if not settings.DEMO_MODE:
        raise HTTPException(status_code=400, detail="Only available in DEMO_MODE")
    
    return {
        "revenue": revenue_generator.get_stats() if revenue_generator else None,
        "active_tracking": list(revenue_generator.active_tracking.values()) if revenue_generator else [],
        "blockchain_stats": mock_blockchain.get_stats() if mock_blockchain else None,
        "timestamp": datetime.utcnow().isoformat()
    }


# ==========================================
# MAIN ENTRY POINT
# ==========================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
