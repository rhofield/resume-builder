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


def test_profile_page_loads(client, mock_profile_path):
    response = client.get("/profile")
    assert response.status_code == 200
    assert "Contact Info" in response.text
    assert "Jane Smith" in response.text


def test_update_static_info(client, mock_profile_path):
    import json
    response = client.post("/profile/static", data={
        "name": "Updated Name",
        "email": "new@example.com",
        "phone": "",
        "location": "",
        "github": "",
        "linkedin": "",
    }, follow_redirects=False)
    assert response.status_code == 303
    saved = json.loads(mock_profile_path.read_text())
    assert saved["static"]["name"] == "Updated Name"
    assert saved["static"]["email"] == "new@example.com"
