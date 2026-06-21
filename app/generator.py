import json
import re
import subprocess


def build_prompt(profile: dict, job_description: str, template_html: str) -> str:
    return f"""You are a senior resume strategist and professional resume writer. You have placed
candidates at top companies and you understand both how human recruiters skim resumes in
under 10 seconds and how automated Applicant Tracking Systems (ATS) parse and rank them.
Your job: turn the candidate's profile into a sharply tailored, truthful, one-page resume for
the specific role below, rendered as a complete HTML document built from the provided template.

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
   entries, projects, and skills are direct hits versus weak or irrelevant.
3. Decide what to include and in what order so the strongest, most relevant evidence appears first.

Then produce the resume by replacing every placeholder comment in the template with real HTML,
following these rules:

SELECTION & ORDERING
- Include only experience entries and projects that support this specific role. Drop or shorten
  weakly relevant ones. A focused one-page resume beats an exhaustive one.
- Order experience by relevance and recency, most compelling first. Lead each entry with its
  strongest, most role-relevant bullet.
- Aim for 3–5 bullets on the most relevant role and 2–3 on others. Keep the whole resume to one
  page of A4.
- Omit the projects section entirely if no project is relevant to this role.

REWRITING ACCOMPLISHMENTS
- Rewrite every bullet in the form: strong action verb + what you did + quantified impact.
  Preserve the real metrics already in the profile (counts, percentages, dollar/time figures) —
  these are the resume's most persuasive elements; never drop or weaken them.
- Naturally incorporate the job's vocabulary and technologies WHERE THEY GENUINELY MATCH the
  candidate's experience. Reuse the job's exact terms for skills the candidate actually has.
- Write in tight, recruiter-friendly phrasing: no first-person pronouns ("I", "my"), no "responsible
  for", no filler. Lead with the verb. Vary verbs across bullets.

TRUTHFULNESS (non-negotiable)
- Use ONLY facts present in the candidate profile. Never invent employers, dates, metrics, titles,
  technologies, or outcomes. Do not claim a skill the profile gives no evidence for, even if the job
  asks for it. Reframing and emphasizing real facts is encouraged; fabricating is forbidden.

SKILLS SECTION
- Derive skills from the candidate's actual experience, projects, and listed tech stacks, prioritizing
  those the job description mentions. Group related skills (e.g. Languages, Frameworks, Tools/Cloud)
  for fast scanning rather than one long undifferentiated list. Do not list skills with no basis in
  the profile.

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
