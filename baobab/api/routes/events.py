from fastapi import APIRouter

router = APIRouter(tags=["events"])


@router.get("/events")
async def list_events():
    return {"events": [], "message": "Event store — à connecter à PostgreSQL"}
