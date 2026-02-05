"""
Tests for the API endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    """Create a test client."""
    with TestClient(app) as client:
        yield client


class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_root(self, client):
        """Test root endpoint returns welcome message."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data

    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


class TestScenariosAPI:
    """Test scenarios API endpoints."""

    def test_list_scenarios(self, client):
        """Test listing all scenarios."""
        response = client.get("/api/scenarios/")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Should have at least one scenario
        assert len(data) > 0

    def test_list_categories(self, client):
        """Test listing categories."""
        response = client.get("/api/scenarios/categories")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Should have at least one category
        assert len(data) > 0

    def test_get_scenario(self, client):
        """Test getting a specific scenario."""
        # First get the list to find a valid ID
        list_response = client.get("/api/scenarios/")
        scenarios = list_response.json()
        if scenarios:
            scenario_id = scenarios[0]["id"]
            response = client.get(f"/api/scenarios/{scenario_id}")
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == scenario_id
            assert "steps" in data

    def test_get_nonexistent_scenario(self, client):
        """Test getting a scenario that doesn't exist."""
        response = client.get("/api/scenarios/nonexistent-scenario-id")
        assert response.status_code == 404


class TestSearchAPI:
    """Test search API endpoints."""

    def test_search(self, client):
        """Test search functionality."""
        response = client.get("/api/search/?q=deploy")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_search_min_query(self, client):
        """Test search with minimum query length."""
        response = client.get("/api/search/?q=a")
        # Should fail validation (min 2 chars)
        assert response.status_code == 422


class TestProgressAPI:
    """Test progress API endpoints."""

    def test_get_progress(self, client):
        """Test getting progress for a scenario."""
        # First get a valid scenario ID
        list_response = client.get("/api/scenarios/")
        scenarios = list_response.json()
        if scenarios:
            scenario_id = scenarios[0]["id"]
            response = client.get(f"/api/progress/{scenario_id}")
            assert response.status_code == 200
            data = response.json()
            assert data["scenario_id"] == scenario_id

    def test_update_progress(self, client):
        """Test updating progress."""
        # Get a scenario with steps
        list_response = client.get("/api/scenarios/")
        scenarios = list_response.json()
        if scenarios:
            scenario_id = scenarios[0]["id"]
            # Get the scenario to find a step ID
            scenario_response = client.get(f"/api/scenarios/{scenario_id}")
            scenario = scenario_response.json()
            if scenario["steps"]:
                step_id = scenario["steps"][0]["id"]
                # Update progress
                response = client.post(
                    f"/api/progress/{scenario_id}",
                    json={"step_id": step_id, "completed": True},
                )
                assert response.status_code == 200
                data = response.json()
                assert step_id in data["completed_steps"]
