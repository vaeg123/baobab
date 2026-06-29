from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime
import uuid

from baobab.engines.event_engine.engine import LegalEventEngine
from baobab.engines.compliance_engine.engine import ComplianceEngine
from baobab.verticals.cima.events import CimaEventType
from baobab.verticals.cima.cascades import SINISTRE_INCENDIE_CASCADE, SINISTRE_AUTO_CASCADE
from baobab.verticals.cima.alerts import generate_alerts
from baobab.core.models.legal_event import LegalEvent, EventStatus

router = APIRouter(tags=["CIMA"])

event_engine = LegalEventEngine()
event_engine.register_cascade(SINISTRE_INCENDIE_CASCADE)
event_engine.register_cascade(SINISTRE_AUTO_CASCADE)

compliance_engine = ComplianceEngine()


class SinistreRequest(BaseModel):
    entity_id: str
    sinistre_type: CimaEventType
    occurred_at: datetime
    metadata: dict = {}


@router.post("/sinistre")
async def declare_sinistre(request: SinistreRequest):
    event = LegalEvent(
        event_id=str(uuid.uuid4()),
        event_type=request.sinistre_type,
        entity_id=request.entity_id,
        occurred_at=request.occurred_at,
        corpus="CIMA",
        territory="CI",
        metadata=request.metadata,
    )

    process = event_engine.process(event)
    compliance = compliance_engine.evaluate(process)
    alerts = generate_alerts(process)

    return {
        "event_id": event.event_id,
        "process_id": process.process_id,
        "steps": [
            {
                "step_id": s.step_id,
                "name": s.name,
                "status": s.status,
                "due_date": s.due_date.isoformat() if s.due_date else None,
                "deadline_days": s.deadline_days,
            }
            for s in process.steps
        ],
        "compliance": {
            "score": compliance.score,
            "status": compliance.status,
            "overdue_count": compliance.overdue_count,
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
