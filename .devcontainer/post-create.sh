#!/bin/bash
set -e

echo "🚀 Auto-Broker Dev Container Setup"
echo "==================================="

# Wait for PostgreSQL
echo "⏳ Waiting for PostgreSQL..."
until pg_isready -h localhost -p 5432 -U postgres > /dev/null 2>&1; do
  echo "  PostgreSQL is unavailable - sleeping"
  sleep 2
done
echo "✅ PostgreSQL is ready!"

# Check and install pgvector extension
echo "🔧 Checking pgvector extension..."
psql -h localhost -U postgres -d autobroker -c "CREATE EXTENSION IF NOT EXISTS vector;" 2>/dev/null || echo "  pgvector may need manual installation"

# Wait for Redis
echo "⏳ Waiting for Redis..."
until redis-cli -h localhost ping > /dev/null 2>&1; do
  echo "  Redis is unavailable - sleeping"
  sleep 2
done
echo "✅ Redis is ready!"

# Wait for Vault
echo "⏳ Waiting for Vault..."
until curl -s http://localhost:8200/v1/sys/health > /dev/null 2>&1; do
  echo "  Vault is unavailable - sleeping"
  sleep 2
done
echo "✅ Vault is ready!"

# Wait for ChromaDB
echo "⏳ Waiting for ChromaDB..."
until curl -s http://localhost:8001/api/v1/heartbeat > /dev/null 2>&1; do
  echo "  ChromaDB is unavailable - sleeping"
  sleep 2
done
echo "✅ ChromaDB is ready!"

# Wait for Ollama
echo "⏳ Waiting for Ollama..."
until curl -s http://localhost:11434/api/tags > /dev/null 2>&1; do
  echo "  Ollama is unavailable - sleeping"
  sleep 2
done
echo "✅ Ollama is ready!"

# Check if model is downloaded
echo "🤖 Checking Ollama model..."
if ! curl -s http://localhost:11434/api/tags | grep -q "llama3.2"; then
  echo "  Downloading llama3.2:3b model (this may take a few minutes)..."
  curl -X POST http://localhost:11434/api/pull -d '{"name": "llama3.2:3b"}' || echo "  Model download may have failed, will retry later"
fi

# Setup Python dependencies
echo "📦 Installing Python dependencies..."
cd /workspaces/auto-broker/api
pip install -q -r requirements.txt 2>/dev/null || \
  pip install -q fastapi uvicorn sqlalchemy asyncpg redis python-jose python-multipart passlib pydantic-settings python-socketio requests aiohttp beautifulsoup4 chromadb sentence-transformers

# Setup Node.js dependencies
echo "📦 Installing Node.js dependencies..."
cd /workspaces/auto-broker/dashboard
npm ci 2>/dev/null || npm install

# Create comprehensive environment files
echo "🔧 Creating environment files..."
cd /workspaces/auto-broker/api
if [ ! -f .env ]; then
  cat > .env << EOF
# Application
DEMO_MODE=true
ENV=development
DEBUG=true
LOG_LEVEL=DEBUG

# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/autobroker
REDIS_URL=redis://localhost:6379/0

# Services
VAULT_ADDR=http://localhost:8200
VAULT_TOKEN=dev-token
CHROMA_HOST=localhost
CHROMA_PORT=8001
OLLAMA_HOST=http://localhost:11434

# Security
JWT_SECRET=$(openssl rand -hex 32)
JWT_ALGORITHM=HS256
JWT_EXPIRE_HOURS=24
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000

# Performance
UVICORN_WORKERS=1
CACHE_TTL_DEFAULT=300
EOF
fi

cd /workspaces/auto-broker/dashboard
if [ ! -f .env ]; then
  cat > .env << EOF
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000
EOF
fi

# Initialize database schema
echo "🗄️  Initializing database..."
cd /workspaces/auto-broker
if [ -f init.sql ]; then
  psql -h localhost -U postgres -d autobroker < init.sql 2>/dev/null || echo "  Database may already be initialized"
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "🚀 To start the application:"
echo "   Terminal 1: cd api && python main.py"
echo "   Terminal 2: cd dashboard && npm run dev"
echo ""
echo "📊 Services available:"
echo "   - Dashboard: http://localhost:5173"
echo "   - API: http://localhost:8000"
echo "   - API Docs: http://localhost:8000/docs"
echo "   - ChromaDB: http://localhost:8001"
echo "   - Vault: http://localhost:8200"
echo ""
echo "🔐 Login credentials:"
echo "   Email: admin@autobroker.com"
echo "   Password: admin"
echo ""
