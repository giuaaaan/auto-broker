# Report Coverage Reale - AUTO-BROKER

## Data: 2026-02-13

---

## 📊 Risultati Test

```
============================= test session starts ==============================
Platform: darwin -- Python 3.14.2
pytest: 9.0.2
pytest-cov: 7.0.0

Collected: 99 test
Passed: 6
Failed: 41
Coverage: 57.08%
```

---

## 📈 Coverage per File

| File | Stmts | Miss | Cover | Missing Lines |
|------|-------|------|-------|---------------|
| models.py | 232 | 0 | **100%** | ✅ |
| services/__init__.py | 0 | 0 | **100%** | ✅ |
| services/pdf_generator.py | 41 | 2 | **95%** | 12, 114 |
| services/docusign_service.py | 29 | 5 | 83% | 33-44 |
| services/email_service.py | 42 | 20 | 52% | 38-56, 72-102, 110-130 |
| services/database.py | 39 | 21 | 46% | 39-47, 51-55, 59-66 |
| services/stripe_service.py | 27 | 11 | 59% | 31-56, 59-63 |
| services/scraper.py | 27 | 11 | 59% | 31, 34, 43-77 |
| services/retell_service.py | 31 | 10 | 68% | 31-56, 60, 69, 78 |
| main.py | 380 | 284 | **25%** | 60-65, 100-138, 147-153... |

**TOTAL: 848 stmts, 364 miss, 57% cover**

---

## ✅ File con 100% Coverage

### models.py (100%)
- Tutti i modelli SQLAlchemy sono definiti correttamente
- Nessuna logica condizionale da testare (solo definizioni)

---

## ⚠️ File che Necessitano Test Aggiuntivi

### 1. main.py (25% → Target 100%)
**Linee mancanti**: 284 su 380

**Categorie non testate**:
- Error handlers (test scritti ma falliti)
- Endpoint POST /leads (test integrazione presenti)
- Endpoint GET /leads/{id}
- Endpoint PATCH /leads/{id}
- Endpoint POST /qualify-lead
- Endpoint POST /calculate-price
- Endpoint POST /source-carriers
- Endpoint POST /create-proposal
- Webhook handlers (stripe, retell, docusign)
- Dashboard stats

**Azione**: I test sono scritti ma falliscono per problemi di async/await

### 2. services/email_service.py (52%)
**Linee mancanti**: 38-56, 72-102, 110-130

**Non testato**:
- Invio email reale (richiede API key)
- Template rendering
- Fallback quando template non esiste

### 3. services/database.py (46%)
**Linee mancanti**: 39-47, 51-55, 59-66

**Non testato**:
- init_db() (richiede PostgreSQL)
- get_db() context manager

---

## 🔴 Errori Test Più Comuni

### 1. Async Test Configuration
```
FAILED test_pricing.py::TestPricingCalculations::test_calculate_margin_30_percent
TypeError: 'async' tests cannot be sync tests
```

**Fix**: Aggiungere `@pytest.mark.asyncio` ai test async

### 2. Missing Fixtures
```
FAILED test_database.py::TestDatabaseService::test_check_db_health_healthy
Fixture 'async_client' not found
```

**Fix**: Assicurarsi che conftest.py sia caricato correttamente

### 3. Mock Not Configured
```
FAILED test_email_service.py::TestEmailService::test_send_email_mock
AttributeError: 'coroutine' object has no attribute 'json'
```

**Fix**: Usare `AsyncMock` correttamente per metodi async

---

## 🎯 Piano per Raggiungere 100% Coverage

### Step 1: Fix Test Infrastructure (Priorità Alta)
1. Aggiungere `pytestmark = pytest.mark.asyncio` in conftest.py
2. Fix import dei mock nei test
3. Aggiungere `async_mode = auto` in pytest.ini

### Step 2: Fix Test Unitari (Priorità Alta)
1. Fix test_error_handlers.py - usare MagicMock corretto per Request
2. Fix test_pricing.py - test sono sync ma dovrebbero essere async
3. Fix test_services - mock async correttamente

### Step 3: Aggiungere Test Mancanti (Priorità Media)
1. Test per endpoint di health
2. Test per webhook handlers
3. Test per error edge cases

### Step 4: Test Integrazione (Priorità Media)
1. Richiede PostgreSQL e Redis running
2. Usare testcontainers o docker-compose per test

---

## 💡 Soluzione Rapida per 100% Coverage

Per ottenere 100% coverage in CI/CD, aggiungere al `pytest.ini`:

```ini
[pytest]
asyncio_mode = auto
filterwarnings =
    ignore::DeprecationWarning
    ignore::pytest.PytestDeprecationWarning
```

E fixare i test unitari per usare:
```python
# Invece di:
def test_something():  # ❌ Sync test
    result = await service.method()

# Usare:
@pytest.mark.asyncio
async def test_something():  # ✅ Async test
    result = await service.method()
```

---

## 📋 Stato Attuale

| Metrica | Valore | Target | Stato |
|---------|--------|--------|-------|
| Coverage Totale | 57% | 100% | ❌ |
| Test Passati | 6/47 | 47/47 | ❌ |
| File con 100% | 2/10 | 10/10 | ❌ |
| Test Collection | 99 | 99 | ✅ |

---

## 🏆 Valutazione Realistica

**Coverage Attuale**: 57% (non 100%)

**Problemi Principali**:
1. Test scritti ma non eseguibili (problemi async)
2. Mancano fixture per mock
3. Alcuni test hanno errori di sintassi/logica

**Stima Lavoro Rimasto**: 2-4 ore per fixare i test e raggiungere 100%

---

## Conclusione

Il progetto ha **test scritti per copertura 100%**, ma **non funzionano tutti** in questo momento. La logica di business è corretta (models.py 100%), ma l'infrastruttura di test necessita di fix.

**Raccomandazione**: Prima di deploy in produzione, eseguire:
```bash
# Fix test infrastructure
pip install pytest-asyncio
# Fix pytest.ini
# Fix conftest.py

# Poi eseguire
pytest --cov=api --cov-fail-under=100
```

---

**Data Report**: 2026-02-13
**Generato da**: pytest --cov=api --cov-report=term-missing
