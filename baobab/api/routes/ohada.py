from fastapi import APIRouter
from pydantic import BaseModel
from datetime import datetime
import uuid

from baobab.engines.event_engine.engine import LegalEventEngine
from baobab.engines.compliance_engine.engine import ComplianceEngine
from baobab.verticals.cima.alerts import generate_alerts
from baobab.verticals.ohada.events import OhadaEventType
from baobab.verticals.ohada.cascades import (
    CREATION_SARL_CASCADE,
    CREATION_SA_CASCADE,
    AGO_ANNUELLE_CASCADE,
    DISSOLUTION_CASCADE,
    CESSION_PARTS_CASCADE,
    FUSION_ABSORPTION_CASCADE,
    INJONCTION_PAYER_CASCADE,
    IMMATRICULATION_RCCM_CASCADE,
)
from baobab.core.models.legal_event import LegalEvent

router = APIRouter(tags=["OHADA"])

event_engine = LegalEventEngine()
for cascade in [
    CREATION_SARL_CASCADE,
    CREATION_SA_CASCADE,
    AGO_ANNUELLE_CASCADE,
    DISSOLUTION_CASCADE,
    CESSION_PARTS_CASCADE,
    FUSION_ABSORPTION_CASCADE,
    INJONCTION_PAYER_CASCADE,
    IMMATRICULATION_RCCM_CASCADE,
]:
    event_engine.register_cascade(cascade)

compliance_engine = ComplianceEngine()


class OhadaEvenementRequest(BaseModel):
    entity_id: str
    event_type: OhadaEventType
    occurred_at: datetime
    metadata: dict = {}


@router.post("/evenement")
async def declarer_evenement(request: OhadaEvenementRequest):
    event = LegalEvent(
        event_id=str(uuid.uuid4()),
        event_type=request.event_type,
        entity_id=request.entity_id,
        occurred_at=request.occurred_at,
        corpus="OHADA",
        territory="CI",
        metadata=request.metadata,
    )

    process = event_engine.process(event)
    compliance = compliance_engine.evaluate(process)
    alerts = generate_alerts(process)

    return {
        "event_id": event.event_id,
        "process_id": process.process_id,
        "corpus": "OHADA",
        "event_type": request.event_type,
        "steps": [
            {
                "step_id": s.step_id,
                "name": s.name,
                "status": s.status,
                "due_date": s.due_date.isoformat() if s.due_date else None,
                "deadline_days": s.deadline_days,
                "rule_id": s.rule_id,
            }
            for s in process.steps
        ],
        "compliance": {
            "score": compliance.score,
            "status": compliance.status,
            "overdue_count": compliance.overdue_count,
            "total_steps": compliance.total_steps,
        },
        "alerts": [
            {
                "level": a.level,
                "message": a.message,
                "due_date": a.due_date.isoformat() if a.due_date else None,
            }
            for a in alerts
        ],
    }
