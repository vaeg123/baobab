from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from baobab.api.routes import accounts, health, events, cima, compliance, ohada, bceao, legal, submissions, legal_fr, stripe_routes, superadmin_auth
from baobab.config import settings

# La documentation Swagger/Redoc expose la carte complète de l'API
# (endpoints, schémas, exemples) : un point de départ idéal pour la
# reconnaissance d'un attaquant. Elle reste activée en développement,
# mais masquée en production sauf activation explicite via
# EXPOSE_API_DOCS=true (ex. API publique documentée volontairement).
_show_docs = (not settings.is_production) or settings.expose_api_docs

app = FastAPI(
    title="BAOBAB API",
    description="Legal Operating System for Africa",
    version="0.1.0",
    docs_url="/api/docs" if _show_docs else None,
    redoc_url="/api/redoc" if _show_docs else None,
    openapi_url="/api/openapi.json" if _show_docs else None,
)

# CORS : jamais de wildcard. Seules les origines explicitement listées
# dans CORS_ALLOWED_ORIGINS (variable d'environnement, séparée par des
# virgules) peuvent effectuer des requêtes cross-origin avec en-têtes
# personnalisés (Authorization, X-Admin-Token, X-Access-Token...).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Admin-Token", "X-Access-Token"],
    allow_credentials=False,
)

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if settings.is_production:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


app.add_middleware(SecurityHeadersMiddleware)

app.include_router(health.router, prefix="/api")
app.include_router(events.router, prefix="/api/v1")
app.include_router(cima.router, prefix="/api/v1/cima")
app.include_router(compliance.router, prefix="/api/v1/compliance")
app.include_router(ohada.router, prefix="/api/v1/ohada")
app.include_router(bceao.router, prefix="/api/v1/bceao")
app.include_router(accounts.router, prefix="/api/v1/accounts")
app.include_router(legal.router, prefix="/api/v1")
app.include_router(submissions.router, prefix="/api/v1")
app.include_router(legal_fr.router, prefix="/api/v1")
app.include_router(stripe_routes.router, prefix="/api/v1")
app.include_router(superadmin_auth.router, prefix="/api/v1")

STATIC_DIR = Path(__file__).parent.parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/", include_in_schema=False)
async def dashboard():
    return FileResponse(STATIC_DIR / "index.html")
