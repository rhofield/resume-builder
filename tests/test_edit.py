import pytest
from fastapi.testclient import TestClient
from app.main import app, OUTPUT_DIR


RESUME_HTML = "<!DOCTYPE html><html><body><h1>Jane Smith</h1></body></html>"


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def generated_resume():
    """A generated resume sitting in output/, removed after the test."""
    stem = "testco-engineer-19700101-000000"
    html_path = OUTPUT_DIR / f"{stem}.html"
    html_path.write_text(RESUME_HTML)
    yield stem
    html_path.unlink(missing_ok=True)
    (OUTPUT_DIR / f"{stem}.pdf").unlink(missing_ok=True)


@pytest.fixture
def fake_pdf(monkeypatch):
    """Stub the Playwright render so tests don't launch a browser."""
    calls = []

    async def _render(html, output_path):
        calls.append((html, output_path))
        output_path.write_bytes(b"%PDF-1.4 fake")
        return True

    monkeypatch.setattr("app.main.render_pdf", _render)
    return calls


def test_edit_page_loads(client, generated_resume):
    response = client.get(f"/edit/{generated_resume}")
    assert response.status_code == 200
    assert f"/output/{generated_resume}.html" in response.text
    assert "contenteditable" in response.text


def test_edit_page_404_for_unknown_resume(client):
    assert client.get("/edit/does-not-exist-at-all").status_code == 404


# Unencoded "../" is normalised away by the HTTP client before it is sent, so the
# cases worth asserting are the encoded ones that actually reach the route handler.
@pytest.mark.parametrize("stem", ["..%2Fprofile", "..%2F..%2Fprofile", ".hidden", "a%2Fb", "%2Fetc%2Fpasswd"])
def test_edit_page_rejects_path_traversal(client, stem):
    assert client.get(f"/edit/{stem}").status_code == 404


def test_save_overwrites_html_and_rerenders_pdf(client, generated_resume, fake_pdf):
    edited = "<!DOCTYPE html><html><body><h1>Jane A. Smith</h1></body></html>"
    response = client.post(f"/edit/{generated_resume}", data={"html": edited})

    assert response.status_code == 200
    assert (OUTPUT_DIR / f"{generated_resume}.html").read_text() == edited
    assert len(fake_pdf) == 1
    assert fake_pdf[0][0] == edited
    assert "Download updated PDF" in response.text


def test_save_rejects_non_html(client, generated_resume, fake_pdf):
    response = client.post(f"/edit/{generated_resume}", data={"html": "just some text"})

    assert response.status_code == 200
    assert "Refusing to save" in response.text
    # The original file must survive a rejected save.
    assert (OUTPUT_DIR / f"{generated_resume}.html").read_text() == RESUME_HTML
    assert fake_pdf == []


def test_save_keeps_edits_when_pdf_fails(client, generated_resume, monkeypatch):
    async def _fail(html, output_path):
        return False

    monkeypatch.setattr("app.main.render_pdf", _fail)
    edited = "<!DOCTYPE html><html><body><h1>Edited</h1></body></html>"
    response = client.post(f"/edit/{generated_resume}", data={"html": edited})

    assert (OUTPUT_DIR / f"{generated_resume}.html").read_text() == edited
    assert "PDF conversion failed" in response.text


def test_save_404_for_unknown_resume(client, fake_pdf):
    response = client.post("/edit/does-not-exist-at-all", data={"html": RESUME_HTML})
    assert response.status_code == 404


def test_recent_outputs_expose_edit_url(generated_resume):
    from app.main import get_recent_outputs

    (OUTPUT_DIR / f"{generated_resume}.pdf").write_bytes(b"%PDF-1.4 fake")
    entry = next(o for o in get_recent_outputs() if o["stem"] == generated_resume)
    assert entry["edit_url"] == f"/edit/{generated_resume}"
