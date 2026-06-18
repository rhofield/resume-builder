import subprocess
import pytest
from unittest.mock import patch, MagicMock
from app.generator import build_prompt, extract_html, generate_resume


def test_build_prompt_contains_all_three_inputs(sample_profile):
    prompt = build_prompt(sample_profile, "Senior Python Engineer at Acme", "<html><!-- STATIC --></html>")
    assert "Jane Smith" in prompt                   # profile present
    assert "Senior Python Engineer at Acme" in prompt  # job description present
    assert "<!-- STATIC -->" in prompt              # template present


def test_build_prompt_includes_accomplishments(sample_profile):
    prompt = build_prompt(sample_profile, "job", "<html></html>")
    assert "10k requests/day" in prompt


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
