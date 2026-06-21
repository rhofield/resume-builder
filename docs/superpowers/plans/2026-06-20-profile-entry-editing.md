# Profile Entry Editing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the user edit existing Education, Experience, and Projects entries in place on the Profile page, instead of only being able to delete and re-add them.

**Architecture:** For each of the three resources, extract the existing list partial's per-entry markup into a standalone "entry" partial (adding an Edit button), add a new "entry edit" partial (a pre-filled form), and add three new routes (`GET .../{index}`, `GET .../{index}/edit`, `PUT .../{index}`) that swap just that one `.entry` div via HTMX, following the swap/target conventions already used by the existing add/delete routes.

**Tech Stack:** FastAPI, Jinja2 (via `Jinja2Templates`), HTMX, pytest + `TestClient`.

## Global Constraints

- Index is positional (matches existing delete behavior) — no stable IDs are introduced.
- Out-of-range `index` on the new `GET .../{index}`, `GET .../{index}/edit`, and `PUT .../{index}` routes returns `404` via `HTTPException` (this is new — the existing `DELETE` route still no-ops silently on out-of-range index; that is unchanged).
- Add and Delete routes/behavior are unchanged — they still re-render the whole list and target `#education-list` / `#experience-list` / `#projects-list`.
- Follow the existing per-resource duplication style in `app/main.py` rather than introducing a generic/shared abstraction.

---

### Task 1: Education entry editing

**Files:**
- Modify: `app/main.py:1-4` (add `HTTPException` import), `app/main.py:104-113` (insert new routes after `delete_education`)
- Modify: `app/templates/partials/education_list.html` (replace loop body with an include)
- Create: `app/templates/partials/education_entry.html`
- Create: `app/templates/partials/education_entry_edit.html`
- Test: `tests/test_routes.py`

**Interfaces:**
- Consumes: `load_profile()` / `save_profile()` from `app/profile.py` (unchanged signatures); `mock_profile_path` and `client` fixtures from `tests/conftest.py` / `tests/test_routes.py`.
- Produces: routes `GET /profile/education/{index}`, `GET /profile/education/{index}/edit`, `PUT /profile/education/{index}` — used as the pattern Tasks 2 and 3 mirror for experience/projects.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_routes.py`:

```python
def test_view_education(client, mock_profile_path):
    response = client.get("/profile/education/0")
    assert response.status_code == 200
    assert "University of London" in response.text
    assert 'hx-get="/profile/education/0/edit"' in response.text


def test_view_education_not_found(client, mock_profile_path):
    response = client.get("/profile/education/99")
    assert response.status_code == 404


def test_edit_education_form(client, mock_profile_path):
    response = client.get("/profile/education/0/edit")
    assert response.status_code == 200
    assert 'value="University of London"' in response.text
    assert 'hx-put="/profile/education/0"' in response.text


def test_update_education(client, mock_profile_path):
    import json
    response = client.put("/profile/education/0", data={
        "institution": "Updated University",
        "degree": "MSc",
        "field": "Data Science",
        "start": "2017",
        "end": "2020",
        "details": "Distinction",
    })
    assert response.status_code == 200
    assert "Updated University" in response.text
    saved = json.loads(mock_profile_path.read_text())
    assert saved["education"][0]["institution"] == "Updated University"
    assert saved["education"][0]["degree"] == "MSc"


def test_update_education_not_found(client, mock_profile_path):
    response = client.put("/profile/education/99", data={
        "institution": "X", "degree": "Y", "field": "",
        "start": "", "end": "", "details": "",
    })
    assert response.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_routes.py -k education -v`
Expected: `test_view_education`, `test_edit_education_form`, `test_update_education` FAIL with 404/405 (routes don't exist yet); `test_view_education_not_found` and `test_update_education_not_found` may pass trivially (still 404, but for the wrong reason — route missing, not bounds-checked) — that's fine, they'll be re-verified in Step 4 once the real routes exist.

- [ ] **Step 3: Add `HTTPException` import**

In `app/main.py`, change line 4 from:

```python
from fastapi import FastAPI, Request, Form
```

to:

```python
from fastapi import FastAPI, Request, Form, HTTPException
```

- [ ] **Step 4: Extract the entry partial**

Create `app/templates/partials/education_entry.html`:

```html
<div class="entry">
  <div class="entry-main">
    <strong>{{ edu.degree }}{% if edu.field %} in {{ edu.field }}{% endif %}</strong>
    — {{ edu.institution }}
    {% if edu.start %}<span class="entry-date">{{ edu.start }}{% if edu.end %} – {{ edu.end }}{% endif %}</span>{% endif %}
  </div>
  {% if edu.details %}<p class="entry-details">{{ edu.details }}</p>{% endif %}
  <div style="margin-top:8px">
    <button class="btn btn-sm"
            hx-get="/profile/education/{{ index }}/edit"
            hx-target="closest .entry"
            hx-swap="outerHTML">Edit</button>
    <button class="btn btn-sm btn-danger"
            hx-delete="/profile/education/{{ index }}"
            hx-target="#education-list"
            hx-swap="innerHTML"
            hx-confirm="Delete this education entry?">Delete</button>
  </div>
</div>
```

- [ ] **Step 5: Create the edit-form partial**

Create `app/templates/partials/education_entry_edit.html`:

```html
<div class="entry">
  <form hx-put="/profile/education/{{ index }}"
        hx-target="closest .entry"
        hx-swap="outerHTML">
    <div class="form-grid">
      <label>Institution
        <input type="text" name="institution" required value="{{ edu.institution }}">
      </label>
      <label>Degree
        <input type="text" name="degree" required value="{{ edu.degree }}">
      </label>
      <label>Field of Study
        <input type="text" name="field" value="{{ edu.field }}">
      </label>
      <label>Start Year
        <input type="text" name="start" value="{{ edu.start }}">
      </label>
      <label>End Year
        <input type="text" name="end" value="{{ edu.end }}">
      </label>
    </div>
    <label>Details
      <textarea name="details" rows="2">{{ edu.details }}</textarea>
    </label>
    <div style="margin-top:8px">
      <button type="submit" class="btn btn-sm btn-primary">Save</button>
      <button type="button" class="btn btn-sm"
              hx-get="/profile/education/{{ index }}"
              hx-target="closest .entry"
              hx-swap="outerHTML">Cancel</button>
    </div>
  </form>
</div>
```

- [ ] **Step 6: Point the list partial at the entry partial**

Replace the full contents of `app/templates/partials/education_list.html` with:

```html
{% for edu in education %}
{% set index = loop.index0 %}
{% include "partials/education_entry.html" %}
{% else %}
<p class="empty-state">No education entries yet.</p>
{% endfor %}
```

- [ ] **Step 7: Add the three routes**

In `app/main.py`, insert immediately after the existing `delete_education` function (currently ending around line 112, right before `@app.post("/profile/experience", ...)`):

```python
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
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `pytest tests/test_routes.py -k education -v`
Expected: all PASS, including `test_add_education`, `test_delete_education`, `test_profile_page_loads` (pre-existing tests must still pass).

Run full suite to check for regressions: `pytest -v`
Expected: all PASS.

- [ ] **Step 9: Commit**

```bash
git add app/main.py app/templates/partials/education_list.html app/templates/partials/education_entry.html app/templates/partials/education_entry_edit.html tests/test_routes.py
git commit -m "feat: add inline editing for education entries"
```

---

### Task 2: Experience entry editing

**Files:**
- Modify: `app/main.py` (insert new routes after `delete_experience`, currently ending around line 149, right before `@app.post("/profile/projects", ...)`)
- Modify: `app/templates/partials/experience_list.html` (replace loop body with an include)
- Create: `app/templates/partials/experience_entry.html`
- Create: `app/templates/partials/experience_entry_edit.html`
- Test: `tests/test_routes.py`

**Interfaces:**
- Consumes: same `load_profile()` / `save_profile()` as Task 1; the accomplishments-parsing logic already used in `add_experience` (split lines, strip leading `•–-` characters).
- Produces: routes `GET /profile/experience/{index}`, `GET /profile/experience/{index}/edit`, `PUT /profile/experience/{index}`, mirroring Task 1's pattern for Task 3.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_routes.py`:

```python
def test_edit_experience_form(client, mock_profile_path):
    response = client.get("/profile/experience/0/edit")
    assert response.status_code == 200
    assert 'value="Tech Corp"' in response.text
    assert "Built REST API serving 10k requests/day using Python and FastAPI" in response.text


def test_update_experience(client, mock_profile_path):
    import json
    response = client.put("/profile/experience/0", data={
        "company": "Updated Corp",
        "title": "Senior Engineer",
        "start": "2019",
        "end": "Present",
        "location": "Remote",
        "accomplishments_raw": "Shipped v2 of the platform\nMentored 2 engineers",
    })
    assert response.status_code == 200
    assert "Updated Corp" in response.text
    saved = json.loads(mock_profile_path.read_text())
    assert saved["experience"][0]["company"] == "Updated Corp"
    assert saved["experience"][0]["accomplishments"] == [
        "Shipped v2 of the platform",
        "Mentored 2 engineers",
    ]


def test_update_experience_not_found(client, mock_profile_path):
    response = client.put("/profile/experience/99", data={
        "company": "X", "title": "Y", "start": "", "end": "",
        "location": "", "accomplishments_raw": "",
    })
    assert response.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_routes.py -k experience -v`
Expected: `test_edit_experience_form` and `test_update_experience` FAIL (routes don't exist yet).

- [ ] **Step 3: Extract the entry partial**

Create `app/templates/partials/experience_entry.html`:

```html
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
  <div style="margin-top:8px">
    <button class="btn btn-sm"
            hx-get="/profile/experience/{{ index }}/edit"
            hx-target="closest .entry"
            hx-swap="outerHTML">Edit</button>
    <button class="btn btn-sm btn-danger"
            hx-delete="/profile/experience/{{ index }}"
            hx-target="#experience-list"
            hx-swap="innerHTML"
            hx-confirm="Delete this experience entry?">Delete</button>
  </div>
</div>
```

- [ ] **Step 4: Create the edit-form partial**

Create `app/templates/partials/experience_entry_edit.html`:

```html
<div class="entry">
  <form hx-put="/profile/experience/{{ index }}"
        hx-target="closest .entry"
        hx-swap="outerHTML">
    <div class="form-grid">
      <label>Company
        <input type="text" name="company" required value="{{ exp.company }}">
      </label>
      <label>Job Title
        <input type="text" name="title" required value="{{ exp.title }}">
      </label>
      <label>Start
        <input type="text" name="start" value="{{ exp.start }}">
      </label>
      <label>End
        <input type="text" name="end" value="{{ exp.end }}">
      </label>
      <label>Location
        <input type="text" name="location" value="{{ exp.location }}">
      </label>
    </div>
    <label>
      Accomplishments
      <small style="font-weight:400;color:#888"> — one per line</small>
      <textarea name="accomplishments_raw" rows="6">{{ exp.accomplishments|join("\n") }}</textarea>
    </label>
    <div style="margin-top:8px">
      <button type="submit" class="btn btn-sm btn-primary">Save</button>
      <button type="button" class="btn btn-sm"
              hx-get="/profile/experience/{{ index }}"
              hx-target="closest .entry"
              hx-swap="outerHTML">Cancel</button>
    </div>
  </form>
</div>
```

- [ ] **Step 5: Point the list partial at the entry partial**

Replace the full contents of `app/templates/partials/experience_list.html` with:

```html
{% for exp in experience %}
{% set index = loop.index0 %}
{% include "partials/experience_entry.html" %}
{% else %}
<p class="empty-state">No experience entries yet.</p>
{% endfor %}
```

- [ ] **Step 6: Add the three routes**

In `app/main.py`, insert immediately after the existing `delete_experience` function, right before `@app.post("/profile/projects", ...)`:

```python
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
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest tests/test_routes.py -k experience -v`
Expected: all PASS.

Run full suite: `pytest -v`
Expected: all PASS.

- [ ] **Step 8: Commit**

```bash
git add app/main.py app/templates/partials/experience_list.html app/templates/partials/experience_entry.html app/templates/partials/experience_entry_edit.html tests/test_routes.py
git commit -m "feat: add inline editing for experience entries"
```

---

### Task 3: Projects entry editing

**Files:**
- Modify: `app/main.py` (insert new routes after `delete_project`, currently ending around line 186, right before `@app.get("/healthz")`)
- Modify: `app/templates/partials/projects_list.html` (replace loop body with an include)
- Create: `app/templates/partials/projects_entry.html`
- Create: `app/templates/partials/projects_entry_edit.html`
- Test: `tests/test_routes.py`

**Interfaces:**
- Consumes: same `load_profile()` / `save_profile()` as Tasks 1–2; the `tech_stack_raw` (comma-split) and `highlights_raw` (newline-split, bullet-stripped) parsing already used in `add_project`.
- Produces: routes `GET /profile/projects/{index}`, `GET /profile/projects/{index}/edit`, `PUT /profile/projects/{index}`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_routes.py`:

```python
def test_edit_project_form(client, mock_profile_path):
    response = client.get("/profile/projects/0/edit")
    assert response.status_code == 200
    assert 'value="CLI Tool"' in response.text
    assert 'value="Python, Click"' in response.text


def test_update_project(client, mock_profile_path):
    import json
    response = client.put("/profile/projects/0", data={
        "name": "Updated Tool",
        "description": "Now does more",
        "tech_stack_raw": "Python, Click, Rich",
        "highlights_raw": "1000 stars\nFeatured on HN",
        "url": "github.com/janesmith/updated-tool",
    })
    assert response.status_code == 200
    assert "Updated Tool" in response.text
    saved = json.loads(mock_profile_path.read_text())
    assert saved["projects"][0]["name"] == "Updated Tool"
    assert saved["projects"][0]["tech_stack"] == ["Python", "Click", "Rich"]
    assert saved["projects"][0]["highlights"] == ["1000 stars", "Featured on HN"]


def test_update_project_not_found(client, mock_profile_path):
    response = client.put("/profile/projects/99", data={
        "name": "X", "description": "", "tech_stack_raw": "",
        "highlights_raw": "", "url": "",
    })
    assert response.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_routes.py -k project -v`
Expected: `test_edit_project_form` and `test_update_project` FAIL (routes don't exist yet).

- [ ] **Step 3: Extract the entry partial**

Create `app/templates/partials/projects_entry.html`:

```html
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
  <div style="margin-top:8px">
    <button class="btn btn-sm"
            hx-get="/profile/projects/{{ index }}/edit"
            hx-target="closest .entry"
            hx-swap="outerHTML">Edit</button>
    <button class="btn btn-sm btn-danger"
            hx-delete="/profile/projects/{{ index }}"
            hx-target="#projects-list"
            hx-swap="innerHTML"
            hx-confirm="Delete this project?">Delete</button>
  </div>
</div>
```

- [ ] **Step 4: Create the edit-form partial**

Create `app/templates/partials/projects_entry_edit.html`:

```html
<div class="entry">
  <form hx-put="/profile/projects/{{ index }}"
        hx-target="closest .entry"
        hx-swap="outerHTML">
    <div class="form-grid">
      <label>Project Name
        <input type="text" name="name" required value="{{ proj.name }}">
      </label>
      <label>URL
        <input type="text" name="url" value="{{ proj.url }}">
      </label>
      <label style="grid-column:1/-1">Tech Stack
        <small style="font-weight:400;color:#888"> (comma-separated)</small>
        <input type="text" name="tech_stack_raw" value="{{ proj.tech_stack|join(', ') }}">
      </label>
    </div>
    <label>Description
      <textarea name="description" rows="2">{{ proj.description }}</textarea>
    </label>
    <label>
      Highlights
      <small style="font-weight:400;color:#888"> — one per line</small>
      <textarea name="highlights_raw" rows="3">{{ proj.highlights|join("\n") }}</textarea>
    </label>
    <div style="margin-top:8px">
      <button type="submit" class="btn btn-sm btn-primary">Save</button>
      <button type="button" class="btn btn-sm"
              hx-get="/profile/projects/{{ index }}"
              hx-target="closest .entry"
              hx-swap="outerHTML">Cancel</button>
    </div>
  </form>
</div>
```

- [ ] **Step 5: Point the list partial at the entry partial**

Replace the full contents of `app/templates/partials/projects_list.html` with:

```html
{% for proj in projects %}
{% set index = loop.index0 %}
{% include "partials/projects_entry.html" %}
{% else %}
<p class="empty-state">No projects yet.</p>
{% endfor %}
```

- [ ] **Step 6: Add the three routes**

In `app/main.py`, insert immediately after the existing `delete_project` function, right before `@app.get("/healthz")`:

```python
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
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest tests/test_routes.py -k project -v`
Expected: all PASS.

Run full suite: `pytest -v`
Expected: all PASS.

- [ ] **Step 8: Commit**

```bash
git add app/main.py app/templates/partials/projects_list.html app/templates/partials/projects_entry.html app/templates/partials/projects_entry_edit.html tests/test_routes.py
git commit -m "feat: add inline editing for project entries"
```
