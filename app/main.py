from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR.parent / "output"
RESUME_TEMPLATES_DIR = BASE_DIR.parent / "resume_templates"
OUTPUT_DIR.mkdir(exist_ok=True)

app = FastAPI(title="Resume Builder")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.mount("/output", StaticFiles(directory=str(OUTPUT_DIR)), name="output")

@app.get("/healthz")
async def health():
    return {"status": "ok"}
