# Resume Builder

A local FastAPI app for maintaining a personal career profile and generating
tailored, job-specific resumes (HTML + PDF) using either the `claude` CLI or
Codex in headless mode.

## How it works

1. You maintain a single profile (`profile.json`) — static info, education,
   experience, and projects — through a web UI.
2. For a given job posting, you pick a resume template and paste in the job
   description.
3. The app sends your profile + the job description + the template to the
   selected headless CLI (`claude` or `codex exec`), which selects relevant
   experience and rewrites bullet points to match the job's language,
   returning a complete HTML resume.
4. The HTML is rendered to PDF (via Playwright) and saved to `output/`.

## Requirements

- Python 3.11+
- At least one supported CLI installed on your `PATH`:
  - The [`claude` CLI](https://docs.claude.com/en/docs/claude-code) for
    `sonnet`, `opus`, or `haiku`
  - `codex` for headless Codex generation via `codex exec`, with access to
    models such as `gpt-5` or `gpt-5-mini`
- Playwright browser binaries for PDF rendering

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

## Running

```bash
uvicorn app.main:app --reload
```

Then open http://127.0.0.1:8000.

- **Dashboard** (`/`) — profile completeness and recent generated resumes.
- **Profile** (`/profile`) — edit static info, education, experience, and projects.
- **Generate** (`/generate`) — paste a job description, pick a template and
  provider/model, and generate a tailored resume.

## Resume templates

HTML templates live in `resume_templates/`. Each one uses placeholder
comments (e.g. `<!-- SKILLS -->`) that the model fills in with real content.
Add a new template by dropping an `.html` file into that directory — it will
appear automatically in the Generate page.

## Tests

```bash
pytest
```
