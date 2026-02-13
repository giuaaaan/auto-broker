"""
Pytest configuration for integration tests.
"""
import pytest
import asyncio
import os
import sys

# Add api to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..', 'api'))


def pytest_configure(config):
    """Configure pytest markers for integration tests."""
    config.addinivalue_line("markers", "integration: Integration tests requiring database")


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
