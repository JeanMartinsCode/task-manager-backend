"""Tests for project initialization and setup."""

import tomllib
from pathlib import Path

from fastapi.testclient import TestClient

from task_manager.main import app


class TestProjectStructure:
    """Verify project structure is correct."""

    def test_project_structure_exists(self) -> None:
        """Verify main project directories exist."""
        assert Path("src/task_manager").exists(), "src/task_manager directory missing"
        assert Path("tests").exists(), "tests directory missing"
        assert (
            Path("src/task_manager/__init__.py").exists()
        ), "src/task_manager/__init__.py missing"

    def test_pyproject_has_required_dependencies(self) -> None:
        """Verify pyproject.toml has all required dependencies."""
        pyproject_path = Path("pyproject.toml")
        assert pyproject_path.exists(), "pyproject.toml missing"

        with open(pyproject_path, "rb") as f:
            config = tomllib.load(f)

        deps = config["project"]["dependencies"]

        assert any("fastapi" in d.lower() for d in deps), "fastapi not in dependencies"
        assert any(
            "sqlalchemy" in d.lower() for d in deps
        ), "sqlalchemy not in dependencies"
        assert any("alembic" in d.lower() for d in deps), "alembic not in dependencies"
        assert any(
            "apscheduler" in d.lower() for d in deps
        ), "apscheduler not in dependencies"


class TestFastAPIApp:
    """Verify FastAPI application is properly configured."""

    def test_fastapi_app_imports(self) -> None:
        """Verify FastAPI app can be imported without errors."""
        assert app is not None, "FastAPI app is None"
        assert hasattr(app, "openapi"), "FastAPI app missing openapi method"

    def test_fastapi_health_endpoint(self) -> None:
        """Verify /health endpoint responds correctly."""
        client = TestClient(app)
        response = client.get("/health")

        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data == {"status": "healthy"}, f"Unexpected response: {data}"


class TestMakefile:
    """Verify Makefile has essential targets."""

    def test_makefile_has_targets(self) -> None:
        """Verify Makefile exists and has required targets."""
        makefile_path = Path("Makefile")
        assert makefile_path.exists(), "Makefile missing"

        content = makefile_path.read_text()

        assert "test:" in content, "Makefile missing 'test:' target"
        assert "run:" in content, "Makefile missing 'run:' target"
        assert "migrate:" in content, "Makefile missing 'migrate:' target"
