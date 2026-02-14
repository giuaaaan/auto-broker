# Auto-Broker Mission Control Center

Dashboard React avanzata per il controllo e monitoraggio in tempo reale della piattaforma Auto-Broker.

## 🚀 Features

### Mappa Avanzata (2D/3D)
- **MapLibre GL JS** per mappe 2D con stile dark (CartoDB)
- **Three.js + React Three Fiber** per visualizzazione globo 3D
- Toggle seamless tra 2D e 3D
- Marker personalizzati con animazioni
- Linee di flusso animate (effetto dati che scorrono)
- Clustering e heatmap

### Real-Time WebSocket
- Connessione Socket.IO a `/ws/command-center`
- Aggiornamenti ogni secondo:
  - Posizioni carrier (lat/long)
  - Cambi stato spedizioni
  - Alert PAOLO
  - Aggiornamento revenue
- Indicatori connessione LED
- Reconnect automatico con backoff esponenziale

### UI/UX Premium
- **Glassmorphism design** con backdrop blur
- **Framer Motion** per animazioni fluide
- **Dark theme** con palette coerente
- **CountUp** per animazioni numeriche
- **Recharts** per grafici complessi
- Responsive (desktop-first, mobile supportato)

### Pannelli Controllo
- **Revenue HUD**: MRR in tempo reale con progress bar livelli
- **AI Agents Status**: Stato SARA, MARCO, PAOLO, GIULIA
- **Active Shipments**: Lista spedizioni con filtri
- **Command Center**: Controlli emergency, Black Friday mode
- **Analytics**: Grafici revenue, margini, heatmap oraria

## 🛠️ Stack Tecnico

- **React 18** + TypeScript (strict mode)
- **Vite** (build tool)
- **Tailwind CSS** (styling)
- **Zustand** (state management)
- **React Query** (server state)
- **Socket.IO Client** (real-time)
- **MapLibre GL JS** (mappe 2D)
- **Three.js + React Three Fiber** (globo 3D)
- **Recharts** (grafici)
- **React Hook Form + Zod** (forms)
- **React Router** (routing)

## 📦 Installazione

```bash
# Installa dipendenze
npm install

# Avvia in sviluppo
npm run dev

# Build produzione
npm run build

# Preview build
npm run preview
```

## 🔧 Configurazione

### Variabili Ambiente

Crea un file `.env` nella root del progetto:

```env
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000
```

### Proxy (Development)

Il `vite.config.ts` include già la configurazione proxy:

```typescript
proxy: {
  '/api': {
    target: 'http://localhost:8000',
    changeOrigin: true,
  },
  '/ws': {
    target: 'ws://localhost:8000',
    ws: true,
  },
}
```

## 🗂️ Struttura Progetto

```
dashboard/
├── src/
│   ├── api/
│   │   └── client.ts          # Axios client + API endpoints
│   ├── components/
│   │   ├── layout/
│   │   │   └── Sidebar.tsx    # Navigation sidebar
│   │   ├── map/
│   │   │   ├── Map2D.tsx      # MapLibre 2D map
│   │   │   └── Globe3D.tsx    # Three.js globe
│   │   ├── modals/
│   │   │   ├── ShipmentDetailsModal.tsx
│   │   │   ├── AgentLogsModal.tsx
│   │   │   ├── CreateShipmentModal.tsx
│   │   │   ├── EmergencyStopModal.tsx
│   │   │   └── RevenueDetailsModal.tsx
│   │   ├── panels/
│   │   │   ├── RevenueHUD.tsx
│   │   │   ├── AgentsPanel.tsx
│   │   │   ├── ShipmentsPanel.tsx
│   │   │   └── CommandCenter.tsx
│   │   └── ui/
│   │       ├── ToastContainer.tsx
│   │       └── ModalContainer.tsx
│   ├── hooks/
│   │   ├── useDashboard.ts    # React Query hooks
│   │   └── useWebSocket.ts    # WebSocket hook
│   ├── pages/
│   │   ├── Dashboard.tsx      # Main dashboard
│   │   ├── Login.tsx          # Auth page
│   │   ├── Shipments.tsx      # Shipments list
│   │   ├── Agents.tsx         # AI agents
│   │   ├── Revenue.tsx        # Revenue analytics
│   │   └── Settings.tsx       # Settings
│   ├── store/
│   │   └── index.ts           # Zustand stores
│   ├── types/
│   │   └── index.ts           # TypeScript types
│   ├── utils/
│   │   └── formatters.ts      # Utility functions
│   ├── App.tsx
│   ├── main.tsx
│   └── index.css
├── index.html
├── package.json
├── tailwind.config.js
├── tsconfig.json
└── vite.config.ts
```

## 🔐 Autenticazione

- JWT token stored in `localStorage`
- Protected routes con redirect a `/login`
- Auto-refresh token implementato
- Ruoli: `admin`, `operator`, `viewer`

## 📡 API Endpoints

Tutte le API sono integrate e funzionanti:

```typescript
// Dashboard
GET /api/v1/dashboard/stats

// Shipments
GET    /api/v1/shipments
GET    /api/v1/shipments/:id
POST   /api/v1/shipments
PUT    /api/v1/shipments/:id
DELETE /api/v1/shipments/:id

// Agents
GET /api/v1/agents/status
GET /api/v1/agents/:id/logs

// Revenue
GET /api/v1/revenue/current
GET /api/v1/revenue/metrics
POST /api/v1/economics/simulate

// Commands
POST /api/v1/command/change-carrier
POST /api/v1/command/veto-paolo
POST /api/v1/command/emergency-stop
POST /api/v1/command/resume
POST /api/v1/command/force-level
POST /api/v1/command/black-friday

// WebSocket
WS /ws/command-center
```

## 🎨 Design System

### Colori
- **Background**: `#0A0A0A`
- **Primary (Cyan)**: `#00D9FF`
- **Success (Green)**: `#00FF88`
- **Warning (Orange)**: `#FF6B00`
- **Danger (Red)**: `#FF2D55`
- **Text Primary**: `#FFFFFF`
- **Text Secondary**: `#A0A0A0`

### Typography
- **Body**: Inter
- **Numbers/Mono**: JetBrains Mono

### Glassmorphism
```css
.glass-panel {
  backdrop-filter: blur(16px);
  background: rgba(10, 10, 10, 0.7);
  border: 1px solid rgba(255, 255, 255, 0.1);
  box-shadow: 0 0 20px rgba(0, 217, 255, 0.2);
}
```

## 🚦 Stato Progetto

- [x] Project setup (Vite + React + TS)
- [x] State management (Zustand)
- [x] API integration (React Query)
- [x] Authentication (JWT)
- [x] Map 2D (MapLibre)
- [x] Map 3D (Three.js)
- [x] WebSocket real-time
- [x] Revenue HUD
- [x] AI Agents panel
- [x] Shipments panel
- [x] Command center
- [x] All modals
- [x] Analytics charts
- [x] Settings page
- [x] Responsive design

## 📈 Performance

- Code splitting con lazy loading
- Bundle optimization con manual chunks
- React Query caching
- Virtual scrolling per liste lunghe
- Debounced search inputs

## 🔒 Security

- XSS protection (React default)
- CSRF tokens per API
- Input validation (Zod)
- Sanitized HTML rendering

## 🔌 Backend Integration

### Avvio Completo

1. **Backend FastAPI** (terminale 1):
```bash
cd ../api
source venv/bin/activate
pip install python-jose[cryptography]  # Se non già installato
python main.py
```

2. **Database Seeder** (terminale 2):
```bash
cd ..
python scripts/seed_dashboard.py
```

3. **Dashboard React** (terminale 3):
```bash
npm install  # Solo prima volta
npm run dev
```

4. **Apri browser**: `http://localhost:5173`
   - Login: `admin@autobroker.com` / `admin`

### CORS Configurato
Il backend accetta richieste da:
- `http://localhost:5173`
- `http://localhost:3000`

### API Endpoints
Vedi `DASHBOARD_INTEGRATION.md` nella root del progetto per la lista completa.

---

## 📄 License

Proprietary - Auto-Broker Platform