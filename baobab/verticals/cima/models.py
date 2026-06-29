"""
Modèles Pydantic spécifiques au vertical CIMA.
"""
from pydantic import BaseModel
from datetime import datetime
from baobab.verticals.cima.events import CimaEventType


class SinistreCreate(BaseModel):
    entity_id: str
    sinistre_type: CimaEventType
    occurred_at: datetime
    metadata: dict = {}


class SinistreResponse(BaseModel):
    event_id: str
    process_id: str
    entity_id: str
    sinistre_type: str
    occurred_at: datetime
    step_count: int
    compliance_score: float
    alert_count: int
