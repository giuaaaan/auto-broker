# AUTO-BROKER Test Suite 🚀

> **Testing like Google/Meta/Netflix in 2026**

## Philosophy

Questa suite di test segue le best practices delle big tech:

- **Test Pyramid**: 70% Unit → 20% Integration → 10% E2E
- **Property-Based Testing**: Hypothesis genera edge cases automatici
- **Contract Testing**: Snapshot testing garantisce retrocompatibilità API
- **Mutation Testing**: Verifica che i test rilevino cambiamenti nel codice
- **Parallel Execution**: Test veloci con pytest-xdist

## Quick Start

```bash
# Installa le dipendenze
make install

# Run all tests
make test

# Run specific test suite
make test-unit        # Unit tests (fast)
make test-integration # Integration tests (needs DB)
make test-e2e         # End-to-end tests
```

## Test Structure

```
tests/
├── unit/              # 🧪 Unit tests - Veloci, isolati
│   ├── test_database.py
│   ├── test_services.py
│   ├── test_property_based.py  # Hypothesis
│   └── ...
├── integration/       # 🔌 Integration tests - Con DB/Redis
│   └── test_main_integration.py
├── e2e/               # 🎭 E2E tests - Flussi completi
│   └── test_complete_flow.py
├── contract/          # 📋 Contract tests - API schemas
│   └── test_api_contracts.py
├── mutation/          # 🧬 Mutation tests - Robustezza
│   └── test_mutation.py
├── factories.py       # 🏭 Test data factories
└── conftest.py        # 🔧 Fixtures globali
```

## Test Pyramid

### 1. Unit Tests (70%)

```bash
make test-unit
```

- **Scope**: Funzioni isolate, nessun external deps
- **Speed**: < 100ms per test
- **Coverage**: Models, Services, Schemas
- **Parallel**: Sì, con `-n auto`

**Esempio**:
```python
@pytest.mark.unit
async def test_calculate_fees():
    result = await stripe_service.calculate_fees(Decimal("100.00"))
    assert result["stripe_fees"] == Decimal("1.75")
```

### 2. Property-Based Tests

```bash
make test-property
```

Usa [Hypothesis](https://hypothesis.readthedocs.io/) per generare automaticamente
edge cases che non avresti mai pensato:

```python
@given(
    origin=st.sampled_from(['Milano', 'Roma', '']),
    weight=st.floats(min_value=0.1, max_value=10000.0)
)
async def test_scraper_always_returns_sorted_quotes(origin, destination, weight):
    quotes = await scraper.scrape_all_carriers(origin, destination, weight)
    assert all(quotes[i].total_cost <= quotes[i+1].total_cost 
               for i in range(len(quotes)-1))
```

### 3. Contract Tests

```bash
make test-contract
```

Snapshot testing garantisce che le API non cambino breaking:

```python
def test_lead_response_contract(self, snapshot):
    lead = LeadResponse(...)
    assert lead.model_dump() == snapshot(
        exclude=props("id", "created_at")  # Esclude campi dinamici
    )
```

### 4. Integration Tests (20%)

```bash
make test-integration
```

- **Scope**: API endpoints con PostgreSQL/Redis reali
- **Speed**: 1-5s per test
- **Setup**: Docker Compose con DB

**Requisiti**:
```bash
docker-compose up -d postgres redis
make test-integration
```

### 5. E2E Tests (10%)

```bash
make test-e2e
```

Test del flusso completo: Lead → Qualificazione → Pricing → Proposal

```python
def test_complete_flow_lead_to_contract(self, client):
    # 1. Crea Lead
    lead = client.post("/leads", json={...})
    
    # 2. Qualifica
    qual = client.post("/qualify-lead", json={...})
    
    # 3. Calcola prezzo
    price = client.post("/calculate-price", json={...})
    
    # 4. Crea proposal
    proposal = client.post("/create-proposal", json={...})
    
    assert proposal["prezzo_finale"] > 0
```

## Running Tests

### Comandi Make

```bash
make test              # Tutti i test
make test-unit         # Solo unit
make test-fast         # Solo test veloci (<100ms)
make test-slow         # Solo test lenti
make test-contract     # Contract tests
make test-property     # Property-based
make test-mutation     # Mutation tests

make coverage          # Coverage report
make coverage-html     # Apri HTML report
make watch             # Watch mode
```

### Pytest Direct

```bash
# Unit tests in parallel
pytest tests/unit/ -n auto

# Con coverage
pytest tests/ --cov=api --cov-report=html

# Solo un marker
pytest tests/ -m "unit and not slow"

# Hypothesis con più esempi
pytest tests/unit/test_property_based.py --hypothesis-seed=0
```

## Test Data Factories

Usiamo `factory_boy` per generare dati realistici:

```python
from tests.factories import LeadFactory

# Crea lead valido automaticamente
lead = LeadFactory()

# Override campi specifici
lead = LeadFactory(nome="Mario", email="custom@test.com")

# Batch
ten_leads = LeadFactory.create_batch(10)
```

## CI/CD (GitHub Actions)

La pipeline esegue:

1. **Unit Tests** → Paralleli, veloci
2. **Property Tests** → Hypothesis edge cases
3. **Contract Tests** → Snapshot comparison
4. **Integration Tests** → Con PostgreSQL/Redis
5. **E2E Tests** → Flussi completi
6. **Mutation Tests** → Solo su PR
7. **Coverage Gate** → 100% required

```yaml
# .github/workflows/test.yml
jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - run: pytest tests/unit/ -n auto
  
  integration-tests:
    needs: unit-tests
    services:
      postgres:
        image: postgres:15-alpine
    steps:
      - run: pytest tests/integration/
```

## Coverage

**Target**: 100% coverage totale

```bash
# Coverage per tipo
coverage-unit        # Solo unit
coverage-integration # Solo integration

# Report completo
make coverage
# Apri: htmlcov/index.html
```

## Mutation Testing

Verifica che i test siano abbastanza robusti:

```python
# Se qualcuno cambia 1.5% in 2.5%, questo DEVE fallire
async def test_stripe_fees_never_exceed_amount(self):
    result = await service.calculate_fees(Decimal("100.00"))
    assert result["stripe_fees"] == Decimal("1.75")  # Preciso!
```

## Best Practices

### DO ✅

- **Test pyramid**: Più unit, meno E2E
- **Async**: Usa `pytest-asyncio` per async code
- **Factories**: Non hardcodare dati, usa factory
- **Markers**: Segna test con `@pytest.mark.unit`
- **Isolation**: Ogni test pulisce dopo sé

### DON'T ❌

- Non fare E2E test per logiche semplici
- Non usare `time.sleep()` nei test
- Non dipendere da stato di altri test
- Non skippare test senza buona ragione

## Troubleshooting

### Test lenti?

```bash
make test-fast  # Solo test <100ms
```

### Database locked?

```bash
make reset-db  # Reset test database
```

### Hypothesis falling?

```bash
# Esegui con seed fisso per reproducibilità
pytest tests/ --hypothesis-seed=0
```

## Resources

- [Hypothesis Docs](https://hypothesis.readthedocs.io/)
- [Syrupy Snapshot Testing](https://github.com/tophat/syrupy)
- [Google Testing Blog](https://testing.googleblog.com/)
- [Netflix Tech Blog](https://netflixtechblog.com/)
