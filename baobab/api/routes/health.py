from fastapi import APIRouter
from datetime import datetime

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    return {
        "status": "ok",
        "system": "BAOBAB",
        "version": "0.1.0",
        "timestamp": datetime.utcnow().isoformat(),
    }
