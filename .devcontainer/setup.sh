#!/bin/bash
set -e

echo "🚀 Setup Auto-Broker..."

# Installa dipendenze Python
cd /workspaces/auto-broker/api
pip install -r requirements.txt 2>/dev/null || pip install fastapi uvicorn sqlalchemy psycopg2-binary redis python-jose[cryptography] python-multipart passlib[bcrypt] pydantic-settings python-socketio requests aiohttp beautifulsoup4

# Installa dipendenze Dashboard
cd /workspaces/auto-broker/dashboard
npm ci

# Crea .env
cat > /workspaces/auto-broker/dashboard/.env << 'EOF'
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000
EOF

# Setup database
echo "🐘 Setup PostgreSQL..."
sudo service postgresql start 2>/dev/null || true
sleep 2

# Crea utente e database
sudo -u postgres psql -c "CREATE USER broker_user WITH PASSWORD 'broker_pass_2024';" 2>/dev/null || true
sudo -u postgres psql -c "CREATE DATABASE broker_db OWNER broker_user;" 2>/dev/null || true
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE broker_db TO broker_user;" 2>/dev/null || true

# Init schema
cd /workspaces/auto-broker
sudo -u postgres psql broker_db < init.sql 2>/dev/null || true

# Seed data
python scripts/seed_dashboard.py 2>/dev/null || true

# Avvia Redis
echo "⚡ Avvio Redis..."
redis-server --daemonize yes 2>/dev/null || true

echo "✅ Setup completato! Avvio servizi..."

# Avvia Backend
cd /workspaces/auto-broker/api
python main.py > /tmp/api.log 2>&1 &

# Avvia Dashboard
cd /workspaces/auto-broker/dashboard
npm run dev > /tmp/dashboard.log 2>&1 &

echo ""
echo "🎉 PRONTO!"
echo "Dashboard: http://localhost:5173"
echo "Login: admin@autobroker.com / admin"
