from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from .profile import load_profile

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR.parent / "output"
RESUME_TEMPLATES_DIR = BASE_DIR.parent / "resume_templates"
OUTPUT_DIR.mkdir(exist_ok=True)

app = FastAPI(title="Resume Builder")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.mount("/output", StaticFiles(directory=str(OUTPUT_DIR)), name="output")

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
    return templates.TemplateResponse(request, "dashboard.html", context={
        "profile": profile,
        "completeness": _completeness(profile),
        "recent_outputs": get_recent_outputs(),
        "setup_banner": setup == "1",
    })


@app.get("/healthz")
async def health():
    return {"status": "ok"}
