import json
import pytest


@pytest.fixture
def sample_profile():
    return {
        "static": {
            "name": "Jane Smith",
            "email": "jane@example.com",
            "phone": "+44 7700 900000",
            "location": "London, UK",
            "github": "github.com/janesmith",
            "linkedin": "linkedin.com/in/janesmith",
        },
        "education": [
            {
                "institution": "University of London",
                "degree": "BSc",
                "field": "Computer Science",
                "start": "2016",
                "end": "2019",
                "details": "First class honours",
            }
        ],
        "experience": [
            {
                "company": "Tech Corp",
                "title": "Software Engineer",
                "start": "2019",
                "end": "Present",
                "location": "London",
                "accomplishments": [
                    "Built REST API serving 10k requests/day using Python and FastAPI",
                    "Reduced deployment time from 45 to 8 minutes by containerising with Docker",
                ],
            }
        ],
        "projects": [
            {
                "name": "CLI Tool",
                "description": "Automates repetitive dev tasks",
                "tech_stack": ["Python", "Click"],
                "highlights": ["500 GitHub stars"],
                "url": "github.com/janesmith/cli-tool",
            }
        ],
    }


@pytest.fixture
def mock_profile_path(tmp_path, sample_profile, monkeypatch):
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(json.dumps(sample_profile))
    monkeypatch.setattr("app.profile.PROFILE_PATH", profile_path)
    return profile_path
