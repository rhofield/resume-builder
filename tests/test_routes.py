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


def test_add_education(client, mock_profile_path):
    import json
    response = client.post("/profile/education", data={
        "institution": "MIT",
        "degree": "MSc",
        "field": "Artificial Intelligence",
        "start": "2020",
        "end": "2022",
        "details": "",
    })
    assert response.status_code == 200
    assert "MIT" in response.text
    saved = json.loads(mock_profile_path.read_text())
    assert len(saved["education"]) == 2  # 1 from fixture + 1 new
    assert saved["education"][-1]["institution"] == "MIT"


def test_delete_education(client, mock_profile_path):
    import json
    response = client.delete("/profile/education/0")
    assert response.status_code == 200
    saved = json.loads(mock_profile_path.read_text())
    assert len(saved["education"]) == 0


def test_add_experience(client, mock_profile_path):
    import json
    response = client.post("/profile/experience", data={
        "company": "New Corp",
        "title": "Lead Engineer",
        "start": "2023",
        "end": "Present",
        "location": "Remote",
        "accomplishments_raw": "Led team of 5 engineers\nDelivered project 2 weeks ahead of schedule",
    })
    assert response.status_code == 200
    assert "New Corp" in response.text
    saved = json.loads(mock_profile_path.read_text())
    last = saved["experience"][-1]
    assert last["company"] == "New Corp"
    assert last["accomplishments"] == [
        "Led team of 5 engineers",
        "Delivered project 2 weeks ahead of schedule",
    ]


def test_delete_experience(client, mock_profile_path):
    import json
    response = client.delete("/profile/experience/0")
    assert response.status_code == 200
    saved = json.loads(mock_profile_path.read_text())
    assert len(saved["experience"]) == 0
