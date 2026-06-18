import json
from pathlib import Path
from typing import Any

PROFILE_PATH = Path(__file__).parent.parent / "profile.json"

EMPTY_PROFILE = {
    "static": {
        "name": "",
        "email": "",
        "phone": "",
        "location": "",
        "github": "",
        "linkedin": "",
    },
    "education": [],
    "experience": [],
    "projects": [],
}


def load_profile(path: Path | None = None) -> dict[str, Any]:
    p = path or PROFILE_PATH
    if not p.exists():
        save_profile(EMPTY_PROFILE, p)
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"profile.json at {p} is corrupted: {exc}") from exc


def save_profile(profile: dict[str, Any], path: Path | None = None) -> None:
    p = path or PROFILE_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(profile, indent=2))
