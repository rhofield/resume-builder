import json
import pytest
from pathlib import Path
from app.profile import load_profile, save_profile, EMPTY_PROFILE


def test_load_profile_returns_data(mock_profile_path, sample_profile):
    profile = load_profile(mock_profile_path)
    assert profile["static"]["name"] == "Jane Smith"
    assert len(profile["education"]) == 1
    assert len(profile["experience"]) == 1


def test_load_profile_auto_scaffolds_if_missing(tmp_path):
    path = tmp_path / "new_profile.json"
    assert not path.exists()
    profile = load_profile(path)
    assert path.exists()
    assert profile == EMPTY_PROFILE


def test_save_profile_writes_json(tmp_path, sample_profile):
    path = tmp_path / "profile.json"
    save_profile(sample_profile, path)
    saved = json.loads(path.read_text())
    assert saved["static"]["name"] == "Jane Smith"


def test_save_and_reload_roundtrip(tmp_path, sample_profile):
    path = tmp_path / "profile.json"
    save_profile(sample_profile, path)
    loaded = load_profile(path)
    assert loaded == sample_profile


def test_empty_profile_has_all_keys():
    assert set(EMPTY_PROFILE.keys()) == {"static", "education", "experience", "projects"}
    assert set(EMPTY_PROFILE["static"].keys()) == {
        "name", "email", "phone", "location", "github", "linkedin"
    }
