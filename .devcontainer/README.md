# 🚀 Auto-Broker su GitHub Codespaces

Questa configurazione ti permette di avviare l'intero sistema Auto-Broker su GitHub Codespaces in pochi click!

## 🎯 Come Iniziare

### 1. Apri su Codespaces
1. Vai su https://github.com/codespaces
2. Clicca **"New codespace"**
3. Seleziona il repository `auto-broker`
4. Scegli la configurazione **Auto-Broker Development**
5. Clicca **Create codespace**

### 2. Attendi l'Avvio Automatico
- Il setup installa automaticamente tutte le dipendenze
- I servizi Docker (Postgres, Redis, n8n, Chroma, Ollama) si avviano
- Il backend FastAPI si avvia sulla porta 8000
- La Dashboard React si avvia sulla porta 5173

### 3. Accedi alla Dashboard
Una volta pronto, vedrai un popup che ti chiede di aprire il browser su:
```
https://<CODESPACE_NAME>-5173.github.dev
```

**Login:**
- Email: `admin@autobroker.com`
- Password: `admin`

---

## 📱 Servizi Disponibili

| Servizio | URL | Porta |
|----------|-----|-------|
| 🌐 Dashboard | `https://<name>-5173.github.dev` | 5173 |
| 🔌 API Docs | `https://<name>-8000.github.dev/docs` | 8000 |
| 📊 n8n | `https://<name>-5678.github.dev` | 5678 |
| 🧠 Chroma | `https://<name>-8001.github.dev` | 8001 |
| 🤖 Ollama | `https://<name>-11434.github.dev` | 11434 |

---

## 🛠️ Comandi Utili

### Terminali disponibili
Codespaces apre automaticamente più terminali:
- **Terminal 1**: Log del backend
- **Terminal 2**: Log della dashboard  
- **Terminal 3**: Shell per comandi

### Comandi Manuali
```bash
# Vedi i processi in esecuzione
ps aux | grep -E "(python|node|vite)"

# Riavvia il backend
cd /workspace/api && python main.py

# Riavvia la dashboard
cd /workspace/dashboard && npm run dev

# Vedi log PostgreSQL
docker logs auto-broker-postgres

# Vedi log Redis
docker logs auto-broker-redis
```

---

## 🎨 Features della Dashboard

- **🗺️ Mappa 2D/3D**: Toggle tra MapLibre GL e Three.js globe
- **📦 Spedizioni**: CRUD completo con tracking
- **🤖 AI Agents**: Stato in tempo reale di SARA, MARCO, PAOLO, GIULIA
- **💰 Revenue HUD**: MRR live con animazioni
- **📡 WebSocket**: Aggiornamenti real-time
- **🎮 Command Center**: Controlli emergency, Black Friday mode

---

## 🐛 Troubleshooting

### Porte non raggiungibili
1. Vai su **Ports** nel pannello inferiore di VS Code
2. Clicca su **Port 5173** → **Port Visibility** → **Public**

### Database vuoto
```bash
cd /workspace
python scripts/seed_dashboard.py
```

### Ricostruisci tutto
```bash
cd /workspace
docker-compose -f docker-compose.codespaces.yml down
docker-compose -f docker-compose.codespaces.yml up -d
```

---

## 💡 Note

- Il primo avvio richiede ~5 minuti (download immagini Docker)
- I dati nel database persistono fino alla distruzione del codespace
- Usa **Stop codespace** per mettere in pausa (conserva dati)
- Usa **Delete codespace** per eliminare definitivamente

---

## 📞 Supporto

Problemi? Controlla:
1. Log in **Output** → **GitHub Codespaces**
2. Porte in **Ports** panel
3. Container in **Docker** extension

Buon lavoro! 🚀
