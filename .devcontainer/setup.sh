#!/bin/bash
set -e

echo "🚀 Setup Auto-Broker..."

# Installa dipendenze Python
cd /workspaces/auto-broker/api
pip install -r requirements.txt 2>/dev/null || pip install fastapi uvicorn sqlalchemy psycopg2-binary redis python-jose[cryptography] python-multipart passlib[bcrypt] pydantic-settings python-socketio requests aiohttp beautifulsoup4

# Installa dipendenze Dashboard
cd /workspaces/auto-broker/dashboard
npm install

# Crea .env
echo "VITE_API_URL=http://localhost:8000" > /workspaces/auto-broker/dashboard/.env
echo "VITE_WS_URL=ws://localhost:8000" >> /workspaces/auto-broker/dashboard/.env

echo "✅ Setup completato!"
