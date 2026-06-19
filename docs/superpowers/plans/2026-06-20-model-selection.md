# Model Selection for Headless Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the user pick which Claude model (sonnet/opus/haiku) generates a resume, per-request, via a dropdown on the existing Generate form.

**Architecture:** A `model` form field flows from `app/templates/generate.html` → `run_generate()` in `app/main.py` (validated against an allow-list) → `generate_resume()` in `app/generator.py`, which inserts `-m <model>` into the `claude -p` subprocess argv. No persistence, no new files.

**Tech Stack:** FastAPI, Jinja2 templates, pytest + `unittest.mock.patch`, `fastapi.testclient.TestClient`.

## Global Constraints

- Allowed model values: exactly `sonnet`, `opus`, `haiku` (CLI short aliases — no hardcoded full model IDs).
- Default model: `sonnet`.
- No persistence of the chosen model across requests (no cookies/localStorage).
- Server-side validation required even though the `<select>` constrains the UI (form values can be forged).

---

### Task 1: `generate_resume` accepts and passes through `model`

**Files:**
- Modify: `app/generator.py:40-62`
- Test: `tests/test_generator.py`

**Interfaces:**
- Produces: `generate_resume(profile: dict, job_description: str, template_html: str, model: str = "sonnet") -> tuple[str, str]` — same return shape as before, new optional 4th parameter.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_generator.py`:

```python
def test_generate_resume_passes_model_flag(sample_profile):
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "<!DOCTYPE html><html><body>Resume content</body></html>"
    mock_result.stderr = ""
    with patch("app.generator.subprocess.run", return_value=mock_result) as mock_run:
        generate_resume(sample_profile, "Python dev role", "<html></html>", model="opus")
    args = mock_run.call_args[0][0]
    assert args == ["claude", "-m", "opus", "-p"]


def test_generate_resume_defaults_to_sonnet(sample_profile):
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "<!DOCTYPE html><html><body>Resume content</body></html>"
    mock_result.stderr = ""
    with patch("app.generator.subprocess.run", return_value=mock_result) as mock_run:
        generate_resume(sample_profile, "Python dev role", "<html></html>")
    args = mock_run.call_args[0][0]
    assert args == ["claude", "-m", "sonnet", "-p"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_generator.py -k "model" -v`
Expected: FAIL — `generate_resume() got an unexpected keyword argument 'model'` (for the first test) since the parameter doesn't exist yet.

- [ ] **Step 3: Implement**

In `app/generator.py`, change the function signature and subprocess call:

```python
def generate_resume(
    profile: dict, job_description: str, template_html: str, model: str = "sonnet"
) -> tuple[str, str]:
    """Returns (html, error). html is empty on failure; error is empty on success."""
    prompt = build_prompt(profile, job_description, template_html)
    try:
        result = subprocess.run(
            ["claude", "-m", model, "-p"],
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

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_generator.py -v`
Expected: All tests PASS, including the two new ones and all pre-existing `test_generate_resume_*` tests (they call `generate_resume` without `model`, which now defaults to `"sonnet"`).

- [ ] **Step 5: Commit**

```bash
git add app/generator.py tests/test_generator.py
git commit -m "feat: add model parameter to generate_resume"
```

---

### Task 2: `/generate` route validates and forwards `model`

**Files:**
- Modify: `app/main.py:209-230`
- Test: `tests/test_routes.py`

**Interfaces:**
- Consumes: `generate_resume(profile, job_description, template_html, model)` from Task 1.
- Produces: `/generate` POST now accepts a `model` form field (default `"sonnet"`); invalid values return the existing `partials/generate_result.html` error partial with `error` set to a message containing the invalid model name, without calling `generate_resume`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_routes.py` (needs `mock_profile_path` fixture and a real template dir, following the pattern of `test_generate_page_shows_templates`):

```python
def test_generate_rejects_invalid_model(client, mock_profile_path, tmp_path, monkeypatch):
    import app.main as main_module
    fake_templates = tmp_path / "resume_templates"
    fake_templates.mkdir()
    (fake_templates / "classic.html").write_text("<!-- STATIC -->")
    monkeypatch.setattr(main_module, "RESUME_TEMPLATES_DIR", fake_templates)

    response = client.post("/generate", data={
        "job_description": "Some job",
        "template_id": "classic",
        "model": "gpt-5",
    })
    assert response.status_code == 200
    assert "gpt-5" in response.text
    assert "not" in response.text.lower()


def test_generate_passes_valid_model_to_generator(client, mock_profile_path, tmp_path, monkeypatch):
    import app.main as main_module
    from unittest.mock import patch

    fake_templates = tmp_path / "resume_templates"
    fake_templates.mkdir()
    (fake_templates / "classic.html").write_text("<!-- STATIC -->")
    monkeypatch.setattr(main_module, "RESUME_TEMPLATES_DIR", fake_templates)
    monkeypatch.setattr(main_module, "OUTPUT_DIR", tmp_path / "output")
    (tmp_path / "output").mkdir()

    with patch(
        "app.main.generate_resume",
        return_value=("<!DOCTYPE html><html><body>x</body></html>", ""),
    ) as mock_generate, patch("app.main.render_pdf", return_value=False):
        client.post("/generate", data={
            "job_description": "Some job",
            "template_id": "classic",
            "model": "opus",
        })

    assert mock_generate.call_args[0][3] == "opus"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_routes.py -k "model" -v`
Expected: FAIL — `test_generate_rejects_invalid_model` fails because there's no model validation yet (it will instead try to call the real `generate_resume`, which will fail differently or hang on a missing `claude` binary); `test_generate_passes_valid_model_to_generator` fails with an `IndexError` or assertion mismatch since `generate_resume` is called with only 3 positional args.

- [ ] **Step 3: Implement**

In `app/main.py`, modify the route:

```python
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
```

(Everything below `html, error = generate_resume(...)` stays unchanged.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_routes.py -v`
Expected: All tests PASS, including pre-existing ones (`test_generate_page_loads`, `test_generate_page_shows_templates`, `test_first_run_redirects_to_profile_with_banner`, etc. — none of them post to `/generate` with a model field, so the `"sonnet"` default keeps them passing).

- [ ] **Step 5: Commit**

```bash
git add app/main.py tests/test_routes.py
git commit -m "feat: validate and forward model selection on /generate"
```

---

### Task 3: Model dropdown on the Generate form

**Files:**
- Modify: `app/templates/generate.html:18-50`
- Test: `tests/test_routes.py` (extend `test_generate_page_loads`)

**Interfaces:**
- Consumes: nothing new — pure template change feeding the `model` form field validated in Task 2.
- Produces: the rendered `/generate` page includes a `<select name="model">` with options `sonnet` (selected by default), `opus`, `haiku`.

- [ ] **Step 1: Write the failing test**

Extend `test_generate_page_loads` in `tests/test_routes.py`:

```python
def test_generate_page_loads(client, mock_profile_path):
    response = client.get("/generate")
    assert response.status_code == 200
    assert "Job Posting" in response.text
    assert "Generate Resume" in response.text
    assert 'name="model"' in response.text
    assert '<option value="sonnet" selected>' in response.text
    assert '<option value="opus">' in response.text
    assert '<option value="haiku">' in response.text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_routes.py::test_generate_page_loads -v`
Expected: FAIL — `assert 'name="model"' in response.text` fails since the field doesn't exist yet.

- [ ] **Step 3: Implement**

In `app/templates/generate.html`, add the model select between the Job Description label and the Template heading:

```html
      <label>Job Description <small style="font-weight:400;color:#888">(paste the full posting)</small>
        <textarea name="job_description" rows="14" required
                  placeholder="Paste the full job posting here..."></textarea>
      </label>

      <label>Model <small style="font-weight:400;color:#888">(which Claude model generates this resume)</small>
        <select name="model">
          <option value="sonnet" selected>Sonnet</option>
          <option value="opus">Opus</option>
          <option value="haiku">Haiku</option>
        </select>
      </label>

      <h2 style="margin:20px 0 12px">Template</h2>
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_routes.py -v`
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/templates/generate.html tests/test_routes.py
git commit -m "feat: add model dropdown to Generate form"
```

---

### Task 4: Full-suite verification

**Files:** none (verification only)

**Interfaces:** none — this task only runs the existing suite to confirm Tasks 1-3 integrate cleanly.

- [ ] **Step 1: Run the full test suite**

Run: `pytest -v`
Expected: All tests PASS (generator, routes, profile, and the new model tests).

- [ ] **Step 2: Manually smoke-test in the browser**

Start the app (e.g. `uvicorn app.main:app --reload`), open `/generate`, confirm the Model dropdown renders with Sonnet selected, submit a generation with each of Opus and Haiku selected, and confirm no server error occurs before the `claude` subprocess call (the actual `claude` CLI call itself is environment-dependent and out of scope to verify here beyond "the request reaches `generate_resume` with the right model").

- [ ] **Step 3: Commit (if any fixups were needed)**

```bash
git add -A
git commit -m "fix: address issues found in full-suite verification"
```

(Skip this commit if no fixups were needed.)
