import re
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from .profile import load_profile, save_profile
from .generator import generate_resume
from .pdf import render_pdf

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


@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request, tab: str = "static", saved: str = ""):
    profile = load_profile()
    return templates.TemplateResponse(request, "profile.html", context={
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
    return templates.TemplateResponse(request, "partials/education_list.html", context={
        "education": profile["education"],
    })


@app.delete("/profile/education/{index}", response_class=HTMLResponse)
async def delete_education(request: Request, index: int):
    profile = load_profile()
    if 0 <= index < len(profile["education"]):
        profile["education"].pop(index)
        save_profile(profile)
    return templates.TemplateResponse(request, "partials/education_list.html", context={
        "education": profile["education"],
    })


@app.get("/profile/education/{index}", response_class=HTMLResponse)
async def view_education(request: Request, index: int):
    profile = load_profile()
    if not 0 <= index < len(profile["education"]):
        raise HTTPException(status_code=404, detail="Education entry not found")
    return templates.TemplateResponse(request, "partials/education_entry.html", context={
        "edu": profile["education"][index],
        "index": index,
    })


@app.get("/profile/education/{index}/edit", response_class=HTMLResponse)
async def edit_education_form(request: Request, index: int):
    profile = load_profile()
    if not 0 <= index < len(profile["education"]):
        raise HTTPException(status_code=404, detail="Education entry not found")
    return templates.TemplateResponse(request, "partials/education_entry_edit.html", context={
        "edu": profile["education"][index],
        "index": index,
    })


@app.put("/profile/education/{index}", response_class=HTMLResponse)
async def update_education(
    request: Request,
    index: int,
    institution: str = Form(...),
    degree: str = Form(...),
    field: str = Form(""),
    start: str = Form(""),
    end: str = Form(""),
    details: str = Form(""),
):
    profile = load_profile()
    if not 0 <= index < len(profile["education"]):
        raise HTTPException(status_code=404, detail="Education entry not found")
    profile["education"][index] = {
        "institution": institution, "degree": degree, "field": field,
        "start": start, "end": end, "details": details,
    }
    save_profile(profile)
    return templates.TemplateResponse(request, "partials/education_entry.html", context={
        "edu": profile["education"][index],
        "index": index,
    })


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
    return templates.TemplateResponse(request, "partials/experience_list.html", context={
        "experience": profile["experience"],
    })


@app.delete("/profile/experience/{index}", response_class=HTMLResponse)
async def delete_experience(request: Request, index: int):
    profile = load_profile()
    if 0 <= index < len(profile["experience"]):
        profile["experience"].pop(index)
        save_profile(profile)
    return templates.TemplateResponse(request, "partials/experience_list.html", context={
        "experience": profile["experience"],
    })


@app.get("/profile/experience/{index}", response_class=HTMLResponse)
async def view_experience(request: Request, index: int):
    profile = load_profile()
    if not 0 <= index < len(profile["experience"]):
        raise HTTPException(status_code=404, detail="Experience entry not found")
    return templates.TemplateResponse(request, "partials/experience_entry.html", context={
        "exp": profile["experience"][index],
        "index": index,
    })


@app.get("/profile/experience/{index}/edit", response_class=HTMLResponse)
async def edit_experience_form(request: Request, index: int):
    profile = load_profile()
    if not 0 <= index < len(profile["experience"]):
        raise HTTPException(status_code=404, detail="Experience entry not found")
    return templates.TemplateResponse(request, "partials/experience_entry_edit.html", context={
        "exp": profile["experience"][index],
        "index": index,
    })


@app.put("/profile/experience/{index}", response_class=HTMLResponse)
async def update_experience(
    request: Request,
    index: int,
    company: str = Form(...),
    title: str = Form(...),
    start: str = Form(""),
    end: str = Form(""),
    location: str = Form(""),
    accomplishments_raw: str = Form(""),
):
    profile = load_profile()
    if not 0 <= index < len(profile["experience"]):
        raise HTTPException(status_code=404, detail="Experience entry not found")
    accomplishments = [
        line.strip().lstrip("•–-").strip()
        for line in accomplishments_raw.splitlines()
        if line.strip()
    ]
    profile["experience"][index] = {
        "company": company, "title": title, "start": start,
        "end": end, "location": location, "accomplishments": accomplishments,
    }
    save_profile(profile)
    return templates.TemplateResponse(request, "partials/experience_entry.html", context={
        "exp": profile["experience"][index],
        "index": index,
    })


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
    return templates.TemplateResponse(request, "partials/projects_list.html", context={
        "projects": profile["projects"],
    })


@app.delete("/profile/projects/{index}", response_class=HTMLResponse)
async def delete_project(request: Request, index: int):
    profile = load_profile()
    if 0 <= index < len(profile["projects"]):
        profile["projects"].pop(index)
        save_profile(profile)
    return templates.TemplateResponse(request, "partials/projects_list.html", context={
        "projects": profile["projects"],
    })


@app.get("/profile/projects/{index}", response_class=HTMLResponse)
async def view_project(request: Request, index: int):
    profile = load_profile()
    if not 0 <= index < len(profile["projects"]):
        raise HTTPException(status_code=404, detail="Project not found")
    return templates.TemplateResponse(request, "partials/projects_entry.html", context={
        "proj": profile["projects"][index],
        "index": index,
    })


@app.get("/profile/projects/{index}/edit", response_class=HTMLResponse)
async def edit_project_form(request: Request, index: int):
    profile = load_profile()
    if not 0 <= index < len(profile["projects"]):
        raise HTTPException(status_code=404, detail="Project not found")
    return templates.TemplateResponse(request, "partials/projects_entry_edit.html", context={
        "proj": profile["projects"][index],
        "index": index,
    })


@app.put("/profile/projects/{index}", response_class=HTMLResponse)
async def update_project(
    request: Request,
    index: int,
    name: str = Form(...),
    description: str = Form(""),
    tech_stack_raw: str = Form(""),
    highlights_raw: str = Form(""),
    url: str = Form(""),
):
    profile = load_profile()
    if not 0 <= index < len(profile["projects"]):
        raise HTTPException(status_code=404, detail="Project not found")
    tech_stack = [t.strip() for t in tech_stack_raw.split(",") if t.strip()]
    highlights = [
        line.strip().lstrip("•–-").strip()
        for line in highlights_raw.splitlines()
        if line.strip()
    ]
    profile["projects"][index] = {
        "name": name, "description": description,
        "tech_stack": tech_stack, "highlights": highlights, "url": url,
    }
    save_profile(profile)
    return templates.TemplateResponse(request, "partials/projects_entry.html", context={
        "proj": profile["projects"][index],
        "index": index,
    })


@app.get("/healthz")
async def health():
    return {"status": "ok"}


def get_resume_templates() -> list[dict]:
    return [
        {"id": p.stem, "name": p.stem.replace("-", " ").title()}
        for p in sorted(RESUME_TEMPLATES_DIR.glob("*.html"))
    ]


@app.get("/generate", response_class=HTMLResponse)
async def generate_page(request: Request):
    profile = load_profile()
    if not profile["static"].get("name") and not profile["experience"]:
        return RedirectResponse("/?setup=1", status_code=302)
    return templates.TemplateResponse(request, "generate.html", context={
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
    model: str = Form("sonnet"),
):
    profile = load_profile()
    valid_ids = {p.stem for p in RESUME_TEMPLATES_DIR.glob("*.html")}
    if template_id not in valid_ids:
        return templates.TemplateResponse(request, "partials/generate_result.html", context={
            "error": f"Template '{template_id}' not found.",
            "raw_output": "",
            "pdf_url": None,
            "html_url": None,
            "pdf_ok": False,
        })
    valid_models = {"sonnet", "opus", "haiku"}
    if model not in valid_models:
        return templates.TemplateResponse(request, "partials/generate_result.html", context={
            "error": f"Model '{model}' not recognized.",
            "raw_output": "",
            "pdf_url": None,
            "html_url": None,
            "pdf_ok": False,
        })
    template_path = RESUME_TEMPLATES_DIR / f"{template_id}.html"

    template_html = template_path.read_text()
    html, error = generate_resume(profile, job_description, template_html, model)

    if not html:
        return templates.TemplateResponse(request, "partials/generate_result.html", context={
            "error": error,
            "raw_output": error,
            "pdf_url": None,
            "html_url": None,
            "pdf_ok": False,
        })

    _safe = lambda s, d: (re.sub(r"[^a-z0-9-]", "", s.strip().lower().replace(" ", "-"))[:20] or d)
    company = _safe(job_company, "company")
    role = _safe(job_title, "resume")
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    stem = f"{company}-{role}-{timestamp}"

    html_path = OUTPUT_DIR / f"{stem}.html"
    if not html_path.resolve().is_relative_to(OUTPUT_DIR.resolve()):
        return templates.TemplateResponse(request, "partials/generate_result.html", context={
            "error": "Invalid output filename.",
            "raw_output": "", "pdf_url": None, "html_url": None, "pdf_ok": False,
        })
    html_path.write_text(html)

    pdf_path = OUTPUT_DIR / f"{stem}.pdf"
    pdf_ok = await render_pdf(html, pdf_path)

    return templates.TemplateResponse(request, "partials/generate_result.html", context={
        "error": "",
        "raw_output": "",
        "pdf_url": f"/output/{stem}.pdf" if pdf_ok else None,
        "html_url": f"/output/{stem}.html",
        "pdf_ok": pdf_ok,
    })
