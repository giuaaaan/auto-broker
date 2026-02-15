#!/bin/bash
set -e

echo "🚀 Avvio Auto-Broker..."

# Aspetta che PostgreSQL sia pronto
echo "⏳ Attendo PostgreSQL..."
until pg_isready -h localhost -p 5432 -U broker_user 2>/dev/null; do
  echo "  PostgreSQL non pronto, aspetto..."
  sleep 2
done
echo "✅ PostgreSQL pronto!"

# Aspetta che Redis sia pronto
echo "⏳ Attendo Redis..."
until redis-cli -h localhost ping 2>/dev/null | grep -q PONG; do
  echo "  Redis non pronto, aspetto..."
  sleep 2
done
echo "✅ Redis pronto!"

# Installa dipendenze Dashboard
echo "📦 Installo npm packages..."
cd /workspace/dashboard
npm ci

# Crea .env
echo "VITE_API_URL=http://localhost:8000" > .env
echo "VITE_WS_URL=ws://localhost:8000" >> .env

# Popola database
echo "🌱 Popolo database..."
cd /workspace
python scripts/seed_dashboard.py 2>/dev/null || true

# Avvia Backend in background
echo "🖥️ Avvio backend..."
cd /workspace/api
nohup python main.py > /tmp/api.log 2>&1 &

# Avvia Dashboard in background  
echo "🎨 Avvio dashboard..."
cd /workspace/dashboard
nohup npm run dev > /tmp/dashboard.log 2>&1 &

echo ""
echo "🎉 TUTTO PRONTO!"
echo "Dashboard: http://localhost:5173"
echo "Login: admin@autobroker.com / admin"
