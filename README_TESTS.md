# AUTO-BROKER Test Suite - Dual Environment Testing

**100% Coverage Target** | Big Tech Platform Engineering Standards 2026

## 🎯 Overview

This project uses a **dual environment testing strategy**:
- **Local Development**: Docker for full integration tests
- **CI/CD (GitHub Actions)**: Services containers for automated testing

## 📊 Coverage Summary

| Test Type | Coverage | Docker Required | Time |
|-----------|----------|-----------------|------|
| Unit Tests | ~66% | ❌ No | ~10s |
| Integration | ~85% | ✅ Yes | ~30s |
| **Full Suite** | **100%** | **✅ Yes** | **~60s** |

## 🚀 Quick Start

```bash
# Setup environment
make setup

# Quick unit tests (no Docker)
make test-unit

# Full test suite with 100% coverage (requires Docker)
make test

# Verify coverage
make verify
```

## 📋 Available Commands

### Make Commands

```bash
make help              # Show all commands
make setup             # Install dependencies
make test              # Full test suite (100% coverage)
make test-unit         # Unit tests only (~66%)
make test-integration  # Integration tests (requires Docker)
make test-e2e          # E2E tests (requires Docker)
make docker-up         # Start PostgreSQL + Redis
make docker-down       # Stop services
make coverage          # Generate HTML coverage report
make verify            # Verify 100% coverage
make ci-local          # Simulate CI/CD locally
```

### Shell Scripts

```bash
./setup_test_env.sh    # Automated setup with Docker detection
./verify_coverage.sh   # Comprehensive coverage verification
```

## 🔧 Configuration

### Environment Variables

```bash
# Local development
export DATABASE_URL="postgresql+asyncpg://broker_user:broker_pass_2024@localhost:5432/broker_db"
export REDIS_URL="redis://localhost:6379/0"

# CI/CD (GitHub Actions)
export DATABASE_URL="postgresql+asyncpg://broker_user:broker_pass_2024@postgres:5432/broker_db"
export REDIS_URL="redis://redis:6379/0"
```

### Test Markers

```bash
# Run specific test categories
pytest tests/unit/                    # Unit tests only
pytest -m unit                        # Marked unit tests
pytest -m integration                 # Marked integration tests
pytest -m e2e                         # Marked E2E tests
pytest -m "not integration"           # Exclude integration tests
```

## 🐳 Docker Services

```yaml
# PostgreSQL 15
Host: localhost:5432
User: broker_user
Pass: broker_pass_2024
DB:   broker_db

# Redis 7
Host: localhost:6379
DB:   0
```

## 🔁 CI/CD Pipeline

### GitHub Actions Workflow

```yaml
# Jobs:
- unit-tests:       Fast feedback (~10s)
- integration-tests: PostgreSQL + Redis tests
- e2e-tests:        Full stack tests
- coverage-gate:    100% enforcement
- lint:             Code quality
- security:         Bandit + Safety scans
- build:            Docker image build
```

### Pipeline Status

![CI/CD Pipeline](https://github.com/yourusername/auto-broker/workflows/CI/CD%20Pipeline/badge.svg)

## 📝 Pre-commit Workflow

```bash
# 1. Quick feedback (no Docker)
make test-unit

# 2. Before pushing (requires Docker)
make test

# 3. Verify 100% coverage
make verify
```

## 🐛 Troubleshooting

### Docker Not Running
```bash
# Unit tests still work
make test-unit

# Or use setup script
./setup_test_env.sh  # Detects Docker automatically
```

### Port Already in Use
```bash
# Stop existing services
make docker-down

# Or manually
docker-compose down
docker stop postgres redis
```

### Coverage Below 100%
```bash
# Check missing coverage
make coverage
open htmlcov/index.html

# Run specific test to debug
pytest tests/path/to/test.py -v --tb=short
```

## 📁 Test Structure

```
tests/
├── unit/              # Unit tests (no external deps)
├── integration/       # Integration tests (DB + Redis)
├── e2e/               # End-to-end tests
├── contract/          # Contract tests
├── mutation/          # Mutation tests
└── conftest.py        # Shared fixtures
```

## 🎓 Best Practices

1. **Unit Tests First**: Always write unit tests before integration tests
2. **Mock External**: Use mocks for external APIs in unit tests
3. **Real Services**: Use real PostgreSQL/Redis in integration tests
4. **Fast Feedback**: Run `make test-unit` frequently during development
5. **Full Coverage**: Run `make test` before pushing
6. **100% Target**: All code paths must be tested

## 📚 Additional Resources

- [pytest Documentation](https://docs.pytest.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [pytest-cov](https://pytest-cov.readthedocs.io/)
- [Hypothesis](https://hypothesis.readthedocs.io/) (Property-based testing)

---

**Maintained by**: Platform Engineering Team  
**Last Updated**: 2026-02-13  
**Coverage Target**: 100%
