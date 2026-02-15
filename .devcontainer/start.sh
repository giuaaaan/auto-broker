#!/bin/bash

echo "🚀 Avvio servizi..."

# Avvia PostgreSQL
docker run -d --name postgres --rm -p 5432:5432 \
  -e POSTGRES_USER=broker_user \
  -e POSTGRES_PASSWORD=broker_pass_2024 \
  -e POSTGRES_DB=broker_db \
  -v /workspaces/auto-broker/init.sql:/docker-entrypoint-initdb.d/init.sql:ro \
  postgres:15-alpine 2>/dev/null || true

# Avvia Redis  
docker run -d --name redis --rm -p 6379:6379 redis:7-alpine 2>/dev/null || true

sleep 5

# Popola database
cd /workspaces/auto-broker
python scripts/seed_dashboard.py 2>/dev/null || true

# Avvia Backend
cd /workspaces/auto-broker/api
python main.py &

# Avvia Dashboard
cd /workspaces/auto-broker/dashboard
npm run dev &

echo "🎉 PRONTO!"
echo "Dashboard: http://localhost:5173"
echo "Login: admin@autobroker.com / admin"
