#!/bin/bash
set -e

echo "🚀 Avvio servizi Auto-Broker..."
echo "================================"

# Start PostgreSQL via Docker
echo "🐘 Avvio PostgreSQL..."
docker run -d \
    --name postgres \
    --rm \
    -p 5432:5432 \
    -e POSTGRES_USER=broker_user \
    -e POSTGRES_PASSWORD=broker_pass_2024 \
    -e POSTGRES_DB=broker_db \
    -v /workspace/init.sql:/docker-entrypoint-initdb.d/init.sql:ro \
    postgres:15-alpine 2>/dev/null || echo "PostgreSQL già in esecuzione"

# Start Redis via Docker
echo "⚡ Avvio Redis..."
docker run -d \
    --name redis \
    --rm \
    -p 6379:6379 \
    redis:7-alpine 2>/dev/null || echo "Redis già in esecuzione"

# Attendi che i servizi siano pronti
echo "⏳ Attendo servizi..."
sleep 5

# Popola database
echo "🌱 Popolando database..."
cd /workspace
python scripts/seed_dashboard.py 2>/dev/null || true

# Avvia Backend
echo "🖥️  Avvio Backend..."
cd /workspace/api
python main.py > /tmp/api.log 2>&1 &

# Avvia Dashboard
echo "🎨 Avvio Dashboard..."
cd /workspace/dashboard
npm run dev > /tmp/dashboard.log 2>&1 &

echo ""
echo "🎉 TUTTO PRONTO!"
echo "================"
echo "Dashboard: https://${CODESPACE_NAME}-5173.github.dev"
echo "API:       https://${CODESPACE_NAME}-8000.github.dev"
echo ""
echo "Login: admin@autobroker.com / admin"
echo ""
