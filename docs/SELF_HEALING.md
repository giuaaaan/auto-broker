# Self-Healing Supply Chain

## Overview

Auto-Broker implementa un **sistema auto-recovery** per la supply chain logistica, dove gli agenti AI PAOLO e GIULIA gestiscono autonomamente eccezioni e dispute senza intervento umano nel 95% dei casi.

## Architettura

```
┌─────────────────────────────────────────────────────────────────┐
│                    SELF-HEALING SYSTEM                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────┐      ┌─────────────────────┐           │
│  │   PAOLO Agent       │      │   GIULIA Agent      │           │
│  │   (Carrier Ops)     │◄────►│  (Dispute Resolver) │           │
│  │                     │      │                     │           │
│  │ • Monitor 5min      │      │ • AI Analysis       │           │
│  │ • Auto-failover     │      │ • Auto-resolve      │           │
│  │ • Escrow transfer   │      │ • Fraud detection   │           │
│  └──────────┬──────────┘      └──────────┬──────────┘           │
│             │                            │                      │
│             └────────────┬───────────────┘                      │
│                          │                                      │
│                          ▼                                      │
│              ┌───────────────────────┐                          │
│              │  Swarm Orchestrator   │                          │
│              │  (Event Coordinator)  │                          │
│              └───────────┬───────────┘                          │
│                          │                                      │
│                          ▼                                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Blockchain Layer (Polygon)                  │   │
│  │  ┌───────────────┐    ┌───────────────┐                │   │
│  │  │  CarrierEscrow│    │ POD Contract  │                │   │
│  │  │  • Lock funds │    │  • Disputes   │                │   │
│  │  │  • Transfer   │    │  • Resolution │                │   │
│  │  │  • Release    │    │               │                │   │
│  │  └───────────────┘    └───────────────┘                │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Agenti

### PAOLO (Preventive Automated Operations & Logistics Orchestrator)

**Responsabilità:** Gestione automatica carrier failover

```python
from api.services.agents.paolo_service import get_paolo_agent

paolo = get_paolo_agent()
await paolo.start_monitoring()

# Esegui failover manuale
result = await paolo.execute_failover(
    shipment_id=uuid,
    reason="Carrier performance degraded",
    admin_override=True
)
```

**Flusso Automatico:**
1. **Monitor** → Controlla `on_time_rate` carrier ogni 5 minuti
2. **Detect** → Se rate < 90%, identifica shipment a rischio
3. **Source** → Trova carrier alternativo (< 2h disponibilità)
4. **Execute** → Failover atomico (DB + Blockchain)
5. **Notify** → Email cliente: *"Carrier cambiato, nessun costo aggiuntivo"*

**Pattern Saga per Atomicità:**
```
BEGIN TRANSACTION
  1. Update DB: spedizioni.carrier_id = new_carrier
  2. Insert carrier_changes log
  3. IF blockchain.tx_success:
       COMMIT
     ELSE:
       ROLLBACK DB
       NOTIFY admin
```

### GIULIA (Generative Intelligent Unified Logistics Investigation Agent)

**Responsabilità:** Risoluzione dispute tramite AI

```python
from api.services.agents.giulia_service import get_giulia_agent, DisputeEvent

giulia = get_giulia_agent()

# Webhook handler
event = DisputeEvent(
    dispute_id=uuid4(),
    shipment_id=shipment_uuid,
    initiator="0x...",
    reason="Not delivered",
    claimed_amount=5000.0,
    created_at=datetime.utcnow()
)

resolution = await giulia.handle_dispute_webhook(event)
```

**AI Analysis Pipeline:**
1. **Gather Evidence**
   - POD document da IPFS
   - Tracking history
   - Foto (se disponibili)
   - Firme digitali

2. **AI Verification**
   ```python
   # Analisi firma (OCR + pattern matching)
   signature_score = await analyze_signature_authenticity(evidence)
   
   # Verifica tracking (GPS vs claim)
   delivery_score = await verify_delivery_tracking(evidence, dispute)
   
   # Computer vision per danni
   damage_score = await check_for_damage(evidence.photos)
   ```

3. **Decision Matrix**
   | Confidence | Action | Human Required? |
   |------------|--------|-----------------|
   | > 85% | Auto-resolve | No |
   | 50-85% | Escalate | Yes |
   | < 50% | More evidence | Yes |

4. **Blockchain Resolution**
   ```solidity
   CarrierEscrow.resolveDispute(
       disputeId,
       carrierWins: bool,
       refundAmount: uint256,
       evidenceHash: bytes32,
       aiAnalysisHash: bytes32,
       confidence: uint256
   )
   ```

## Smart Contracts

### CarrierEscrow.sol

**Features:**
- Lock fondi al carrier iniziale
- Atomic transfer a nuovo carrier (failover)
- Release condizionato (delivery + no dispute)
- Refund al shipper

```solidity
// Lock fondi
escrow.lockFunds{value: 1 ether}(
    "SHIP-123",
    carrierAddress,
    7 days  // deadline
);

// Failover atomico (solo PAOLO)
escrow.transferToNewCarrier(
    "SHIP-123",
    newCarrierAddress,
    FailoverReason.CARRIER_DELAY,
    evidenceHash
);

// Risoluzione dispute (solo GIULIA)
escrow.resolveDispute(
    "SHIP-123",
    true,           // carrier wins
    0,              // no refund
    evidenceHash,
    aiHash,
    92              // 92% confidence
);
```

**Human-in-the-Loop:**
- Importi > 10k EUR: richiede approvazione admin per failover
- Importi > 5k EUR o confidence < 85%: richiede human arbitration

## Orchestratore Swarm

Coordina PAOLO e GIULIA per azioni complesse:

```python
from api.services.orchestrator_swarm import get_swarm_orchestrator

orchestrator = get_swarm_orchestrator()
await orchestrator.start()

# Eventi automatici:
# 1. PAOLO failovera carrier → GIULIA monitora dispute
# 2. GIULIA rileva frode pattern → PAOLO blacklist carrier

# Blacklist coordinata
await orchestrator.blacklist_carrier(
    carrier_id=123,
    reason="Fraud pattern detected",
    permanent=False
)
```

**Event-Driven Architecture:**
```python
# PAOLO emette evento
await orchestrator.emit_event(
    event_type="failover_executed",
    source_agent="paolo",
    payload={"carrier_id": 123, "shipment_id": "..."}
)

# Orchestrator route a GIULIA
# Se 3+ failover per stesso carrier → investigazione frode
```

## API Endpoints

### Dashboard
```bash
# Stato sistema
GET /self-healing/status

{
  "status": "operational",
  "agents": {
    "paolo": {"running": true, "check_interval": 300},
    "giulia": {"auto_resolve_threshold": 85}
  },
  "metrics": {
    "active_failovers": 3,
    "resolved_disputes_24h": 12,
    "avg_resolution_time": "4.5 minutes",
    "human_escalation_rate": "5%"
  }
}
```

### Failover Management
```bash
# Storico failover
GET /self-healing/failovers?limit=50

# Esegui failover manuale
POST /self-healing/failover/execute
{
  "shipment_id": "uuid",
  "reason": "Emergency failover",
  "admin_override": true
}

# Override PAOLO (emergenza)
POST /admin/override-paolo
{
  "reason": "False positives detected",
  "duration_minutes": 60
}
```

### Dispute Resolution
```bash
# Storico dispute
GET /self-healing/disputes?only_human=true

# Risoluzione manuale
POST /self-healing/dispute/resolve
{
  "dispute_id": "uuid",
  "carrier_wins": true,
  "refund_amount": 0,
  "admin_notes": "Signature verified authentic"
}

# Override GIULIA
POST /admin/override-giulia
{
  "reason": "Override for testing",
  "duration_minutes": 120
}
```

### Blacklist Management
```bash
# Blacklist carrier
POST /self-healing/admin/blacklist-carrier
{
  "carrier_id": 123,
  "reason": "Repeated fraud pattern",
  "permanent": false
}
```

## Database Models

### CarrierChange
```python
class CarrierChange(Base):
    """Log cambio carrier per audit trail"""
    
    id: UUID
    spedizione_id: UUID          # FK to Spedizione
    vecchio_carrier_id: UUID     # FK to Corriere
    nuovo_carrier_id: UUID       # FK to Corriere
    motivo: str                  # Ragione failover
    eseguito_da: str             # "paolo_agent" | "admin"
    tx_hash: str                 # Blockchain transaction
    success: bool
    rollback_tx_hash: str        # Se rollback
    created_at: datetime
```

### Corriere (estensione)
```python
class Corriere(Base):
    # ... existing fields ...
    
    on_time_rate: Decimal        # Performance %
    affidabilita: int            # 0-100 reputation score
    wallet_address: str          # Ethereum address
```

## Configurazione

### Environment Variables
```bash
# PAOLO
FAILOVER_THRESHOLD=90.0              # % minimo on_time_rate
PAOLO_CHECK_INTERVAL=300             # Secondi (5 min)
FAILOVER_TIMEOUT=30                  # Minuti per trovare replacement
AUTO_FAILOVER_LIMIT=10000            # EUR max senza approvazione

# GIULIA
GIULIA_AUTO_RESOLVE_THRESHOLD=85     # Confidence % per auto-resolve
AUTO_RESOLUTION_LIMIT=5000           # EUR max per auto-resolve
HUMAN_ESCALATION_THRESHOLD=50        # Min confidence per escalation

# Blockchain
CARRIER_ESCROW_ADDRESS=0x...
PAOLO_AGENT_WALLET=0x...
GIULIA_AGENT_WALLET=0x...
```

## Testing

### Unit Tests
```bash
pytest tests/test_paolo_agent.py -v
pytest tests/test_giulia_agent.py -v
```

### Integration Tests
```bash
# Test flusso completo failover
pytest tests/integration/test_self_healing.py::TestEndToEndSelfHealing::test_full_failover_flow -v

# Test atomicità (rollback)
pytest tests/integration/test_self_healing.py::TestFailoverAtomicity::test_rollback_on_blockchain_failure -v

# Test dispute resolution
pytest tests/integration/test_self_healing.py::TestEndToEndSelfHealing::test_full_dispute_resolution_flow -v
```

### E2E Test Scenarios
1. **Carrier Failure** → PAOLO detecta, trova replacement, esegue failover
2. **Fraud Detection** → GIULIA analizza POD falso, rileva frode, flagga carrier
3. **Blockchain Down** → PAOLO rollbacka DB, notifica admin
4. **High Value** → PAOLO/GIULIA escalano a human, non eseguono

## Monitoring

### Metriche Key
```python
# Prometheus metrics
self_healing_failovers_total  # Counter
self_healing_disputes_resolved  # Counter
self_healing_resolution_duration_seconds  # Histogram
self_healing_human_escalation_rate  # Gauge
```

### Alerting
```yaml
# Alert su failover rate alto
- alert: HighFailoverRate
  expr: rate(self_healing_failovers_total[1h]) > 10
  labels:
    severity: warning
  annotations:
    summary: "High carrier failover rate detected"

# Alert su escalation rate alto
- alert: HighHumanEscalation
  expr: self_healing_human_escalation_rate > 20
  labels:
    severity: info
  annotations:
    summary: "More than 20% disputes require human intervention"
```

## Compliance

### Audit Trail
Ogni decisione AI è salvata su blockchain:
- Hash evidence analizzata
- Confidence score
- Reasoning AI
- Timestamp
- Agent wallet address

### GDPR
- Dati personali (firme, foto) su IPFS (encrypted)
- Hash su blockchain (immutable)
- Retention policy: 7 anni

## Roadmap

- **Q2 2026**: Deployment PAOLO in production
- **Q3 2026**: GIULIA con GPT-4 Vision
- **Q4 2026**: Predictive failover (prima del failure)

## Troubleshooting

### PAOLO non failovera
```bash
# Check circuit breaker
curl /self-healing/status | jq .agents.paolo.circuit_breaker_failures

# Verifica threshold
echo $FAILOVER_THRESHOLD  # Dovrebbe essere 90.0
```

### GIULIA sempre in escalation
```bash
# Check confidence threshold
echo $GIULIA_AUTO_RESOLVE_THRESHOLD  # Dovrebbe essere 85

# Verifica Ollama connection
curl $OLLAMA_URL/api/tags
```

### Blockchain tx fallite
```bash
# Check gas price
gas_price=$(curl -s $POLYGON_RPC -X POST ...)
# Se > 500 gwei, usa EIP-1559
```

## Riferimenti

- [Solidity Docs](https://docs.soliditylang.org/)
- [Web3.py](https://web3py.readthedocs.io/)
- [OpenZeppelin Contracts](https://docs.openzeppelin.com/contracts/)