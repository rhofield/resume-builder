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
5. You can edit the result by hand in the browser and rebuild the PDF, without
   re-running the model.

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
- **Edit** (`/edit/<name>`) — make manual edits to a generated resume and
  rebuild its PDF.

## Editing a generated resume

Generation is a slow, non-deterministic step, so fixing a typo or reordering a
job should not require another model call. Every generated resume has an
**Edit** link (on the dashboard and on the generate result) that opens it in a
WYSIWYG editor.

The generated HTML in `output/` is the source of truth; the PDF is derived from
it. Saving overwrites both, so the PDF always matches what you last saw.

- **Edit text** — click anywhere on the rendered resume and type.
- **Format** — bold, italics, underline, bulleted and numbered lists, indent,
  and links.
- **Resize** — `A-` / `A+` adjust the selected text; the `Document` control
  scales every font size in the resume at once, for fitting the page.
- **Paste** — keeps bold, italics, links and bullets, but drops the source's
  fonts, sizes and colours so pasted text adopts the template's styling.
  `Ctrl+Shift+V` pastes plain text.
- **Reorder** — hover a section, entry or bullet to move it up or down, step
  out to the block containing it, or delete it. `Undo` reverses moves and
  deletions as well as text edits.
- **Fit the page** — a live page count plus dashed guides showing where the A4
  page breaks fall.

`Ctrl+S` saves and rebuilds the PDF.

## Resume templates

HTML templates live in `resume_templates/`. Each one uses placeholder
comments (e.g. `<!-- SKILLS -->`) that the model fills in with real content.
Add a new template by dropping an `.html` file into that directory — it will
appear automatically in the Generate page.

## Tests

```bash
pytest
```

The editor's behaviour lives in browser JavaScript, so `tests/test_editor_browser.py`
drives a real Chromium instance against a live server via Playwright. It needs
the same `playwright install chromium` step as PDF rendering, and adds roughly
30 seconds to the run.
