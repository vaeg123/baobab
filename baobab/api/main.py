from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from baobab.api.routes import accounts, health, events, cima, compliance, ohada, bceao, legal, submissions

app = FastAPI(
    title="BAOBAB API",
    description="Legal Operating System for Africa",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(events.router, prefix="/api/v1")
app.include_router(cima.router, prefix="/api/v1/cima")
app.include_router(compliance.router, prefix="/api/v1/compliance")
app.include_router(ohada.router, prefix="/api/v1/ohada")
app.include_router(bceao.router, prefix="/api/v1/bceao")
app.include_router(accounts.router, prefix="/api/v1/accounts")
app.include_router(legal.router, prefix="/api/v1")
app.include_router(submissions.router, prefix="/api/v1")

STATIC_DIR = Path(__file__).parent.parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/", include_in_schema=False)
async def dashboard():
    return FileResponse(STATIC_DIR / "index.html")
