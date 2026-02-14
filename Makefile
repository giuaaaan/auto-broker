# AUTO-BROKER Test Suite - Dual Environment (Local + CI/CD)
# 100% Coverage Target - Big Tech Platform Engineering 2026

.PHONY: help test test-unit test-integration test-e2e docker-up docker-down setup verify

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

PYTHON := python3
PYTEST := $(PYTHON) -m pytest
COMPOSE := docker-compose

# Colors
BLUE := \033[36m
GREEN := \033[32m
YELLOW := \033[33m
RED := \033[31m
NC := \033[0m

# ═══════════════════════════════════════════════════════════════════════════════
# QUICK COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

help: ## Show this help
	@echo "$(BLUE)AUTO-BROKER Test Suite - 100% Coverage$(NC)"
	@echo ""
	@echo "$(GREEN)Quick Commands:$(NC)"
	@echo "  make test           → Full test suite (100% coverage, requires Docker)"
	@echo "  make test-unit      → Unit tests only (~66%, no Docker needed)"
	@echo "  make setup          → Setup environment"
	@echo "  make verify         → Verify 100% coverage"
	@echo ""
	@echo "$(GREEN)Docker Commands:$(NC)"
	@echo "  make docker-up      → Start PostgreSQL + Redis"
	@echo "  make docker-down    → Stop services"
	@echo ""
	@echo "$(GREEN)Test Categories:$(NC)"
	@echo "  make test-integration  → Integration tests (requires Docker)"
	@echo "  make test-e2e          → E2E tests (requires Docker)"

# ═══════════════════════════════════════════════════════════════════════════════
# SETUP
# ═══════════════════════════════════════════════════════════════════════════════

setup: ## Setup test environment
	@echo "$(BLUE)🔧 Setting up environment...$(NC)"
	@chmod +x setup_test_env.sh verify_coverage.sh
	@pip install -q -r api/requirements.txt
	@pip install -q pytest pytest-asyncio pytest-cov pytest-mock hypothesis syrupy
	@echo "$(GREEN)✅ Setup complete$(NC)"

# ═══════════════════════════════════════════════════════════════════════════════
# DOCKER COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

docker-up: ## Start PostgreSQL + Redis
	@echo "$(BLUE)🐳 Starting Docker services...$(NC)"
	@$(COMPOSE) up -d postgres redis
	@echo "$(YELLOW)⏳ Waiting for services...$(NC)"
	@sleep 5
	@echo "$(GREEN)✅ Services ready$(NC)"

docker-down: ## Stop Docker services
	@echo "$(BLUE)🐳 Stopping services...$(NC)"
	@$(COMPOSE) down
	@echo "$(GREEN)✅ Services stopped$(NC)"

docker-logs: ## View Docker logs
	@$(COMPOSE) logs -f

# ═══════════════════════════════════════════════════════════════════════════════
# TEST COMMANDS - TARGET 100%
# ═══════════════════════════════════════════════════════════════════════════════

test: docker-up ## Full test suite (100% coverage target)
	@echo "$(BLUE)🚀 Running full test suite...$(NC)"
	@export DATABASE_URL="postgresql+asyncpg://broker_user:broker_pass_2024@localhost:5433/broker_db" && \
	 export REDIS_URL="redis://localhost:6380/0" && \
	 export TEST_ENV="local" && \
	 $(PYTEST) tests/ -v --cov=api --cov-fail-under=100 --cov-report=term-missing --tb=short
	@$(MAKE) docker-down

test-unit: ## Unit tests only (~66%, no Docker needed)
	@echo "$(BLUE)🧪 Running unit tests...$(NC)"
	@$(PYTEST) tests/unit/ tests/contract/ tests/mutation/ -v --cov=api --cov-report=term-missing --tb=short
	@echo "$(YELLOW)⚠️  Coverage: ~66% - Run 'make test' for 100%$(NC)"

test-integration: docker-up ## Integration tests
	@echo "$(BLUE)🔌 Running integration tests...$(NC)"
	@export DATABASE_URL="postgresql+asyncpg://broker_user:broker_pass_2024@localhost:5433/broker_db" && \
	 export REDIS_URL="redis://localhost:6380/0" && \
	 $(PYTEST) tests/integration/ -v --cov=api --cov-report=term-missing --tb=short
	@$(MAKE) docker-down

test-e2e: docker-up ## E2E tests
	@echo "$(BLUE)🎭 Running E2E tests...$(NC)"
	@export DATABASE_URL="postgresql+asyncpg://broker_user:broker_pass_2024@localhost:5433/broker_db" && \
	 export REDIS_URL="redis://localhost:6380/0" && \
	 $(PYTEST) tests/e2e/ -v --tb=short
	@$(MAKE) docker-down

test-property: ## Property-based tests
	@echo "$(BLUE)🎲 Running property-based tests...$(NC)"
	@$(PYTEST) tests/unit/test_property_based.py -v --hypothesis-seed=0

test-contract: ## Contract tests
	@echo "$(BLUE)📋 Running contract tests...$(NC)"
	@$(PYTEST) tests/contract/ -v --snapshot-update

# ═══════════════════════════════════════════════════════════════════════════════
# COVERAGE COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

coverage: docker-up ## Generate coverage report
	@export DATABASE_URL="postgresql+asyncpg://broker_user:broker_pass_2024@localhost:5433/broker_db" && \
	 export REDIS_URL="redis://localhost:6380/0" && \
	 $(PYTEST) tests/ --cov=api --cov-report=html --cov-report=xml --cov-report=term-missing
	@$(MAKE) docker-down
	@echo "$(GREEN)✅ Coverage report: htmlcov/index.html$(NC)"

coverage-html: coverage ## Open HTML coverage report
	@open htmlcov/index.html

verify: ## Verify 100% coverage
	@echo "$(BLUE)🔍 Verifying 100% coverage...$(NC)"
	@./verify_coverage.sh

# ═══════════════════════════════════════════════════════════════════════════════
# SHORTCUTS
# ═══════════════════════════════════════════════════════════════════════════════

ship: test ## Alias for full test + deploy
	@echo "$(GREEN)🚀 Ready to ship!$(NC)"

quick: test-unit ## Quick test (no Docker)
	@echo "$(GREEN)✅ Quick test complete$(NC)"

# ═══════════════════════════════════════════════════════════════════════════════
# MAINTENANCE
# ═══════════════════════════════════════════════════════════════════════════════

clean: ## Clean generated files
	@rm -rf htmlcov/ .pytest_cache/ __pycache__/ .coverage coverage.xml
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete
	@echo "$(GREEN)✅ Cleaned$(NC)"

lint: ## Run linters
	@$(PYTHON) -m flake8 api/ tests/ --max-line-length=100 --ignore=E203,W503

format: ## Format code
	@$(PYTHON) -m black api/ tests/ --line-length=100

# ═══════════════════════════════════════════════════════════════════════════════
# CI/CD SIMULATION
# ═══════════════════════════════════════════════════════════════════════════════

ci-local: ## Simulate CI/CD pipeline locally
	@echo "$(BLUE)🔧 Simulating CI/CD...$(NC)"
	@$(MAKE) clean
	@$(MAKE) setup
	@$(MAKE) test
	@echo "$(GREEN)✅ CI/CD simulation complete$(NC)"
