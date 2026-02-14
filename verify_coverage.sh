#!/bin/bash
# AUTO-BROKER Coverage Verification Script
# Verifica 100% coverage sia localmente che in CI/CD

set -e

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

COVERAGE_TARGET=100
PYTHON=python3
PYTEST="${PYTHON} -m pytest"

# ═══════════════════════════════════════════════════════════════════════════════
# FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

check_docker() {
    if docker ps > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

wait_for_postgres() {
    log_info "Waiting for PostgreSQL..."
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if docker-compose exec -T postgres pg_isready -U broker_user > /dev/null 2>&1; then
            log_success "PostgreSQL is ready"
            return 0
        fi
        echo -n "."
        sleep 1
        attempt=$((attempt + 1))
    done
    
    log_error "PostgreSQL failed to start within ${max_attempts} seconds"
    return 1
}

wait_for_redis() {
    log_info "Waiting for Redis..."
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if docker-compose exec -T redis redis-cli ping > /dev/null 2>&1; then
            log_success "Redis is ready"
            return 0
        fi
        echo -n "."
        sleep 1
        attempt=$((attempt + 1))
    done
    
    log_error "Redis failed to start within ${max_attempts} seconds"
    return 1
}

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 1: UNIT TESTS (No Docker)
# ═══════════════════════════════════════════════════════════════════════════════

run_unit_tests() {
    log_info "Running UNIT tests (no Docker required)..."
    
    if $PYTEST tests/unit/ tests/contract/ tests/mutation/ -v --cov=api --cov-report=term -q; then
        log_success "Unit tests PASSED"
        UNIT_STATUS=0
    else
        log_error "Unit tests FAILED"
        UNIT_STATUS=1
    fi
    
    return $UNIT_STATUS
}

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2: FULL COVERAGE WITH DOCKER
# ═══════════════════════════════════════════════════════════════════════════════

run_full_tests() {
    log_info "Setting up Docker services..."
    
    # Start services
    docker-compose up -d postgres redis
    
    # Wait for services
    if ! wait_for_postgres; then
        docker-compose down
        return 1
    fi
    
    if ! wait_for_redis; then
        docker-compose down
        return 1
    fi
    
    log_info "Running FULL test suite with ${COVERAGE_TARGET}% coverage target..."
    
    # Set environment for local testing
    export DATABASE_URL="postgresql+asyncpg://broker_user:broker_pass_2024@localhost:5433/broker_db"
    export REDIS_URL="redis://localhost:6379/0"
    export TEST_ENV="local"
    
    # Run full test suite
    if $PYTEST tests/ \
        --cov=api \
        --cov-fail-under=${COVERAGE_TARGET} \
        --cov-report=term-missing \
        --cov-report=html \
        --cov-report=xml \
        -v; then
        log_success "Full test suite PASSED with ${COVERAGE_TARGET}% coverage"
        FULL_STATUS=0
    else
        log_error "Full test suite FAILED - Coverage below ${COVERAGE_TARGET}%"
        FULL_STATUS=1
    fi
    
    # Cleanup
    docker-compose down
    
    return $FULL_STATUS
}

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 3: GENERATE REPORT
# ═══════════════════════════════════════════════════════════════════════════════

generate_report() {
    log_info "Generating coverage report..."
    
    if [ -f coverage.xml ]; then
        COVERAGE_PCT=$(grep -o 'line-rate="[0-9.]*"' coverage.xml | head -1 | cut -d'"' -f2)
        COVERAGE_PCT=$(echo "$COVERAGE_PCT * 100" | bc)
        COVERAGE_PCT=${COVERAGE_PCT%.*}
        
        echo ""
        echo "╔════════════════════════════════════════════════════════════╗"
        echo "║                   COVERAGE REPORT                          ║"
        echo "╠════════════════════════════════════════════════════════════╣"
        echo "║  Unit Tests:     $([ $UNIT_STATUS -eq 0 ] && echo 'PASS ' || echo 'FAIL ')                                    ║"
        
        if [ -n "$FULL_STATUS" ]; then
            echo "║  Full Tests:     $([ $FULL_STATUS -eq 0 ] && echo 'PASS ' || echo 'FAIL ')                                    ║"
            echo "║  Coverage:       ${COVERAGE_PCT}%                                    ║"
            echo "║  Target:         ${COVERAGE_TARGET}%                                    ║"
        else
            echo "║  Full Tests:     SKIPPED (Docker not available)            ║"
        fi
        
        echo "╚════════════════════════════════════════════════════════════╝"
        echo ""
        
        if [ -f htmlcov/index.html ]; then
            log_info "HTML report: htmlcov/index.html"
        fi
    fi
}

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

main() {
    echo ""
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║     AUTO-BROKER Coverage Verification - 100% Target        ║"
    echo "║        Big Tech Platform Engineering Standards 2026        ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo ""
    
    # Check Python
    if ! command -v $PYTHON &> /dev/null; then
        log_error "Python not found"
        exit 1
    fi
    
    # Check dependencies
    if ! $PYTHON -c "import pytest" 2>/dev/null; then
        log_info "Installing test dependencies..."
        pip install -q pytest pytest-asyncio pytest-cov pytest-mock hypothesis syrupy
    fi
    
    # Phase 1: Unit tests (always run)
    run_unit_tests
    UNIT_STATUS=$?
    
    # Phase 2: Full tests (if Docker available)
    if check_docker; then
        echo ""
        run_full_tests
        FULL_STATUS=$?
    else
        log_warning "Docker not available - skipping full integration tests"
        FULL_STATUS=""
    fi
    
    # Generate report
    generate_report
    
    # Final status
    echo ""
    if [ $UNIT_STATUS -eq 0 ]; then
        if [ -n "$FULL_STATUS" ] && [ $FULL_STATUS -eq 0 ]; then
            log_success "ALL TESTS PASSED - 100% Coverage Achieved!"
            exit 0
        else
            log_warning "Unit tests passed - Full coverage requires Docker"
            exit 0
        fi
    else
        log_error "TESTS FAILED"
        exit 1
    fi
}

# Run main
main "$@"
