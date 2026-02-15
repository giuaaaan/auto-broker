#!/bin/bash
set -e

echo "🚀 Auto-Broker Setup (Big Tech Style)"
echo "======================================"

# Installa Redis
sudo apt-get update && sudo apt-get install -y redis-tools lsof

# Installa dipendenze Python
echo "📦 Installing Python dependencies..."
cd /workspace/api
pip install --no-cache-dir -r requirements.txt 2>/dev/null || pip install --no-cache-dir \
    fastapi uvicorn sqlalchemy psycopg2-binary redis \
    python-jose[cryptography] python-multipart passlib[bcrypt] \
    pydantic-settings python-socketio requests aiohttp beautifulsoup4

# Installa dipendenze Dashboard
echo "📦 Installing Dashboard dependencies..."
cd /workspace/dashboard
npm ci

# Crea .env per dashboard
cat > /workspace/dashboard/.env << 'EOF'
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000
EOF

echo "✅ Setup completo!"
