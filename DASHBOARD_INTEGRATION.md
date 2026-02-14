# AUTO-BROKER: Dashboard Integration Guide

Guida completa per integrare la Mission Control Center Dashboard React con il backend FastAPI.

## 🚀 Quick Start

### 1. Avvia il Backend FastAPI

```bash
cd /Users/romanogiovanni1993gmail.com/Desktop/auto-broker/api

# Attiva virtual environment
source venv/bin/activate  # macOS/Linux
# oppure: venv\Scripts\activate  # Windows

# Installa dipendenze aggiuntive per JWT
pip install python-jose[cryptography]

# Avvia il server
python main.py
# oppure: uvicorn main:app --reload --port 8000
```

Il backend sarà disponibile su `http://localhost:8000`

### 2. Popola il Database con Dati Demo

```bash
cd /Users/romanogiovanni1993gmail.com/Desktop/auto-broker

# Assicurati che il DB sia inizializzato
python scripts/seed_dashboard.py
```

Questo creerà:
- 4 corrieri (Bartolini, DHL, SDA, TNT)
- 8 spedizioni con varie rotte italiane
- 15 pagamenti per simulare €4.850 MRR (Livello 2)

### 3. Avvia la Dashboard React

```bash
cd /Users/romanogiovanni1993gmail.com/Desktop/auto-broker/dashboard

# Installa dipendenze (prima volta)
npm install

# Avvia dev server
npm run dev
```

La dashboard sarà disponibile su `http://localhost:5173`

### 4. Login

Apri il browser su `http://localhost:5173` e accedi con:

- **Email**: `admin@autobroker.com`
- **Password**: `admin`

---

## 📡 API Endpoints Implementati

### Autenticazione
```
POST /api/v1/auth/login          # JWT login
GET  /api/v1/auth/me             # Current user info
POST /api/v1/auth/logout         # Logout
POST /api/v1/auth/refresh        # Refresh token
```

### Dashboard
```
GET /api/v1/dashboard/stats      # Statistiche aggregate
GET /api/v1/agents/status        # Stato AI agents
GET /api/v1/revenue/current      # Livello economico corrente
GET /api/v1/revenue/metrics      # Metriche revenue
```

### Spedizioni
```
GET    /api/v1/shipments         # Lista con filtri
POST   /api/v1/shipments         # Crea nuova
GET    /api/v1/shipments/{id}    # Dettaglio
PUT    /api/v1/shipments/{id}    # Aggiorna
DELETE /api/v1/shipments/{id}    # Elimina
```

### Comandi
```
POST /api/v1/command/change-carrier   # Cambia carrier
POST /api/v1/command/veto-paolo       # Veto PAOLO
POST /api/v1/command/emergency-stop   # Emergency stop
POST /api/v1/command/resume           # Ripristina
POST /api/v1/command/black-friday     # Toggle BF mode
POST /api/v1/command/force-level      # Forza livello
```

### WebSocket
```
WS /ws/command-center           # Real-time updates
```

---

## 🔌 Configurazione CORS

Il CORS è già configurato in `api/main.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Dashboard React
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## 🔐 Autenticazione JWT

Il sistema usa JWT per proteggere gli endpoint:

### Token Structure
```json
{
  "sub": "admin@autobroker.com",
  "user_id": "user-001",
  "role": "admin",
  "exp": 1708473600
}
```

### Protected Routes
Tutte le route `/api/v1/*` (tranne `/api/v1/auth/login`) richiedono il token JWT nell'header:

```
Authorization: Bearer <token>
```

### Ruoli Utente
- **admin**: Accesso completo
- **operator**: Operazioni standard
- **viewer**: Solo lettura

---

## 🌐 WebSocket Real-Time

### Connessione
```javascript
const socket = io('ws://localhost:8000/ws/command-center');
```

### Eventi Supportati

#### Client → Server
- `ping`: Keepalive
- `subscribe`: Iscrizione a canale specifico

#### Server → Client
- `shipment_update`: Aggiornamento spedizione
- `carrier_position`: Posizione carrier
- `agent_activity`: Attività AI agent
- `revenue_update`: Aggiornamento revenue
- `system_alert`: Alert di sistema

### Esempio
```javascript
socket.on('shipment_update', (data) => {
  console.log('Shipment updated:', data);
  // { shipment_id: "...", status: "in_transit", current_position: {...} }
});

socket.on('agent_activity', (data) => {
  if (data.agent_id === 'PAOLO' && data.activity.suggestion) {
    // Mostra notifica suggerimento PAOLO
  }
});
```

---

## 🗂️ Database Schema

### Tabelle Principali

#### Spedizioni
```sql
CREATE TABLE spedizioni (
    id UUID PRIMARY KEY,
    codice_tracking VARCHAR(50) UNIQUE,
    corriere_id UUID REFERENCES corrieri(id),
    origine TEXT,
    destinazione TEXT,
    stato VARCHAR(20),  -- pending, confirmed, in_transit, delivered, cancelled, disputed
    peso_kg FLOAT,
    valore_merce DECIMAL(18,2),
    data_consegna_stimata TIMESTAMP,
    data_consegna_effettiva TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);
```

#### Corrieri
```sql
CREATE TABLE corrieri (
    id UUID PRIMARY KEY,
    nome VARCHAR(100),
    tipo VARCHAR(20),  -- nazionale, internazionale
    rating FLOAT,
    prezzo_per_km DECIMAL(10,4),
    disponibile BOOLEAN DEFAULT TRUE
);
```

#### Pagamenti
```sql
CREATE TABLE pagamenti (
    id UUID PRIMARY KEY,
    importo DECIMAL(18,2),
    stripe_payment_status VARCHAR(20),
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## 🧪 Testing

### Test Manuale

1. **Login**: `curl -X POST http://localhost:8000/api/v1/auth/login -H "Content-Type: application/json" -d '{"email":"admin@autobroker.com","password":"admin"}'`

2. **Get Stats**: `curl -H "Authorization: Bearer <token>" http://localhost:8000/api/v1/dashboard/stats`

3. **List Shipments**: `curl -H "Authorization: Bearer <token>" http://localhost:8000/api/v1/shipments`

4. **Create Shipment**:
```bash
curl -X POST http://localhost:8000/api/v1/shipments \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "origin_address": "Via Test 1",
    "origin_city": "Milano",
    "dest_address": "Via Dest 2",
    "dest_city": "Roma",
    "customer_name": "Test Customer",
    "customer_email": "test@test.com",
    "weight": 100,
    "value": 5000
  }'
```

### Test WebSocket

Apri la console browser sulla dashboard e verifica:
```javascript
// Dovrebbe mostrare "LIVE" connesso
console.log(socket.connected);
```

---

## 🐛 Troubleshooting

### Problema: CORS Error
**Soluzione**: Verifica che `main.py` abbia i giusti `allow_origins` e che il backend sia su porta 8000.

### Problema: JWT Invalid
**Soluzione**: Effettua nuovo login. Il token scade dopo 24h.

### Problema: WebSocket Disconnesso
**Soluzione**: 
1. Verifica che il backend sia running
2. Controlla la console browser per errori
3. Il reconnect è automatico con backoff

### Problema: Database Vuoto
**Soluzione**: Esegui `python scripts/seed_dashboard.py`

---

## 📁 File Structure

```
auto-broker/
├── api/
│   ├── main.py                    # FastAPI app con CORS aggiornato
│   ├── routers/
│   │   ├── auth.py                # JWT authentication
│   │   └── dashboard.py           # Dashboard API endpoints
│   ├── schemas/
│   │   └── dashboard.py           # Pydantic models
│   └── websocket/
│       └── command_center.py      # Socket.IO WebSocket
├── dashboard/
│   ├── src/
│   │   ├── api/client.ts          # Axios client (già configurato)
│   │   └── ...                    # React components
│   └── package.json
├── scripts/
│   └── seed_dashboard.py          # Database seeder
└── DASHBOARD_INTEGRATION.md       # Questo file
```

---

## 🎨 Features Implementate

### ✅ Dashboard React
- [x] Mappa 2D (MapLibre GL JS)
- [x] Mappa 3D (Three.js)
- [x] Toggle 2D/3D
- [x] WebSocket real-time
- [x] Revenue HUD con CountUp
- [x] AI Agents Panel
- [x] Shipments Panel
- [x] Command Center
- [x] Glassmorphism UI
- [x] Dark theme
- [x] Responsive design

### ✅ Backend FastAPI
- [x] CORS configuration
- [x] JWT authentication
- [x] Dashboard endpoints
- [x] Shipments CRUD
- [x] Agents status
- [x] Revenue metrics
- [x] Command endpoints
- [x] WebSocket Socket.IO
- [x] Database seeder

---

## 📞 Supporto

Per problemi o domande:
1. Controlla i log del backend
2. Verifica la console browser
3. Controlla che tutti i servizi siano running

**Status**: ✅ Integrazione completa e testata