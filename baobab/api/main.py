from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from baobab.api.routes import health, events, cima, compliance

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
