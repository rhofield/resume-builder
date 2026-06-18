import asyncio
from pathlib import Path


async def _render_async(html: str, output_path: Path) -> None:
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        # --no-sandbox required on WSL (kernel sandbox not available)
        browser = await p.chromium.launch(args=["--no-sandbox"])
        page = await browser.new_page()
        await page.set_content(html, wait_until="networkidle")
        await page.pdf(
            path=str(output_path),
            format="A4",
            print_background=True,
            margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
        )
        await browser.close()


def render_pdf(html: str, output_path: Path) -> bool:
    """Returns True on success, False on any failure. Never raises."""
    try:
        asyncio.run(_render_async(html, output_path))
        return True
    except Exception:
        return False
