# AUTO-BROKER Test Suite - Big Tech Style
# Inspired by Google/Meta/Netflix testing practices

.PHONY: help test test-unit test-integration test-e2e test-all test-contract test-property test-mutation coverage lint format

PYTHON := python3
PYTEST := $(PYTHON) -m pytest
PYTEST_OPTS := -v --tb=short

# Colors for output
BLUE := \033[36m
GREEN := \033[32m
YELLOW := \033[33m
RED := \033[31m
NC := \033[0m

help: ## Show this help message
	@echo "$(BLUE)AUTO-BROKER Test Suite$(NC)"
	@echo ""
	@echo "$(GREEN)Quick Commands:$(NC)"
	@echo "  make test           Run all tests (parallel)"
	@echo "  make test-unit      Run unit tests only"
	@echo "  make test-fast      Run fast tests (<100ms)"
	@echo "  make test-ci        Run CI test suite"
	@echo ""
	@echo "$(GREEN)Test Pyramid:$(NC)"
	@echo "  make test-unit      Unit tests (70%) - Isolated"
	@echo "  make test-contract  Contract tests - API compatibility"
	@echo "  make test-property  Property-based tests - Hypothesis"
	@echo "  make test-integration Integration tests (20%) - With DB"
	@echo "  make test-e2e       E2E tests (10%) - Full flows"
	@echo ""
	@echo "$(GREEN)Advanced:$(NC)"
	@echo "  make test-mutation  Mutation testing"
	@echo "  make coverage       Generate coverage report"
	@echo "  make coverage-html  Open HTML coverage report"
	@echo "  make lint           Run linters"
	@echo "  make format         Format code"

# ==========================================
# MAIN TEST COMMANDS
# ==========================================

test: ## Run all tests with coverage
	@echo "$(BLUE)🚀 Running full test suite...$(NC)"
	$(PYTEST) tests/ $(PYTEST_OPTS) --cov=api --cov-report=term-missing -n auto

test-all: test ## Alias for test

test-ci: ## Run tests in CI mode (no parallel, strict)
	@echo "$(BLUE)🔧 Running CI test suite...$(NC)"
	$(PYTEST) tests/ $(PYTEST_OPTS) --cov=api --cov-fail-under=100 --strict-markers

# ==========================================
# TEST PYRAMID
# ==========================================

test-unit: ## Run unit tests (fast, isolated)
	@echo "$(GREEN)🧪 Running unit tests...$(NC)"
	$(PYTEST) tests/unit/ $(PYTEST_OPTS) --cov=api -m unit -n auto

test-integration: ## Run integration tests (needs DB)
	@echo "$(YELLOW)🔌 Running integration tests...$(NC)"
	$(PYTEST) tests/integration/ $(PYTEST_OPTS) --cov=api -m integration

test-e2e: ## Run E2E tests (full flows)
	@echo "$(YELLOW)🎭 Running E2E tests...$(NC)"
	$(PYTEST) tests/e2e/ $(PYTEST_OPTS) --cov=api -m e2e

# ==========================================
# ADVANCED TEST TYPES
# ==========================================

test-contract: ## Run contract tests (snapshot)
	@echo "$(BLUE)📋 Running contract tests...$(NC)"
	$(PYTEST) tests/contract/ $(PYTEST_OPTS) --snapshot-update

test-property: ## Run property-based tests (Hypothesis)
	@echo "$(BLUE)🎲 Running property-based tests...$(NC)"
	$(PYTEST) tests/unit/test_property_based.py $(PYTEST_OPTS) --hypothesis-profile=ci

test-mutation: ## Run mutation tests
	@echo "$(BLUE)🧬 Running mutation tests...$(NC)"
	$(PYTEST) tests/mutation/ $(PYTEST_OPTS)

# ==========================================
# SPEED-BASED COMMANDS
# ==========================================

test-fast: ## Run only fast tests (<100ms)
	@echo "$(GREEN)⚡ Running fast tests...$(NC)"
	$(PYTEST) tests/ $(PYTEST_OPTS) -m fast -n auto

test-slow: ## Run only slow tests
	@echo "$(YELLOW)🐢 Running slow tests...$(NC)"
	$(PYTEST) tests/ $(PYTEST_OPTS) -m slow

# ==========================================
# FEATURE-BASED COMMANDS
# ==========================================

test-lead: ## Run lead management tests
	$(PYTEST) tests/ $(PYTEST_OPTS) -m lead

test-pricing: ## Run pricing engine tests
	$(PYTEST) tests/ $(PYTEST_OPTS) -m pricing

test-webhook: ## Run webhook tests
	$(PYTEST) tests/ $(PYTEST_OPTS) -m webhook

# ==========================================
# COVERAGE COMMANDS
# ==========================================

coverage: ## Generate coverage report
	@echo "$(BLUE)📊 Generating coverage report...$(NC)"
	$(PYTEST) tests/ --cov=api --cov-report=term-missing --cov-report=html --cov-report=xml

coverage-html: coverage ## Open HTML coverage report
	@echo "$(GREEN)📊 Opening coverage report...$(NC)"
	@open htmlcov/index.html || echo "Open htmlcov/index.html in your browser"

coverage-unit: ## Coverage for unit tests only
	$(PYTEST) tests/unit/ --cov=api --cov-report=term-missing

coverage-integration: ## Coverage for integration tests only
	$(PYTEST) tests/integration/ --cov=api --cov-report=term-missing

# ==========================================
# WATCH MODE (auto-rerun on changes)
# ==========================================

watch: ## Run tests in watch mode
	@echo "$(BLUE)👁️  Watching for changes...$(NC)"
	$(PYTEST) tests/ $(PYTEST_OPTS) -f

watch-unit: ## Watch unit tests only
	$(PYTEST) tests/unit/ $(PYTEST_OPTS) -f

# ==========================================
# LINTING & FORMATTING
# ==========================================

lint: ## Run linters
	@echo "$(BLUE)🔍 Running linters...$(NC)"
	$(PYTHON) -m flake8 api/ tests/ --max-line-length=100 --ignore=E203,W503
	$(PYTHON) -m mypy api/ --ignore-missing-imports

format: ## Format code with black
	@echo "$(BLUE)✨ Formatting code...$(NC)"
	$(PYTHON) -m black api/ tests/ --line-length=100

format-check: ## Check code formatting
	@echo "$(BLUE)🔍 Checking code formatting...$(NC)"
	$(PYTHON) -m black api/ tests/ --line-length=100 --check

# ==========================================
# SETUP & UTILITIES
# ==========================================

install: ## Install dependencies
	@echo "$(BLUE)📦 Installing dependencies...$(NC)"
	pip install -r api/requirements.txt
	pip install pytest pytest-asyncio pytest-cov pytest-xdist pytest-factoryboy hypothesis syrupy

clean: ## Clean generated files
	@echo "$(BLUE)🧹 Cleaning up...$(NC)"
	rm -rf htmlcov/
	rm -rf .pytest_cache/
	rm -rf __pycache__/
	rm -rf .coverage
	rm -f coverage.xml
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

reset-db: ## Reset test database
	@echo "$(YELLOW)🗑️  Resetting test database...$(NC)"
	# Assumes PostgreSQL is running locally
	dropdb broker_test 2>/dev/null || true
	createdb broker_test

db-logs: ## Show database logs
	docker logs auto-broker-postgres 2>/dev/null || echo "DB not running in Docker"

# ==========================================
# DOCKER COMMANDS
# ==========================================

docker-up: ## Start services with Docker Compose
	@echo "$(BLUE)🐳 Starting services...$(NC)"
	docker-compose up -d postgres redis

docker-down: ## Stop Docker services
	@echo "$(BLUE)🐳 Stopping services...$(NC)"
	docker-compose down

docker-test: docker-up ## Run tests with Docker services
	@sleep 3
	make test-integration
	make test-e2e
