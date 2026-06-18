import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_dashboard_loads(client, mock_profile_path):
    response = client.get("/")
    assert response.status_code == 200
    assert "Dashboard" in response.text
    assert "Generate Resume" in response.text
