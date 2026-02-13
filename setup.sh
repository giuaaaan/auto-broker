#!/bin/bash
set -e

echo "=========================================="
echo "  AUTO-BROKER Setup"
echo "=========================================="

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not installed"
    exit 1
fi

# Create env file
if [ ! -f .env ]; then
    cp .env.example .env
    echo "⚠️  Created .env - edit it with your API keys"
fi

# Create directories
mkdir -p data api/generated logs

# Build and start
echo "🐳 Building and starting services..."
docker-compose build
docker-compose up -d

# Wait for services
echo "⏳ Waiting for services..."
sleep 30

# Health checks
echo "🏥 Checking health..."
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ API is running"
else
    echo "⚠️  API not responding yet"
fi

if curl -s http://localhost:5678/healthz > /dev/null 2>&1; then
    echo "✅ n8n is running"
else
    echo "⚠️  n8n not responding yet"
fi

echo ""
echo "=========================================="
echo "  ✅ Setup Complete!"
echo "=========================================="
echo ""
echo "📍 Access Points:"
echo "   • n8n:     http://localhost:5678 (admin/admin123)"
echo "   • API:     http://localhost:8000/docs"
echo "   • Health:  http://localhost:8000/health"
echo ""
echo "📖 Next Steps:"
echo "   1. Edit .env with real API keys"
echo "   2. Import workflows from n8n-workflows/"
echo "   3. Upload leads to data/leads.csv"
echo ""
echo "🛑 Stop: docker-compose down"
echo "📊 Logs: docker-compose logs -f"
