from fastapi import APIRouter

router = APIRouter(tags=["compliance"])


@router.get("/compliance/{entity_id}")
async def get_compliance(entity_id: str):
    return {"entity_id": entity_id, "message": "Compliance report — à connecter au Digital Twin"}
