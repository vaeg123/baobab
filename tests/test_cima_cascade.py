from datetime import datetime, timezone
from baobab.core.models.legal_event import LegalEvent
from baobab.engines.event_engine.engine import LegalEventEngine
from baobab.engines.compliance_engine.engine import ComplianceEngine, ComplianceStatus
from baobab.verticals.cima.cascades import SINISTRE_INCENDIE_CASCADE
from baobab.verticals.cima.events import CimaEventType
from baobab.verticals.cima.alerts import generate_alerts, AlertLevel


def test_compliance_engine_on_new_process():
    event_engine = LegalEventEngine()
    event_engine.register_cascade(SINISTRE_INCENDIE_CASCADE)
    compliance_engine = ComplianceEngine()

    event = LegalEvent(
        event_id="test-003",
        event_type=CimaEventType.SINISTRE_INCENDIE,
        entity_id="insurer-001",
        occurred_at=datetime.now(timezone.utc),
        corpus="CIMA",
        territory="CI",
    )

    process = event_engine.process(event)
    report = compliance_engine.evaluate(process)

    assert report.entity_id == "insurer-001"
    assert report.overdue_count == 0
    assert report.status == ComplianceStatus.PENDING


def test_alerts_generated_for_past_event():
    event_engine = LegalEventEngine()
    event_engine.register_cascade(SINISTRE_INCENDIE_CASCADE)

    # Événement datant de 100 jours — tout est en retard
    past_event = LegalEvent(
        event_id="test-004",
        event_type=CimaEventType.SINISTRE_INCENDIE,
        entity_id="insurer-002",
        occurred_at=datetime(2024, 1, 1),
        corpus="CIMA",
        territory="CI",
    )

    process = event_engine.process(past_event)
    alerts = generate_alerts(process)

    assert len(alerts) > 0
    levels = {a.level for a in alerts}
    assert AlertLevel.OVERDUE in levels or AlertLevel.CRITICAL in levels
