import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


STATIC_LLM_PROVIDERS = {
    "claude": {
        "label": "Claude Code",
        "models": {
            "sonnet": "Sonnet",
            "opus": "Opus",
            "haiku": "Haiku",
        },
    },
}

FALLBACK_CODEX_MODELS = {
    "gpt-5.5": "GPT-5.5",
}

# Two-page resumes produce substantially more output than the old one-page target,
# so generation regularly runs 90–120s. Give the CLI real headroom above that.
GENERATION_TIMEOUT_SECONDS = 300


def get_default_provider() -> str:
    return "claude"


def _source_codex_home() -> Path:
    source_home = Path(os.environ.get("HOME", "~")).expanduser()
    return Path(os.environ.get("CODEX_HOME", str(source_home / ".codex"))).expanduser()


def _load_codex_models() -> dict[str, str]:
    models: dict[str, str] = {}
    codex_home = _source_codex_home()
    models_cache_path = codex_home / "models_cache.json"
    if models_cache_path.exists():
        try:
            payload = json.loads(models_cache_path.read_text())
            for model in payload.get("models", []):
                slug = model.get("slug")
                display_name = model.get("display_name")
                visibility = model.get("visibility")
                if slug and display_name and visibility == "list":
                    models[slug] = display_name
        except (json.JSONDecodeError, OSError):
            pass

    config_path = codex_home / "config.toml"
    if config_path.exists():
        try:
            for line in config_path.read_text().splitlines():
                match = re.match(r'^model\s*=\s*"([^"]+)"\s*$', line.strip())
                if match:
                    configured_model = match.group(1)
                    models.setdefault(
                        configured_model,
                        configured_model.replace("-", " ").upper(),
                    )
                    break
        except OSError:
            pass

    return models or FALLBACK_CODEX_MODELS.copy()


def get_llm_providers() -> dict[str, dict]:
    providers = {
        provider_id: {
            "label": provider["label"],
            "models": dict(provider["models"]),
        }
        for provider_id, provider in STATIC_LLM_PROVIDERS.items()
    }
    providers["codex"] = {
        "label": "Codex",
        "models": _load_codex_models(),
    }
    return providers


def get_default_model(provider: str) -> str:
    providers = get_llm_providers()
    return next(iter(providers[provider]["models"]))


def is_valid_provider_model(provider: str, model: str) -> bool:
    providers = get_llm_providers()
    return provider in providers and model in providers[provider]["models"]


def build_prompt(profile: dict, job_description: str, template_html: str) -> str:
    return f"""You are a senior resume strategist and professional resume writer. You have placed
candidates at top companies and you understand both how human recruiters skim resumes in
under 10 seconds and how automated Applicant Tracking Systems (ATS) parse and rank them.
Your job: turn the candidate's profile into a sharply tailored, truthful resume that fits within a
STRICT MAXIMUM of two A4 pages for the specific role below, rendered as a complete HTML document
built from the provided template.

<candidate_profile>
{json.dumps(profile, indent=2)}
</candidate_profile>

<job_description>
{job_description}
</job_description>

<resume_template>
{template_html}
</resume_template>

Before writing any HTML, work through this plan silently (do NOT include it in your output):
1. Extract the role's top requirements from the job description: the core responsibilities,
   must-have skills, seniority level, and the exact keywords/technologies it repeats.
2. Map each requirement to concrete evidence in the candidate's profile. Note which experience
   entries and projects are direct hits versus weak or irrelevant. Be generous about what
   counts as relevant: a project that demonstrates a required technology, technique, or domain is a hit
   even if it was personal or unpaid.
3. Decide what to include and in what order so the strongest, most relevant evidence appears first,
   then cut the least relevant material until everything fits within two A4 pages. Two pages is a hard
   ceiling, not a target to fill.

Then produce the resume by replacing every placeholder comment in the template with real HTML,
following these rules:

LENGTH & COVERAGE
- Two A4 pages is a STRICT MAXIMUM. The finished resume must NEVER exceed two pages. If the content
  would spill onto a third page, cut the least relevant projects and the weakest bullets until it fits.
  Fitting within two pages takes priority over including every piece of evidence.
- Within that ceiling, aim for a substantial, well-packed resume — but a tight one-to-one-and-a-half
  page resume is fine and preferable to overflow or invented filler.

SELECTION & ORDERING
- Prioritise the experience entries and projects that provide the strongest evidence for this role.
  Because two pages is a hard ceiling, be willing to drop or heavily shorten weaker entries so the most
  relevant proof fits comfortably. Relevance and fit come before completeness.
- Order experience by relevance and recency, most compelling first. Lead each entry with its strongest,
  most role-relevant bullet.
- Any experience entry marked "always_include": true is one the candidate considers a cornerstone of
  their history that they want featured. Keep these near the top and include them unless they are
  genuinely irrelevant to the role.
- Aim for 4–6 bullets on the most relevant roles and 2–4 on others.

PROJECTS (select the strongest that fit)
- The candidate may have a large project portfolio. Select the projects that best demonstrate the
  skills, technologies, techniques, or domains the job cares about — typically the 3–5 strongest
  matches. Do NOT try to include every project; choose the ones that fit within the two-page ceiling.
- Rank projects by relevance to the role and lead with the most impressive, most on-target one.
- Any project marked "always_include": true is one the candidate considers flagship work they want
  featured. Rank these at the very top of the projects section and include them unless they are
  genuinely irrelevant to the role.
- For each selected project, lead with a one-line description of what it is and why it is impressive
  (scale, novelty, shipped/published status, real users), then 2–4 highlight bullets rewritten in the
  same action-verb + concrete-impact style as experience. Name the specific technologies and techniques
  from the job's vocabulary wherever they genuinely apply.
- Only omit the projects section entirely if NO project relates to the role.

REWRITING ACCOMPLISHMENTS
- Rewrite every bullet in the form: strong action verb + what you did + quantified impact.
  Preserve the real metrics already in the profile (counts, percentages, dollar/time figures) —
  these are the resume's most persuasive elements; never drop or weaken them.
- Naturally incorporate the job's vocabulary and technologies WHERE THEY GENUINELY MATCH the
  candidate's experience. Reuse the job's exact terms for skills the candidate actually has.
- Write in tight, recruiter-friendly phrasing: no first-person pronouns ("I", "my"), no "responsible
  for", no filler. Lead with the verb. Vary verbs across bullets.
- Make every bullet concrete and technically specific: name the technology, the scale, and the outcome.
  Prefer "Built X using Y, achieving Z" over vague "Worked on X". Avoid generic phrasing that could
  describe any engineer — surface the detail in the profile that makes this candidate's work distinctive.

SOUND HUMAN, NOT AI-GENERATED
- Recruiters and hiring managers increasingly recognise and distrust AI-written resumes. Write like an
  experienced human writer, and avoid the language patterns that mark text as machine-generated.
- Do NOT use inflated-importance or puffery phrasing: no "stands as", "serves as", "is a testament to",
  "plays a pivotal/vital/crucial/key role", "underscores", "highlights", "showcases", "spearheaded"
  (unless literally true), "instrumental in", "marks a turning point", "leaves a lasting impact".
- Ban this AI-vocabulary cluster: leverage, utilize (use "use"), delve, robust, seamless, seamlessly,
  streamline, foster, cultivate, harness, elevate, empower, unlock, drive/driving (as filler),
  meticulous, intricate, tapestry, landscape, realm, myriad, plethora, holistic, synergy, cutting-edge,
  state-of-the-art, best-in-class, world-class, game-changing, next-level, deep dive, comprehensive
  (as filler), innovative/innovate (as filler), passionate, dynamic, results-driven, detail-oriented.
- No "not only X but also Y" constructions and no mechanical rule-of-three lists ("designed, developed,
  and deployed") used just to pad a bullet. Use a list only when all items carry real, distinct weight.
- Do not editorialise with adverbs like "notably", "significantly", "seamlessly", "successfully",
  "effectively" — let the concrete metric do the work instead.
- Prefer plain verbs and the verb "is/was" over fancy copula-avoidance ("serves as", "represents").
  Write "Built X" not "Engineered a robust solution that serves as X". Short, direct, specific.
- Use straight quotes and standard hyphens/en-dashes in date ranges; do not litter bullets with em-dashes.
- The test: every bullet should read like something a sharp person wrote about their own work, naming
  real specifics — not like generic marketing copy that could describe anyone.

TRUTHFULNESS (non-negotiable)
- Use ONLY facts present in the candidate profile. Never invent employers, dates, metrics, titles,
  technologies, or outcomes. Do not claim a skill the profile gives no evidence for, even if the job
  asks for it. Reframing and emphasizing real facts is encouraged; fabricating is forbidden.

NO SKILLS SECTION
- Do NOT produce a standalone Skills section. The candidate's skills are conveyed implicitly through
  the experience and project bullets, which name the specific technologies and techniques in context.
  Leave the template's SKILLS placeholder empty (remove it) rather than inventing a skills list.

FORMATTING & ATS
- Replace EVERY placeholder comment in the template; leave none behind. Keep the template's existing
  CSS, class names, and structure intact — only fill in content.
- Keep standard, ATS-readable section headings. Don't bury text in images or unusual markup.
- Gracefully omit any empty or missing profile fields (e.g. a blank phone). Never emit dangling
  separators like " · · " or empty parentheses/brackets where data is absent.
- Format dates and locations consistently across all entries.

OUTPUT FORMAT (strict)
- Return ONLY the complete HTML document. No explanation, no markdown code fences, no commentary
  before or after.
- Your response must begin with <!DOCTYPE html> or <html and end with </html>."""


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


def _codex_runtime_dirs() -> tuple[Path, Path]:
    runtime_root = Path(__file__).resolve().parent.parent
    codex_home = runtime_root / ".codex-home"
    user_home = runtime_root / ".codex-user-home"
    codex_home.mkdir(parents=True, exist_ok=True)
    user_home.mkdir(parents=True, exist_ok=True)
    source_codex_home = _source_codex_home()
    for filename in ("auth.json", "config.toml"):
        source = source_codex_home / filename
        target = codex_home / filename
        if source.exists() and not target.exists():
            shutil.copy2(source, target)
    return codex_home, user_home


def _clean_codex_error(stderr: str) -> str:
    lines = [line.rstrip() for line in stderr.splitlines()]
    filtered = []
    skipping_banner = False
    for line in lines:
        if line.startswith("OpenAI Codex v"):
            skipping_banner = True
            continue
        if skipping_banner:
            if line.strip() == "--------":
                skipping_banner = False
            continue
        if line.startswith("workdir:") or line.startswith("model:") or line.startswith("provider:"):
            continue
        if line.startswith("approval:") or line.startswith("sandbox:"):
            continue
        if line.startswith("reasoning effort:") or line.startswith("reasoning summaries:"):
            continue
        if line.startswith("session id:"):
            continue
        if line.startswith("user"):
            continue
        filtered.append(line)
    cleaned = "\n".join(line for line in filtered if line.strip()).strip()
    return cleaned or stderr.strip()


def _run_claude(prompt: str, model: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["claude", "--model", model, "--print"],
        input=prompt,
        capture_output=True,
        text=True,
        timeout=GENERATION_TIMEOUT_SECONDS,
    )


def _run_codex(prompt: str, model: str) -> subprocess.CompletedProcess:
    with tempfile.NamedTemporaryFile(suffix=".txt") as output_file:
        codex_home, user_home = _codex_runtime_dirs()
        env = os.environ.copy()
        env["CODEX_HOME"] = str(codex_home)
        env["HOME"] = str(user_home)
        result = subprocess.run(
            [
                "codex",
                "exec",
                "--model",
                model,
                "--color",
                "never",
                "--output-last-message",
                output_file.name,
                "-",
            ],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=GENERATION_TIMEOUT_SECONDS,
            env=env,
        )
        stdout = Path(output_file.name).read_text() if result.returncode == 0 else result.stdout
        return subprocess.CompletedProcess(
            args=result.args,
            returncode=result.returncode,
            stdout=stdout,
            stderr=result.stderr,
        )


def generate_resume(
    profile: dict,
    job_description: str,
    template_html: str,
    provider: str = "claude",
    model: str | None = None,
) -> tuple[str, str]:
    """Returns (html, error). html is empty on failure; error is empty on success."""
    providers = get_llm_providers()
    if provider not in providers:
        return "", f"Provider '{provider}' not recognized."
    if model is None:
        model = get_default_model(provider)
    if model not in providers[provider]["models"]:
        return "", f"Model '{model}' is not valid for provider '{provider}'."

    prompt = build_prompt(profile, job_description, template_html)
    cli_name = "claude" if provider == "claude" else "codex"
    try:
        runner = _run_claude if provider == "claude" else _run_codex
        result = runner(prompt, model)
        if result.returncode != 0:
            stderr = _clean_codex_error(result.stderr) if provider == "codex" else result.stderr
            return "", f"{cli_name} exited with code {result.returncode}:\n{stderr}"
        html = extract_html(result.stdout)
        if not html:
            return "", result.stdout
        return html, ""
    except subprocess.TimeoutExpired:
        return "", (
            f"Generation timed out after {GENERATION_TIMEOUT_SECONDS} seconds. "
            "Please try again."
        )
    except FileNotFoundError:
        return "", f"{cli_name} CLI not found. Make sure it is installed and on your PATH."
