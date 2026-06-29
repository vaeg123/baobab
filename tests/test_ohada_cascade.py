from datetime import datetime, timezone
from baobab.core.models.legal_event import LegalEvent
from baobab.engines.event_engine.engine import LegalEventEngine
from baobab.engines.compliance_engine.engine import ComplianceEngine
from baobab.verticals.ohada.events import OhadaEventType
from baobab.verticals.ohada.cascades import (
    CREATION_SARL_CASCADE,
    AGO_ANNUELLE_CASCADE,
    DISSOLUTION_CASCADE,
    INJONCTION_PAYER_CASCADE,
)
from baobab.verticals.cima.alerts import generate_alerts, AlertLevel


def _make_engine(*cascades):
    engine = LegalEventEngine()
    for c in cascades:
        engine.register_cascade(c)
    return engine


def test_creation_sarl_steps():
    engine = _make_engine(CREATION_SARL_CASCADE)
    event = LegalEvent(
        event_id="ohada-001",
        event_type=OhadaEventType.CREATION_SARL,
        entity_id="entreprise-ci-001",
        occurred_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        corpus="OHADA",
        territory="CI",
    )
    process = engine.process(event)
    assert len(process.steps) == 7
    assert process.steps[0].name == "Rédaction et signature des statuts"


def test_ago_annuelle_steps():
    engine = _make_engine(AGO_ANNUELLE_CASCADE)
    event = LegalEvent(
        event_id="ohada-002",
        event_type=OhadaEventType.AGO_ANNUELLE,
        entity_id="entreprise-ci-002",
        occurred_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        corpus="OHADA",
        territory="CI",
    )
    process = engine.process(event)
    assert len(process.steps) == 6
    # AGO doit se tenir dans les 6 mois (180j)
    ago_step = next(s for s in process.steps if "Tenue" in s.name or s.name.startswith("Tenue"))
    assert ago_step.deadline_days == 180


def test_dissolution_ends_with_radiation():
    engine = _make_engine(DISSOLUTION_CASCADE)
    event = LegalEvent(
        event_id="ohada-003",
        event_type=OhadaEventType.DISSOLUTION,
        entity_id="entreprise-ci-003",
        occurred_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        corpus="OHADA",
        territory="CI",
    )
    process = engine.process(event)
    last_step = process.steps[-1]
    assert "Radiation" in last_step.name or "RCCM" in last_step.name


def test_injonction_payer_has_signification_step():
    engine = _make_engine(INJONCTION_PAYER_CASCADE)
    event = LegalEvent(
        event_id="ohada-004",
        event_type=OhadaEventType.INJONCTION_PAYER,
        entity_id="creancier-001",
        occurred_at=datetime(2024, 6, 1, tzinfo=timezone.utc),
        corpus="OHADA",
        territory="CI",
    )
    process = engine.process(event)
    names = [s.name for s in process.steps]
    assert any("Signification" in n or "signification" in n for n in names)


def test_past_ago_generates_alerts():
    engine = _make_engine(AGO_ANNUELLE_CASCADE)
    event = LegalEvent(
        event_id="ohada-005",
        event_type=OhadaEventType.AGO_ANNUELLE,
        entity_id="entreprise-ci-004",
        occurred_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
        corpus="OHADA",
        territory="CI",
    )
    process = engine.process(event)
    alerts = generate_alerts(process)
    assert len(alerts) > 0
    assert any(a.level in ("overdue", "critical") for a in alerts)
