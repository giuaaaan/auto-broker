#!/bin/bash

echo "🚀 Starting Auto-Broker Services..."

# Function to check if a service is healthy
check_service() {
    local name=$1
    local url=$2
    local max_attempts=30
    local attempt=1
    
    echo "⏳ Waiting for $name..."
    while [ $attempt -le $max_attempts ]; do
        if curl -s "$url" > /dev/null 2>&1; then
            echo "✅ $name is ready!"
            return 0
        fi
        echo "  Attempt $attempt/$max_attempts - waiting..."
        sleep 2
        attempt=$((attempt + 1))
    done
    
    echo "⚠️  $name may not be ready, continuing anyway..."
    return 1
}

# Check all services
check_service "PostgreSQL" "localhost:5432" || true
check_service "Redis" "localhost:6379" || true
check_service "Vault" "http://localhost:8200/v1/sys/health" || true
check_service "ChromaDB" "http://localhost:8001/api/v1/heartbeat" || true
check_service "Ollama" "http://localhost:11434/api/tags" || true

# Start Backend
echo "🖥️  Starting Backend API..."
cd /workspaces/auto-broker/api
source .env 2>/dev/null || true
python main.py > /tmp/api.log 2>&1 &
API_PID=$!
echo "✅ Backend started (PID: $API_PID) on http://localhost:8000"

# Wait for API to be ready
echo "⏳ Waiting for API to be ready..."
sleep 5
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ API is responding!"
else
    echo "⚠️  API may still be starting, check logs with: tail -f /tmp/api.log"
fi

# Start Frontend
echo "🎨 Starting Frontend Dashboard..."
cd /workspaces/auto-broker/dashboard
npm run dev > /tmp/dashboard.log 2>&1 &
DASH_PID=$!
echo "✅ Frontend started (PID: $DASH_PID) on http://localhost:5173"

# Save PIDs for later
echo $API_PID > /tmp/auto-broker-api.pid
echo $DASH_PID > /tmp/auto-broker-dashboard.pid

echo ""
echo "🎉 Auto-Broker is starting up!"
echo ""
echo "📊 Services Status:"
echo "   🔌 API:        http://localhost:8000"
echo "   📖 API Docs:   http://localhost:8000/docs"
echo "   🌐 Dashboard:  http://localhost:5173"
echo "   🗄️  ChromaDB:   http://localhost:8001"
echo "   🔐 Vault:      http://localhost:8200"
echo "   🤖 Ollama:     http://localhost:11434"
echo ""
echo "🔐 Default Login:"
echo "   Email: admin@autobroker.com"
echo "   Password: admin"
echo ""
echo "📝 Logs:"
echo "   API:        tail -f /tmp/api.log"
echo "   Dashboard:  tail -f /tmp/dashboard.log"
echo ""
echo "⚡ To stop services:"
echo "   kill \$(cat /tmp/auto-broker-api.pid) \$(cat /tmp/auto-broker-dashboard.pid)"
echo ""
