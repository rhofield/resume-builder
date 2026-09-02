"""Browser-level tests for the in-place resume editor.

The editing logic lives in JavaScript inside app/templates/edit.html, so it can
only be exercised by driving a real browser. Playwright is already a dependency
(app/pdf.py renders the PDF with it), so these run against a live server.
"""
import socket
import threading
import time
import uuid

import pytest
import uvicorn

from app.main import app, OUTPUT_DIR

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright  # noqa: E402


# Mirrors how the real templates are built: absolute pt sizes in one <style> block.
FIXTURE_HTML = """<!DOCTYPE html>
<html><head><style>
  body { font-family: Arial, sans-serif; font-size: 10.5pt; padding: 1.5cm; }
  h1 { font-size: 22pt; }
  li { font-size: 9pt; }
</style></head>
<body>
  <h1>Jane Smith</h1>
  <p id="summary">A summary paragraph that is not yet a list.</p>
  <ul><li id="bullet">Built a REST API serving 10k requests a day</li></ul>
</body></html>
"""


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def live_server():
    port = _free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 15
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    if not server.started:
        pytest.fail("uvicorn did not start")
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=10)


STRUCTURED_HTML = """<!DOCTYPE html>
<html><head><style>
  body { font-size: 10.5pt; padding: 1cm; }
  .entry { margin-bottom: 8pt; }
  li { font-size: 9pt; }
</style></head>
<body>
  <div class="header"><div class="name">Jane Smith</div></div>
  <div class="section">
    <div class="section-title">EXPERIENCE</div>
    <div class="entry"><div class="entry-header">Job A</div>
      <ul><li>bullet a1</li><li>bullet a2</li><li>bullet a3</li></ul></div>
    <div class="entry"><div class="entry-header">Job B</div>
      <ul><li>bullet b1</li></ul></div>
    <div class="entry"><div class="entry-header">Job C</div>
      <ul><li>bullet c1</li></ul></div>
  </div>
  <div class="section">
    <div class="section-title">EDUCATION</div>
    <div class="entry"><div class="entry-header">BSc Computer Science</div></div>
  </div>
</body></html>
"""


@pytest.fixture
def structured(live_server, browser):
    stem = f"editor-struct-{uuid.uuid4().hex[:12]}"
    (OUTPUT_DIR / f"{stem}.html").write_text(STRUCTURED_HTML)
    pg = browser.new_page(viewport={"width": 1400, "height": 1000})
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(f"{live_server}/edit/{stem}", wait_until="networkidle")
    pg.wait_for_function("() => document.getElementById('resume-frame').contentDocument.body.isContentEditable")
    pg.stem = stem
    yield pg
    assert errors == [], f"JavaScript errors: {errors}"
    pg.close()
    (OUTPUT_DIR / f"{stem}.html").unlink(missing_ok=True)
    (OUTPUT_DIR / f"{stem}.pdf").unlink(missing_ok=True)


@pytest.fixture
def resume(live_server):
    """A fresh resume in output/, cleaned up afterwards."""
    stem = f"editor-test-{uuid.uuid4().hex[:12]}"
    (OUTPUT_DIR / f"{stem}.html").write_text(FIXTURE_HTML)
    yield f"{live_server}/edit/{stem}", stem
    (OUTPUT_DIR / f"{stem}.html").unlink(missing_ok=True)
    (OUTPUT_DIR / f"{stem}.pdf").unlink(missing_ok=True)


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--no-sandbox"])
        yield b
        b.close()


@pytest.fixture
def page(browser, resume):
    url, stem = resume
    pg = browser.new_page(viewport={"width": 1400, "height": 1000})
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(url, wait_until="networkidle")
    pg.wait_for_function("() => document.getElementById('resume-frame').contentDocument.body.isContentEditable")
    pg.stem = stem
    pg.js_errors = errors
    yield pg
    assert errors == [], f"JavaScript errors on the page: {errors}"
    pg.close()


# --- helpers -----------------------------------------------------------------

SELECT_TEMPLATE = """(sel) => {
    const d = document.getElementById('resume-frame').contentDocument;
    const el = d.querySelector(sel);
    const r = d.createRange(); r.selectNodeContents(el);
    const s = d.getSelection(); s.removeAllRanges(); s.addRange(r);
}"""

RENDERED_SIZE = """(sel) => {
    const w = document.getElementById('resume-frame').contentWindow;
    const el = w.document.querySelector(sel);
    const leaf = el.querySelector('span') || el;
    return parseFloat(w.getComputedStyle(leaf).fontSize);
}"""


def select(page, selector):
    page.evaluate(SELECT_TEMPLATE, selector)


def frame_html(page, selector):
    return page.evaluate(
        "(sel) => document.getElementById('resume-frame').contentDocument.querySelector(sel).innerHTML",
        selector,
    )


def stylesheet_pt(page):
    return page.evaluate("""() => {
        const d = document.getElementById('resume-frame').contentDocument;
        return [...d.querySelector('style').textContent.matchAll(/font-size:\\s*([\\d.]+)pt/gi)]
            .map(m => parseFloat(m[1]));
    }""")


# --- tests -------------------------------------------------------------------

def test_body_is_editable_and_guides_render(page):
    assert page.evaluate(
        "() => document.getElementById('resume-frame').contentDocument.body.getAttribute('contenteditable')"
    ) == "true"
    assert "page" in page.locator("#page-count").inner_text()


def test_bold_produces_semantic_tag(page):
    select(page, "#bullet")
    page.locator('[data-cmd="bold"]').click()
    assert "<b>" in frame_html(page, "#bullet")


def test_toolbar_reflects_active_state(page):
    select(page, "#bullet")
    page.locator('[data-cmd="bold"]').click()
    select(page, "#bullet")
    page.wait_for_selector('[data-cmd="bold"].tb-btn-active')


def test_paragraph_becomes_a_bullet_list(page):
    select(page, "#summary")
    page.locator('[data-cmd="insertUnorderedList"]').click()

    # The paragraph is converted to an <li>. Note the browser merges it into an
    # adjacent <ul> rather than creating a new one, so count list items, not lists.
    assert page.evaluate("""() => {
        const d = document.getElementById('resume-frame').contentDocument;
        return d.querySelector('#summary') === null
            && [...d.querySelectorAll('ul li')].some(li => li.textContent.startsWith('A summary paragraph'));
    }""")


def test_bullet_list_toggles_back_off(page):
    select(page, "#bullet")
    page.locator('[data-cmd="insertUnorderedList"]').click()
    assert page.evaluate(
        "() => document.getElementById('resume-frame').contentDocument.querySelectorAll('li').length"
    ) == 0


def test_selection_font_size_compounds_and_round_trips(page):
    original = page.evaluate(RENDERED_SIZE, "#bullet")

    sizes = []
    for _ in range(3):
        select(page, "#bullet")
        page.locator('[data-size="0.9"]').click()
        sizes.append(page.evaluate(RENDERED_SIZE, "#bullet"))

    # Each click must shrink again; the regression was that it stuck after one.
    assert sizes[0] < original
    assert sizes[1] < sizes[0]
    assert sizes[2] < sizes[1]

    for _ in range(3):
        select(page, "#bullet")
        page.locator('[data-size="1.111"]').click()
    assert page.evaluate(RENDERED_SIZE, "#bullet") == pytest.approx(original, rel=0.01)


def test_font_size_leaves_no_legacy_font_tags(page):
    select(page, "#bullet")
    page.locator('[data-size="0.9"]').click()
    assert page.evaluate(
        "() => document.getElementById('resume-frame').contentDocument.querySelectorAll('font').length"
    ) == 0


def test_font_size_does_not_nest_spans(page):
    for _ in range(4):
        select(page, "#bullet")
        page.locator('[data-size="0.9"]').click()
    assert page.evaluate(
        "() => document.getElementById('resume-frame').contentDocument.querySelectorAll('#bullet span span').length"
    ) == 0


def test_document_scale_rewrites_every_pt_size(page):
    base = stylesheet_pt(page)
    page.locator('[data-scale="-1"]').click()
    page.locator('[data-scale="-1"]').click()

    assert page.locator("#scale-value").inner_text() == "95%"
    scaled = stylesheet_pt(page)
    assert len(scaled) == len(base)
    for before, after in zip(base, scaled):
        assert after == pytest.approx(before * 0.95, rel=0.001)


def test_document_scale_resets_to_original_values(page):
    base = stylesheet_pt(page)
    for _ in range(3):
        page.locator('[data-scale="-1"]').click()
    page.locator("#scale-value").click()

    assert page.locator("#scale-value").inner_text() == "100%"
    assert stylesheet_pt(page) == pytest.approx(base)


def test_save_writes_clean_html_without_editor_attributes(page):
    select(page, "#bullet")
    page.locator('[data-cmd="bold"]').click()
    page.locator('[data-scale="-1"]').click()
    page.locator("#save-btn").click()
    page.wait_for_selector("#save-result .banner")

    saved = (OUTPUT_DIR / f"{page.stem}.html").read_text()
    assert "contenteditable" not in saved
    assert "spellcheck" not in saved
    assert "<b>" in saved
    # The document scale must persist into the saved file, not just the preview.
    assert "10.24pt" in saved


def test_editing_marks_the_document_dirty(page):
    assert page.locator("#dirty-flag").inner_text() == ""
    select(page, "#bullet")
    page.locator('[data-cmd="bold"]').click()
    assert page.locator("#dirty-flag").inner_text() == "Unsaved changes"


# --- paste sanitising -------------------------------------------------------

def sanitize(page, html):
    return page.evaluate("(h) => window.sanitizePastedHtml(h)", html)


def paste(page, selector, payload, plain=None):
    """Dispatch a real paste event carrying the given clipboard payload."""
    page.evaluate(
        """([sel, html, text]) => {
            const d = document.getElementById('resume-frame').contentDocument;
            const el = d.querySelector(sel);
            const r = d.createRange(); r.selectNodeContents(el);
            const s = d.getSelection(); s.removeAllRanges(); s.addRange(r);
            d.body.focus();
            const dt = new DataTransfer();
            if (html) dt.setData('text/html', html);
            if (text) dt.setData('text/plain', text);
            el.dispatchEvent(new ClipboardEvent('paste', {
                clipboardData: dt, bubbles: true, cancelable: true
            }));
        }""",
        [selector, payload, plain],
    )


def test_paste_keeps_bold_and_italic_tags(page):
    assert sanitize(page, "<p>plain <b>bold</b> and <i>italic</i></p>") == \
        "<p>plain <b>bold</b> and <i>italic</i></p>"


def test_paste_keeps_bullet_structure(page):
    out = sanitize(page, "<ul><li>first point</li><li>second point</li></ul>")
    assert out == "<ul><li>first point</li><li>second point</li></ul>"


def test_paste_strips_presentational_attributes(page):
    out = sanitize(
        page,
        '<p class="MsoNormal" style="color:#1F497D;font-family:Calibri;font-size:18pt">'
        '<b>Keep me</b></p>',
    )
    assert out == "<p><b>Keep me</b></p>"
    assert "style" not in out and "class" not in out and "Calibri" not in out


def test_paste_recovers_word_style_bold(page):
    # Word emits emphasis as CSS on a span, not as a <b> tag.
    out = sanitize(page, '<span style="font-weight:700">Machine Learning Engineer</span>')
    assert out == "<b>Machine Learning Engineer</b>"


def test_paste_recovers_css_italic_and_underline(page):
    assert sanitize(page, '<span style="font-style:italic">Sydney</span>') == "<i>Sydney</i>"
    assert sanitize(page, '<span style="text-decoration:underline">Note</span>') == "<u>Note</u>"


def test_paste_survives_google_docs_bold_wrapper(page):
    # Google Docs wraps the whole payload in <b style="font-weight:normal">.
    out = sanitize(
        page,
        '<b style="font-weight:normal" id="docs-internal-guid-x">'
        '<p dir="ltr"><span style="font-weight:400">normal</span>'
        '<span style="font-weight:700">bold</span></p></b>',
    )
    assert out == "<p>normal<b>bold</b></p>"
    assert not out.startswith("<b>")


def test_paste_drops_font_tags_but_keeps_their_text(page):
    out = sanitize(page, '<font face="Times" size="6" color="red">Ryan Oldfield</font>')
    assert out == "Ryan Oldfield"


def test_paste_maps_headings_to_bold_paragraphs(page):
    # Keeps prominence without importing a 32pt heading into the template.
    assert sanitize(page, "<h1>Experience</h1>") == "<p><b>Experience</b></p>"


def test_paste_keeps_safe_links_and_drops_dangerous_ones(page):
    assert sanitize(page, '<a href="https://github.com/rhofield">gh</a>') == \
        '<a href="https://github.com/rhofield">gh</a>'
    assert sanitize(page, '<a href="javascript:alert(1)">x</a>') == "<a>x</a>"


def test_paste_removes_scripts_entirely(page):
    out = sanitize(page, '<p>safe</p><script>alert(1)</script>')
    assert out == "<p>safe</p>"
    assert "alert" not in out


def test_pasting_into_the_document_preserves_formatting(page):
    paste(page, "#summary", "<b>Led</b> a team of <i>eight</i> engineers", "Led a team of eight engineers")
    html = frame_html(page, "body")
    assert "<b>Led</b>" in html
    assert "<i>eight</i>" in html
    assert page.locator("#dirty-flag").inner_text() == "Unsaved changes"


def test_pasted_text_adopts_the_template_font_size(page):
    paste(page, "#bullet", '<span style="font-size:28pt;font-family:Courier">Big</span>', "Big")
    # 9pt on li, in px.
    assert page.evaluate("""() => {
        const w = document.getElementById('resume-frame').contentWindow;
        const li = w.document.querySelector('ul li');
        return parseFloat(w.getComputedStyle(li).fontSize);
    }""") == pytest.approx(12.0, rel=0.01)


def test_plain_paste_fallback_when_no_html_offered(page):
    paste(page, "#summary", None, "just plain text")
    assert "just plain text" in frame_html(page, "body")


# --- block reordering --------------------------------------------------------

HOVER = """(sel) => {
    const d = document.getElementById('resume-frame').contentDocument;
    const el = d.querySelector(sel);
    const r = el.getBoundingClientRect();
    el.dispatchEvent(new MouseEvent('mousemove', {
        bubbles: true, clientX: r.left + 2, clientY: r.top + 2
    }));
}"""


def texts(page, selector):
    return page.evaluate(
        """(sel) => [...document.getElementById('resume-frame').contentDocument
             .querySelectorAll(sel)].map(e => e.textContent.replace(/\s+/g, ' ').trim())""",
        selector,
    )


def hover(page, selector):
    page.evaluate(HOVER, selector)


def entry_titles(page, section=0):
    """Entry headings inside the Nth .section (:first-of-type counts divs, not classes)."""
    return page.evaluate(
        """(i) => {
            const d = document.getElementById('resume-frame').contentDocument;
            const s = d.querySelectorAll('.section')[i];
            return [...s.querySelectorAll('.entry .entry-header')].map(e => e.textContent.trim());
        }""",
        section,
    )


def test_hovering_an_entry_targets_the_entry(structured):
    hover(structured, ".section .entry .entry-header")
    assert structured.locator("#block-overlay").is_visible()
    assert structured.locator(".block-label").inner_text() == "ENTRY 1/3"


def test_hovering_a_bullet_targets_the_bullet(structured):
    hover(structured, ".entry li")
    assert structured.locator(".block-label").inner_text() == "BULLET 1/3"


def test_move_entry_down_reorders_jobs(structured):
    assert entry_titles(structured) == ["Job A", "Job B", "Job C"]
    hover(structured, ".section .entry .entry-header")
    structured.locator('[data-move="down"]').click()
    assert entry_titles(structured) == ["Job B", "Job A", "Job C"]


def test_move_bullet_up_reorders_within_its_list(structured):
    hover(structured, ".entry ul li:nth-child(3)")
    structured.locator('[data-move="up"]').click()
    assert structured.evaluate("""() => {
        const d = document.getElementById('resume-frame').contentDocument;
        return [...d.querySelectorAll('.entry')[0].querySelectorAll('li')].map(e => e.textContent.trim());
    }""") == ["bullet a1", "bullet a3", "bullet a2"]


def test_move_whole_section(structured):
    assert texts(structured, ".section .section-title") == ["EXPERIENCE", "EDUCATION"]
    hover(structured, ".section .section-title")
    structured.locator('[data-move="down"]').click()
    assert texts(structured, ".section .section-title") == ["EDUCATION", "EXPERIENCE"]


def test_first_block_cannot_move_up_and_last_cannot_move_down(structured):
    hover(structured, ".section .entry .entry-header")
    assert structured.locator('[data-move="up"]').is_disabled()
    assert not structured.locator('[data-move="down"]').is_disabled()

    hover(structured, ".section .entry:nth-of-type(4) .entry-header")
    assert structured.locator(".block-label").inner_text() == "ENTRY 3/3"
    assert structured.locator('[data-move="down"]').is_disabled()


def test_an_entry_never_jumps_above_its_section_heading(structured):
    """The section title is not a peer, so moving the first entry up is a no-op."""
    hover(structured, ".section .entry .entry-header")
    structured.locator('[data-move="up"]').click(force=True)
    assert structured.evaluate("""() => {
        const d = document.getElementById('resume-frame').contentDocument;
        return d.querySelectorAll('.section')[0].children[0].textContent.trim();
    }""") == "EXPERIENCE"


def test_select_parent_walks_up_to_the_section(structured):
    hover(structured, ".entry li")
    assert structured.locator(".block-label").inner_text() == "BULLET 1/3"
    structured.locator('[data-move="parent"]').click()
    assert structured.locator(".block-label").inner_text() == "ENTRY 1/3"
    structured.locator('[data-move="parent"]').click()
    assert structured.locator(".block-label").inner_text() == "SECTION 1/2"


def test_delete_block_and_undo_restores_it(structured):
    hover(structured, ".section .entry .entry-header")
    structured.locator('[data-move="delete"]').click()
    assert entry_titles(structured) == ["Job B", "Job C"]

    structured.locator('[data-cmd="undo"]').click()
    assert entry_titles(structured) == ["Job A", "Job B", "Job C"]


def test_undo_reverses_a_move(structured):
    hover(structured, ".section .entry .entry-header")
    structured.locator('[data-move="down"]').click()
    assert entry_titles(structured) == ["Job B", "Job A", "Job C"]
    structured.locator('[data-cmd="undo"]').click()
    assert entry_titles(structured) == ["Job A", "Job B", "Job C"]


def test_reordering_marks_dirty_and_saves(structured):
    hover(structured, ".section .entry .entry-header")
    structured.locator('[data-move="down"]').click()
    assert structured.locator("#dirty-flag").inner_text() == "Unsaved changes"

    structured.locator("#save-btn").click()
    structured.wait_for_selector("#save-result .banner")
    saved = (OUTPUT_DIR / f"{structured.stem}.html").read_text()
    assert saved.index("Job B") < saved.index("Job A")


def test_overlay_chrome_never_reaches_the_saved_file(structured):
    hover(structured, ".section .entry .entry-header")
    structured.locator('[data-move="down"]').click()
    structured.locator("#save-btn").click()
    structured.wait_for_selector("#save-result .banner")

    saved = (OUTPUT_DIR / f"{structured.stem}.html").read_text()
    for chrome in ("block-overlay", "block-tools", "block-btn", "data-move", "contenteditable"):
        assert chrome not in saved
