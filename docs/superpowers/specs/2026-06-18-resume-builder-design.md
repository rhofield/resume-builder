# Resume Builder — Design Spec
**Date:** 2026-06-18  
**Status:** Approved  

---

## Overview

A local web application that stores detailed facts about a user (education, work history with accomplishments, personal projects, static contact info) and generates tailored, job-specific resumes as PDFs. The user pastes a job description, selects a resume template, and the app calls the Claude CLI to produce a filled-in HTML resume which is then converted to PDF via Playwright.

Runs entirely locally on WSL. Single user. No cloud, no accounts.

---

## Stack

| Layer | Choice |
|---|---|
| Backend | Python + FastAPI |
| Templating (UI) | Jinja2 + HTMX |
| Claude integration | `claude -p "..."` subprocess |
| PDF generation | Playwright (HTML → PDF) |
| PDF fallback | Serve raw HTML with Ctrl+P instruction |
| Data storage | `profile.json` (flat file, single user) |
| Resume templates | HTML files in `resume_templates/` (auto-discovered) |

---

## Project Structure

```
resume-builder/
├── app/
│   ├── main.py              # FastAPI app + all routes
│   ├── generator.py         # claude -p subprocess + prompt builder
│   ├── pdf.py               # Playwright HTML → PDF
│   ├── profile.py           # profile.json read/write helpers
│   ├── templates/           # Jinja2 UI templates
│   │   ├── base.html
│   │   ├── dashboard.html
│   │   ├── profile.html
│   │   └── generate.html
│   └── static/              # CSS, HTMX, minimal JS
├── resume_templates/        # pluggable HTML/CSS resume styles
│   ├── classic.html
│   ├── modern-sidebar.html
│   └── minimalist-accent.html
├── profile.json             # all user data lives here
├── output/                  # generated PDFs saved here
└── requirements.txt
```

---

## Data Model

`profile.json` is the single source of truth. Claude reads from it but never writes to it.

```json
{
  "static": {
    "name": "",
    "email": "",
    "phone": "",
    "location": "",
    "github": "",
    "linkedin": ""
  },
  "education": [
    {
      "institution": "",
      "degree": "",
      "field": "",
      "start": "",
      "end": "",
      "details": ""
    }
  ],
  "experience": [
    {
      "company": "",
      "title": "",
      "start": "",
      "end": "",
      "location": "",
      "accomplishments": ["raw bullet points — as detailed as possible"]
    }
  ],
  "projects": [
    {
      "name": "",
      "description": "",
      "tech_stack": [],
      "highlights": [],
      "url": ""
    }
  ]
}
```

Accomplishments and highlights should be stored with maximum detail — Claude selects and rewrites them per job posting, never invents facts.

If `profile.json` is missing on first run, an empty scaffold is auto-created and the user is redirected to `/profile` with a setup banner.

---

## Pages

### `/` — Dashboard
- Profile completeness indicator
- Quick-add buttons (+ Job, + Project, + Education)
- Recent generations list with download links
- "Generate Resume" CTA

### `/profile` — Profile Editor
- Tabbed sections: Static Info · Education · Experience · Projects
- Each tab: listed entries (ordered by insertion) + inline add/edit/delete forms
- HTMX handles all mutations without full page reloads
- All saves write directly to `profile.json`

### `/generate` — Generate Resume
- **Left panel:** large textarea for pasting job description, optional job title + company fields (used for output filename)
- **Right panel:** template selector as a card grid (one card per file in `resume_templates/`, showing template name), Generate button, progress indicator, result links
- Generation takes 10–30s; UI shows a spinner and disables the button during generation

---

## Template System

Each file in `resume_templates/` is a self-contained HTML document with:
- All CSS inlined (so Playwright renders it standalone with no external assets)
- Placeholder comments marking injection points:

```html
<!-- STATIC: name, email, phone, location, linkedin, github -->
<!-- EXPERIENCE_ITEMS: jobs selected as relevant to this role -->
<!-- EDUCATION_ITEMS -->
<!-- PROJECT_ITEMS: only if relevant to the role -->
<!-- SKILLS: inferred from selected experience + job keywords -->
```

**Auto-discovery:** templates are enumerated at startup by scanning `resume_templates/*.html`. Template display name = filename without extension, title-cased (e.g. `modern-sidebar.html` → "Modern Sidebar"). No config required — dropping a new `.html` file into the folder makes it appear in the UI.

---

## Generation Engine

**File:** `app/generator.py`

```
1. Load profile.json
2. Load selected template HTML
3. Build prompt (see Prompt Strategy below)
4. subprocess.run(["claude", "-p", prompt], capture_output=True, text=True, timeout=120)
5. extract_html(stdout)  — strip markdown fences if present, validate <html> present
6. Playwright renders HTML → PDF → saved to output/<company>-<title>-<timestamp>.pdf
7. Return PDF path + HTML preview path to caller
```

### Prompt Strategy

The prompt passes Claude three things:

1. **Full profile as JSON** — all entries, all detail
2. **Job description** — verbatim paste
3. **Template HTML** — with placeholder comments intact

Claude's instruction:
> Select the most relevant experience entries and projects for this role. Rewrite accomplishment bullet points to mirror the job's language and keywords without inventing facts. Fill the template placeholders exactly. Return only the complete, valid HTML document — no explanation, no markdown fences, no commentary.

Output format constraint: response must begin with `<!DOCTYPE html>` or `<html`.

---

## Error Handling

| Failure | Behaviour |
|---|---|
| `claude -p` times out (>120s) | Show "Generation timed out" in UI. Log stderr. Allow retry with same inputs. |
| Claude returns non-HTML | `extract_html()` strips fences. If no `<html>` found, show raw output in a copyable box. |
| Playwright PDF fails | Fall back to serving raw HTML with "Save as PDF via Ctrl+P" instruction banner. |
| `profile.json` missing | Auto-create empty scaffold. Redirect to `/profile` with setup banner. |

---

## LinkedIn Job Posting

**v1: paste-only.** LinkedIn's auth wall makes scraping fragile and unreliable. The paste workflow is 5 seconds and 100% reliable.

**Future extension (no architecture changes required):** Add an optional "LinkedIn URL" field that attempts a best-effort `requests` fetch + BeautifulSoup parse. On auth failure, fall back silently to the paste box.

---

## Out of Scope (v1)

- Multi-user support / accounts
- Cloud hosting / deployment
- Cover letter generation (same engine, trivial extension)
- Resume version history (`output/` folder provides this implicitly via timestamped filenames)
- ATS score / keyword gap analysis
