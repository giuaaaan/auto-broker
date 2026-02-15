#!/bin/bash
set -e

echo "🚀 Auto-Broker Codespace Setup"
echo "=============================="

# Installa le dipendenze Python per l'API
echo "📦 Installando dipendenze Python..."
cd /workspace/api
pip install -r requirements.txt 2>/dev/null || pip install fastapi uvicorn sqlalchemy psycopg2-binary redis python-jose[cryptography] python-multipart passlib[bcrypt] pydantic-settings python-socketio requests aiohttp beautifulsoup4

# Installa le dipendenze della Dashboard
echo "📦 Installando dipendenze Dashboard..."
cd /workspace/dashboard
npm install

# Crea file .env per la dashboard se non esiste
if [ ! -f "/workspace/dashboard/.env" ]; then
    echo "🔧 Creando file .env per la dashboard..."
    cat > /workspace/dashboard/.env << 'EOF'
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000
EOF
fi

echo ""
echo "✅ Setup completato!"
echo ""
echo "📝 Prossimi passi:"
echo "   1. Attendi che i servizi Docker siano pronti (postgres, redis, etc.)"
echo "   2. Il sistema si avvierà automaticamente"
echo "   3. Accedi alla dashboard su: http://localhost:5173"
echo ""
echo "   Login: admin@autobroker.com / admin"
echo ""
