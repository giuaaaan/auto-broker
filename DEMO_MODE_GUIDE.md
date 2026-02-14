# 🎮 Auto-Broker DEMO MODE Guide

**Testa Auto-Broker su Oracle Cloud senza spendere 1 euro**

> Dashboard NASA al 100% funzionale - Mappe animate, grafici in tempo reale, WebSocket attivi - tutto con dati simulati.

---

## 💰 Costi Reali

| Modalità | Costo Mensile |
|----------|---------------|
| **DEMO_MODE** | **€0.00** |
| Produzione (con API reali) | €50-200/mese |

---

## ⚡ Quick Start (3 comandi)

```bash
# 1. Clone repository
git clone https://github.com/giuaaaan/auto-broker.git
cd auto-broker

# 2. Configura DEMO_MODE
cp .env.oracle.example .env.oracle
# Modifica: DEMO_MODE=true (già impostato di default)

# 3. Deploy
./scripts/deploy-oracle-enterprise.sh

# 4. Apri nel browser
echo "http://$(curl -s ifconfig.me)"
```

**Risultato:** Dashboard NASA funzionante con:
- 🗺️ **Mappe animate** - Camion che si muovono da Milano a Roma
- 📈 **Revenue che sale** - +€50-300 ogni 30 secondi
- 🤖 **Agenti AI simulati** - SARA, PAOLO, GIULIA in azione
- 🚨 **Alert real-time** - Failover carrier, dispute resolution
- 💬 **WebSocket attivi** - Tutto in tempo reale

---

## 🎯 Cosa Funziona in DEMO_MODE

### ✅ Completamente Funzionale

| Feature | Stato | Note |
|---------|-------|------|
| **Dashboard NASA** | ✅ 100% | Tutte le animazioni attive |
| **Mappe 2D/3D** | ✅ 100% | Marker GPS che si muovono |
| **Grafici Revenue** | ✅ 100% | Crescono in tempo reale |
| **WebSocket** | ✅ 100% | Update ogni 5 secondi |
| **Agent Status** | ✅ 100% | Badge attività simulata |
| **Tutti i bottoni** | ✅ 100% | Cliccabili con feedback |
| **Autenticazione JWT** | ✅ 100% | Login funzionante |
| **API Documentazione** | ✅ 100% | /api/docs disponibile |

### 🎭 Simulato (No Costi Reali)

| Servizio Reale | Simulazione | Risparmio |
|----------------|-------------|-----------|
| Hume AI (emozioni) | Mock con latenza 0.5s | ~€0.01/chiamata |
| Insighto (telefonate) | Mock con audio placeholder | ~€0.15/chiamata |
| Blockchain Polygon | Mock istantaneo | ~€0.50-5.00/tx |
| Carrier API | Dati finti realistici | Variabile |

---

## 🔧 Configurazione

### File .env.oracle minimale per DEMO:

```bash
# Obbligatorio
DEMO_MODE=true

# Opzionali in DEMO (possono essere vuoti/finti)
HUME_API_KEY=demo_key
HUME_SECRET_KEY=demo_secret
INSIGHTO_API_KEY=demo_key
JWT_SECRET=qualunque_stringa_lunga_32_chars

# Database (default va bene)
DB_PASSWORD=autobroker_secure_2024
```

**Nessuna API key reale richiesta!**

---

## 🧪 Testare gli Endpoint Demo

### 1. Verifica Stato Demo

```bash
curl http://localhost:8000/demo/status
```

**Risposta:**
```json
{
  "demo_mode": true,
  "mock_services": {
    "hume": 0,
    "insighto": 0,
    "blockchain": {
      "total_transactions": 0,
      "gas_saved_usd": "$0.00"
    }
  },
  "timestamp": "2025-01-15T10:30:00"
}
```

### 2. Test Emergency Stop

```bash
curl -X POST http://localhost:8000/demo/command/emergency-stop
```

**Risposta:**
```json
{
  "success": true,
  "message": "Emergency stop simulated (Demo Mode)",
  "action": "all_operations_halted",
  "mock": true
}
```

### 3. Test Cambio Carrier

```bash
curl -X POST "http://localhost:8000/demo/command/change-carrier?shipment_id=SHIP-123&new_carrier=DHL"
```

### 4. Test Analisi Emozioni (Mock Hume)

```bash
curl -X POST "http://localhost:8000/demo/test/emotion-analysis?text=Sono%20molto%20interessato"
```

**Risposta:**
```json
{
  "sentiment": "positive",
  "engagement_score": 0.85,
  "mock": true
}
```

### 5. Test Telefonata (Mock Insighto)

```bash
curl -X POST "http://localhost:8000/demo/test/make-call?phone=+390123456789&script=Demo"
```

**Risposta:**
```json
{
  "call_id": "...",
  "status": "completed",
  "duration_seconds": 245,
  "mock": true,
  "cost_saved": "€0.15"
}
```

### 6. Test Blockchain (Mock Polygon)

```bash
curl -X POST "http://localhost:8000/demo/test/blockchain-tx?value_eth=0.01"
```

**Risposta:**
```json
{
  "transaction_hash": "0x...",
  "value_eth": 0.01,
  "gas_cost_usd": "$0.00 (Demo Mode)",
  "mock": true
}
```

---

## 🎬 Cosa Vedrai nella Dashboard

### 1. Banner Demo Mode

In alto nella dashboard vedrai:
```
🎮 DEMO MODE - Dati simulati, nessun costo reale
```

### 2. Revenue che Sale

Ogni 30 secondi:
- Revenue totale aumenta di €50-300
- Nuove spedizioni appaiono sulla mappa
- Grafici si aggiornano in tempo reale

### 3. Agenti in Azione

Ogni 2-10 minuti:
- **SARA**: "Chiamata completata: Rossi Srl - Interested!"
- **MARCO**: "Lead qualified: Bianchi Spa - Score 85/100"
- **PAOLO**: "🚨 Alert: Bartolini performance degraded"
- **GIULIA**: "Dispute resolved: damaged_goods"
- **ANNA**: "Shipment delivered successfully"

### 4. Camion che Si Muovono

Sulla mappa:
- Marker blu si spostano da città a città
- Partono da Milano, arrivano a Roma
- Velocità realistica (60-90 km/h)
- Percorso interpolato

### 5. Toast Notifications

Quando clicchi bottoni:
```
✅ Azione simulata con successo (Demo)
```

---

## 🔍 Monitoraggio Demo

### Logs Container

```bash
# Vedi log dei mock services
docker-compose -f docker-compose.oracle.enterprise.yml logs -f api
```

**Output atteso:**
```
api  | 🎮 [MOCK Hume] Emotion analysis: joy (0.85)
api  | 📞 [MOCK Insighto] Called +39... - Success!
api  | ⛓️  [MOCK Blockchain] TX sent: 0.01 ETH
api  | 📞 [MOCK SARA] Called Rossi Srl - Success!
api  | 🚨 [MOCK PAOLO] Alert: Bartolini - Failover initiated
api  | 💰 [MOCK] New shipment: SHIP-ABC123 €150.00
api  | ✅ [MOCK PAOLO] Failover resolved for Bartolini
```

### Statistiche Demo

```bash
curl http://localhost:8000/demo/mock-data
```

---

## 🚀 Passaggio a Produzione

Quando sei pronto per usare API reali:

```bash
# 1. Ottieni API keys reali
# Hume AI: https://dev.hume.ai
# Insighto: https://insighto.ai

# 2. Modifica .env.oracle
DEMO_MODE=false
HUME_API_KEY=tua_chiave_reale
HUME_SECRET_KEY=tuo_secret_reale
INSIGHTO_API_KEY=tua_chiave_reale
JWT_SECRET=stringa_casuale_lunga_32_chars

# 3. Riavvia
./scripts/deploy-oracle-enterprise.sh
```

**Costi stimati produzione:**
- Hume AI: €0.01-0.05 per analisi
- Insighto: €0.10-0.20 per telefonata
- Blockchain: €0.50-5.00 per transazione

---

## 🐛 Troubleshooting Demo

### Dashboard non mostra dati

```bash
# Verifica che DEMO_MODE sia attivo
curl http://localhost:8000/demo/status

# Riavvia i servizi
docker-compose -f docker-compose.oracle.enterprise.yml restart api
```

### Mappe non animate

```bash
# Verifica WebSocket
curl http://localhost:8000/health

# Controlla logs errori
docker-compose -f docker-compose.oracle.enterprise.yml logs api | grep -i error
```

### Revenue non sale

```bash
# Verifica revenue generator
curl http://localhost:8000/demo/mock-data

# Riavvia se necessario
docker-compose -f docker-compose.oracle.enterprise.yml restart api
```

---

## 📊 Comparativa DEMO vs Produzione

| Aspetto | DEMO_MODE | Produzione |
|---------|-----------|------------|
| **Costo** | €0 | €50-200/mese |
| **Setup** | 3 comandi | 10+ comandi |
| **API Keys** | Non necessarie | Richieste |
| **Telefonate** | Simulate | Reali |
| **Blockchain** | Mock | Polygon reale |
| **Dati** | Finti ma realistici | Reali |
| **Dashboard** | Identica | Identica |
| **Performance** | Stessa | Stessa |

---

## 💡 Use Cases Demo Mode

### ✅ Ideale Per:
- **Demo vendita** - Mostra al cliente senza costi
- **Sviluppo** - Testa UI/UX senza API rate limits
- **Staging** - Ambiente pre-produzione
- **Formazione** - Impara il sistema senza rischi
- **Presentazioni** - Pitch a investitori

### ❌ Non Adatto Per:
- **Produzione reale** - Dati non persistenti
- **Testing integrazione** - API esterne mockate
- **Load testing** - Comportamento diverso sotto carico

---

## 🔐 Sicurezza Demo

- I dati sono **completamente finti**
- **Nessuna chiamata HTTP esterna**
- **Nessuna persistenza** oltre il container
- Safe per **pubblic exposure**

---

**Built with ❤️ for zero-cost testing**

*Deploy su Oracle Cloud Free Tier e inizia a testare in 5 minuti!*
