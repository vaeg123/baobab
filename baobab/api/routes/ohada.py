from fastapi import APIRouter, Header
from pydantic import BaseModel, Field
from datetime import datetime
import re
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
from baobab.api.routes.accounts import _connect_db, require_workspace_service

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

RULE_RE = re.compile(r"^OHADA\.([A-Z]+)\.ART([0-9.-]+)\.V([0-9]{4})$")
RULE_DOCUMENTS = {
    ("AUSCGIE", "2014"): "AUSCGIE-2014",
    ("AUDCG", "2010"): "AUDCG-2010",
    # Le moteur historique nomme ce corpus AUVE.V2010 ; le texte actuellement
    # matérialisé et applicable à ces étapes est l'AUPSRVE de 1998.
    ("AUVE", "2010"): "AUPSRVE-1998",
}


def rule_target(rule_id: str) -> tuple[str, str] | None:
    match = RULE_RE.match(rule_id)
    if not match:
        return None
    family, article, version = match.groups()
    reference = RULE_DOCUMENTS.get((family, version))
    return (reference, article) if reference else None


async def resolve_rule_links(steps) -> dict[str, dict]:
    targets = {step.rule_id: rule_target(step.rule_id) for step in steps}
    references = sorted({target[0] for target in targets.values() if target})
    if not references:
        return {}
    connection = await _connect_db()
    try:
        rows = await connection.fetch(
            """SELECT c.id AS document_id,c.ref,p.provision_id,p.provision_number,
                      p.verification_status,p.valid_from,p.valid_until,
                      (SELECT count(*) FROM legal_document_relations r
                       WHERE r.target_document_id=c.id
                         AND r.relation_type='EXPLICITLY_CITES_PROVISION'
                         AND r.provision_ref='Article '||p.provision_number) AS citation_count
               FROM legal_corpus c JOIN legal_provisions p ON p.document_id=c.id
               WHERE c.ref=ANY($1::text[])""",
            references,
        )
    finally:
        await connection.close()
    available = {(row["ref"], row["provision_number"]): dict(row) for row in rows}
    return {
        rule_id: available[target]
        for rule_id, target in targets.items()
        if target and target in available
    }


class OhadaEvenementRequest(BaseModel):
    entity_id: str
    event_type: OhadaEventType
    occurred_at: datetime
    country_code: str = Field(default="CI", pattern=r"^[A-Za-z]{2}$")
    metadata: dict = Field(default_factory=dict)


@router.post("/evenement")
async def declarer_evenement(request: OhadaEvenementRequest, x_user_token: str | None = Header(default=None)):
    await require_workspace_service(x_user_token, "ohada")
    event = LegalEvent(
        event_id=str(uuid.uuid4()),
        event_type=request.event_type,
        entity_id=request.entity_id,
        occurred_at=request.occurred_at,
        corpus="OHADA",
        territory=request.country_code.upper(),
        metadata=request.metadata,
    )

    process = event_engine.process(event)
    compliance = compliance_engine.evaluate(process)
    alerts = generate_alerts(process)
    legal_references = await resolve_rule_links(process.steps)

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
                "authority": "OHADA" if s.rule_id.startswith("OHADA.") else "NATIONAL",
                "date_basis": "OPERATIONAL_TARGET_TO_VERIFY",
                "legal_reference": legal_references.get(s.rule_id),
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
