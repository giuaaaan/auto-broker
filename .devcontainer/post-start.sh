#!/bin/bash
set -e

echo "🚀 Avvio Auto-Broker su Codespace..."
echo "===================================="

# Attendi che Postgres sia pronto
echo "⏳ Attendo che PostgreSQL sia pronto..."
until pg_isready -h localhost -p 5432 -U broker_user 2>/dev/null; do
    echo "   PostgreSQL non ancora pronto..."
    sleep 2
done
echo "✅ PostgreSQL pronto!"

# Attendi che Redis sia pronto
echo "⏳ Attendo che Redis sia pronto..."
until redis-cli -h localhost ping 2>/dev/null | grep -q PONG; do
    echo "   Redis non ancora pronto..."
    sleep 2
done
echo "✅ Redis pronto!"

# Popola il database con dati demo
echo "🌱 Popolando database con dati demo..."
cd /workspace
python scripts/seed_dashboard.py 2>/dev/null || echo "⚠️  Seeder non trovato o già eseguito"

# Avvia il backend in background
echo "🖥️  Avvio backend FastAPI..."
cd /workspace/api
python main.py &
API_PID=$!

# Attendi che l'API sia pronta
echo "⏳ Attendo che l'API sia pronta..."
for i in {1..30}; do
    if curl -s http://localhost:8000/health 2>/dev/null | grep -q "ok"; then
        echo "✅ API pronta su http://localhost:8000"
        break
    fi
    echo "   API non ancora pronta... (tentativo $i/30)"
    sleep 2
done

# Avvia la dashboard in background
echo "🎨 Avvio Dashboard React..."
cd /workspace/dashboard
npm run dev &
DASH_PID=$!

# Salva i PID per lo shutdown
echo $API_PID > /tmp/auto-broker-api.pid
echo $DASH_PID > /tmp/auto-broker-dashboard.pid

echo ""
echo "========================================"
echo "🎉 Auto-Broker è pronto!"
echo "========================================"
echo ""
echo "📱 Servizi disponibili:"
echo "   🌐 Dashboard:     https://${CODESPACE_NAME}-5173.${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN}"
echo "   🔌 API:           https://${CODESPACE_NAME}-8000.${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN}"
echo "   📊 n8n:           https://${CODESPACE_NAME}-5678.${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN}"
echo ""
echo "   Login: admin@autobroker.com / admin"
echo ""
echo "📖 Per vedere i log:"
echo "   Backend:   ps aux | grep python"
echo "   Dashboard: ps aux | grep vite"
echo ""

# Keep script running
wait
