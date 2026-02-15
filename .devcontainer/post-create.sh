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

# Wait for Redis
echo "⏳ Waiting for Redis..."
until redis-cli -h localhost ping > /dev/null 2>&1; do
  echo "  Redis is unavailable - sleeping"
  sleep 2
done
echo "✅ Redis is ready!"

# Setup Python dependencies
echo "📦 Installing Python dependencies..."
cd /workspaces/auto-broker/api
pip install -q -r requirements.txt 2>/dev/null || \
  pip install -q fastapi uvicorn sqlalchemy asyncpg redis python-jose python-multipart passlib pydantic-settings python-socketio requests aiohttp beautifulsoup4

# Setup Node.js dependencies
echo "📦 Installing Node.js dependencies..."
cd /workspaces/auto-broker/dashboard
npm ci 2>/dev/null || npm install

# Create environment files
echo "🔧 Creating environment files..."
cd /workspaces/auto-broker/api
if [ ! -f .env ]; then
  cat > .env << EOF
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/autobroker
REDIS_URL=redis://localhost:6379
DEMO_MODE=true
ENV=development
DEBUG=true
EOF
fi

cd /workspaces/auto-broker/dashboard
if [ ! -f .env ]; then
  cat > .env << EOF
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000
EOF
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "To start the application:"
echo "  Terminal 1: cd api && python main.py"
echo "  Terminal 2: cd dashboard && npm run dev"
echo ""
