from fastapi import FastAPI

app = FastAPI(title="Resume Builder")

@app.get("/healthz")
async def health():
    return {"status": "ok"}
