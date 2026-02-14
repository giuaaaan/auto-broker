# Auto-Broker Platform Engineering Document

**Versione:** 2.5.0  
**Data:** 2026-02-15  
**Stato:** Aggiornato con Confidential Computing, Self-Healing Supply Chain, ZK Pricing

---

## 1. Architecture Vision

### 1.1 Vision Statement

> "Costruire la piattaforma logistica più intelligente, sicura e sostenibile d'Europa, capaci di orchestrare supply chain complesse con intelligenza artificiale emotional-aware, compliance automatica e tracciabilità blockchain garantita."

### 1.2 Architectural Principles

1. **Resilience by Design:** Ogni componente deve degradare graceful, mai fallire catastrophic
2. **Zero Trust Security:** Trust nothing, verify everything - ogni richiesta autenticata e autorizzata
3. **Compliance as Code:** GDPR, eFTI, CSRD implementati programmaticamente, mai manuali
4. **Observability First:** Ogni componente emette metriche, log strutturati, tracing distribuito
5. **Cloud Native:** Container-first, Kubernetes-ready, infrastructure as code

### 1.3 System Context (C4 Level 1)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Auto-Broker System                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐           │
│    │  Shipper │    │  Carrier │    │   ERP    │    │  Market  │           │
│    │  Portal  │    │  Portal  │    │ Systems  │    │  Data    │           │
│    └────┬─────┘    └────┬─────┘    └────┬─────┘    └────┬─────┘           │
│         │               │               │               │                  │
│         └───────────────┴───────┬───────┴───────────────┘                  │
│                                 │                                           │
│                    ┌────────────▼────────────┐                              │
│                    │    Auto-Broker API      │                              │
│                    │    (FastAPI/Python)     │                              │
│                    └────────────┬────────────┘                              │
│                                 │                                           │
│    ┌──────────┐    ┌──────────┐┌┴┐┌──────────┐    ┌──────────┐            │
│    │ PostgreSQL│    │  Redis   ││ ││ ChromaDB │    │  Vault   │            │
│    │  +pgvect │    │  Cache   ││ ││  Vector  │    │ Secrets  │            │
│    └──────────┘    └──────────┘│ │└──────────┘    └──────────┘            │
│                                │ │                                          │
│    ┌──────────┐    ┌──────────┐│ │┌──────────┐    ┌──────────┐            │
│    │  Polygon │    │  DAT iQ  ││ ││  Hume AI │    │  Ollama  │            │
│    │Blockchain│    │ Market   ││ ││ Emotional│    │  Local   │            │
│    └──────────┘    └──────────┘│ ││  Intelligence  │    │   LLM    │            │
│                                │ │└──────────┘    └──────────┘            │
│    ┌──────────┐    ┌──────────┐│ │                                          │
│    │   SAP    │    │ NetSuite ││ │                                          │
│    │S/4HANA   │    │          ││ │                                          │
│    └──────────┘    └──────────┘│ │                                          │
│                                │ │                                          │
│    ┌───────────────────────────┴─┴───────────────────────────┐             │
│    │              Enterprise Security Layer                   │             │
│    │  • Istio mTLS    • Vault Dynamic Secrets  • PII Masking │             │
│    └─────────────────────────────────────────────────────────┘             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Component Architecture (C4 Level 2)

### 2.1 Container Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Auto-Broker Platform                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                         API Gateway (Istio Ingress)                      │ │
│  │                    mTLS termination, Rate limiting, Auth                 │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                    │                                        │
│  ┌─────────────────────────────────┼──────────────────────────────────────┐ │
│  │                                 ▼                                      │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐ │ │
│  │  │   EQ Layer   │  │  Business    │  │   Security   │  │ Compliance │ │ │
│  │  │              │  │    Layer     │  │              │  │            │ │ │
│  │  │• Sentiment   │  │• ERP Connect │  │• Vault Client│  │• GDPR Audit│ │ │
│  │  │• Profiling   │  │• Pricing Eng │  │• PII Masking │  │• eFTI Gen  │ │ │
│  │  │• Persuasion  │  │• Blockchain  │  │• RBAC Matrix │  │• CSRD Rep  │ │ │
│  │  │              │  │• Carbon Calc │  │              │  │            │ │ │
│  │  │Circuit       │  │              │  │              │  │            │ │ │
│  │  │Breaker       │  │              │  │              │  │            │ │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  └────────────┘ │ │
│  │                                                                         │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                   │ │
│  │  │  Market      │  │   Chaos      │  │    HITL      │                   │ │
│  │  │  Intelligence│  │ Engineering  │  │  Dashboard   │                   │ │
│  │  │              │  │              │  │              │                   │ │
│  │  │• DAT iQ      │  │• Experiments │  │• Human-in-the│                   │ │
│  │  │• Teleroute   │  │• Failure Inj │  │  Loop Review │                   │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘                   │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                         Data Layer                                       │ │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐                │ │
│  │  │PostgreSQL│  │  Redis   │  │ ChromaDB │  │  Vault   │                │ │
│  │  │ 15 +     │  │ Cluster  │  │ Vector   │  │  HA      │                │ │
│  │  │pgvector  │  │  3 nodes │  │ Storage  │  │  Mode    │                │ │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘                │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                      External Integrations                               │ │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │ │
│  │  │   SAP    │  │ NetSuite │  │Dynamics  │  │  DAT iQ  │  │  Polygon │ │ │
│  │  │S/4HANA   │  │  RESTlet│  │  365     │  │ WebSocket│  │   PoS    │ │ │
│  │  │ OData v4 │  │   v2    │  │ OData v4 │  │  Stream  │  │   Chain  │ │ │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘ │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Technical Standards

### 3.1 Code Standards

| Standard | Implementazione | Enforcement |
|----------|-----------------|-------------|
| Python | 3.14+ with type hints | mypy strict |
| Async/Await | Tutte le I/O operations | pylint async checks |
| Testing | pytest-asyncio, 95% coverage | CI gate |
| Documentation | Google docstrings, ADRs | mkdocs build |
| Linting | ruff, black | pre-commit hooks |

### 3.2 Database Standards

```sql
-- Naming Convention
-- Tables: plural, snake_case
-- Columns: snake_case, no abbreviations
-- Indexes: idx_{table}_{columns}
-- Constraints: fk_{table}_{ref_table}_{column}

-- Example
CREATE TABLE shipments (
    id SERIAL PRIMARY KEY,
    shipper_id INTEGER NOT NULL REFERENCES shippers(id) ON DELETE CASCADE,
    tracking_number VARCHAR(100) UNIQUE NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX CONCURRENTLY idx_shipments_shipper_status 
ON shipments(shipper_id, status) WHERE status != 'delivered';
```

### 3.3 API Standards

- **REST:** OpenAPI 3.0 specification
- **Auth:** OAuth 2.0 + JWT, RBAC matrix
- **Rate Limiting:** 100 req/min anonymous, 1000 req/min authenticated
- **Versioning:** URL path `/api/v1/...`, `/api/v2/...`
- **Error Format:** RFC 7807 Problem Details

---

## 4. Infrastructure

### 4.1 Deployment Architecture

```yaml
# Kubernetes Deployment Structure
namespace: auto-broker
├── deployments/
│   ├── api-deployment.yaml          # FastAPI app (3 replicas)
│   ├── worker-deployment.yaml       # Background jobs (2 replicas)
│   ├── hitl-dashboard.yaml          # Human-in-the-loop UI
│   └── chaos-runner.yaml            # Chaos experiments
├── services/
│   ├── api-service.yaml             # ClusterIP:8000
│   ├── postgres-service.yaml        # ClusterIP:5432
│   ├── redis-service.yaml           # ClusterIP:6379
│   └── vault-service.yaml           # ClusterIP:8200
├── configmaps/
│   ├── api-config.yaml              # Non-secret config
│   └── app-settings.yaml            # Feature flags
├── secrets/
│   └── vault-credentials.yaml       # Vault root credentials
└── network-policies/
    ├── deny-all.yaml                # Default deny
    ├── allow-api-to-db.yaml         # API → PostgreSQL
    └── allow-api-to-redis.yaml      # API → Redis
```

### 4.2 CI/CD Pipeline

```
┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐
│  Code   │ → │  Lint   │ → │  Test   │ → │  Build  │ → │ Deploy  │
│  Push   │   │  Check  │   │  95%    │   │  Image  │   │  Stage  │
└─────────┘   └─────────┘   └─────────┘   └─────────┘   └─────────┘
                  │             │             │             │
             ┌────┘             │             │             │
             ▼                  ▼             ▼             ▼
         ┌──────┐          ┌──────┐     ┌──────┐      ┌──────┐
         │ ruff │          │pytest│     │docker│      │kubectl│
         │ black│          │cov 95│     │ build│      │ apply│
         └──────┘          └──────┘     └──────┘      └──────┘
```

---

## 5. Monitoring & Observability

### 5.1 Three Pillars

| Pillar | Tool | Key Metrics |
|--------|------|-------------|
| **Metrics** | Prometheus + Grafana | Latency P95, Error rate, Saturation |
| **Logs** | ELK Stack (Elasticsearch, Logstash, Kibana) | Structured JSON, correlation IDs |
| **Traces** | Jaeger | Distributed tracing, span analysis |

### 5.2 SLIs/SLOs

| Service | SLI | SLO | Error Budget |
|---------|-----|-----|--------------|
| API Gateway | Availability | 99.9% | 43m/month |
| Quote Generation | Latency P95 | <500ms | - |
| ERP Sync | Success Rate | 99.5% | - |
| Blockchain Tx | Confirmation | <5min | - |

### 5.3 Alerting Rules

```yaml
# Prometheus Alerting Rules
groups:
  - name: auto-broker
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.01
        for: 2m
        labels:
          severity: critical
          
      - alert: CircuitBreakerOpen
        expr: circuit_breaker_state == 2  # OPEN=2
        for: 0m
        labels:
          severity: warning
          
      - alert: DatabaseConnectionsHigh
        expr: pg_stat_activity_count > 80
        for: 5m
        labels:
          severity: warning
```

---

## 6. Security Architecture

### 6.1 Defense in Depth

```
┌────────────────────────────────────────────────────────────────┐
│ Layer 1: Perimeter Security                                    │
│ • WAF (AWS WAF / Cloudflare)                                   │
│ • DDoS Protection                                              │
│ • Rate Limiting                                                │
├────────────────────────────────────────────────────────────────┤
│ Layer 2: Network Security                                      │
│ • Istio Service Mesh with mTLS                                 │
│ • Network Policies (deny-by-default)                           │
│ • VPC Isolation                                                │
├────────────────────────────────────────────────────────────────┤
│ Layer 3: Application Security                                  │
│ • OAuth 2.0 / JWT Authentication                               │
│ • RBAC Authorization                                           │
│ • Input Validation / Sanitization                              │
├────────────────────────────────────────────────────────────────┤
│ Layer 4: Data Security                                         │
│ • HashiCorp Vault for Secrets                                  │
│ • PII Masking middleware                                       │
│ • Encryption at Rest (AES-256)                                 │
├────────────────────────────────────────────────────────────────┤
│ Layer 5: Audit & Compliance                                    │
│ • GDPR Article 22 Audit Logger                                 │
│ • Immutable audit logs (append-only)                           │
│ • Regular security scans (Trivy, Snyk)                         │
└────────────────────────────────────────────────────────────────┘
```

### 6.2 Secret Management

```python
# Vault Integration Pattern
from security.vault_integration import VaultClient

vault = VaultClient()

# Dynamic database credentials
db_creds = vault.get_database_credentials(
    role="auto-broker-app",
    ttl="1h"
)
# Returns: {"username": "auto-broker-app-xxx", "password": "..."}

# Automatic rotation on lease expiry
vault.renew_lease(db_creds.lease_id)
```

### 6.3 Confidential Computing

#### 6.3.1 TEE (Trusted Execution Environment)

Implementazione AMD SEV-SNP e Intel TDX:

```yaml
# Kubernetes Confidential Pod
apiVersion: apps/v1
kind: Deployment
spec:
  template:
    spec:
      runtimeClassName: kata-cc-amd-sev
      nodeSelector:
        confidential-computing: "amd-sev-snp"
      containers:
      - name: agent
        resources:
          limits:
            amd.com/sev-snp: "1"
```

#### 6.3.2 Attestation Service

```python
# api/services/enclave_attestation.py
class EnclaveAttestation:
    def get_attestation_report(self) -> bytes:
        # SEV-SNP: /dev/sev-guest
        # Intel TDX: tdx-attest
        pass
    
    async def verify_attestation(self, report: bytes) -> bool:
        # Verify AMD/Intel signature
        # Compare measurement hash
        pass
```

#### 6.3.3 Security Guarantees

| Feature | Protection Level |
|---------|------------------|
| Memory Encryption | Host OS cannot read RAM |
| Remote Attestation | Verifiable identity |
| Sealed Secrets | Bound to enclave measurement |
| No Disk Logging | stdout only (encrypted) |

---

## 7. Scalability Planning

### 7.1 Horizontal Scaling

| Component | Current | Target (Q2 2026) | Strategy |
|-----------|---------|------------------|----------|
| API Pods | 3 | 10 | HPA based on CPU/memory |
| Database | Single | Primary-Replica | Streaming replication |
| Redis | Single | Cluster (6 nodes) | Redis Cluster mode |
| Vault | Single | HA (3 nodes) | Raft consensus |

### 7.2 Performance Tuning

```python
# Database Connection Pool
DATABASE_CONFIG = {
    "pool_size": 20,              # Default connections
    "max_overflow": 10,           # Extra connections under load
    "pool_timeout": 30,           # Wait for connection
    "pool_recycle": 3600,         # Recycle connections hourly
    "echo": False,                # No query logging in prod
}

# Redis Connection Pool
REDIS_CONFIG = {
    "max_connections": 100,
    "socket_timeout": 5,
    "socket_connect_timeout": 5,
    "retry_on_timeout": True,
}
```

---

## 8. Disaster Recovery

### 8.1 RTO/RPO by Component

| Component | RTO | RPO | Strategy |
|-----------|-----|-----|----------|
| Database | 30 min | 15 min | Streaming replica + WAL archiving |
| Redis | 5 min | 0 min | AOF persistence + RDB snapshots |
| Vault | 15 min | 0 min | Raft HA + auto-unseal (AWS KMS) |
| Object Storage | 1 hour | 0 min | S3 cross-region replication |

### 8.2 Backup Procedures

```bash
# Database Backup (hourly)
pg_dump -Fc --verbose auto_broker > s3://backups/auto-broker/$(date +%Y%m%d-%H%M).dump

# WAL Archiving (continuous)
archive_command = 'aws s3 cp %p s3://backups/wal/%f'

# Point-in-Time Recovery
target_time="2026-02-14 14:30:00"
pg_basebackup -D /recovery -X fetch
pg_ctl start -D /recovery -o "--recovery-target-time='$target_time'"
```

---

## 2.3 New Components (v9.6-v9.8)

### Semantic Cache Service
```python
# api/services/semantic_cache.py
class SemanticCacheService:
    """
    Cache semantica per riduzione costi Hume AI del 90%.
    
    Features:
    - sentence-transformers (384 dimensioni)
    - Cosine similarity >= 0.95 per cache hit
    - Privacy: solo hash SHA256, mai transcription completa
    - Hit rate target: 85%
    """
    
    async def get_or_compute(transcription, compute_func):
        # 1. Check exact match (hash)
        # 2. Check semantic similarity
        # 3. Call Hume if miss, save to cache
```

### Cost Tracking Service
```python
# api/services/cost_tracker.py
class CostTracker:
    """
    Tracciamento costi granulari per spedizione.
    
    Features:
    - Precisione 6 decimali (micro-transazioni)
    - Batch insert ogni 10 eventi
    - Cost projection basata su media storica
    - Prometheus metrics integration
    """
    
    COST_CONFIG = {
        "hume_ai_per_minute": 0.15,
        "polygon_tx_base": 0.001,
        "dat_iq_per_request": 0.05,
    }
```

### FRANCO Retention Agent
```python
# api/services/franco_service.py
class FrancoService:
    """
    Retention Agent per chiamate post-consegna.
    
    Features:
    - Trigger 7 giorni dopo consegna
    - Rate limiting: 10 chiamate/ora
    - Idempotenza (no duplicati)
    - Circuit breaker per Retell API
    """
```

---

## 9. Roadmap Q2 2026

### 9.1 Planned Enhancements

| Feature | Priority | ETA | Owner |
|---------|----------|-----|-------|
| Kubernetes Migration | P0 | 2026-03 | Platform Team |
| Graph Database (Neo4j) | P1 | 2026-04 | Data Team |
| Digital Twins (NVIDIA) | P1 | 2026-05 | AI Team |
| IoT Platform Integration | P2 | 2026-06 | Hardware Team |
| Mobile App (React Native) | P2 | 2026-06 | Mobile Team |

### 9.2 Technical Debt

| Item | Impact | Effort | Priority |
|------|--------|--------|----------|
| pgvector migration | Medium | 2d | P1 |
| Test coverage 95% → 98% | Low | 3d | P2 |
| Documentation refresh | Medium | 1d | P2 |
| Performance optimization | High | 5d | P1 |

---

## 8. Self-Healing Supply Chain

### 8.1 Autonomous Agents

#### PAOLO (Carrier Failover Agent)

**Responsabilità:** Monitoraggio carrier e failover automatico

```python
# Pattern Saga per atomicità
async def execute_failover(shipment_id, reason):
    # Step 1: Update DB
    await db.execute(update_shipment_carrier)
    
    # Step 2: Blockchain tx
    tx_hash = await blockchain.transfer_to_new_carrier()
    
    if tx_hash:
        await db.commit()
    else:
        await db.rollback()  # Rollback su failure
```

**Human-in-the-loop:**
- Importo > €10k: richiede approvazione admin
- Timeout 30min: escalation a human

#### GIULIA (Dispute Resolution Agent)

**AI Analysis:**
- OCR firma su POD
- GPS tracking verification
- Computer vision per danni

**Decision Matrix:**
```python
if confidence > 85%:
    auto_resolve()
elif confidence > 50%:
    escalate_to_human()
else:
    request_more_evidence()
```

### 8.2 Smart Contract Architecture

```solidity
contract CarrierEscrow {
    // Atomic transfer a nuovo carrier
    function transferToNewCarrier(
        string memory shipmentId,
        address newCarrier
    ) external onlyPaoloAgent;
    
    // Risoluzione dispute con AI confidence
    function resolveDispute(
        string memory shipmentId,
        bool carrierWins,
        uint256 confidence
    ) external onlyGiuliaAgent;
}
```

### 8.3 Orchestrator Swarm

```python
class SwarmOrchestrator:
    # Event-driven coordination
    async def on_failover_executed(event):
        # Notifica GIULIA di monitorare dispute
        await giulia.investigate_carrier(event.carrier_id)
    
    async def on_fraud_detected(event):
        # PAOLO blacklist carrier
        await paolo.blacklist_carrier(event.carrier_id)
```

---

## 9. Zero-Knowledge Pricing

### 9.1 zk-SNARK Circuit

Verifica `markup <= 30%` senza rivelare `base_cost`:

```python
# Constraint: selling_price * 100 <= base_cost * 130
circuit = ZKPricingCircuit()
commitment = circuit.commit(base_cost, salt)
proof = circuit.prove(selling_price, commitment)
verify(proof, public_inputs=[selling_price, commitment])
```

---

## 10. Appendix

### 10.1 Technology Stack

| Layer | Technology | Version |
|-------|------------|---------|
| Language | Python | 3.14+ |
| Framework | FastAPI | 0.115+ |
| ORM | SQLAlchemy | 2.0+ |
| Database | PostgreSQL | 15+ |
| Cache | Redis | 7+ |
| Vector DB | ChromaDB | 0.5.x |
| Semantic Cache | sentence-transformers | 3.0+ |
| Message Queue | Redis Streams | 7+ |
| Secrets | HashiCorp Vault | 1.18+ |
| Service Mesh | Istio | 1.24+ |
| Container | Docker | 25+ |
| Orchestration | Kubernetes | 1.32+ |
| CI/CD | GitHub Actions | - |
| Monitoring | Prometheus/Grafana | - |

### 10.2 Cost Estimates (Monthly)

| Component | Development | Production |
|-----------|-------------|------------|
| Compute (EKS/GKE) | $200 | $1,500 |
| Database (RDS/Cloud SQL) | $100 | $800 |
| Redis (ElastiCache/Memorystore) | $50 | $300 |
| Storage (S3/GCS) | $20 | $200 |
| External APIs | $100 | $1,000 |
| Security (Vault/WAF) | $0 | $300 |
| **Total** | **$470** | **$4,100** |

---

## Version History

### v2.5.0 (2026-02-15)
- Aggiunte sezioni 6.3 Confidential Computing, 8 Self-Healing, 9 ZK Pricing
- Aggiornati costi mensili con infrastruttura TEE
- Aggiunte ADR-014, ADR-015, ADR-016

### v2.4.0 (2026-02-15)
- Aggiunti componenti Semantic Cache, Cost Dashboard, FRANCO
- Aggiornata Technology Stack con sentence-transformers
- Aggiunta sezione 2.3 New Components

### v2.3.0 (2026-02-14)
- Aggiunta Architecture Vision
- Aggiornato C4 Component Diagram
- Aggiunta sezione Scalability Planning
- Aggiornati costi mensili con Business Layer

### v2.2.0 (2026-02-01)
- Aggiunti componenti Business Layer
- Aggiornati security standards
- Aggiunta sezione Chaos Engineering

### v2.0.0 (2026-01-15)
- Platform Engineering foundation
- Kubernetes deployment specs
- Initial monitoring setup
