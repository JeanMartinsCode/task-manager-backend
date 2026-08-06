"""Pytest configuration and shared fixtures."""

import os

# Must run before any test module (or conftest fixture) imports
# `task_manager.main`, since security.require_api_key and the rate
# limiter read these at request/decoration time. Root conftest.py is
# always imported first by pytest, so this is the one safe place to
# guarantee ordering.
TEST_API_KEY = "test-api-key-for-pytest-only"
os.environ.setdefault("API_KEY", TEST_API_KEY)
os.environ.setdefault("RATE_LIMIT_WRITE", "5/minute")

import pytest  # noqa: E402


@pytest.fixture
def client():
    """Provide a TestClient for FastAPI testing, pre-authenticated with the API key.

    Shared across every test module so individual test files don't each
    redefine the same fixture.
    """
    from fastapi.testclient import TestClient

    from task_manager.main import app

    test_client = TestClient(app)
    test_client.headers.update({"X-API-Key": TEST_API_KEY})
    return test_client


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Prevent write-endpoint rate-limit state from leaking between tests.

    The limiter storage lives on a module-level singleton shared by the
    whole pytest session (same `app` object across every test file), so
    without a reset each test would inherit the write-request count left
    behind by every test that ran before it.
    """
    from task_manager.rate_limit import limiter

    limiter.reset()
    yield
