# Model Selection for Headless Claude Generation

## Problem

`generate_resume()` (`app/generator.py`) always shells out to `claude -p` with
no model flag, so resume generation silently uses whatever the `claude` CLI
defaults to. There's no way for the user to pick a faster/cheaper model
(haiku) or a higher-quality one (opus) for a given generation.

## Design

Add a model selector to the existing Generate form. It's a per-request
choice, not a global setting — no persistence across page loads.

### 1. Form (`app/templates/generate.html`)

Add a `<select name="model">` field above or beside the template grid:

```html
<label>Model
  <select name="model">
    <option value="sonnet" selected>Sonnet</option>
    <option value="opus">Opus</option>
    <option value="haiku">Haiku</option>
  </select>
</label>
```

Default selection is `sonnet`. No JS, no localStorage — matches the existing
plain HTML form pattern used for `template_id`.

### 2. Route (`app/main.py`, `run_generate`)

- Add `model: str = Form("sonnet")` to the handler signature.
- Validate against the allow-list `{"sonnet", "opus", "haiku"}` using the
  same pattern as the existing `template_id` validation (lines 218-226):
  return `partials/generate_result.html` with an error if invalid.
- Pass `model` through to `generate_resume(profile, job_description,
  template_html, model)`.

### 3. Generator (`app/generator.py`, `generate_resume`)

- Add a `model: str = "sonnet"` parameter.
- Change the subprocess invocation from:
  ```python
  ["claude", "-p"]
  ```
  to:
  ```python
  ["claude", "-m", model, "-p"]
  ```
- No other behavior changes — error handling, timeout, and HTML extraction
  stay the same.

## Validation

The allow-list is checked server-side in `run_generate` even though the
`<select>` already constrains the UI, since the value comes in as a plain
form field and could be forged. This mirrors the existing `template_id`
check.

## Out of scope

- Persisting the last-chosen model (cookie/localStorage) — explicitly
  rejected in favor of simplicity.
- Hardcoded full model IDs (e.g. `claude-sonnet-4-6`) — using the CLI's
  built-in short aliases instead, so this code doesn't need updating when
  Anthropic ships new model snapshots.
- A separate global settings page — model choice lives entirely in the
  per-generation form.

## Testing

- `tests/test_generator.py`: assert `generate_resume(..., model="opus")`
  invokes `subprocess.run` with `["claude", "-m", "opus", "-p"]` in the args.
- `tests/test_routes.py`: assert posting `/generate` with an invalid `model`
  value returns the error partial without calling `generate_resume`.
