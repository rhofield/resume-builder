import json
import re
import subprocess


def build_prompt(profile: dict, job_description: str, template_html: str) -> str:
    return f"""You are an expert resume writer. Produce a tailored resume as a complete HTML document.

USER PROFILE (JSON):
{json.dumps(profile, indent=2)}

JOB DESCRIPTION:
{job_description}

RESUME TEMPLATE (HTML with placeholder comments):
{template_html}

Instructions:
- Select only the most relevant experience entries and projects for this specific role
- Rewrite accomplishment bullet points to mirror the job's language and keywords exactly
- Never invent facts — only use information present in the profile
- Replace every placeholder comment in the template with real HTML content
- For <!-- SKILLS -->, infer skills from the selected experience + job description keywords
- Return ONLY the complete HTML document — no explanation, no markdown fences, no commentary
- The response must begin with <!DOCTYPE html> or <html"""


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
