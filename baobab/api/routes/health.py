from datetime import datetime

from fastapi import APIRouter

from baobab.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    if settings.is_production:
        return {"status": "ok"}
    return {
        "status": "ok",
        "system": "BAOBAB",
        "version": "0.1.0",
        "timestamp": datetime.utcnow().isoformat(),
    }
