# Auto-Broker Dev Container

Configurazione DevContainer professionale per sviluppo locale con tutti i servizi necessari.

## 🚀 Servizi Inclusi

| Servizio | Porta | Descrizione |
|----------|-------|-------------|
| **App** | - | Ambiente di sviluppo principale (Python 3.11 + Node 20) |
| **PostgreSQL** | 5432 | Database principale con pgvector |
| **Redis** | 6379 | Cache e sessioni |
| **Vault** | 8200 | Gestione secrets (dev mode) |
| **ChromaDB** | 8001 | Vector database per AI |
| **Ollama** | 11434 | Local LLM (llama3.2:3b) |

## 🛠️ Setup

### Prerequisiti
- Docker Desktop
- VS Code con estensione "Dev Containers"
- GitHub CLI (opzionale)

### Avvio

1. **Apri in GitHub Codespaces:**
   ```bash
   gh codespace create --repo giuaaaan/auto-broker
   ```

2. **Oppure apri localmente:**
   - Apri VS Code
   - `Cmd/Ctrl + Shift + P` → "Dev Containers: Open Folder in Container"
   - Seleziona la cartella del progetto

3. **Attendi l'inizializzazione:**
   - Lo script `post-create.sh` installerà tutte le dipendenze
   - Verificherà che tutti i servizi siano pronti
   - Creerà i file `.env` necessari

## 🎯 Utilizzo

### Avviare l'applicazione

```bash
# Terminal 1 - Backend
cd api && python main.py

# Terminal 2 - Frontend
cd dashboard && npm run dev
```

### Oppure usa lo script automatico:

```bash
bash .devcontainer/post-start.sh
```

## 🔗 Endpoint Disponibili

Dopo l'avvio:

- 🌐 **Dashboard**: http://localhost:5173
- 🔌 **API**: http://localhost:8000
- 📖 **API Docs**: http://localhost:8000/docs
- 🔐 **Vault UI**: http://localhost:8200 (token: `dev-token`)
- 🗄️ **ChromaDB**: http://localhost:8001
- 🤖 **Ollama**: http://localhost:11434

## 🔐 Credenziali Default

- **Email**: `admin@autobroker.com`
- **Password**: `admin`
- **Vault Token**: `dev-token`

## 📝 Logs

```bash
# Backend API
tail -f /tmp/api.log

# Frontend Dashboard
tail -f /tmp/dashboard.log
```

## 🧪 Testing

```bash
# Esegui tutti i test
cd api && pytest

# Con coverage
cd api && pytest --cov=api --cov-report=html
```

## 🔧 Troubleshooting

### Problema: Servizi non si avviano

```bash
# Verifica lo stato dei container
docker-compose -f .devcontainer/docker-compose.yml ps

# Restart servizi
docker-compose -f .devcontainer/docker-compose.yml restart
```

### Problema: Database non inizializzato

```bash
# Esegui init.sql manualmente
psql -h localhost -U postgres -d autobroker < init.sql
```

### Problema: Ollama modello non scaricato

```bash
# Scarica manualmente
curl -X POST http://localhost:11434/api/pull -d '{"name": "llama3.2:3b"}'
```

## 📊 Health Checks

Tutti i servizi hanno health checks configurati:

```bash
# Verifica salute API
curl http://localhost:8000/health

# Verifica salute ChromaDB
curl http://localhost:8001/api/v1/heartbeat

# Verifica salute Ollama
curl http://localhost:11434/api/tags
```

## 🎨 Features

- ✅ **Hot Reload**: Modifiche al codice si riflettono immediatamente
- ✅ **Debug**: Porte aperte per debug Python e Node.js
- ✅ **Extensions**: Estensioni VS Code preinstallate
- ✅ **Git**: Integrazione completa con Git e GitHub
- ✅ **Testing**: Ambiente pronto per test automatizzati

## 📚 Documentazione

- [Architecture](../docs/ARCHITECTURE.md)
- [API Reference](../docs/API.md)
- [Changelog](../CHANGELOG.md)

---

**BIG TECH 100 Standards** - Production-ready development environment 🚀
