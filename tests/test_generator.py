import json
import subprocess
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from app.generator import build_prompt, extract_html, generate_resume, get_llm_providers


def test_build_prompt_contains_all_three_inputs(sample_profile):
    prompt = build_prompt(sample_profile, "Senior Python Engineer at Acme", "<html><!-- STATIC --></html>")
    assert "Jane Smith" in prompt                   # profile present
    assert "Senior Python Engineer at Acme" in prompt  # job description present
    assert "<!-- STATIC -->" in prompt              # template present


def test_build_prompt_includes_accomplishments(sample_profile):
    prompt = build_prompt(sample_profile, "job", "<html></html>")
    assert "10k requests/day" in prompt


def test_build_prompt_instructs_on_always_include(sample_profile):
    prompt = build_prompt(sample_profile, "job", "<html></html>")
    assert "always_include" in prompt


def test_build_prompt_carries_always_include_flag(sample_profile):
    sample_profile["projects"][0]["always_include"] = True
    prompt = build_prompt(sample_profile, "job", "<html></html>")
    assert '"always_include": true' in prompt


def test_build_prompt_carries_experience_always_include_flag(sample_profile):
    sample_profile["experience"][0]["always_include"] = True
    prompt = build_prompt(sample_profile, "job", "<html></html>")
    assert '"always_include": true' in prompt


def test_build_prompt_enforces_two_page_ceiling(sample_profile):
    prompt = build_prompt(sample_profile, "job", "<html></html>")
    assert "STRICT MAXIMUM" in prompt
    assert "never exceed two pages" in prompt.lower()


def test_build_prompt_suppresses_skills_section(sample_profile):
    prompt = build_prompt(sample_profile, "job", "<html></html>")
    assert "NO SKILLS SECTION" in prompt
    assert "Do NOT produce a standalone Skills section" in prompt


def test_build_prompt_avoids_ai_voice(sample_profile):
    prompt = build_prompt(sample_profile, "job", "<html></html>")
    assert "SOUND HUMAN, NOT AI-GENERATED" in prompt
    # A few of the specific AI tells the prompt must instruct against.
    for banned in ("leverage", "is a testament to", "not only X but also Y"):
        assert banned in prompt


def test_templates_have_no_skills_placeholder():
    from pathlib import Path
    for tpl in Path("resume_templates").glob("*.html"):
        assert "SKILLS:" not in tpl.read_text(), f"{tpl.name} still has a SKILLS placeholder"


def test_extract_html_strips_markdown_fences():
    raw = "```html\n<!DOCTYPE html><html><body>Hello</body></html>\n```"
    result = extract_html(raw)
    assert result.startswith("<!DOCTYPE html>")
    assert "```" not in result


def test_extract_html_passthrough_clean():
    raw = "<!DOCTYPE html><html><body>Hello</body></html>"
    assert extract_html(raw) == raw


def test_extract_html_strips_preamble():
    raw = "Sure! Here is your resume:\n\n<!DOCTYPE html><html><body></body></html>"
    result = extract_html(raw)
    assert result.startswith("<!DOCTYPE html>")


def test_extract_html_returns_empty_for_no_html():
    assert extract_html("Here is some plain text with no HTML.") == ""


def test_extract_html_handles_lowercase_doctype():
    raw = "<!doctype html><html><body></body></html>"
    result = extract_html(raw)
    assert result.startswith("<!doctype html>")


def test_generate_resume_success(sample_profile):
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "<!DOCTYPE html><html><body>Resume content</body></html>"
    mock_result.stderr = ""
    with patch("app.generator.subprocess.run", return_value=mock_result):
        html, error = generate_resume(sample_profile, "Python dev role", "<html><!-- STATIC --></html>")
    assert html.startswith("<!DOCTYPE html>")
    assert error == ""


def test_generate_resume_timeout(sample_profile):
    with patch(
        "app.generator.subprocess.run",
        side_effect=subprocess.TimeoutExpired("claude", 120),
    ):
        html, error = generate_resume(sample_profile, "Python dev role", "<html></html>")
    assert html == ""
    assert "timed out" in error.lower()


def test_generate_resume_claude_not_found(sample_profile):
    with patch("app.generator.subprocess.run", side_effect=FileNotFoundError()):
        html, error = generate_resume(sample_profile, "Python dev role", "<html></html>")
    assert html == ""
    assert "not found" in error.lower()


def test_generate_resume_nonzero_exit(sample_profile):
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""
    mock_result.stderr = "authentication required"
    with patch("app.generator.subprocess.run", return_value=mock_result):
        html, error = generate_resume(sample_profile, "Python dev role", "<html></html>")
    assert html == ""
    assert "authentication required" in error


def test_generate_resume_non_html_output(sample_profile):
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "I'm sorry, I cannot complete this request."
    mock_result.stderr = ""
    with patch("app.generator.subprocess.run", return_value=mock_result):
        html, error = generate_resume(sample_profile, "Python dev role", "<html></html>")
    assert html == ""
    assert "I'm sorry" in error


def test_generate_resume_passes_model_flag(sample_profile):
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "<!DOCTYPE html><html><body>Resume content</body></html>"
    mock_result.stderr = ""
    with patch("app.generator.subprocess.run", return_value=mock_result) as mock_run:
        generate_resume(
            sample_profile,
            "Python dev role",
            "<html></html>",
            provider="claude",
            model="opus",
        )
    args = mock_run.call_args[0][0]
    assert args == ["claude", "--model", "opus", "--print"]


def test_generate_resume_defaults_to_sonnet(sample_profile):
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "<!DOCTYPE html><html><body>Resume content</body></html>"
    mock_result.stderr = ""
    with patch("app.generator.subprocess.run", return_value=mock_result) as mock_run:
        generate_resume(sample_profile, "Python dev role", "<html></html>")
    args = mock_run.call_args[0][0]
    assert args == ["claude", "--model", "sonnet", "--print"]


def test_generate_resume_codex_exec_uses_output_file(sample_profile):
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "transient logs"
    mock_result.stderr = ""

    def fake_run(*args, **kwargs):
        output_path = args[0][7]
        with open(output_path, "w") as f:
            f.write("<!DOCTYPE html><html><body>Resume content</body></html>")
        return mock_result

    with patch("app.generator.subprocess.run", side_effect=fake_run) as mock_run:
        html, error = generate_resume(
            sample_profile,
            "Python dev role",
            "<html></html>",
            provider="codex",
            model="gpt-5.5",
        )

    args = mock_run.call_args[0][0]
    assert args[:8] == [
        "codex",
        "exec",
        "--model",
        "gpt-5.5",
        "--color",
        "never",
        "--output-last-message",
        args[7],
    ]
    assert html.startswith("<!DOCTYPE html>")
    assert error == ""


def test_generate_resume_rejects_invalid_provider_model_pair(sample_profile):
    html, error = generate_resume(
        sample_profile,
        "Python dev role",
        "<html></html>",
        provider="codex",
        model="opus",
    )
    assert html == ""
    assert "not valid" in error


def test_generate_resume_codex_sets_writable_home(sample_profile):
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "transient logs"
    mock_result.stderr = ""

    def fake_run(*args, **kwargs):
        output_path = args[0][7]
        with open(output_path, "w") as f:
            f.write("<!DOCTYPE html><html><body>Resume content</body></html>")
        env = kwargs["env"]
        assert env["CODEX_HOME"].endswith(".codex-home")
        assert env["HOME"].endswith(".codex-user-home")
        return mock_result

    with patch("app.generator.subprocess.run", side_effect=fake_run):
        html, error = generate_resume(
            sample_profile,
            "Python dev role",
            "<html></html>",
            provider="codex",
            model="gpt-5.5",
        )

    assert html.startswith("<!DOCTYPE html>")
    assert error == ""


def test_generate_resume_codex_cleans_banner_from_error(sample_profile):
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""
    mock_result.stderr = """OpenAI Codex v0.143.0
--------
workdir: /tmp
model: gpt-5
provider: openai
approval: never
sandbox: workspace-write
reasoning effort: medium
reasoning summaries: none
session id: abc
--------
user
Prompt

Error: failed to initialize in-process app-server client: Read-only file system (os error 30)
"""
    with patch("app.generator.subprocess.run", return_value=mock_result):
        html, error = generate_resume(
            sample_profile,
            "Python dev role",
            "<html></html>",
            provider="codex",
            model="gpt-5.5",
        )

    assert html == ""
    assert "Read-only file system" in error
    assert "OpenAI Codex" not in error


def test_generate_resume_codex_seeds_auth_from_user_home(sample_profile, tmp_path):
    source_home = tmp_path / "source-home"
    source_codex_home = source_home / ".codex"
    runtime_root = tmp_path / "runtime-root"
    runtime_app_dir = runtime_root / "app"
    source_codex_home.mkdir(parents=True)
    runtime_app_dir.mkdir(parents=True)
    (source_codex_home / "auth.json").write_text('{"mode":"chatgpt"}')
    (source_codex_home / "config.toml").write_text('model = "gpt-5.5"')

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "transient logs"
    mock_result.stderr = ""

    def fake_run(*args, **kwargs):
        output_path = args[0][7]
        with open(output_path, "w") as f:
            f.write("<!DOCTYPE html><html><body>Resume content</body></html>")
        codex_home = Path(kwargs["env"]["CODEX_HOME"])
        assert (codex_home / "auth.json").read_text() == '{"mode":"chatgpt"}'
        assert (codex_home / "config.toml").read_text() == 'model = "gpt-5.5"'
        return mock_result

    with patch.dict("app.generator.os.environ", {"HOME": str(source_home)}, clear=False):
        with patch("app.generator.__file__", str(runtime_app_dir / "generator.py")):
            with patch("app.generator.subprocess.run", side_effect=fake_run):
                html, error = generate_resume(
                    sample_profile,
                    "Python dev role",
                    "<html></html>",
                    provider="codex",
                    model="gpt-5.5",
                )

    assert html.startswith("<!DOCTYPE html>")
    assert error == ""


def test_get_llm_providers_loads_codex_models_from_cache(tmp_path):
    source_home = tmp_path / "source-home"
    source_codex_home = source_home / ".codex"
    source_codex_home.mkdir(parents=True)
    (source_codex_home / "models_cache.json").write_text(
        json.dumps({
            "models": [
                {"slug": "gpt-5.5", "display_name": "GPT-5.5", "visibility": "list"},
                {"slug": "codex-auto-review", "display_name": "Auto Review", "visibility": "hidden"},
            ]
        })
    )
    (source_codex_home / "config.toml").write_text('model = "gpt-5.5"\n')

    with patch.dict("app.generator.os.environ", {"HOME": str(source_home)}, clear=False):
        providers = get_llm_providers()

    assert providers["codex"]["models"] == {"gpt-5.5": "GPT-5.5"}
