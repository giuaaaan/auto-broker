#!/bin/bash
# =============================================================================
# Auto-Broker Enterprise Deploy Script
# Oracle Cloud Free Tier - ARM Ampere A1 (4GB RAM / 1 CPU)
# Zero-Waste Architecture Deployment
# =============================================================================

set -euo pipefail

# Colori per output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configurazione
COMPOSE_FILE="docker-compose.oracle.enterprise.yml"
ENV_FILE=".env.oracle"
PROJECT_NAME="autobroker"

# Logging functions
log_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
log_success() { echo -e "${GREEN}✅ $1${NC}"; }
log_warn() { echo -e "${YELLOW}⚠️  $1${NC}"; }
log_error() { echo -e "${RED}❌ $1${NC}"; }
log_step() { echo -e "${BLUE}🚀 $1${NC}"; }

# =============================================================================
# PRE-FLIGHT CHECKS
# =============================================================================
log_step "Pre-flight checks..."

# Check se siamo su Oracle Cloud
if [[ -f /etc/oracle-release ]] || [[ -f /etc/oracle-linux-release ]]; then
    log_info "Detected Oracle Cloud Infrastructure"
    IS_ORACLE_CLOUD=true
else
    log_warn "Not running on Oracle Cloud - some optimizations may not apply"
    IS_ORACLE_CLOUD=false
fi

# Check Docker
docker info > /dev/null 2>&1 || {
    log_error "Docker is not running or not installed"
    exit 1
}

# Check Docker Compose
if ! docker-compose --version > /dev/null 2>&1 && ! docker compose version > /dev/null 2>&1; then
    log_error "Docker Compose is not installed"
    exit 1
fi

# Check env file
if [[ ! -f "$ENV_FILE" ]]; then
    log_warn "Environment file $ENV_FILE not found, creating from example..."
    if [[ -f ".env.oracle.example" ]]; then
        cp .env.oracle.example "$ENV_FILE"
        log_error "Please edit $ENV_FILE with your credentials before deploying"
        exit 1
    else
        log_error "No .env.oracle.example file found"
        exit 1
    fi
fi

# Check required env vars
source "$ENV_FILE"
MISSING_VARS=()

[[ -z "${HUME_API_KEY:-}" ]] && MISSING_VARS+=("HUME_API_KEY")
[[ -z "${JWT_SECRET:-}" ]] && MISSING_VARS+=("JWT_SECRET")

if [[ ${#MISSING_VARS[@]} -gt 0 ]]; then
    log_error "Missing required environment variables:"
    printf '  - %s\n' "${MISSING_VARS[@]}"
    exit 1
fi

log_success "Pre-flight checks passed"

# =============================================================================
# SYSTEM TUNING (Oracle Cloud specific)
# =============================================================================
if [[ "$IS_ORACLE_CLOUD" == true ]]; then
    log_step "Applying Oracle Cloud system tuning..."
    
    # VM Swappiness - preferisci RAM a swap
    sudo sysctl -w vm.swappiness=10 2>/dev/null || true
    sudo sysctl -w vm.vfs_cache_pressure=50 2>/dev/null || true
    
    # Aumenta limiti file descriptors
    sudo sysctl -w fs.file-max=65536 2>/dev/null || true
    
    # Network tuning per containers
    sudo sysctl -w net.ipv4.ip_local_port_range="1024 65535" 2>/dev/null || true
    sudo sysctl -w net.ipv4.tcp_tw_reuse=1 2>/dev/null || true
    
    # Persisti tuning
    if [[ ! -f /etc/sysctl.d/99-autobroker.conf ]]; then
        echo "vm.swappiness=10
vm.vfs_cache_pressure=50
fs.file-max=65536
net.ipv4.ip_local_port_range=1024 65535
net.ipv4.tcp_tw_reuse=1" | sudo tee /etc/sysctl.d/99-autobroker.conf > /dev/null
        log_info "System tuning persisted to /etc/sysctl.d/99-autobroker.conf"
    fi
    
    log_success "System tuning applied"
fi

# =============================================================================
# DOCKER PRUNE (se richiesto)
# =============================================================================
if [[ "${PRUNE:-false}" == "true" ]]; then
    log_step "Pruning Docker system..."
    docker system prune -af --volumes
    log_success "Docker system pruned"
fi

# =============================================================================
# BUILD IMAGES
# =============================================================================
log_step "Building optimized Docker images..."

export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1

docker-compose -f "$COMPOSE_FILE" build --parallel --no-cache

log_success "Images built successfully"

# =============================================================================
# DATABASE MIGRATIONS
# =============================================================================
log_step "Running database setup..."

# Start database layer
docker-compose -f "$COMPOSE_FILE" up -d postgres redis

# Wait for PostgreSQL health
log_info "Waiting for PostgreSQL to be ready..."
for i in {1..30}; do
    if docker-compose -f "$COMPOSE_FILE" exec -T postgres pg_isready -U "${DB_USER:-autobroker}" > /dev/null 2>&1; then
        log_success "PostgreSQL is ready"
        break
    fi
    sleep 1
    if [[ $i -eq 30 ]]; then
        log_error "PostgreSQL failed to start"
        exit 1
    fi
done

# Run migrations
log_info "Running database migrations..."
docker-compose -f "$COMPOSE_FILE" run --rm api python -m alembic upgrade head 2>/dev/null || {
    log_warn "No migrations found or migration failed, continuing..."
}

log_success "Database setup complete"

# =============================================================================
# START SERVICES
# =============================================================================
log_step "Starting services..."

# Start core services (senza Ollama per default)
docker-compose -f "$COMPOSE_FILE" up -d

# Wait for API health
log_info "Waiting for API to be ready..."
for i in {1..60}; do
    if curl -sf http://localhost:8000/health > /dev/null 2>&1 || \
       docker-compose -f "$COMPOSE_FILE" exec -T api wget -qO- http://localhost:8000/health > /dev/null 2>&1; then
        log_success "API is ready"
        break
    fi
    sleep 2
    if [[ $i -eq 60 ]]; then
        log_error "API failed to start"
        docker-compose -f "$COMPOSE_FILE" logs api --tail=50
        exit 1
    fi
done

# =============================================================================
# DEPLOYMENT SUMMARY
# =============================================================================
log_step "Deployment complete!"

# Get public IP
PUBLIC_IP=$(curl -s ifconfig.me 2>/dev/null || echo "localhost")

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "                    🚀 AUTO-BROKER v1.5.0                      "
echo "              Enterprise Deployment Complete                   "
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "  📍 Access URLs:"
echo "     • Dashboard:  http://${PUBLIC_IP}"
echo "     • API Docs:   http://${PUBLIC_IP}/api/docs"
echo "     • Health:     http://${PUBLIC_IP}/health"
echo ""
echo "  🐳 Container Status:"
docker-compose -f "$COMPOSE_FILE" ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || \
    docker-compose -f "$COMPOSE_FILE" ps
echo ""
echo "  💾 Resource Usage:"
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}" 2>/dev/null | grep autobroker || \
    echo "    Run 'docker stats' to see live resource usage"
echo ""
echo "  📊 Useful Commands:"
echo "     View logs:        docker-compose -f ${COMPOSE_FILE} logs -f"
echo "     Restart API:      docker-compose -f ${COMPOSE_FILE} restart api"
echo "     Shell in API:     docker-compose -f ${COMPOSE_FILE} exec api sh"
echo "     DB Console:       docker-compose -f ${COMPOSE_FILE} exec postgres psql -U autobroker"
echo "     Backup DB:        ./scripts/backup-oracle.sh"
echo ""
echo "  ⚠️  Notes:"
echo "     • Ollama AI is DISABLED by default (saves 1.5GB RAM)"
echo "     • Using Hume AI Cloud for emotional intelligence"
echo "     • If you need local AI: docker-compose -f ${COMPOSE_FILE} --profile local-ai up -d ollama"
echo ""
echo "═══════════════════════════════════════════════════════════════"

# =============================================================================
# POST-DEPLOY HEALTH CHECK
# =============================================================================
sleep 2
if curl -sf http://localhost/health > /dev/null 2>&1; then
    log_success "✨ All systems operational!"
else
    log_warn "Health check pending - services may still be starting"
fi
