# Profile Entry Editing — Design

## Problem

The Education, Experience, and Projects tabs on the Profile page only support adding and deleting entries (`app/main.py`, `partials/{education,experience,projects}_list.html`). There is no way to fix a typo or update a detail without deleting the entry and re-adding it from scratch.

## Goals

- Let the user edit an existing education, experience, or project entry in place.
- Follow the existing HTMX swap conventions already used for add/delete rather than introducing a new UI pattern.

## Non-goals

- Reordering entries.
- Stable entry IDs (entries remain positionally indexed, matching current delete behavior).
- A generic/shared "entry" abstraction across the three resource types — the codebase already triplicates add/delete logic per resource, so editing follows the same per-resource style.

## Design

### UI behavior

Each entry currently renders with a single **Delete** button. It gains an **Edit** button next to it.

- **Edit** (`hx-get .../{index}/edit`, target `closest .entry`, swap `outerHTML`) replaces that single entry's display with a pre-filled form.
- The edit form has **Save** (`hx-put .../{index}`) and **Cancel** (`hx-get .../{index}`) buttons, both targeting `closest .entry` with `outerHTML` swap.
- Save persists changes and swaps back to the read-only entry view. Cancel discards changes and swaps back to the read-only entry view without saving.
- Add and Delete are unchanged — they still re-render the whole list (`#education-list` / `#experience-list` / `#projects-list`).

### Templates

For each resource (education, experience, projects), the existing list partial's loop body is extracted into a new entry partial, included from the loop:

- `partials/{resource}_entry.html` — read-only entry markup (existing markup + new Edit button). Used both inside the list partial's loop and as the response body for view/save requests.
- `partials/{resource}_entry_edit.html` — new. Same fields as the existing "Add Entry" form, pre-filled with the entry's current values.

The list partial sets `index` from `loop.index0` before including the entry partial, so the entry partial can build its own `hx-get`/`hx-put`/`hx-delete` URLs without depending on Jinja's `loop` object being in scope (it won't be, once rendered standalone for view/edit/save responses).

### Routes

Three new routes per resource (nine total), added alongside the existing `POST /profile/{resource}` and `DELETE /profile/{resource}/{index}` in `app/main.py`:

- `GET /profile/{resource}/{index}` — returns the read-only entry partial. Used by the Cancel button.
- `GET /profile/{resource}/{index}/edit` — returns the pre-filled edit-form partial.
- `PUT /profile/{resource}/{index}` — validates form fields (same `Form(...)` signature as the existing add route), overwrites `profile[resource][index]`, saves, and returns the read-only entry partial for that index.

### Data transformations

Experience's `accomplishments_raw` and Projects' `tech_stack_raw` / `highlights_raw` are parsed into lists on add (newline-split / comma-split). The edit form pre-fills these `_raw` fields by re-joining the stored list (`"\n".join(...)` or `", ".join(...)`) so the textarea/input shows editable raw text consistent with the Add form's input format.

### Error handling

`index` is a positional list index, same as today's delete route. If a request arrives for an `index` that's no longer valid (e.g., another tab deleted that entry first), the view/edit/PUT routes return `404 Not Found` via `HTTPException` rather than crashing on an `IndexError`. This is a new behavior — the existing delete route currently no-ops silently on an out-of-range index; that's left unchanged since deletion is idempotent by nature and the design doesn't need to touch it.

## Testing

- Existing tests in `tests/test_routes.py` / `tests/test_profile.py` cover add/delete; extend with cases for:
  - `GET /profile/{resource}/{index}/edit` returns the pre-filled form.
  - `PUT /profile/{resource}/{index}` updates the stored entry and returns the updated read view.
  - `GET`/`PUT` with an out-of-range index returns 404.
