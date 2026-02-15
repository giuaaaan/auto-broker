#!/bin/bash

echo "🚀 Starting Auto-Broker Services..."

# Start Backend
cd /workspaces/auto-broker/api
python main.py > /tmp/api.log 2>&1 &
echo "✅ Backend started on http://localhost:8000"

# Wait a moment for backend to start
sleep 5

# Start Frontend
cd /workspaces/auto-broker/dashboard
npm run dev > /tmp/dashboard.log 2>&1 &
echo "✅ Frontend started on http://localhost:5173"

echo ""
echo "🎉 Auto-Broker is running!"
echo "📊 Dashboard: http://localhost:5173"
echo "🔌 API Docs: http://localhost:8000/docs"
echo ""
echo "Login: admin@autobroker.com / admin"
echo ""
