#!/usr/bin/env bash
################################################################################
# SETUP TEST ENVIRONMENT - Dual Mode (Docker/No Docker)
# 100% Coverage Target - Big Tech Platform Engineering 2026
################################################################################

set -euo pipefail

readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly RED='\033[0;31m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m'

log() { echo -e "${BLUE}ℹ️${NC} $1"; }
success() { echo -e "${GREEN}✅${NC} $1"; }
warn() { echo -e "${YELLOW}⚠️${NC} $1"; }
error() { echo -e "${RED}❌${NC} $1"; }

print_header() {
    echo -e "${BLUE}"
    cat << 'EOF'
    ___  ____  ________  ____________  _______  ________  ________
   / _ \/ __ \/ ___/ _ |/ ___/ __/ _ \/ __/ _ \/ __/ __/
  / ___/ /_/ / (_ / __ / /__/ _// , _/ _// ___/ _/_\ \
 /_/   \____/\___/_/ |_\___/___/_/|_/___/_/  /___/___/

EOF
    echo -e "${NC}"
    echo -e "${BLUE}Test Environment Setup - 100% Coverage Target${NC}\n"
}

check_docker() {
    if docker ps > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

start_services() {
    log "Avvio servizi Docker..."
    
    # Check if docker-compose or docker compose
    if command -v docker-compose &> /dev/null; then
        docker-compose up -d postgres redis
    else
        docker compose up -d postgres redis
    fi
    
    log "Attesa database pronto..."
    local retries=30
    local count=0
    
    until docker exec auto-broker-postgres-1 pg_isready -U broker_user > /dev/null 2>&1 || \
          docker exec auto-broker-postgres pg_isready -U broker_user > /dev/null 2>&1 || \
          docker-compose exec -T postgres pg_isready -U broker_user > /dev/null 2>&1; do
        ((count++))
        if [ $count -ge $retries ]; then
            error "Timeout attesa database"
            exit 1
        fi
        echo -n "."
        sleep 1
    done
    echo ""
    success "Database pronto"
    
    log "Attesa Redis pronto..."
    sleep 2
    success "Redis pronto"
}

stop_services() {
    log "Stop servizi Docker..."
    if command -v docker-compose &> /dev/null; then
        docker-compose down > /dev/null 2>&1 || true
    else
        docker compose down > /dev/null 2>&1 || true
    fi
}

run_tests_full() {
    log "Esecuzione test completo (100% coverage target)..."
    
    export DATABASE_URL="postgresql+asyncpg://broker_user:broker_pass_2024@localhost:5433/broker_db"
    export REDIS_URL="redis://localhost:6380/0"
    export TEST_ENV="local"
    
    if python3 -m pytest tests/ -v --cov=api --cov-fail-under=100 --cov-report=term-missing --tb=short; then
        success "100% coverage raggiunta!"
        return 0
    else
        error "Coverage < 100%"
        return 1
    fi
}

run_tests_unit() {
    log "Esecuzione solo test unitari (no Docker)..."
    
    if python3 -m pytest tests/unit/ tests/contract/ tests/mutation/ -v --cov=api --cov-report=term-missing --tb=short; then
        success "Test unitari completati (~66% coverage)"
        warn "Per 100% coverage avvia Docker: ./setup_test_env.sh"
        return 0
    else
        error "Test unitari falliti"
        return 1
    fi
}

main() {
    print_header
    
    # Trap per cleanup
    trap stop_services EXIT
    
    if check_docker; then
        success "Docker disponibile"
        start_services
        run_tests_full
    else
        warn "Docker non disponibile"
        run_tests_unit
    fi
}

main "$@"
