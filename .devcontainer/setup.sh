#!/bin/bash
set -e

echo "╔════════════════════════════════════════╗"
echo "║      Auto-Broker Setup Script          ║"
echo "╚════════════════════════════════════════╝"
echo ""

# Setup PostgreSQL
echo "🐘 Setting up PostgreSQL..."
sudo service postgresql start || true
sleep 3

sudo -u postgres psql -c "CREATE USER broker_user WITH PASSWORD 'broker_pass_2024';" 2>/dev/null || true
sudo -u postgres psql -c "CREATE DATABASE broker_db OWNER broker_user;" 2>/dev/null || true
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE broker_db TO broker_user;" 2>/dev/null || true
sudo -u postgres psql broker_db < /workspace/init.sql 2>/dev/null || true

# Install Redis
echo "🧠 Installing Redis..."
sudo apt-get update && sudo apt-get install -y redis-server 2>/dev/null || true
sudo service redis-server start || true

# Install Python deps
echo "🐍 Installing Python packages..."
cd /workspace/api
pip install -q -r requirements.txt 2>/dev/null || pip install -q fastapi uvicorn sqlalchemy psycopg2-binary redis python-jose[cryptography] python-multipart passlib[bcrypt] pydantic-settings python-socketio requests aiohttp beautifulsoup4 2>/dev/null || true

# Seed database
echo "🌱 Seeding database..."
cd /workspace
python scripts/seed_dashboard.py 2>/dev/null || true

# Install npm deps
echo "📦 Installing npm packages..."
cd /workspace/dashboard
npm ci --silent

# Create .env
echo "VITE_API_URL=http://localhost:8000" > .env
echo "VITE_WS_URL=ws://localhost:8000" >> .env

echo ""
echo "✅ Setup complete!"
echo ""
echo "🚀 Starting services..."
nohup python /workspace/api/main.py > /tmp/api.log 2>&1 &
nohup npm run dev > /tmp/dashboard.log 2>&1 &

echo ""
echo "╔════════════════════════════════════════╗"
echo "║     🎉 Auto-Broker is ready!           ║"
echo "╠════════════════════════════════════════╣"
echo "║  Dashboard: http://localhost:5173      ║"
echo "║  API:       http://localhost:8000      ║"
echo "╠════════════════════════════════════════╣"
echo "║  Login: admin@autobroker.com           ║"
echo "║  Pass:   admin                         ║"
echo "╚════════════════════════════════════════╝"
