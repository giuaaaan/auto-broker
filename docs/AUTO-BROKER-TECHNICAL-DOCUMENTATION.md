# Auto-Broker Technical Documentation

**Versione:** 1.4.0  
**Data:** 2026-02-15  
**Audience:** Engineers, Architects, DevOps  
**Aggiornamenti:** Confidential Computing (SEV-SNP/TDX), Self-Healing Agents (PAOLO/GIULIA)

---

## 1. System Overview

### 1.1 Architecture Stack

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Presentation Layer                               │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐  │
│  │  HITL Dashboard │  │  Carrier Portal │  │    Shipper Portal (WIP)     │  │
│  │  (React/FastAPI)│  │    (Future)     │  │         (Future)            │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────────────────┤
│                               API Layer (FastAPI)                             │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │  /api/v1/          /api/v1/           /api/v1/          /api/v1/       │  │
│  │  leads            quotes            shipments        tracking          │  │
│  │     │                │                 │                │              │  │
│  │     ▼                ▼                 ▼                ▼              │  │
│  │  ┌──────┐        ┌──────┐         ┌──────┐         ┌──────┐          │  │
│  │  │  EQ  │        │Pricing│        │Blockchain│      │ Carbon │        │  │
│  │  │ Layer│        │Engine│         │ Service  │      │ Calc   │        │  │
│  │  └──┬───┘        └──┬───┘         └────┬─────┘      └──┬─────┘        │  │
│  │     │               │                  │               │              │  │
│  │  ┌──┴───────────────┴──────────────────┴───────────────┴──┐           │  │
│  │  │              Services Layer (Business Logic)            │           │  │
│  │  └─────────────────────────────────────────────────────────┘           │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────────────────┤
│                              Data Layer                                       │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐  │
│  │  PostgreSQL 15  │  │  Redis 7        │  │  ChromaDB / JSONB           │  │
│  │  + pgvector     │  │  Cluster        │  │  Vector Storage             │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────────────────┤
│                          External Integrations                                │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐  │
│  │   SAP    │ │ NetSuite │ │Dynamics  │ │  DAT iQ  │ │     Polygon      │  │
│  │S/4HANA   │ │  RESTlet│  │  365     │ │ WebSocket│ │   Blockchain     │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────────────┘  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐  │
│  │  Hume AI        │  │  Ollama Local   │  │  HashiCorp Vault            │  │
│  │  Prosody API    │  │  LLM Fallback   │  │  Secret Management          │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Core Components

### 2.1 EQ Emotional Intelligence Layer

#### Sentiment Analysis Service

```python
# api/services/eq_sentiment_service.py
class SentimentService:
    """
    Three-tier sentiment analysis with graceful degradation:
    1. Hume AI Prosody API (voice emotion analysis)
    2. Ollama Local LLM (text-based sentiment)
    3. Italian keyword regex (guaranteed fallback)
    """
    
    async def analyze(self, recording_url: str, transcription: str, lead_id: int) -> Dict:
        """
        Analyze sentiment from voice recording and/or transcription.
        
        Args:
            recording_url: URL to audio recording (for Hume AI)
            transcription: Text transcription (for Ollama/keywords)
            lead_id: Lead identifier for caching/context
            
        Returns:
            Dict with sentiment scores, emotions, confidence
            
        Raises:
            SentimentAnalysisError: If all tiers fail
        """
        # Check Hume quota and circuit breaker
        quota = await self.check_hume_quota()
        
        # Tier 1: Hume AI
        if recording_url and quota.get("remaining_minutes", 0) > 0:
            try:
                return await self.hume_breaker.call(
                    self._analyze_hume, recording_url, lead_id
                )
            except Exception as e:
                logger.warning(f"Hume failed: {e}")
        
        # Tier 2: Ollama Local LLM
        if transcription:
            try:
                return await self.ollama_breaker.call(
                    self._analyze_ollama, transcription, lead_id
                )
            except Exception as e:
                logger.warning(f"Ollama failed: {e}")
        
        # Tier 3: Keyword fallback (guaranteed)
        return self._analyze_keywords(transcription, lead_id)
```

#### Circuit Breaker Implementation

```python
# api/services/circuit_breaker.py
class CircuitBreaker:
    """
    Netflix-style circuit breaker for resilient external API calls.
    
    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Failure threshold exceeded, requests fail fast
    - HALF_OPEN: Testing if service recovered
    """
    
    def __init__(self, name: str, failure_threshold: int = 5,
                 recovery_timeout: int = 30, half_open_max_calls: int = 3):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self._state = CircuitState.CLOSED
        self._lock = asyncio.Lock()
        
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""
        async with self._lock:
            if self._state == CircuitState.OPEN:
                if time.time() - self._last_failure_time > self.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                else:
                    raise CircuitBreakerOpenError(f"Circuit {self.name} is OPEN")
        
        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except Exception as e:
            await self._on_failure()
            raise e
```

### 2.2 ERP Connectors

#### SAP S/4HANA Adapter

```python
# connectors/erp/sap_s4hana_adapter.py
class SAPS4HANAAdapter(BaseERPAdapter):
    """
    SAP S/4HANA OData v4 adapter with circuit breaker protection.
    
    Features:
    - Bidirectional sync (inbound/outbound)
    - Conflict resolution (timestamp/version/manual)
    - Transaction journaling for audit
    - Automatic retry with exponential backoff
    """
    
    SYSTEM_NAME = "sap_s4hana"
    BASE_URL = "https://sap-s4hana.company.com/sap/opu/odata/sap/API_BUSINESS_PARTNER"
    
    async def sync_customer(self, customer_id: str, direction: str) -> SyncResult:
        """
        Sync customer data between Auto-Broker and SAP.
        
        Args:
            customer_id: External customer identifier
            direction: 'inbound' (SAP→AB) or 'outbound' (AB→SAP)
            
        Returns:
            SyncResult with status, changes, conflicts
        """
        if direction == "inbound":
            sap_data = await self._fetch_sap_customer(customer_id)
            local_data = await self._fetch_local_customer(customer_id)
            
            # Conflict detection
            if sap_data["last_modified"] > local_data["last_modified"]:
                resolution = await self._resolve_conflict(sap_data, local_data)
                return await self._apply_resolution(resolution)
        
        elif direction == "outbound":
            return await self._push_to_sap(customer_id)
    
    async def _fetch_sap_customer(self, customer_id: str) -> Dict:
        """Fetch customer from SAP with circuit breaker."""
        url = f"{self.BASE_URL}/A_BusinessPartner('{customer_id}')"
        return await self.circuit_breaker.call(
            self._odata_request, "GET", url
        )
```

#### Sync Orchestrator

```python
# connectors/erp/sync_orchestrator.py
class SyncOrchestrator:
    """
    Central coordinator for multi-ERP synchronization.
    
    Manages:
    - Adapter registration
    - Conflict resolution strategies
    - Transaction journaling
    - Failed change queue
    """
    
    def __init__(self, db_pool, redis_client):
        self.adapters: Dict[str, BaseERPAdapter] = {}
        self.db = db_pool
        self.redis = redis_client
        self.conflict_strategies = {
            "timestamp_wins": TimestampWinsStrategy(),
            "version_wins": VersionWinsStrategy(),
            "manual_queue": ManualQueueStrategy(),
        }
    
    def register_adapter(self, adapter: BaseERPAdapter):
        """Register an ERP adapter."""
        self.adapters[adapter.system_name] = adapter
    
    async def sync_all(self, entity_type: str, entity_id: str):
        """Sync entity across all registered ERPs."""
        results = {}
        for name, adapter in self.adapters.items():
            try:
                result = await adapter.sync_entity(entity_type, entity_id)
                results[name] = result
            except Exception as e:
                logger.error(f"Sync failed for {name}: {e}")
                results[name] = SyncResult(status="failed", error=str(e))
        return results
```

### 2.3 Pricing Engine V2

```python
# pricing/pricing_engine_v2.py
class PricingEngineV2:
    """
    Market-based dynamic pricing engine.
    
    Formula: Final Price = Base Cost + Margin + Market Adjustment
    
    Strategies:
    - market_based: Use DAT iQ benchmark rates
    - cost_plus: Base cost + fixed margin
    - competitive: Match/beat competitor rates
    - value_based: Price based on customer value
    """
    
    STRATEGIES = {
        "market_based": MarketBasedStrategy(),
        "cost_plus": CostPlusStrategy(),
        "competitive": CompetitiveStrategy(),
        "value_based": ValueBasedStrategy(),
    }
    
    async def calculate_quote(
        self,
        route: Route,
        cargo: Cargo,
        strategy: str = "market_based"
    ) -> Quote:
        """
        Calculate shipping quote with confidence intervals.
        
        Args:
            route: Origin/destination with distance
            cargo: Weight, dimensions, type
            strategy: Pricing strategy to use
            
        Returns:
            Quote with price, confidence interval, factors
        """
        # Get base cost from internal calculation
        base_cost = await self._calculate_base_cost(route, cargo)
        
        # Get market data if strategy requires
        market_data = None
        if strategy in ["market_based", "competitive"]:
            market_data = await self.dat_iq_client.get_rate(
                route.origin, route.destination, cargo
            )
        
        # Apply strategy
        strategy_impl = self.STRATEGIES[strategy]
        price = await strategy_impl.calculate(
            base_cost=base_cost,
            market_data=market_data,
            cargo=cargo
        )
        
        # Calculate confidence interval (95%)
        confidence = self._calculate_confidence(price, market_data)
        
        return Quote(
            price=price,
            confidence_low=confidence.low,
            confidence_high=confidence.high,
            strategy=strategy,
            factors={
                "base_cost": base_cost,
                "market_adjustment": price - base_cost,
                "dat_iq_rate": market_data.current_rate if market_data else None,
            }
        )
```

### 2.4 Blockchain Integration

```solidity
// blockchain/pod_smart_contract.sol
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

/**
 * @title PODSmartContract
 * @notice Proof of Delivery verification on Polygon
 * @dev Multi-signature verification with dispute resolution
 */
contract PODSmartContract {
    enum DeliveryStatus { Pending, PickedUp, InTransit, Delivered, Disputed }
    
    struct Delivery {
        bytes32 documentHash;      // Hash of POD document
        bytes32 ipfsHash;          // IPFS location of document
        address carrier;           // Carrier wallet address
        address consignee;         // Consignee wallet address
        DeliveryStatus status;
        uint256 timestamp;
        bytes carrierSignature;
        bytes consigneeSignature;
    }
    
    mapping(string => Delivery) public deliveries;
    mapping(string => Dispute) public disputes;
    
    event DeliveryCreated(string deliveryId, address carrier);
    event DeliveryConfirmed(string deliveryId, address confirmer);
    event DisputeOpened(string deliveryId, string reason);
    event DisputeResolved(string deliveryId, bool carrierWins);
    
    /**
     * @notice Create new delivery record
     * @param deliveryId Unique identifier
     * @param documentHash Hash of POD document
     * @param ipfsHash IPFS hash for document storage
     * @param consignee Consignee wallet address
     */
    function createDelivery(
        string memory deliveryId,
        bytes32 documentHash,
        bytes32 ipfsHash,
        address consignee
    ) external {
        require(deliveries[deliveryId].timestamp == 0, "Delivery exists");
        
        deliveries[deliveryId] = Delivery({
            documentHash: documentHash,
            ipfsHash: ipfsHash,
            carrier: msg.sender,
            consignee: consignee,
            status: DeliveryStatus.Pending,
            timestamp: block.timestamp,
            carrierSignature: "",
            consigneeSignature: ""
        });
        
        emit DeliveryCreated(deliveryId, msg.sender);
    }
    
    /**
     * @notice Complete delivery with signatures
     * @param deliveryId Delivery identifier
     * @param signature ECDSA signature from carrier
     */
    function completeDelivery(
        string memory deliveryId,
        bytes memory signature
    ) external {
        Delivery storage delivery = deliveries[deliveryId];
        require(delivery.carrier == msg.sender, "Only carrier");
        require(delivery.status != DeliveryStatus.Delivered, "Already delivered");
        
        // Verify signature
        bytes32 messageHash = keccak256(abi.encodePacked(deliveryId));
        require(
            ECDSA.recover(messageHash, signature) == msg.sender,
            "Invalid signature"
        );
        
        delivery.carrierSignature = signature;
        delivery.status = DeliveryStatus.Delivered;
        
        emit DeliveryConfirmed(deliveryId, msg.sender);
    }
}
```

### 2.5 Carbon Calculator

```python
# carbon/glec_calculator.py
class GLECCalculator:
    """
    GLEC Framework v3.0 / ISO 14083:2023 carbon emissions calculator.
    
    Calculates Well-to-Wheel (WTW) emissions including:
    - Fuel production and distribution (upstream)
    - Vehicle operation (tank-to-wheel)
    """
    
    # Emission factors kg CO2e per ton-km
    EMISSION_FACTORS = {
        "road_hgv_diesel": 0.072,
        "road_hgv_electric": 0.018,
        "rail_electric": 0.018,
        "sea_container": 0.020,
        "air_cargo": 0.602,
    }
    
    # Well-to-tank factors (fuel production)
    WTT_FACTORS = {
        "diesel": 0.18,
        "electric": 0.45,  # Grid mix EU average
        "marine_fuel": 0.15,
        "jet_fuel": 0.20,
    }
    
    async def calculate_shipment_emissions(
        self,
        shipment_id: str,
        legs: List[TransportLeg]
    ) -> EmissionResult:
        """
        Calculate total emissions for multi-leg shipment.
        
        Args:
            shipment_id: Unique shipment identifier
            legs: List of transport legs with mode, distance, weight
            
        Returns:
            EmissionResult with total, breakdown, intensity
        """
        total_emissions = 0.0
        breakdown = []
        
        for leg in legs:
            # Get emission factor for transport mode
            factor = self.EMISSION_FACTORS.get(leg.transport_mode)
            if not factor:
                raise ValueError(f"Unknown transport mode: {leg.transport_mode}")
            
            # Calculate TTW (Tank-to-Wheel)
            ttw = factor * leg.distance_km * (leg.weight_kg / 1000)
            
            # Calculate WTT (Well-to-Tank)
            fuel_type = self._get_fuel_type(leg.transport_mode)
            wtt_factor = self.WTT_FACTORS.get(fuel_type, 0)
            wtt = ttw * wtt_factor
            
            # Total WTW
            leg_emissions = ttw + wtt
            total_emissions += leg_emissions
            
            breakdown.append({
                "leg_id": leg.id,
                "mode": leg.transport_mode,
                "distance": leg.distance_km,
                "weight": leg.weight_kg,
                "ttw": ttw,
                "wtt": wtt,
                "total": leg_emissions,
            })
        
        # Calculate intensity (g CO2e per ton-km)
        total_ton_km = sum(
            leg.distance_km * (leg.weight_kg / 1000) for leg in legs
        )
        intensity = (total_emissions * 1000) / total_ton_km if total_ton_km > 0 else 0
        
        return EmissionResult(
            shipment_id=shipment_id,
            total_kg_co2e=total_emissions,
            intensity_g_per_ton_km=intensity,
            breakdown=breakdown,
            methodology="GLEC_v3.0_ISO_14083_2023",
            calculated_at=datetime.utcnow(),
        )
```

---

## 3. Database Schema

### 3.1 Core Tables

```sql
-- Leads with sentiment analysis
CREATE TABLE leads (
    id SERIAL PRIMARY KEY,
    company_name VARCHAR(255) NOT NULL,
    contact_email VARCHAR(255) NOT NULL,
    phone VARCHAR(50),
    transcription TEXT,
    sentiment_score DECIMAL(4,3),
    bant_c_profile JSONB,
    psychological_profile JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX CONCURRENTLY idx_leads_sentiment ON leads(sentiment_score) 
WHERE sentiment_score IS NOT NULL;

CREATE INDEX CONCURRENTLY idx_leads_bant_c ON leads USING GIN (bant_c_profile);

-- AI decisions audit log (append-only, GDPR Article 22)
CREATE TABLE ai_decisions (
    id BIGSERIAL PRIMARY KEY,
    decision_type VARCHAR(50) NOT NULL,
    lead_id INTEGER REFERENCES leads(id),
    input_data JSONB NOT NULL,
    output_data JSONB NOT NULL,
    confidence_score DECIMAL(4,3),
    model_version VARCHAR(50),
    human_reviewed BOOLEAN DEFAULT FALSE,
    human_override JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
) PARTITION BY RANGE (created_at);

-- Monthly partitions
CREATE TABLE ai_decisions_2026_02 PARTITION OF ai_decisions
    FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');

CREATE INDEX CONCURRENTLY idx_ai_decisions_lead ON ai_decisions(lead_id, created_at DESC);

-- ERP unapplied changes queue
CREATE TABLE unapplied_changes (
    id SERIAL PRIMARY KEY,
    system_name VARCHAR(50) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    entity_id VARCHAR(100) NOT NULL,
    change_data JSONB NOT NULL,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    next_retry_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX CONCURRENTLY idx_unapplied_system ON unapplied_changes(system_name, next_retry_at);

-- Blockchain transaction queue
CREATE TABLE blockchain_queue (
    id SERIAL PRIMARY KEY,
    delivery_id VARCHAR(100) NOT NULL,
    tx_type VARCHAR(50) NOT NULL,
    tx_data JSONB NOT NULL,
    tx_hash VARCHAR(100),
    status VARCHAR(20) DEFAULT 'pending',
    gas_price_wei BIGINT,
    retry_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    submitted_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX CONCURRENTLY idx_blockchain_status ON blockchain_queue(status, retry_count);
```

### 3.2 Vector Storage Fallback

```python
# Fallback when pgvector unavailable - JSONB vector storage
{
    "embedding_id": "uuid",
    "vector": [0.1, 0.2, 0.3, ...],  -- 384 dimensions
    "metadata": {
        "lead_id": 123,
        "text": "original text",
        "created_at": "2026-02-14T10:00:00Z"
    },
    "similarity_search": "cosine"  -- calculated at query time
}

-- Query example
SELECT id, vector, metadata,
       (vector <-> query_vector) AS distance
FROM embeddings
WHERE metadata->>'lead_id' = '123'
ORDER BY distance
LIMIT 10;
```

---

## 4. API Reference

### 4.1 Authentication

```bash
# OAuth 2.0 flow
curl -X POST https://api.auto-broker.com/oauth/token \
  -d "grant_type=client_credentials" \
  -d "client_id=$CLIENT_ID" \
  -d "client_secret=$CLIENT_SECRET"

# Response
{
  "access_token": "eyJhbGciOiJSUzI1NiIs...",
  "token_type": "Bearer",
  "expires_in": 3600
}
```

### 4.2 Key Endpoints

#### Sentiment Analysis
```bash
POST /api/v1/eq/sentiment
Content-Type: application/json
Authorization: Bearer $TOKEN

{
  "recording_url": "https://storage.example.com/call-123.wav",
  "transcription": "Buongiorno, vorrei un preventivo per una spedizione",
  "lead_id": 456
}

# Response
{
  "sentiment": "positive",
  "score": 0.82,
  "emotions": {
    "joy": 0.45,
    "confidence": 0.78
  },
  "confidence": 0.91,
  "tier": "hume",
  "processing_time_ms": 245
}
```

#### Pricing Quote
```bash
POST /api/v1/pricing/quote
Content-Type: application/json
Authorization: Bearer $TOKEN

{
  "origin": {"lat": 45.4642, "lon": 9.1900, "country": "IT"},
  "destination": {"lat": 48.8566, "lon": 2.3522, "country": "FR"},
  "cargo": {
    "weight_kg": 5000,
    "volume_m3": 15,
    "type": "general"
  },
  "strategy": "market_based"
}

# Response
{
  "quote_id": "q-abc123",
  "price": {
    "amount": 1250.00,
    "currency": "EUR"
  },
  "confidence": {
    "low": 1150.00,
    "high": 1350.00,
    "level": 0.95
  },
  "factors": {
    "base_cost": 1000.00,
    "market_adjustment": 250.00,
    "dat_iq_rate": 1200.00
  },
  "valid_until": "2026-02-15T14:00:00Z"
}
```

#### POD Blockchain Verification
```bash
POST /api/v1/blockchain/pod
Content-Type: application/json
Authorization: Bearer $TOKEN

{
  "shipment_id": "SH-2026-001",
  "document_hash": "0xabc123...",
  "ipfs_hash": "QmXyz789...",
  "carrier_signature": "0xdef456..."
}

# Response
{
  "tx_hash": "0xghi789...",
  "block_number": 45612378,
  "gas_used": 125000,
  "gas_price_gwei": 25,
  "status": "confirmed",
  "confirmations": 12
}
```

---

## 4.8 Confidential Computing Architecture

### 4.8.1 TEE (Trusted Execution Environment)

Supporto per AMD SEV-SNP e Intel TDX:

```yaml
# Kubernetes RuntimeClass per enclaves
apiVersion: node.k8s.io/v1
kind: RuntimeClass
metadata:
  name: kata-cc-amd-sev
handler: kata-cc
scheduling:
  nodeSelector:
    confidential-computing: "amd-sev-snp"
```

### 4.8.2 Remote Attestation Flow

```
Enclave Boot → Generate Report → Vault Verify → Secrets Provisioned
     ↓              ↓                ↓                ↓
  SEV-SNP      Measurement      Signature       Wrapped Keys
```

### 4.8.3 Agenti in Enclave

- **SARA/MARCO/FRANCO**: Processamento chiamate in TEE
- **Memory Encryption**: Dati in RAM cifrati (host non può leggere)
- **No Disk Logging**: Solo stdout, nessuna persistenza su filesystem

### 4.8.4 Vault Integration

```python
# api/services/enclave_attestation.py
attestation = EnclaveAttestation(mode="sev-snp")
report = attestation.get_attestation_report()
secrets = await attestation.provision_secrets(report, ["hume/api-key"])
```

---

## 4.9 Self-Healing Supply Chain

### 4.9.1 PAOLO Agent (Carrier Failover)

**Monitoraggio:** Ogni 5 minuti verifica `on_time_rate` carrier
**Pattern Saga:**
```
BEGIN
  UPDATE DB: cambia carrier_id
  INSERT: carrier_changes log
  IF blockchain_tx_success:
    COMMIT
  ELSE:
    ROLLBACK DB
    ALERT admin
```

**Human-in-the-loop:**
- Importo > €10k: richiede approvazione admin
- Timeout 30min senza replacement: escalation

### 4.9.2 GIULIA Agent (Dispute Resolution)

**AI Analysis Pipeline:**
1. OCR firma su POD → `signature_authentic` score
2. GPS tracking vs claim → `delivery_verified` score
3. Computer vision foto → `damage_visible` score

**Decision Matrix:**
| Confidence | Action | Human Required |
|------------|--------|----------------|
| > 85% | Auto-resolve | No |
| 50-85% | Escalate | Yes |
| < 50% | More evidence | Yes |

### 4.9.3 CarrierEscrow Smart Contract

```solidity
// Failover atomico (solo PAOLO)
function transferToNewCarrier(
    string memory shipmentId,
    address newCarrier,
    FailoverReason reason,
    bytes32 evidenceHash
) external onlyPaoloAgent;

// Risoluzione dispute (solo GIULIA)
function resolveDispute(
    string memory shipmentId,
    bool carrierWins,
    uint256 refundAmount,
    bytes32 evidenceHash,
    uint256 confidence
) external onlyGiuliaAgent;
```

### 4.9.4 Orchestratore Swarm

Coordina PAOLO e GIULIA via event-driven architecture:
- PAOLO failovera → GIULIA monitora dispute aumentate
- GIULIA rileva frode → PAOLO blacklist carrier

---

## 5. Deployment

### 5.1 Docker Compose (Development)

```yaml
# docker-compose.yml
version: '3.8'

services:
  api:
    build:
      context: ./api
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@postgres:5432/auto_broker
      - REDIS_URL=redis://redis:6379
      - VAULT_ADDR=http://vault:8200
    depends_on:
      - postgres
      - redis
      - vault
    networks:
      - auto-broker

  postgres:
    image: postgres:15-alpine
    environment:
      - POSTGRES_DB=auto_broker
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    networks:
      - auto-broker

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    networks:
      - auto-broker

  vault:
    image: hashicorp/vault:1.18
    cap_add:
      - IPC_LOCK
    environment:
      - VAULT_DEV_ROOT_TOKEN_ID=dev-token
    ports:
      - "8200:8200"
    networks:
      - auto-broker

volumes:
  postgres_data:
  redis_data:

networks:
  auto-broker:
    driver: bridge
```

### 5.2 Kubernetes (Production)

```yaml
# k8s/api-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: auto-broker-api
  namespace: auto-broker
spec:
  replicas: 3
  selector:
    matchLabels:
      app: auto-broker-api
  template:
    metadata:
      labels:
        app: auto-broker-api
    spec:
      containers:
      - name: api
        image: auto-broker/api:v9.5.0
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: db-credentials
              key: url
        - name: VAULT_TOKEN
          valueFrom:
            secretKeyRef:
              name: vault-credentials
              key: token
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
```

---

## 6. Testing

### 6.1 Test Structure

```
tests/
├── unit/                    # Unit tests (< 10s)
│   ├── services/
│   │   ├── test_circuit_breaker.py
│   │   ├── test_eq_sentiment.py
│   │   ├── test_pricing_engine.py
│   │   ├── test_franco_service.py      # NEW
│   │   ├── test_cost_tracker.py        # NEW
│   │   └── test_semantic_cache.py      # NEW
│   ├── connectors/
│   │   ├── test_sap_adapter.py
│   │   └── test_netsuite_adapter.py
│   └── security/
│       ├── test_pii_masking.py
│       └── test_vault_client.py
├── integration/             # Integration tests (~ 60s)
│   ├── test_main_complete.py
│   ├── test_erp_sync.py
│   └── test_blockchain.py
├── contract/                # API contract tests
│   └── test_api_contracts.py
├── e2e/                     # End-to-end tests
│   └── test_full_flow.py
└── mutation/                # Mutation testing
    └── test_mutation.py
```

### 6.2 Running Tests

```bash
# Unit tests only (fast)
pytest tests/unit -xvs --cov=api --cov-report=term-missing

# Integration tests
pytest tests/integration -xvs --timeout=60

# Full test suite with coverage
pytest --cov=api --cov-report=html --cov-fail-under=95

# Specific test
pytest tests/unit/services/test_circuit_breaker.py::TestCircuitBreaker::test_state_transitions -xvs
```

---

## 7. Monitoring & Debugging

### 7.1 Health Check Endpoints

```bash
# Basic health
curl http://localhost:8000/health

{
  "status": "healthy",
  "components": {
    "database": "connected",
    "redis": "connected",
    "vault": "connected"
  },
  "timestamp": "2026-02-14T14:30:00Z"
}

# Detailed metrics
curl http://localhost:8000/metrics

{
  "requests": {
    "total": 15234,
    "errors": 23,
    "latency_p95_ms": 245
  },
  "circuit_breakers": {
    "hume_api": "CLOSED",
    "ollama": "CLOSED",
    "sap_adapter": "CLOSED",
    "dat_iq": "CLOSED"
  },
  "database": {
    "connections_active": 12,
    "connections_idle": 8,
    "query_time_avg_ms": 15
  }
}
```

### 7.2 Common Issues

#### Circuit Breaker Open
```bash
# Check circuit breaker status
redis-cli get circuit_breaker:hume_api

# Force reset (emergency only)
redis-cli del circuit_breaker:hume_api

# Check logs
docker logs auto-broker-api-1 | grep -i "circuit\|hume"
```

#### Database Connection Pool Exhausted
```bash
# Check active connections
psql -c "SELECT count(*), state FROM pg_stat_activity GROUP BY state;"

# Check for idle connections
psql -c "SELECT pid, usename, state, query_start FROM pg_stat_activity WHERE state = 'idle in transaction';"

# Restart connection pool (graceful)
curl -X POST http://localhost:8000/admin/reset-db-pool
```

---

## 8. Additional Components

### 8.1 Semantic Cache Service

```python
# api/services/semantic_cache.py
class SemanticCacheService:
    """
    Cache semantica per Hume AI con 90% cost reduction.
    
    Model: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
    Dimensions: 384
    Similarity threshold: 0.95 (cosine)
    """
    
    async def get_or_compute(
        self,
        transcription: str,
        compute_func: Callable,
        shipment_id: Optional[UUID] = None,
        customer_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Recupera da cache o computa sentiment analysis.
        
        Returns:
            {
                "sentiment_score": 0.82,
                "emotions": {...},
                "source": "cache" | "hume",
                "cache_hit": True | False,
                "cache_type": "exact" | "semantic"
            }
        """
```

### 8.2 Cost Tracker

```python
# api/services/cost_tracker.py
class CostTracker:
    """
    Tracciamento costi granulari per spedizione.
    Precisione: 6 decimali (micro-transazioni)
    """
    
    async def track_event(
        self,
        event_type: str,  # "hume_api_call", "blockchain_tx", etc.
        shipment_id: UUID,
        cost_eur: Decimal,  # 0.000001 precision
        provider: str
    ) -> CostEvent
```

### 8.3 FRANCO Retention Agent

```python
# api/services/franco_service.py
class FrancoService:
    """
    Retention Agent per chiamate 7 giorni post-consegna.
    
    Rate limiting: 10 chiamate/ora
    Idempotenza: deduplicazione per spedizione_id
    """
    
    async def process_retention(self) -> Dict[str, Any]:
        """
        Processa spedizioni consegnate 7 giorni fa.
        
        Returns:
            {
                "processed": 5,
                "successful_calls": 4,
                "failed_calls": 1,
                "skipped": 0
            }
        """
```

---

## 9. Security Checklist

### 9.1 Pre-Deployment

- [ ] All secrets in Vault (no env vars for secrets)
- [ ] PII masking enabled in logs
- [ ] mTLS configured in Istio
- [ ] Network policies applied (deny-by-default)
- [ ] Security scan passed (Trivy: no CRITICAL/HIGH)
- [ ] Rate limiting configured
- [ ] CORS properly restricted
- [ ] Input validation on all endpoints

### 8.2 Runtime

- [ ] Audit logging enabled
- [ ] GDPR Article 22 decisions logged
- [ ] Vault leases renewed correctly
- [ ] Certificate expiration monitored
- [ ] RBAC permissions minimal
- [ ] Container running as non-root

---

## Version History

### v1.3.0 (2026-02-15)
- Aggiunti Semantic Cache, Cost Tracker, FRANCO Agent
- Documentazione completa nuovi servizi
- Test references aggiornate
- API examples per /cache, /costs, /franco

### v1.2.0 (2026-02-14)
- Aggiunti componenti Business Layer
- Documentazione ERP connectors completa
- Aggiunti esempi API blockchain e carbon
- Aggiornati deployment manifests

### v1.1.0 (2026-02-01)
- Business Layer initial documentation
- Pricing engine V2 docs

### v1.0.0 (2026-01-15)
- Initial technical documentation
- EQ Layer documentation
