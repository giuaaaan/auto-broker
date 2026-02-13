"""
Unit tests for main FastAPI application endpoints.
Tests endpoint existence and basic functionality.
"""
import pytest
import sys
import os

# Add api to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..', 'api'))


class TestMainImports:
    """Test that main module can be imported."""

    @pytest.mark.unit
    def test_main_imports(self):
        """Test that main module imports work."""
        from main import app
        assert app is not None
        assert app.title == "AUTO-BROKER API"

    @pytest.mark.unit
    def test_app_routes_exist(self):
        """Test that app has routes defined."""
        from main import app
        routes = [route.path for route in app.routes]
        # Check that key routes exist
        assert "/health" in routes or any("/health" in r for r in routes)


class TestMainModule:
    """Test main module components."""

    @pytest.mark.unit
    def test_limiter_exists(self):
        """Test that rate limiter is defined."""
        from main import limiter
        assert limiter is not None

    @pytest.mark.unit  
    def test_logger_exists(self):
        """Test that logger is defined."""
        from main import logger
        assert logger is not None
