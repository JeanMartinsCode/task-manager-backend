"""Pytest configuration and shared fixtures."""

import pytest


@pytest.fixture
def test_client():
    """Provide a TestClient for FastAPI testing."""
    from fastapi.testclient import TestClient

    from src.task_manager.main import app

    return TestClient(app)
