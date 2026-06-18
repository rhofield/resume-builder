# Resume Builder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local FastAPI web app that stores a user's career facts as JSON, accepts pasted job descriptions, calls `claude -p` to produce tailored HTML resumes, and converts them to PDF via Playwright.

**Architecture:** FastAPI serves Jinja2 templates with HTMX handling profile mutations without full page reloads. `profile.json` is the single source of truth; `claude -p` reads it to produce filled-in HTML from a chosen resume template; Playwright renders the HTML to PDF.

**Tech Stack:** Python 3.11+, FastAPI, Jinja2, HTMX 1.9, Playwright (Chromium), pytest, httpx

---

## File Map

```
resume-builder/
├── app/
│   ├── __init__.py
│   ├── main.py                         # FastAPI app + all routes
│   ├── profile.py                      # profile.json read/write helpers
│   ├── generator.py                    # claude -p subprocess + prompt builder
│   ├── pdf.py                          # Playwright HTML → PDF
│   ├── templates/
│   │   ├── base.html
│   │   ├── dashboard.html
│   │   ├── profile.html
│   │   ├── generate.html
│   │   └── partials/
│   │       ├── education_list.html
│   │       ├── experience_list.html
│   │       ├── projects_list.html
│   │       └── generate_result.html
│   └── static/
│       └── style.css
├── resume_templates/
│   ├── classic.html
│   ├── modern-sidebar.html
│   └── minimalist-accent.html
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_profile.py
│   ├── test_generator.py
│   └── test_routes.py
├── output/                             # generated PDFs land here (gitignored)
├── profile.json                        # auto-created on first run (gitignored)
└── requirements.txt
```

---

## Task 1: Project Scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `app/__init__.py`
- Create: `app/main.py`
- Create: `tests/__init__.py`
- Create: `output/.gitkeep`
- Create: `resume_templates/.gitkeep`

- [ ] **Step 1: Create `requirements.txt`**

```
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
jinja2>=3.1.0
python-multipart>=0.0.6
playwright>=1.40.0
pytest>=7.4.0
httpx>=0.25.0
```

- [ ] **Step 2: Create `.gitignore`**

```
__pycache__/
*.pyc
.pytest_cache/
.venv/
profile.json
output/*.pdf
output/*.html
.superpowers/
```

- [ ] **Step 3: Create directory structure and placeholder files**

```bash
mkdir -p app/templates/partials app/static resume_templates output tests
touch app/__init__.py tests/__init__.py output/.gitkeep resume_templates/.gitkeep
```

- [ ] **Step 4: Create minimal `app/main.py`**

```python
from fastapi import FastAPI

app = FastAPI(title="Resume Builder")

@app.get("/healthz")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 5: Install dependencies and verify the server starts**

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
uvicorn app.main:app --reload
```

Expected: server starts at `http://127.0.0.1:8000`. `curl http://localhost:8000/healthz` returns `{"status":"ok"}`. Kill with Ctrl+C.

- [ ] **Step 6: Commit**

```bash
git add requirements.txt .gitignore app/__init__.py app/main.py tests/__init__.py output/.gitkeep resume_templates/.gitkeep
git commit -m "chore: project scaffold"
```

---

## Task 2: Profile Data Layer

**Files:**
- Create: `app/profile.py`
- Create: `tests/conftest.py`
- Create: `tests/test_profile.py`

- [ ] **Step 1: Create `tests/conftest.py`**

```python
import json
import pytest
from pathlib import Path


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
```

- [ ] **Step 2: Write failing tests in `tests/test_profile.py`**

```python
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
```

- [ ] **Step 3: Run tests — expect failure**

```bash
pytest tests/test_profile.py -v
```

Expected: `ImportError: cannot import name 'load_profile' from 'app.profile'`

- [ ] **Step 4: Create `app/profile.py`**

```python
import json
from pathlib import Path

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


def load_profile(path: Path = None) -> dict:
    p = path or PROFILE_PATH
    if not p.exists():
        save_profile(EMPTY_PROFILE, p)
    return json.loads(p.read_text())


def save_profile(profile: dict, path: Path = None) -> None:
    p = path or PROFILE_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(profile, indent=2))
```

- [ ] **Step 5: Run tests — expect all pass**

```bash
pytest tests/test_profile.py -v
```

Expected: `5 passed`

- [ ] **Step 6: Commit**

```bash
git add app/profile.py tests/conftest.py tests/test_profile.py
git commit -m "feat: profile.json data layer"
```

---

## Task 3: Base UI Layout

**Files:**
- Create: `app/static/style.css`
- Create: `app/templates/base.html`
- Modify: `app/main.py` (add static files + templates setup)

- [ ] **Step 1: Download HTMX locally (no CDN — keeps the app offline-capable and avoids SRI concerns)**

```bash
curl -sL https://unpkg.com/htmx.org@1.9.10/dist/htmx.min.js -o app/static/htmx.min.js
```

Verify: `wc -c app/static/htmx.min.js` should be ~50KB.

- [ ] **Step 2: Create `app/static/style.css`**

```css
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  font-size: 15px;
  color: #1a1a2e;
  background: #f8f9fc;
  line-height: 1.6;
}

nav {
  background: #1a1a2e;
  padding: 0 24px;
  display: flex;
  align-items: center;
  gap: 32px;
  height: 52px;
}
.nav-logo { color: #fff; font-weight: 700; font-size: 16px; text-decoration: none; }
.nav-links { display: flex; gap: 4px; }
.nav-links a {
  color: #aab4d0; text-decoration: none; padding: 6px 12px;
  border-radius: 6px; font-size: 14px;
}
.nav-links a:hover, .nav-links a.active { color: #fff; background: rgba(255,255,255,0.1); }

main { max-width: 1000px; margin: 0 auto; padding: 32px 24px; }

.page-header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 24px;
}
.page-header h1 { font-size: 24px; font-weight: 700; }

.card {
  background: #fff; border: 1px solid #e4e7f0; border-radius: 10px;
  padding: 24px; margin-bottom: 20px;
}
.card h2 { font-size: 16px; font-weight: 600; margin-bottom: 16px; }
.card h3 { font-size: 14px; font-weight: 600; margin: 20px 0 12px; color: #555; }

.btn {
  display: inline-flex; align-items: center; padding: 8px 16px;
  border: 1px solid #d0d5e8; border-radius: 7px; background: #fff;
  font-size: 14px; font-weight: 500; cursor: pointer; text-decoration: none;
  color: #1a1a2e; transition: background 0.15s;
}
.btn:hover { background: #f0f2f8; }
.btn-primary { background: #2563eb; color: #fff; border-color: #2563eb; }
.btn-primary:hover { background: #1d4ed8; }
.btn-danger { background: #fee2e2; color: #dc2626; border-color: #fca5a5; }
.btn-danger:hover { background: #fecaca; }
.btn-sm { padding: 4px 10px; font-size: 12px; }
.btn-lg { padding: 12px 28px; font-size: 16px; }
.button-row { display: flex; gap: 10px; flex-wrap: wrap; }

label { display: block; font-size: 13px; font-weight: 500; color: #555; margin-bottom: 14px; }
input[type="text"], input[type="email"], textarea {
  display: block; width: 100%; margin-top: 4px;
  padding: 8px 12px; border: 1px solid #d0d5e8; border-radius: 7px;
  font-size: 14px; font-family: inherit; background: #fff;
}
input:focus, textarea:focus { outline: none; border-color: #2563eb; box-shadow: 0 0 0 3px rgba(37,99,235,0.12); }
textarea { resize: vertical; }

.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0 20px; }

.tabs { display: flex; gap: 4px; margin-bottom: 20px; border-bottom: 2px solid #e4e7f0; padding-bottom: 0; }
.tab {
  padding: 10px 18px; text-decoration: none; color: #666;
  font-size: 14px; font-weight: 500; border-bottom: 2px solid transparent;
  margin-bottom: -2px;
}
.tab:hover { color: #1a1a2e; }
.tab.active { color: #2563eb; border-bottom-color: #2563eb; }

.entry {
  border: 1px solid #eef0f8; border-radius: 8px; padding: 14px;
  margin-bottom: 10px; background: #fafbfd;
}
.entry-main { font-size: 14px; margin-bottom: 4px; }
.entry-date { color: #888; font-size: 12px; margin-left: 8px; }
.entry-location { color: #888; font-size: 12px; margin-left: 8px; }
.entry-url { color: #2563eb; font-size: 12px; margin-left: 8px; }
.entry-details { font-size: 13px; color: #666; margin: 4px 0; }
.entry-tags { margin: 6px 0; display: flex; gap: 6px; flex-wrap: wrap; }
.tag { background: #e0e7ff; color: #3730a3; font-size: 11px; padding: 2px 8px; border-radius: 10px; }
.accomplishments { margin: 6px 0 8px 16px; font-size: 13px; color: #444; }
.accomplishments li { margin-bottom: 2px; }
.empty-state { color: #aaa; font-size: 13px; padding: 12px 0; }

.banner {
  border-radius: 8px; padding: 12px 16px; margin-bottom: 20px; font-size: 14px;
}
.banner-info { background: #eff6ff; border: 1px solid #bfdbfe; color: #1e40af; }
.banner-warning { background: #fffbeb; border: 1px solid #fcd34d; color: #92400e; }

.progress-bar {
  background: #e4e7f0; border-radius: 999px; height: 8px; margin: 8px 0;
}
.progress-fill { background: #2563eb; border-radius: 999px; height: 100%; transition: width 0.3s; }

.output-list { list-style: none; }
.output-list li { padding: 6px 0; border-bottom: 1px solid #eef0f8; font-size: 14px; }
.output-list li:last-child { border-bottom: none; }
.output-list a { color: #2563eb; text-decoration: none; }

.generate-layout { display: grid; grid-template-columns: 1fr 380px; gap: 20px; align-items: start; }
.generate-left {}
.generate-right {}

.template-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin: 12px 0 20px; }
.template-card {
  border: 2px solid #d0d5e8; border-radius: 8px; padding: 14px;
  cursor: pointer; text-align: center; font-size: 13px; font-weight: 500;
  display: block; color: #1a1a2e;
}
.template-card input[type="radio"] { display: none; }
.template-card:has(input:checked) { border-color: #2563eb; background: #eff6ff; color: #1d4ed8; }

.htmx-indicator { display: none; }
.htmx-request .htmx-indicator { display: block; }
.spinner {
  text-align: center; padding: 24px; color: #666; font-size: 14px;
  background: #fff; border: 1px solid #e4e7f0; border-radius: 10px; margin-top: 12px;
}

.card-success { border-color: #bbf7d0; background: #f0fdf4; }
.card-success h3 { color: #166534; margin-bottom: 14px; }
.card-error { border-color: #fca5a5; background: #fff5f5; }
.card-error h3 { color: #991b1b; margin-bottom: 8px; }
.card-error p { font-size: 14px; color: #7f1d1d; margin-bottom: 12px; }
.card-error pre {
  background: #1e1e2e; color: #cdd6f4; padding: 12px; border-radius: 6px;
  font-size: 12px; overflow-x: auto; white-space: pre-wrap; margin-top: 8px;
}
kbd {
  background: #f0f0f0; border: 1px solid #ccc; border-radius: 4px;
  padding: 1px 5px; font-size: 12px; font-family: monospace;
}
details summary { cursor: pointer; font-size: 13px; color: #888; margin-top: 8px; }
```

- [ ] **Step 2: Create `app/templates/base.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{% block title %}Resume Builder{% endblock %}</title>
  <link rel="stylesheet" href="/static/style.css">
  <script src="/static/htmx.min.js" defer></script>
</head>
<body>
  <nav>
    <a href="/" class="nav-logo">Resume Builder</a>
    <div class="nav-links">
      <a href="/" {% if request.url.path == "/" %}class="active"{% endif %}>Dashboard</a>
      <a href="/profile" {% if request.url.path.startswith("/profile") %}class="active"{% endif %}>Profile</a>
      <a href="/generate" {% if request.url.path == "/generate" %}class="active"{% endif %}>Generate</a>
    </div>
  </nav>
  <main>
    {% block content %}{% endblock %}
  </main>
</body>
</html>
```

- [ ] **Step 3: Update `app/main.py` to wire up static files and templates**

```python
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR.parent / "output"
RESUME_TEMPLATES_DIR = BASE_DIR.parent / "resume_templates"
OUTPUT_DIR.mkdir(exist_ok=True)

app = FastAPI(title="Resume Builder")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.mount("/output", StaticFiles(directory=str(OUTPUT_DIR)), name="output")

@app.get("/healthz")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 4: Verify server starts with static files**

```bash
uvicorn app.main:app --reload
```

Expected: starts without error. Kill with Ctrl+C.

- [ ] **Step 5: Commit**

```bash
git add app/main.py app/static/style.css app/templates/base.html
git commit -m "feat: base UI layout and static files"
```

---

## Task 4: Dashboard Page

**Files:**
- Modify: `app/main.py` (add GET / route)
- Create: `app/templates/dashboard.html`

- [ ] **Step 1: Write failing route test in `tests/test_routes.py`**

```python
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
```

- [ ] **Step 2: Run test — expect failure**

```bash
pytest tests/test_routes.py::test_dashboard_loads -v
```

Expected: `404 Not Found`

- [ ] **Step 3: Add dashboard route to `app/main.py`**

Add these imports and route (keep the existing health route and mounts):

```python
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from .profile import load_profile

# ... keep BASE_DIR, OUTPUT_DIR, RESUME_TEMPLATES_DIR, app, mounts ...

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def _completeness(profile: dict) -> int:
    filled = sum([
        bool(profile["static"].get("name")),
        bool(profile["static"].get("email")),
        bool(profile["education"]),
        bool(profile["experience"]),
    ])
    return int((filled / 4) * 100)


def get_recent_outputs() -> list[dict]:
    files = sorted(
        OUTPUT_DIR.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True
    )
    return [{"name": p.name, "url": f"/output/{p.name}"} for p in files[:10]]


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, setup: str = ""):
    profile = load_profile()
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "profile": profile,
        "completeness": _completeness(profile),
        "recent_outputs": get_recent_outputs(),
        "setup_banner": setup == "1",
    })
```

- [ ] **Step 4: Create `app/templates/dashboard.html`**

```html
{% extends "base.html" %}
{% block title %}Dashboard — Resume Builder{% endblock %}
{% block content %}

{% if setup_banner %}
<div class="banner banner-info">
  Welcome! Fill in your profile before generating a resume.
  <a href="/profile">Get started →</a>
</div>
{% endif %}

<div class="page-header">
  <h1>Dashboard</h1>
  <a href="/generate" class="btn btn-primary">Generate Resume</a>
</div>

<div class="card">
  <h2>Profile completeness</h2>
  <div class="progress-bar">
    <div class="progress-fill" style="width: {{ completeness }}%"></div>
  </div>
  <p style="font-size:13px;color:#666;margin-top:6px">
    {{ completeness }}% complete —
    <a href="/profile">Edit profile</a>
  </p>
</div>

<div class="card">
  <h2>Quick add</h2>
  <div class="button-row">
    <a href="/profile?tab=experience" class="btn">+ Job</a>
    <a href="/profile?tab=projects" class="btn">+ Project</a>
    <a href="/profile?tab=education" class="btn">+ Education</a>
  </div>
</div>

{% if recent_outputs %}
<div class="card">
  <h2>Recent generations</h2>
  <ul class="output-list">
    {% for item in recent_outputs %}
    <li><a href="{{ item.url }}" target="_blank">{{ item.name }}</a></li>
    {% endfor %}
  </ul>
</div>
{% endif %}

{% endblock %}
```

- [ ] **Step 5: Run test — expect pass**

```bash
pytest tests/test_routes.py::test_dashboard_loads -v
```

Expected: `1 passed`

- [ ] **Step 6: Commit**

```bash
git add app/main.py app/templates/dashboard.html tests/test_routes.py
git commit -m "feat: dashboard page"
```

---

## Task 5: Profile Editor — Static Info

**Files:**
- Modify: `app/main.py` (add GET /profile, POST /profile/static)
- Create: `app/templates/profile.html`

- [ ] **Step 1: Add failing tests to `tests/test_routes.py`**

```python
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
```

- [ ] **Step 2: Run tests — expect failure**

```bash
pytest tests/test_routes.py::test_profile_page_loads tests/test_routes.py::test_update_static_info -v
```

Expected: `2 failed` (404)

- [ ] **Step 3: Add profile routes to `app/main.py`**

```python
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from .profile import load_profile, save_profile

# Add inside app/main.py, after the dashboard route:

@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request, tab: str = "static", saved: str = ""):
    profile = load_profile()
    return templates.TemplateResponse("profile.html", {
        "request": request,
        "profile": profile,
        "active_tab": tab,
        "saved": saved == "1",
    })


@app.post("/profile/static")
async def update_static(
    name: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    location: str = Form(""),
    github: str = Form(""),
    linkedin: str = Form(""),
):
    profile = load_profile()
    profile["static"] = {
        "name": name, "email": email, "phone": phone,
        "location": location, "github": github, "linkedin": linkedin,
    }
    save_profile(profile)
    return RedirectResponse("/profile?tab=static&saved=1", status_code=303)
```

- [ ] **Step 4: Create `app/templates/profile.html`**

```html
{% extends "base.html" %}
{% block title %}Profile — Resume Builder{% endblock %}
{% block content %}

<div class="page-header">
  <h1>Profile</h1>
</div>

{% if saved %}
<div class="banner banner-info">Saved.</div>
{% endif %}

<div class="tabs">
  <a href="/profile?tab=static"
     class="tab {% if active_tab == 'static' %}active{% endif %}">Contact Info</a>
  <a href="/profile?tab=education"
     class="tab {% if active_tab == 'education' %}active{% endif %}">Education</a>
  <a href="/profile?tab=experience"
     class="tab {% if active_tab == 'experience' %}active{% endif %}">Experience</a>
  <a href="/profile?tab=projects"
     class="tab {% if active_tab == 'projects' %}active{% endif %}">Projects</a>
</div>

{% if active_tab == 'static' %}
<div class="card">
  <h2>Contact Information</h2>
  <form method="POST" action="/profile/static">
    <div class="form-grid">
      <label>Full Name
        <input type="text" name="name" value="{{ profile.static.name }}">
      </label>
      <label>Email
        <input type="email" name="email" value="{{ profile.static.email }}">
      </label>
      <label>Phone
        <input type="text" name="phone" value="{{ profile.static.phone }}">
      </label>
      <label>Location
        <input type="text" name="location" value="{{ profile.static.location }}"
               placeholder="London, UK">
      </label>
      <label>GitHub
        <input type="text" name="github" value="{{ profile.static.github }}"
               placeholder="github.com/username">
      </label>
      <label>LinkedIn
        <input type="text" name="linkedin" value="{{ profile.static.linkedin }}"
               placeholder="linkedin.com/in/username">
      </label>
    </div>
    <button type="submit" class="btn btn-primary">Save</button>
  </form>
</div>
{% endif %}

{% if active_tab == 'education' %}
<div class="card">
  <h2>Education</h2>
  <div id="education-list">
    {% include "partials/education_list.html" %}
  </div>
  <h3>Add Entry</h3>
  <form hx-post="/profile/education"
        hx-target="#education-list"
        hx-swap="innerHTML"
        hx-on::after-request="this.reset()">
    <div class="form-grid">
      <label>Institution
        <input type="text" name="institution" required placeholder="University of London">
      </label>
      <label>Degree
        <input type="text" name="degree" required placeholder="BSc, MSc, PhD">
      </label>
      <label>Field of Study
        <input type="text" name="field" placeholder="Computer Science">
      </label>
      <label>Start Year
        <input type="text" name="start" placeholder="2018">
      </label>
      <label>End Year
        <input type="text" name="end" placeholder="2021 or Present">
      </label>
    </div>
    <label>Details
      <textarea name="details" rows="2"
                placeholder="First class honours, relevant modules, awards..."></textarea>
    </label>
    <button type="submit" class="btn btn-primary">Add</button>
  </form>
</div>
{% endif %}

{% if active_tab == 'experience' %}
<div class="card">
  <h2>Experience</h2>
  <div id="experience-list">
    {% include "partials/experience_list.html" %}
  </div>
  <h3>Add Entry</h3>
  <form hx-post="/profile/experience"
        hx-target="#experience-list"
        hx-swap="innerHTML"
        hx-on::after-request="this.reset()">
    <div class="form-grid">
      <label>Company
        <input type="text" name="company" required>
      </label>
      <label>Job Title
        <input type="text" name="title" required>
      </label>
      <label>Start
        <input type="text" name="start" placeholder="Jan 2020">
      </label>
      <label>End
        <input type="text" name="end" placeholder="Mar 2023 or Present">
      </label>
      <label>Location
        <input type="text" name="location" placeholder="London / Remote">
      </label>
    </div>
    <label>
      Accomplishments
      <small style="font-weight:400;color:#888"> — one per line, include numbers where possible</small>
      <textarea name="accomplishments_raw" rows="6"
                placeholder="Built REST API serving 50k req/day using Python and FastAPI&#10;Reduced CI build time from 20min to 4min by caching Docker layers&#10;Mentored 3 junior engineers"></textarea>
    </label>
    <button type="submit" class="btn btn-primary">Add</button>
  </form>
</div>
{% endif %}

{% if active_tab == 'projects' %}
<div class="card">
  <h2>Projects</h2>
  <div id="projects-list">
    {% include "partials/projects_list.html" %}
  </div>
  <h3>Add Entry</h3>
  <form hx-post="/profile/projects"
        hx-target="#projects-list"
        hx-swap="innerHTML"
        hx-on::after-request="this.reset()">
    <div class="form-grid">
      <label>Project Name
        <input type="text" name="name" required>
      </label>
      <label>URL
        <input type="text" name="url" placeholder="github.com/user/repo">
      </label>
      <label style="grid-column:1/-1">Tech Stack
        <small style="font-weight:400;color:#888"> (comma-separated)</small>
        <input type="text" name="tech_stack_raw" placeholder="Python, FastAPI, PostgreSQL">
      </label>
    </div>
    <label>Description
      <textarea name="description" rows="2"></textarea>
    </label>
    <label>
      Highlights
      <small style="font-weight:400;color:#888"> — one per line</small>
      <textarea name="highlights_raw" rows="3"
                placeholder="500 GitHub stars&#10;Used in production by 3 companies"></textarea>
    </label>
    <button type="submit" class="btn btn-primary">Add</button>
  </form>
</div>
{% endif %}

{% endblock %}
```

- [ ] **Step 5: Create placeholder partials (needed for profile.html includes)**

Create `app/templates/partials/education_list.html` (minimal for now):
```html
<p class="empty-state">No education entries yet.</p>
```

Create `app/templates/partials/experience_list.html`:
```html
<p class="empty-state">No experience entries yet.</p>
```

Create `app/templates/partials/projects_list.html`:
```html
<p class="empty-state">No projects yet.</p>
```

- [ ] **Step 6: Run tests — expect pass**

```bash
pytest tests/test_routes.py::test_profile_page_loads tests/test_routes.py::test_update_static_info -v
```

Expected: `2 passed`

- [ ] **Step 7: Commit**

```bash
git add app/main.py app/templates/profile.html app/templates/partials/
git commit -m "feat: profile editor with static info tab"
```

---

## Task 6: Profile Editor — Education

**Files:**
- Modify: `app/main.py` (add POST /profile/education, DELETE /profile/education/{index})
- Modify: `app/templates/partials/education_list.html` (replace placeholder)

- [ ] **Step 1: Add failing tests to `tests/test_routes.py`**

```python
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
```

- [ ] **Step 2: Run tests — expect failure**

```bash
pytest tests/test_routes.py::test_add_education tests/test_routes.py::test_delete_education -v
```

Expected: `2 failed` (404)

- [ ] **Step 3: Add education routes to `app/main.py`**

```python
@app.post("/profile/education", response_class=HTMLResponse)
async def add_education(
    request: Request,
    institution: str = Form(...),
    degree: str = Form(...),
    field: str = Form(""),
    start: str = Form(""),
    end: str = Form(""),
    details: str = Form(""),
):
    profile = load_profile()
    profile["education"].append({
        "institution": institution, "degree": degree, "field": field,
        "start": start, "end": end, "details": details,
    })
    save_profile(profile)
    return templates.TemplateResponse("partials/education_list.html", {
        "request": request, "education": profile["education"],
    })


@app.delete("/profile/education/{index}", response_class=HTMLResponse)
async def delete_education(request: Request, index: int):
    profile = load_profile()
    if 0 <= index < len(profile["education"]):
        profile["education"].pop(index)
        save_profile(profile)
    return templates.TemplateResponse("partials/education_list.html", {
        "request": request, "education": profile["education"],
    })
```

- [ ] **Step 4: Replace `app/templates/partials/education_list.html`**

```html
{% for edu in education %}
<div class="entry">
  <div class="entry-main">
    <strong>{{ edu.degree }}{% if edu.field %} in {{ edu.field }}{% endif %}</strong>
    — {{ edu.institution }}
    {% if edu.start %}<span class="entry-date">{{ edu.start }}{% if edu.end %} – {{ edu.end }}{% endif %}</span>{% endif %}
  </div>
  {% if edu.details %}<p class="entry-details">{{ edu.details }}</p>{% endif %}
  <button class="btn btn-sm btn-danger" style="margin-top:8px"
          hx-delete="/profile/education/{{ loop.index0 }}"
          hx-target="#education-list"
          hx-swap="innerHTML"
          hx-confirm="Delete this education entry?">Delete</button>
</div>
{% else %}
<p class="empty-state">No education entries yet.</p>
{% endfor %}
```

- [ ] **Step 5: Run tests — expect pass**

```bash
pytest tests/test_routes.py::test_add_education tests/test_routes.py::test_delete_education -v
```

Expected: `2 passed`

- [ ] **Step 6: Commit**

```bash
git add app/main.py app/templates/partials/education_list.html
git commit -m "feat: education CRUD with HTMX partials"
```

---

## Task 7: Profile Editor — Experience

**Files:**
- Modify: `app/main.py`
- Modify: `app/templates/partials/experience_list.html`

- [ ] **Step 1: Add failing tests to `tests/test_routes.py`**

```python
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
```

- [ ] **Step 2: Run tests — expect failure**

```bash
pytest tests/test_routes.py::test_add_experience tests/test_routes.py::test_delete_experience -v
```

Expected: `2 failed`

- [ ] **Step 3: Add experience routes to `app/main.py`**

```python
@app.post("/profile/experience", response_class=HTMLResponse)
async def add_experience(
    request: Request,
    company: str = Form(...),
    title: str = Form(...),
    start: str = Form(""),
    end: str = Form(""),
    location: str = Form(""),
    accomplishments_raw: str = Form(""),
):
    profile = load_profile()
    accomplishments = [
        line.strip().lstrip("•–-").strip()
        for line in accomplishments_raw.splitlines()
        if line.strip()
    ]
    profile["experience"].append({
        "company": company, "title": title, "start": start,
        "end": end, "location": location, "accomplishments": accomplishments,
    })
    save_profile(profile)
    return templates.TemplateResponse("partials/experience_list.html", {
        "request": request, "experience": profile["experience"],
    })


@app.delete("/profile/experience/{index}", response_class=HTMLResponse)
async def delete_experience(request: Request, index: int):
    profile = load_profile()
    if 0 <= index < len(profile["experience"]):
        profile["experience"].pop(index)
        save_profile(profile)
    return templates.TemplateResponse("partials/experience_list.html", {
        "request": request, "experience": profile["experience"],
    })
```

- [ ] **Step 4: Replace `app/templates/partials/experience_list.html`**

```html
{% for exp in experience %}
<div class="entry">
  <div class="entry-main">
    <strong>{{ exp.title }}</strong> at {{ exp.company }}
    <span class="entry-date">{{ exp.start }}{% if exp.end %} – {{ exp.end }}{% endif %}</span>
    {% if exp.location %}<span class="entry-location">{{ exp.location }}</span>{% endif %}
  </div>
  {% if exp.accomplishments %}
  <ul class="accomplishments">
    {% for a in exp.accomplishments %}<li>{{ a }}</li>{% endfor %}
  </ul>
  {% endif %}
  <button class="btn btn-sm btn-danger" style="margin-top:8px"
          hx-delete="/profile/experience/{{ loop.index0 }}"
          hx-target="#experience-list"
          hx-swap="innerHTML"
          hx-confirm="Delete this experience entry?">Delete</button>
</div>
{% else %}
<p class="empty-state">No experience entries yet.</p>
{% endfor %}
```

- [ ] **Step 5: Run tests — expect pass**

```bash
pytest tests/test_routes.py::test_add_experience tests/test_routes.py::test_delete_experience -v
```

Expected: `2 passed`

- [ ] **Step 6: Commit**

```bash
git add app/main.py app/templates/partials/experience_list.html
git commit -m "feat: experience CRUD with HTMX partials"
```

---

## Task 8: Profile Editor — Projects

**Files:**
- Modify: `app/main.py`
- Modify: `app/templates/partials/projects_list.html`

- [ ] **Step 1: Add failing tests to `tests/test_routes.py`**

```python
def test_add_project(client, mock_profile_path):
    import json
    response = client.post("/profile/projects", data={
        "name": "My App",
        "description": "A useful tool",
        "tech_stack_raw": "Python, FastAPI, React",
        "highlights_raw": "1000 users\nOpen source",
        "url": "github.com/user/myapp",
    })
    assert response.status_code == 200
    assert "My App" in response.text
    saved = json.loads(mock_profile_path.read_text())
    last = saved["projects"][-1]
    assert last["name"] == "My App"
    assert last["tech_stack"] == ["Python", "FastAPI", "React"]
    assert last["highlights"] == ["1000 users", "Open source"]


def test_delete_project(client, mock_profile_path):
    import json
    response = client.delete("/profile/projects/0")
    assert response.status_code == 200
    saved = json.loads(mock_profile_path.read_text())
    assert len(saved["projects"]) == 0
```

- [ ] **Step 2: Run tests — expect failure**

```bash
pytest tests/test_routes.py::test_add_project tests/test_routes.py::test_delete_project -v
```

Expected: `2 failed`

- [ ] **Step 3: Add project routes to `app/main.py`**

```python
@app.post("/profile/projects", response_class=HTMLResponse)
async def add_project(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    tech_stack_raw: str = Form(""),
    highlights_raw: str = Form(""),
    url: str = Form(""),
):
    profile = load_profile()
    tech_stack = [t.strip() for t in tech_stack_raw.split(",") if t.strip()]
    highlights = [
        line.strip().lstrip("•–-").strip()
        for line in highlights_raw.splitlines()
        if line.strip()
    ]
    profile["projects"].append({
        "name": name, "description": description,
        "tech_stack": tech_stack, "highlights": highlights, "url": url,
    })
    save_profile(profile)
    return templates.TemplateResponse("partials/projects_list.html", {
        "request": request, "projects": profile["projects"],
    })


@app.delete("/profile/projects/{index}", response_class=HTMLResponse)
async def delete_project(request: Request, index: int):
    profile = load_profile()
    if 0 <= index < len(profile["projects"]):
        profile["projects"].pop(index)
        save_profile(profile)
    return templates.TemplateResponse("partials/projects_list.html", {
        "request": request, "projects": profile["projects"],
    })
```

- [ ] **Step 4: Replace `app/templates/partials/projects_list.html`**

```html
{% for proj in projects %}
<div class="entry">
  <div class="entry-main">
    <strong>{{ proj.name }}</strong>
    {% if proj.url %}<a href="{{ proj.url }}" target="_blank" class="entry-url">{{ proj.url }}</a>{% endif %}
  </div>
  {% if proj.description %}<p class="entry-details">{{ proj.description }}</p>{% endif %}
  {% if proj.tech_stack %}
  <div class="entry-tags">
    {% for t in proj.tech_stack %}<span class="tag">{{ t }}</span>{% endfor %}
  </div>
  {% endif %}
  {% if proj.highlights %}
  <ul class="accomplishments">
    {% for h in proj.highlights %}<li>{{ h }}</li>{% endfor %}
  </ul>
  {% endif %}
  <button class="btn btn-sm btn-danger" style="margin-top:8px"
          hx-delete="/profile/projects/{{ loop.index0 }}"
          hx-target="#projects-list"
          hx-swap="innerHTML"
          hx-confirm="Delete this project?">Delete</button>
</div>
{% else %}
<p class="empty-state">No projects yet.</p>
{% endfor %}
```

- [ ] **Step 5: Run all profile tests**

```bash
pytest tests/test_routes.py -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add app/main.py app/templates/partials/projects_list.html
git commit -m "feat: projects CRUD with HTMX partials"
```

---

## Task 9: Resume HTML Templates

**Files:**
- Create: `resume_templates/classic.html`
- Create: `resume_templates/modern-sidebar.html`
- Create: `resume_templates/minimalist-accent.html`

No unit tests for these — Claude fills in the placeholders at generation time. Verify by checking that all 5 placeholder comments are present in each file.

- [ ] **Step 1: Create `resume_templates/classic.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: Georgia, 'Times New Roman', serif;
      font-size: 10.5pt;
      color: #1a1a1a;
      padding: 1.8cm 2cm;
      line-height: 1.5;
    }
    .header {
      text-align: center;
      border-bottom: 2px solid #1a1a1a;
      padding-bottom: 10px;
      margin-bottom: 16px;
    }
    .name { font-size: 22pt; font-weight: bold; letter-spacing: 2px; text-transform: uppercase; }
    .contact { font-size: 8.5pt; color: #555; margin-top: 5px; }
    .section { margin-bottom: 16px; }
    .section-title {
      font-size: 9pt;
      font-weight: bold;
      text-transform: uppercase;
      letter-spacing: 1.5px;
      border-bottom: 1px solid #999;
      padding-bottom: 3px;
      margin-bottom: 8px;
    }
    .entry { margin-bottom: 10px; }
    .entry-header { display: flex; justify-content: space-between; align-items: baseline; }
    .entry-title { font-weight: bold; font-size: 10.5pt; }
    .entry-date { font-size: 9pt; color: #666; }
    .entry-subtitle { font-size: 9.5pt; color: #555; font-style: italic; margin-top: 1px; }
    ul { margin: 4px 0 0 14px; }
    li { margin-bottom: 2px; font-size: 10pt; }
    .skills-section { font-size: 10pt; }
    @media print {
      body { padding: 1.2cm 1.5cm; }
      @page { margin: 0; size: A4; }
    }
  </style>
</head>
<body>

  <!-- STATIC: Replace this comment with the header block. Use this exact structure:
       <div class="header">
         <div class="name">[FULL NAME]</div>
         <div class="contact">[email] · [phone] · [location] · [github] · [linkedin]</div>
       </div>
  -->

  <!-- EXPERIENCE_ITEMS: Replace with a section containing the most relevant jobs.
       Use this structure:
       <div class="section">
         <div class="section-title">Experience</div>
         <div class="entry">
           <div class="entry-header">
             <span class="entry-title">[Job Title] — [Company]</span>
             <span class="entry-date">[Start] – [End]</span>
           </div>
           <div class="entry-subtitle">[Location]</div>
           <ul><li>[Rewritten accomplishment tailored to job]</li></ul>
         </div>
       </div>
  -->

  <!-- EDUCATION_ITEMS: Replace with education section.
       <div class="section">
         <div class="section-title">Education</div>
         <div class="entry">
           <div class="entry-header">
             <span class="entry-title">[Degree] in [Field] — [Institution]</span>
             <span class="entry-date">[Start] – [End]</span>
           </div>
           <div class="entry-subtitle">[Details if notable]</div>
         </div>
       </div>
  -->

  <!-- PROJECT_ITEMS: Replace with a projects section only if projects are relevant to this role.
       Omit the entire section if no projects apply. Structure:
       <div class="section">
         <div class="section-title">Projects</div>
         <div class="entry">
           <div class="entry-header">
             <span class="entry-title">[Project Name]</span>
             <span class="entry-date">[URL if available]</span>
           </div>
           <div class="entry-subtitle">[Tech stack]</div>
           <ul><li>[Highlight rewritten for this role]</li></ul>
         </div>
       </div>
  -->

  <!-- SKILLS: Replace with a skills section derived from selected experience + job keywords.
       <div class="section">
         <div class="section-title">Skills</div>
         <div class="skills-section">[Comma-separated or grouped skill list]</div>
       </div>
  -->

</body>
</html>
```

- [ ] **Step 2: Create `resume_templates/modern-sidebar.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: Arial, Helvetica, sans-serif; font-size: 10pt; color: #1a1a1a; display: flex; min-height: 100vh; }
    .sidebar {
      background: #1a2e4a; color: #e8edf5;
      width: 220px; min-width: 220px; padding: 28px 18px;
      font-size: 9.5pt;
    }
    .sidebar .name { font-size: 16pt; font-weight: bold; color: #fff; margin-bottom: 4px; line-height: 1.2; }
    .sidebar .role-title { font-size: 9pt; color: #88aacc; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 18px; }
    .sidebar-section { margin-bottom: 18px; }
    .sidebar-section-title { font-size: 8pt; font-weight: bold; text-transform: uppercase; letter-spacing: 1px; color: #88aacc; border-bottom: 1px solid #2e4a6a; padding-bottom: 3px; margin-bottom: 8px; }
    .sidebar-section p, .sidebar-section li { font-size: 9pt; color: #c8d4e8; line-height: 1.6; }
    .sidebar-section ul { margin-left: 12px; }
    .main { flex: 1; padding: 28px 24px; }
    .section { margin-bottom: 18px; }
    .section-title { font-size: 9pt; font-weight: bold; text-transform: uppercase; letter-spacing: 1.5px; color: #1a2e4a; border-bottom: 2px solid #1a2e4a; padding-bottom: 3px; margin-bottom: 10px; }
    .entry { margin-bottom: 10px; }
    .entry-header { display: flex; justify-content: space-between; align-items: baseline; }
    .entry-title { font-weight: bold; font-size: 10pt; }
    .entry-date { font-size: 8.5pt; color: #666; }
    .entry-subtitle { font-size: 9pt; color: #666; margin-top: 1px; }
    ul { margin: 4px 0 0 14px; }
    li { margin-bottom: 2px; font-size: 9.5pt; }
    @media print { @page { margin: 0; size: A4; } body { -webkit-print-color-adjust: exact; } }
  </style>
</head>
<body>

  <aside class="sidebar">
    <!-- STATIC: Replace with sidebar header + contact block. Structure:
         <div class="name">[FULL NAME]</div>
         <div class="role-title">[Infer a short role title from the job description]</div>
         <div class="sidebar-section">
           <div class="sidebar-section-title">Contact</div>
           <p>[email]</p><p>[phone]</p><p>[location]</p><p>[github]</p><p>[linkedin]</p>
         </div>
    -->

    <!-- SKILLS: Replace with skills sidebar section. Structure:
         <div class="sidebar-section">
           <div class="sidebar-section-title">Skills</div>
           <ul><li>[skill]</li></ul>
         </div>
    -->
  </aside>

  <main class="main">

    <!-- EXPERIENCE_ITEMS: Replace with experience section. Structure:
         <div class="section">
           <div class="section-title">Experience</div>
           <div class="entry">
             <div class="entry-header">
               <span class="entry-title">[Title] — [Company]</span>
               <span class="entry-date">[Start] – [End]</span>
             </div>
             <div class="entry-subtitle">[Location]</div>
             <ul><li>[Accomplishment]</li></ul>
           </div>
         </div>
    -->

    <!-- EDUCATION_ITEMS: Replace with education section (same structure as EXPERIENCE_ITEMS). -->

    <!-- PROJECT_ITEMS: Replace with projects section if relevant; omit entirely if not. -->

  </main>

</body>
</html>
```

- [ ] **Step 3: Create `resume_templates/minimalist-accent.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: 'Helvetica Neue', Arial, sans-serif; font-size: 10.5pt; color: #1a1a1a; padding: 1.8cm 2cm; line-height: 1.6; }
    .header { border-left: 4px solid #2563eb; padding-left: 14px; margin-bottom: 22px; }
    .name { font-size: 21pt; font-weight: 700; color: #0f172a; }
    .role-title { font-size: 9pt; color: #2563eb; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; margin-top: 2px; }
    .contact { font-size: 8.5pt; color: #666; margin-top: 4px; }
    .section { margin-bottom: 18px; }
    .section-title { font-size: 8.5pt; font-weight: 700; color: #2563eb; text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 8px; }
    .entry { margin-bottom: 10px; }
    .entry-header { display: flex; justify-content: space-between; align-items: baseline; }
    .entry-title { font-weight: 600; font-size: 10.5pt; }
    .entry-date { font-size: 9pt; color: #888; }
    .entry-subtitle { font-size: 9pt; color: #888; margin-top: 1px; }
    ul { margin: 4px 0 0 14px; }
    li { margin-bottom: 2px; font-size: 10pt; }
    .skills-section { font-size: 10pt; color: #333; }
    @media print { @page { margin: 0; size: A4; } body { padding: 1.2cm 1.5cm; } }
  </style>
</head>
<body>

  <!-- STATIC: Replace with header block. Structure:
       <div class="header">
         <div class="name">[FULL NAME]</div>
         <div class="role-title">[Infer a short role title from the job description]</div>
         <div class="contact">[email] · [phone] · [location] · [github] · [linkedin]</div>
       </div>
  -->

  <!-- EXPERIENCE_ITEMS: Replace with experience section. Structure:
       <div class="section">
         <div class="section-title">Experience</div>
         <div class="entry">
           <div class="entry-header">
             <span class="entry-title">[Title] — [Company]</span>
             <span class="entry-date">[Start] – [End]</span>
           </div>
           <div class="entry-subtitle">[Location]</div>
           <ul><li>[Accomplishment]</li></ul>
         </div>
       </div>
  -->

  <!-- EDUCATION_ITEMS: Replace with education section (same structure). -->

  <!-- PROJECT_ITEMS: Replace with projects section if relevant; omit entirely if not. -->

  <!-- SKILLS: Replace with skills section. Structure:
       <div class="section">
         <div class="section-title">Skills</div>
         <div class="skills-section">[Grouped or comma-separated skills]</div>
       </div>
  -->

</body>
</html>
```

- [ ] **Step 4: Verify all three templates have all 5 placeholder comments**

```bash
for f in resume_templates/*.html; do
  echo "=== $f ==="; 
  grep -c "<!-- STATIC\|<!-- EXPERIENCE_ITEMS\|<!-- EDUCATION_ITEMS\|<!-- PROJECT_ITEMS\|<!-- SKILLS" "$f"
done
```

Expected: each file prints `5` (one per grep match per file). `modern-sidebar.html` has STATIC and SKILLS in the sidebar and the rest in main — still 5 total.

- [ ] **Step 5: Commit**

```bash
git add resume_templates/
git commit -m "feat: three resume HTML templates with placeholder comments"
```

---

## Task 10: Generation Engine

**Files:**
- Create: `app/generator.py`
- Create: `tests/test_generator.py`

- [ ] **Step 1: Write failing tests in `tests/test_generator.py`**

```python
import subprocess
import pytest
from unittest.mock import patch, MagicMock
from app.generator import build_prompt, extract_html, generate_resume


def test_build_prompt_contains_all_three_inputs(sample_profile):
    prompt = build_prompt(sample_profile, "Senior Python Engineer at Acme", "<html><!-- STATIC --></html>")
    assert "Jane Smith" in prompt                   # profile present
    assert "Senior Python Engineer at Acme" in prompt  # job description present
    assert "<!-- STATIC -->" in prompt              # template present


def test_build_prompt_includes_accomplishments(sample_profile):
    prompt = build_prompt(sample_profile, "job", "<html></html>")
    assert "10k requests/day" in prompt


def test_extract_html_strips_markdown_fences():
    raw = "```html\n<!DOCTYPE html><html><body>Hello</body></html>\n```"
    result = extract_html(raw)
    assert result.startswith("<!DOCTYPE html>")
    assert "```" not in result


def test_extract_html_passthrough_clean():
    raw = "<!DOCTYPE html><html><body>Hello</body></html>"
    assert extract_html(raw) == raw


def test_extract_html_strips_preamble():
    raw = "Sure! Here is your resume:\n\n<!DOCTYPE html><html><body></body></html>"
    result = extract_html(raw)
    assert result.startswith("<!DOCTYPE html>")


def test_extract_html_returns_empty_for_no_html():
    assert extract_html("Here is some plain text with no HTML.") == ""


def test_extract_html_handles_lowercase_doctype():
    raw = "<!doctype html><html><body></body></html>"
    result = extract_html(raw)
    assert result.startswith("<!doctype html>")


def test_generate_resume_success(sample_profile):
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "<!DOCTYPE html><html><body>Resume content</body></html>"
    mock_result.stderr = ""
    with patch("app.generator.subprocess.run", return_value=mock_result):
        html, error = generate_resume(sample_profile, "Python dev role", "<html><!-- STATIC --></html>")
    assert html.startswith("<!DOCTYPE html>")
    assert error == ""


def test_generate_resume_timeout(sample_profile):
    with patch(
        "app.generator.subprocess.run",
        side_effect=subprocess.TimeoutExpired("claude", 120),
    ):
        html, error = generate_resume(sample_profile, "Python dev role", "<html></html>")
    assert html == ""
    assert "timed out" in error.lower()


def test_generate_resume_claude_not_found(sample_profile):
    with patch("app.generator.subprocess.run", side_effect=FileNotFoundError()):
        html, error = generate_resume(sample_profile, "Python dev role", "<html></html>")
    assert html == ""
    assert "not found" in error.lower()


def test_generate_resume_nonzero_exit(sample_profile):
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""
    mock_result.stderr = "authentication required"
    with patch("app.generator.subprocess.run", return_value=mock_result):
        html, error = generate_resume(sample_profile, "Python dev role", "<html></html>")
    assert html == ""
    assert "authentication required" in error


def test_generate_resume_non_html_output(sample_profile):
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "I'm sorry, I cannot complete this request."
    mock_result.stderr = ""
    with patch("app.generator.subprocess.run", return_value=mock_result):
        html, error = generate_resume(sample_profile, "Python dev role", "<html></html>")
    assert html == ""
    assert "I'm sorry" in error
```

- [ ] **Step 2: Run tests — expect failure**

```bash
pytest tests/test_generator.py -v
```

Expected: `ImportError` (module not found)

- [ ] **Step 3: Create `app/generator.py`**

```python
import json
import re
import subprocess


def build_prompt(profile: dict, job_description: str, template_html: str) -> str:
    return f"""You are an expert resume writer. Produce a tailored resume as a complete HTML document.

USER PROFILE (JSON):
{json.dumps(profile, indent=2)}

JOB DESCRIPTION:
{job_description}

RESUME TEMPLATE (HTML with placeholder comments):
{template_html}

Instructions:
- Select only the most relevant experience entries and projects for this specific role
- Rewrite accomplishment bullet points to mirror the job's language and keywords exactly
- Never invent facts — only use information present in the profile
- Replace every placeholder comment in the template with real HTML content
- For <!-- SKILLS -->, infer skills from the selected experience + job description keywords
- Return ONLY the complete HTML document — no explanation, no markdown fences, no commentary
- The response must begin with <!DOCTYPE html> or <html"""


def extract_html(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```html?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"```\s*$", "", text.strip(), flags=re.MULTILINE)
    text = text.strip()
    for marker in ("<!DOCTYPE", "<!doctype", "<html", "<HTML"):
        idx = text.find(marker)
        if idx != -1:
            return text[idx:]
    return ""


def generate_resume(
    profile: dict, job_description: str, template_html: str
) -> tuple[str, str]:
    """Returns (html, error). html is empty on failure; error is empty on success."""
    prompt = build_prompt(profile, job_description, template_html)
    try:
        result = subprocess.run(
            ["claude", "-p"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            return "", f"claude exited with code {result.returncode}:\n{result.stderr}"
        html = extract_html(result.stdout)
        if not html:
            return "", result.stdout
        return html, ""
    except subprocess.TimeoutExpired:
        return "", "Generation timed out after 120 seconds. Please try again."
    except FileNotFoundError:
        return "", "claude CLI not found. Make sure it is installed and on your PATH."
```

- [ ] **Step 4: Run tests — expect all pass**

```bash
pytest tests/test_generator.py -v
```

Expected: `12 passed`

- [ ] **Step 5: Commit**

```bash
git add app/generator.py tests/test_generator.py
git commit -m "feat: generation engine with claude -p subprocess"
```

---

## Task 11: PDF Renderer

**Files:**
- Create: `app/pdf.py`

No unit test here — Playwright requires a Chromium install that may not be present in the test environment. The generate route (Task 12) covers the fallback path. Manual verification in Task 12.

- [ ] **Step 1: Create `app/pdf.py`**

```python
import asyncio
from pathlib import Path


async def _render_async(html: str, output_path: Path) -> None:
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        # --no-sandbox required on WSL (kernel sandbox not available)
        browser = await p.chromium.launch(args=["--no-sandbox"])
        page = await browser.new_page()
        await page.set_content(html, wait_until="networkidle")
        await page.pdf(
            path=str(output_path),
            format="A4",
            print_background=True,
            margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
        )
        await browser.close()


def render_pdf(html: str, output_path: Path) -> bool:
    """Returns True on success, False on any failure. Never raises."""
    try:
        asyncio.run(_render_async(html, output_path))
        return True
    except Exception:
        return False
```

- [ ] **Step 2: Verify Playwright is installed**

```bash
python -c "from playwright.async_api import async_playwright; print('ok')"
playwright install chromium
```

Expected: `ok` and then Chromium download completes.

- [ ] **Step 3: Commit**

```bash
git add app/pdf.py
git commit -m "feat: Playwright PDF renderer"
```

---

## Task 12: Generate Page & Full Pipeline

**Files:**
- Modify: `app/main.py` (add GET /generate, POST /generate)
- Create: `app/templates/generate.html`
- Create: `app/templates/partials/generate_result.html`

- [ ] **Step 1: Add failing route tests to `tests/test_routes.py`**

```python
def test_generate_page_loads(client, mock_profile_path):
    response = client.get("/generate")
    assert response.status_code == 200
    assert "Job Posting" in response.text
    assert "Generate Resume" in response.text


def test_generate_page_shows_templates(client, mock_profile_path, tmp_path, monkeypatch):
    import app.main as main_module
    fake_templates = tmp_path / "resume_templates"
    fake_templates.mkdir()
    (fake_templates / "classic.html").write_text("<!-- STATIC -->")
    (fake_templates / "modern-sidebar.html").write_text("<!-- STATIC -->")
    monkeypatch.setattr(main_module, "RESUME_TEMPLATES_DIR", fake_templates)
    response = client.get("/generate")
    assert "Classic" in response.text
    assert "Modern Sidebar" in response.text
```

- [ ] **Step 2: Run tests — expect failure**

```bash
pytest tests/test_routes.py::test_generate_page_loads tests/test_routes.py::test_generate_page_shows_templates -v
```

Expected: `2 failed`

- [ ] **Step 3: Add `get_resume_templates` helper and generate routes to `app/main.py`**

```python
from datetime import datetime
from .generator import generate_resume
from .pdf import render_pdf


def get_resume_templates() -> list[dict]:
    return [
        {"id": p.stem, "name": p.stem.replace("-", " ").title()}
        for p in sorted(RESUME_TEMPLATES_DIR.glob("*.html"))
    ]


@app.get("/generate", response_class=HTMLResponse)
async def generate_page(request: Request):
    profile = load_profile()
    return templates.TemplateResponse("generate.html", {
        "request": request,
        "resume_templates": get_resume_templates(),
        "has_experience": bool(profile["experience"]),
    })


@app.post("/generate", response_class=HTMLResponse)
async def run_generate(
    request: Request,
    job_description: str = Form(...),
    job_title: str = Form(""),
    job_company: str = Form(""),
    template_id: str = Form(...),
):
    profile = load_profile()
    template_path = RESUME_TEMPLATES_DIR / f"{template_id}.html"

    if not template_path.exists():
        return templates.TemplateResponse("partials/generate_result.html", {
            "request": request,
            "error": f"Template '{template_id}' not found.",
            "raw_output": "",
            "pdf_url": None,
            "html_url": None,
            "pdf_ok": False,
        })

    template_html = template_path.read_text()
    html, error = generate_resume(profile, job_description, template_html)

    if not html:
        return templates.TemplateResponse("partials/generate_result.html", {
            "request": request,
            "error": error,
            "raw_output": error,
            "pdf_url": None,
            "html_url": None,
            "pdf_ok": False,
        })

    company = (job_company.strip().replace(" ", "-")[:20] or "company").lower()
    role = (job_title.strip().replace(" ", "-")[:20] or "resume").lower()
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    stem = f"{company}-{role}-{timestamp}"

    html_path = OUTPUT_DIR / f"{stem}.html"
    html_path.write_text(html)

    pdf_path = OUTPUT_DIR / f"{stem}.pdf"
    pdf_ok = render_pdf(html, pdf_path)

    return templates.TemplateResponse("partials/generate_result.html", {
        "request": request,
        "error": "",
        "raw_output": "",
        "pdf_url": f"/output/{stem}.pdf" if pdf_ok else None,
        "html_url": f"/output/{stem}.html",
        "pdf_ok": pdf_ok,
    })
```

- [ ] **Step 4: Create `app/templates/generate.html`**

```html
{% extends "base.html" %}
{% block title %}Generate Resume — Resume Builder{% endblock %}
{% block content %}

<div class="page-header">
  <h1>Generate Resume</h1>
</div>

{% if not has_experience %}
<div class="banner banner-warning">
  Your profile has no experience entries.
  <a href="/profile?tab=experience">Add some</a> for better results.
</div>
{% endif %}

<div class="generate-layout">

  <div class="generate-left card">
    <h2>Job Posting</h2>
    <form hx-post="/generate"
          hx-target="#generate-result"
          hx-swap="innerHTML"
          hx-indicator="#spinner"
          hx-on::before-request="document.querySelector('button[type=submit]').disabled=true"
          hx-on::after-request="document.querySelector('button[type=submit]').disabled=false">

      <label>Job Title <small style="font-weight:400;color:#888">(optional — used for filename)</small>
        <input type="text" name="job_title" placeholder="e.g. Senior Software Engineer">
      </label>
      <label>Company <small style="font-weight:400;color:#888">(optional — used for filename)</small>
        <input type="text" name="job_company" placeholder="e.g. Acme Corp">
      </label>
      <label>Job Description <small style="font-weight:400;color:#888">(paste the full posting)</small>
        <textarea name="job_description" rows="14" required
                  placeholder="Paste the full job posting here..."></textarea>
      </label>

      <h2 style="margin:20px 0 12px">Template</h2>
      <div class="template-grid">
        {% for tmpl in resume_templates %}
        <label class="template-card">
          <input type="radio" name="template_id" value="{{ tmpl.id }}"
                 {% if loop.first %}checked{% endif %}>
          <span>{{ tmpl.name }}</span>
        </label>
        {% endfor %}
      </div>

      <button type="submit" class="btn btn-primary btn-lg">Generate Resume</button>
    </form>

    <div id="spinner" class="htmx-indicator spinner">
      Generating your resume — this takes 15–30 seconds...
    </div>
  </div>

  <div class="generate-right">
    <div id="generate-result"></div>
  </div>

</div>
{% endblock %}
```

- [ ] **Step 5: Create `app/templates/partials/generate_result.html`**

```html
{% if error %}
<div class="card card-error">
  <h3>Generation failed</h3>
  <p>{{ error }}</p>
  {% if raw_output and raw_output != error %}
  <details>
    <summary>Raw output (for debugging)</summary>
    <pre>{{ raw_output }}</pre>
  </details>
  {% endif %}
</div>
{% else %}
<div class="card card-success">
  <h3>Resume ready!</h3>
  <div class="button-row" style="margin-top:4px">
    {% if pdf_ok %}
    <a href="{{ pdf_url }}" download class="btn btn-primary">Download PDF</a>
    {% else %}
    <div class="banner banner-warning" style="width:100%">
      PDF conversion failed. <a href="{{ html_url }}" target="_blank">Open HTML</a>
      and use <kbd>Ctrl+P → Save as PDF</kbd>.
    </div>
    {% endif %}
    <a href="{{ html_url }}" target="_blank" class="btn">Preview HTML</a>
  </div>
</div>
{% endif %}
```

- [ ] **Step 6: Run all route tests**

```bash
pytest tests/test_routes.py -v
```

Expected: all tests pass.

- [ ] **Step 7: Manual end-to-end smoke test**

```bash
uvicorn app.main:app --reload
```

1. Open http://localhost:8000
2. Go to Profile → fill in name + email → Save
3. Add one experience entry with accomplishments
4. Go to Generate → paste any job description → select Classic → click Generate
5. Confirm spinner appears, then result card appears with download links

- [ ] **Step 8: Commit**

```bash
git add app/main.py app/templates/generate.html app/templates/partials/generate_result.html
git commit -m "feat: generate page with full claude -p pipeline"
```

---

## Task 13: Error Handling & First-Run UX

**Files:**
- Modify: `app/main.py` (add first-run redirect)
- Modify: `app/templates/profile.html` (add saved banner — already done)

- [ ] **Step 1: Add failing test to `tests/test_routes.py`**

```python
def test_first_run_redirects_to_profile_with_banner(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    import app.main as main_module
    import app.profile as profile_module

    missing_path = tmp_path / "profile.json"
    monkeypatch.setattr(profile_module, "PROFILE_PATH", missing_path)

    client = TestClient(main_module.app)
    response = client.get("/generate", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"].startswith("/")
    # After redirect, profile.json should now exist (auto-scaffolded)
    assert missing_path.exists()
```

- [ ] **Step 2: Run test — expect failure**

```bash
pytest tests/test_routes.py::test_first_run_redirects_to_profile_with_banner -v
```

Expected: `1 failed` (no redirect happens yet)

- [ ] **Step 3: Add first-run guard to `generate_page` in `app/main.py`**

Replace the existing `generate_page` route body:

```python
@app.get("/generate", response_class=HTMLResponse)
async def generate_page(request: Request):
    profile = load_profile()
    if not profile["static"].get("name") and not profile["experience"]:
        return RedirectResponse("/?setup=1", status_code=302)
    return templates.TemplateResponse("generate.html", {
        "request": request,
        "resume_templates": get_resume_templates(),
        "has_experience": bool(profile["experience"]),
    })
```

- [ ] **Step 4: Run test — expect pass**

```bash
pytest tests/test_routes.py::test_first_run_redirects_to_profile_with_banner -v
```

Expected: `1 passed`

- [ ] **Step 5: Run the full test suite**

```bash
pytest -v
```

Expected: all tests pass. Note the count — fix any failures before continuing.

- [ ] **Step 6: Final end-to-end test**

```bash
uvicorn app.main:app --reload
```

Walk through the full flow:
1. Open http://localhost:8000 — should show 0% completeness and setup prompt
2. Navigate to Profile → fill in name, email, at least one job with accomplishments
3. Paste a real job description into Generate, pick a template, click Generate
4. Confirm PDF downloads and opens correctly

- [ ] **Step 7: Final commit**

```bash
git add app/main.py tests/test_routes.py
git commit -m "feat: first-run redirect and complete error handling"
```

---

## Running the App

```bash
cd resume-builder
source .venv/bin/activate        # if using venv
uvicorn app.main:app --reload
# open http://localhost:8000
```

## Running Tests

```bash
pytest -v                         # all tests
pytest tests/test_profile.py -v   # profile layer only
pytest tests/test_generator.py -v # generation engine only
pytest tests/test_routes.py -v    # route integration tests
```
