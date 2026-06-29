from fastapi import APIRouter
from pydantic import BaseModel
from datetime import datetime
import uuid

from baobab.engines.event_engine.engine import LegalEventEngine
from baobab.engines.compliance_engine.engine import ComplianceEngine
from baobab.verticals.cima.alerts import generate_alerts
from baobab.verticals.bceao.events import BceaoEventType
from baobab.verticals.bceao.cascades import (
    DECLARATION_SOUPCON_CASCADE,
    CONTROLE_CBF_CASCADE,
    RAPPORT_MENSUEL_CASCADE,
    INCIDENT_PAIEMENT_CASCADE,
    AGREMENT_BANQUE_CASCADE,
    AGREMENT_MONNAIE_ELEC_CASCADE,
    RATIO_PRUDENTIEL_BREACH_CASCADE,
    OUVERTURE_COMPTE_KYC_CASCADE,
)
from baobab.core.models.legal_event import LegalEvent

router = APIRouter(tags=["BCEAO"])

event_engine = LegalEventEngine()
for cascade in [
    DECLARATION_SOUPCON_CASCADE,
    CONTROLE_CBF_CASCADE,
    RAPPORT_MENSUEL_CASCADE,
    INCIDENT_PAIEMENT_CASCADE,
    AGREMENT_BANQUE_CASCADE,
    AGREMENT_MONNAIE_ELEC_CASCADE,
    RATIO_PRUDENTIEL_BREACH_CASCADE,
    OUVERTURE_COMPTE_KYC_CASCADE,
]:
    event_engine.register_cascade(cascade)

compliance_engine = ComplianceEngine()


class BceaoEvenementRequest(BaseModel):
    entity_id: str
    event_type: BceaoEventType
    occurred_at: datetime
    metadata: dict = {}


@router.post("/evenement")
async def declarer_evenement(request: BceaoEvenementRequest):
    event = LegalEvent(
        event_id=str(uuid.uuid4()),
        event_type=request.event_type,
        entity_id=request.entity_id,
        occurred_at=request.occurred_at,
        corpus="BCEAO",
        territory="CI",
        metadata=request.metadata,
    )

    process = event_engine.process(event)
    compliance = compliance_engine.evaluate(process)
    alerts = generate_alerts(process)

    return {
        "event_id": event.event_id,
        "process_id": process.process_id,
        "corpus": "BCEAO",
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
