# 🤖 AUTO-BROKER

[![CI/CD Pipeline](https://github.com/yourusername/auto-broker/actions/workflows/ci.yml/badge.svg)](https://github.com/yourusername/auto-broker/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/yourusername/auto-broker/branch/main/graph/badge.svg)](https://codecov.io/gh/yourusername/auto-broker)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Piattaforma di Brokeraggio Logistico 100% Autonoma**

Un sistema completo che prospetta, qualifica, negozia, chiude contratti e gestisce spedizioni logistiche in completa autonomia. L'unico input umano richiesto è il monitoraggio del profitto.

---

## 🏗️ Architettura

```
┌─────────────────────────────────────────────────────────────────────┐
│                         AUTO-BROKER SYSTEM                          │
├─────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐ │
│  │    SARA     │  │    MARCO    │  │    CARLO    │  │    LAURA   │ │
│  │ Acquisition │→ │Qualification│→ │   Sourcing  │→ │  Proposal  │ │
│  │  (Retell)   │  │  (Retell)   │  │  (Scraper)  │  │(PDF/Email) │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └────────────┘ │
│         ↓                                                        ↓  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐ │
│  │    LUIGI    │→ │   Stripe    │→ │    ANNA     │  │  Tracking  │ │
│  │   Closing   │  │   Payment   │  │   Operations│  │ AfterShip  │ │
│  │  (Retell)   │  │  (Webhook)  │  │(Ship/Alert) │  │   6h Cron  │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └────────────┘ │
├─────────────────────────────────────────────────────────────────────┤
│                    INFRASTRUCTURE                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │     n8n      │  │   FastAPI    │  │  PostgreSQL  │              │
│  │  (Orchestra) │  │   (Logic)    │  │  (Database)  │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │    Redis     │  │ DocuSign API │  │  Resend API  │              │
│  │   (Queue)    │  │ (Contracts)  │  │   (Email)    │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- 4GB RAM minimum
- 10GB disk space

### Installation (One Command)

```bash
# Clone repository
git clone https://github.com/yourusername/auto-broker.git
cd auto-broker

# Run setup (creates .env, builds images, starts services)
make setup

# Or manually:
# cp .env.example .env
# docker-compose up -d
```

### Access Services

| Service | URL | Credentials |
|---------|-----|-------------|
| n8n Dashboard | http://localhost:5678 | admin / admin123 |
| API Documentation | http://localhost:8000/docs | - |
| API Health | http://localhost:8000/health | - |
| PostgreSQL | localhost:5432 | broker_user / broker_pass_2024 |
| Redis | localhost:6379 | - |

---

## 🔄 Workflow Agents

### SARA - Acquisition Agent
- **Trigger**: Schedule every 2 hours
- **Action**: Calls new leads from CSV
- **Script**: *"Sono Sara di Logistik AI. Aiutiamo aziende a ridurre costi spedizioni del 20-30%. Le interessa una valutazione gratuita?"*
- **Outcomes**: 
  - SÌ → Passa a Marco dopo 5 min
  - NO → Follow-up in 90 giorni
  - Segreteria → Riprova dopo 2 ore

### MARCO - Qualification Agent
- **Trigger**: Webhook quando Sara ha successo
- **Action**: Raccoglie dati aziendali (volume kg, lane, prezzo attuale, P.IVA)
- **Outcome**: Credit check → Se score > 70, triggera Carlo

### CARLO - Sourcing Agent
- **Trigger**: Webhook quando qualifica completata
- **Action**: Cerca corrieri (API + scraping + DB)
- **Filtro**: on-time > 95%
- **Calcolo**: prezzo vendita = costo × 1.30
- **Outcome**: Passa a Laura

### LAURA - Proposal Agent
- **Trigger**: Webhook quando prezzo pronto
- **Action**: 
  - Genera PDF con WeasyPrint
  - Invia email via Resend
  - Crea envelope DocuSign
- **Tracciamento**: Se aperta ma non firmata in 4h → Triggera Luigi

### LUIGI - Closing Agent
- **Trigger**: Webhook quando proposta visualizzata
- **Action**: Chiama cliente
- **Script**: *"Ho visto che ha aperto la proposta, ha domande?"*
- **Obiezioni**: "Troppo caro" → Offre -5%
- **Outcome**: Firma → Stripe payment

### ANNA - Operations Agent
- **Trigger**: Pagamento confermato
- **Action**:
  - Ordine a corriere (API/email)
  - Genera CMR ed etichette
  - Tracking via AfterShip
- **Alert**: Se ritardo > 2h → Email cliente
- **Post-consegna**: Richiesta recensione

### PAOLO - Carrier Failover Agent 🤖
- **Trigger**: Carrier on_time_rate < 90% (check ogni 5 min)
- **Action**:
  - Identifica shipment a rischio
  - Trova carrier alternativo (< 2h disponibilità)
  - Esegue failover atomico (DB + Blockchain)
  - Trasferisce escrow a nuovo carrier
- **Human-in-the-loop**: Importi > €10k richiedono approvazione
- **Outcome**: Cliente notificato, nessun costo aggiuntivo

### GIULIA - Dispute Resolution Agent 🤖
- **Trigger**: PODSmartContract.openDispute() webhook
- **Action**:
  - Analizza POD con AI (OCR, pattern matching)
  - Verifica tracking (GPS vs claim)
  - Computer vision per danni
- **Decisione**:
  - Confidence > 85% → Auto-resolve
  - Confidence 50-85% → Escalation umana
  - Confidence < 50% → Richiede più evidence
- **Outcome**: Scrive risoluzione su blockchain, aggiorna reputazione carrier

---

## 🧪 Testing

### Run All Tests

```bash
make test
```

### Run Specific Test Types

```bash
# Unit tests only
make test-unit

# Integration tests only
make test-integration

# E2E tests only
make test-e2e

# With coverage report
make coverage
```

### Test Coverage

Il progetto richiede **100% code coverage**. La CI fallisce se coverage < 100%.

```bash
pytest --cov=api --cov-report=html
# View report: htmlcov/index.html
```

---

## 🔒 Security & Confidential Computing

Auto-Broker implementa **Confidential Computing** per proteggere dati sensibili durante l'elaborazione.

### Features di Sicurezza

| Feature | Implementation | Status |
|---------|---------------|--------|
| **Memory Encryption** | AMD SEV-SNP / Intel TDX | ✅ Implemented |
| **Remote Attestation** | Vault Integration | ✅ Implemented |
| **Zero-Knowledge Pricing** | zk-SNARK Circuits | ✅ Implemented |
| **Semantic Cache** | Sentence Transformers | ✅ Implemented |
| **PII Masking** | SHA256 Hashing | ✅ Active |
| **mTLS** | Istio Service Mesh | ✅ Active |
| **Secret Management** | HashiCorp Vault | ✅ Active |

### Confidential Enclaves

Gli agenti AI (SARA, MARCO, FRANCO) possono girare in **Trusted Execution Environments (TEE)**:

```yaml
# Kubernetes deployment con confidential computing
apiVersion: apps/v1
kind: Deployment
spec:
  template:
    spec:
      runtimeClassName: kata-cc-amd-sev  # Enclave runtime
      containers:
      - name: sara-agent
        resources:
          limits:
            amd.com/sev-snp: "1"  # Richiede SEV-SNP
```

**Garanzie di Sicurezza:**
- 🔐 Dati in RAM cifrati (host non può leggere)
- 🔑 Secrets solo dopo attestation verificata
- 📝 Nessun log su disco (solo stdout)
- ✅ Verificabilità da terze parti

📖 [Confidential Computing Docs](docs/CONFIDENTIAL_COMPUTING.md)

---

## 🔧 Development

### Useful Commands

```bash
# Start services
make up

# Stop services
make down

# View logs
make logs

# Access database shell
make db-shell

# Access API container
make api-shell

# Check health
make health-check

# Format code
make format

# Run linters
make lint
```

### Code Style

- **Formatter**: Black (line length 100)
- **Import sorting**: isort
- **Linter**: flake8
- **Type checking**: mypy

---

## 📋 Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | ✅ | PostgreSQL connection string |
| `REDIS_URL` | ✅ | Redis connection string |
| `RETELL_API_KEY` | ❌ | Retell AI API key (voice calls) |
| `RETELL_AGENT_ID_SARA` | ❌ | SARA agent ID |
| `RETELL_AGENT_ID_MARCO` | ❌ | MARCO agent ID |
| `RETELL_AGENT_ID_LUIGI` | ❌ | LUIGI agent ID |
| `STRIPE_SECRET_KEY` | ❌ | Stripe secret key |
| `STRIPE_WEBHOOK_SECRET` | ❌ | Stripe webhook signing secret |
| `RESEND_API_KEY` | ❌ | Resend email API key |
| `DOCUSIGN_INTEGRATION_KEY` | ❌ | DocuSign integration key |
| `DOCUSIGN_ACCOUNT_ID` | ❌ | DocuSign account ID |
| `AFTERSHIP_API_KEY` | ❌ | AfterShip tracking API key |

---

## 🐛 Troubleshooting

### Services won't start

```bash
# Check logs
docker-compose logs

# Rebuild everything
docker-compose down -v
docker-compose build --no-cache
docker-compose up -d
```

### Database connection issues

```bash
# Reset database (WARNING: deletes all data!)
docker-compose down -v
docker-compose up -d postgres

# Check PostgreSQL is ready
docker-compose exec postgres pg_isready -U broker_user
```

### n8n workflows not triggering

1. Check webhook URLs use `http://api:8000` (not localhost)
2. Verify credentials are configured in n8n
3. Check n8n execution logs in the UI

### API returning 500 errors

```bash
# Check API logs
docker-compose logs api

# Verify environment variables
docker-compose exec api env | grep -E '(API_KEY|SECRET)'
```

---

## 📊 API Endpoints

### Leads
```
POST   /leads                    # Create lead
GET    /leads                    # List leads
GET    /leads/{id}               # Get lead
PATCH  /leads/{id}               # Update lead
POST   /leads/{id}/call/{agent}  # Trigger call (sara/marco/luigi)
```

### Qualification
```
POST   /qualify-lead             # Qualify lead (MARCO)
GET    /qualificazioni/{id}      # Get qualification
```

### Pricing
```
POST   /calculate-price          # Calculate selling price
POST   /source-carriers          # Source carriers (CARLO)
```

### Proposals
```
POST   /create-proposal          # Create proposal (LAURA)
```

### Webhooks
```
POST   /stripe-webhook           # Stripe payment webhook
POST   /retell-webhook           # Retell call completion
POST   /docusign-webhook         # DocuSign events
```

### Shipments
```
GET    /shipment-status/{id}     # Track shipment
POST   /disruption-alert         # Delay alert (ANNA)
```

### Dashboard
```
GET    /stats/dashboard          # Get statistics
GET    /health                   # Health check
```

---

## 🔐 Security Features

- ✅ Rate limiting (SlowAPI)
- ✅ CORS protection
- ✅ Input validation (Pydantic)
- ✅ Structured JSON logging
- ✅ No hardcoded secrets (env vars only)
- ✅ SQL injection protection (SQLAlchemy ORM)
- ✅ XSS protection (Jinja2 autoescape)

---

## 📁 Project Structure

```
auto-broker/
├── docker-compose.yml               # All services configuration
├── docker-compose.oracle.enterprise.yml  # Oracle Cloud optimized
├── .env.example                     # Environment template
├── .env.oracle.example              # Oracle Cloud environment
├── ORACLE_ENTERPRISE_DEPLOY.md      # Oracle deploy guide
├── init.sql                         # Database schema + seed data
├── setup.sh                         # Setup script
├── Makefile                         # Useful commands
├── pytest.ini                       # Test configuration
├── .coveragerc                      # Coverage settings
│
├── config/                          # Configuration files
│   └── postgresql.oracle.conf       # Tuned for 4GB RAM
│
├── dashboard/                       # React Dashboard
│   ├── Dockerfile.optimized         # Multi-stage build
│   └── nginx/                       # Nginx configs
│
├── nginx/                           # Reverse proxy configs
│   ├── oracle-nginx.conf            # Main proxy config
│   └── nginx.conf                   # Base nginx config
│
├── scripts/                         # Automation scripts
│   ├── deploy-oracle-enterprise.sh  # One-command deploy
│   └── backup-oracle.sh             # Backup automation
│
├── api/                             # FastAPI Application
│   ├── Dockerfile
│   ├── Dockerfile.optimized         # Multi-stage for Oracle
│   ├── requirements.txt
│   ├── main.py                      # All endpoints
│   ├── models.py                    # SQLAlchemy models
│   ├── schemas.py                   # Pydantic schemas
│   ├── templates/
│   │   └── email_proposal.html
│   └── services/
│       ├── database.py              # DB connection
│       ├── redis_service.py         # Redis caching
│       ├── retell_service.py        # Voice AI
│       ├── stripe_service.py        # Payments
│       ├── docusign_service.py      # E-signatures
│       ├── email_service.py         # Email
│       ├── pdf_generator.py         # PDF generation
│       └── scraper.py               # Web scraping
│
├── tests/                     # Test Suite
│   ├── conftest.py           # Pytest fixtures
│   ├── unit/                 # Unit tests (services)
│   ├── integration/          # API integration tests
│   └── e2e/                  # End-to-end tests
│
├── n8n-workflows/            # Exported n8n workflows
│   ├── 01_import_leads_csv.json
│   ├── 02_chiamata_sara.json
│   ├── 03_qualifica_marco.json
│   ├── 04_sourcing_carlo.json
│   ├── 05_closing_luigi.json
│   ├── 06_pagamento_stripe.json
│   └── 07_tracking_anna.json
│
├── .github/workflows/        # CI/CD
│   ├── ci.yml                # Test & lint pipeline
│   └── docker-build.yml      # Build & push images
│
└── postman/
    └── auto-broker-collection.json
```

---

## 🚢 Deployment

### Production Deployment

1. **Set up environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with production values
   ```

2. **Start production stack:**
   ```bash
   docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
   ```

3. **Run database migrations:**
   ```bash
   docker-compose exec api alembic upgrade head
   ```

### Using Docker Hub

```bash
# Build and push
docker build -t yourusername/auto-broker-api:latest ./api
docker push yourusername/auto-broker-api:latest

# Pull and run
docker pull yourusername/auto-broker-api:latest
docker-compose up -d
```

---

## 🚀 Oracle Cloud Free Tier Deployment (Enterprise)

Deploy enterprise-grade Auto-Broker on **Oracle Cloud Free Tier** (4GB RAM / 1 CPU ARM Ampere A1) with zero cost.

### 🎮 DEMO_MODE - Test Gratis (€0)

Prova Auto-Broker **senza spendere 1 euro** - nessuna API key necessaria!

```bash
# 1. Clone
git clone https://github.com/giuaaaan/auto-broker.git
cd auto-broker

# 2. Attiva DEMO_MODE (già impostato di default)
echo "DEMO_MODE=true" > .env.oracle

# 3. Deploy
./scripts/deploy-oracle-enterprise.sh

# 4. Apri nel browser
echo "http://$(curl -s ifconfig.me)"
```

**Cosa funziona in DEMO_MODE:**
- ✅ Dashboard NASA al 100% (mappe, grafici, WebSocket)
- ✅ Revenue che sale automaticamente (+€50-300 ogni 30s)
- ✅ Agenti AI simulati (SARA, PAOLO, GIULIA in azione)
- ✅ Camion che si muovono sulla mappa
- ✅ Zero costi API (Hume, Insighto, Blockchain mockate)

📖 **[DEMO_MODE Guide](DEMO_MODE_GUIDE.md)** - Istruzioni complete per test gratuito

### Production Deploy (con API reali)

```bash
# 1. Configura con API keys reali
cp .env.oracle.example .env.oracle
# Edit: DEMO_MODE=false + aggiungi HUME_API_KEY, INSIGHTO_API_KEY

# 2. Deploy
./scripts/deploy-oracle-enterprise.sh
```

### Resource Allocation (Zero-Waste Architecture)

| Service | RAM | Purpose |
|---------|-----|---------|
| nginx | 64MB | Reverse proxy + static assets |
| PostgreSQL | 1.2GB | Tuned for ARM + SSD |
| Redis | 256MB | Cache & sessions |
| FastAPI | 768MB | 2 uvicorn workers |
| **Total Used** | ~2.3GB | Leaves 1.7GB buffer |

### Documentation

📖 **[Complete Oracle Deploy Guide](ORACLE_ENTERPRISE_DEPLOY.md)** - Step-by-step instructions, troubleshooting, scaling path to Hetzner

### Key Features

- ✅ **Multi-stage Docker builds** (Alpine Linux)
- ✅ **PostgreSQL tuned** for 4GB systems
- ✅ **Automated backup** to Oracle Object Storage
- ✅ **Health checks** on all services
- ✅ **Non-root containers** for security
- ✅ **One-command deploy** script
- ✅ **DEMO_MODE** - Zero cost testing

---

## 📄 License

MIT License - see [LICENSE](LICENSE) file

---

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Run tests (`make test`)
4. Commit changes (`git commit -m 'Add amazing feature'`)
5. Push to branch (`git push origin feature/amazing-feature`)
6. Open a Pull Request

---

## 💬 Support

For issues and questions:
- Check [Troubleshooting](#troubleshooting) section
- Review [API Documentation](http://localhost:8000/docs)
- Check n8n execution logs
- Open an issue on GitHub

---

**Built with ❤️ for autonomous logistics**
