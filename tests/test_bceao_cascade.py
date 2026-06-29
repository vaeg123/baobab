from datetime import datetime, timezone
from baobab.core.models.legal_event import LegalEvent
from baobab.engines.event_engine.engine import LegalEventEngine
from baobab.engines.compliance_engine.engine import ComplianceEngine, ComplianceStatus
from baobab.verticals.bceao.events import BceaoEventType
from baobab.verticals.bceao.cascades import (
    DECLARATION_SOUPCON_CASCADE,
    CONTROLE_CBF_CASCADE,
    RAPPORT_MENSUEL_CASCADE,
    RATIO_PRUDENTIEL_BREACH_CASCADE,
    OUVERTURE_COMPTE_KYC_CASCADE,
)
from baobab.verticals.cima.alerts import generate_alerts, AlertLevel


def _engine(*cascades):
    e = LegalEventEngine()
    for c in cascades: e.register_cascade(c)
    return e


def test_declaration_soupcon_steps():
    engine = _engine(DECLARATION_SOUPCON_CASCADE)
    event = LegalEvent(
        event_id="bceao-001",
        event_type=BceaoEventType.DECLARATION_SOUPCON,
        entity_id="banque-atlantique-ci",
        occurred_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        corpus="BCEAO", territory="CI",
    )
    process = engine.process(event)
    assert len(process.steps) == 6
    # La déclaration CENTIF doit être dans 1 jour
    centif_step = next(s for s in process.steps if "CENTIF" in s.name)
    assert centif_step.deadline_days == 1


def test_declaration_soupcon_deadline_is_24h():
    engine = _engine(DECLARATION_SOUPCON_CASCADE)
    event = LegalEvent(
        event_id="bceao-002",
        event_type=BceaoEventType.DECLARATION_SOUPCON,
        entity_id="banque-test",
        occurred_at=datetime(2024, 6, 1, tzinfo=timezone.utc),
        corpus="BCEAO", territory="CI",
    )
    process = engine.process(event)
    assert process.steps[1].deadline_days == 1  # 24h = J+1


def test_controle_cbf_steps():
    engine = _engine(CONTROLE_CBF_CASCADE)
    event = LegalEvent(
        event_id="bceao-003",
        event_type=BceaoEventType.CONTROLE_CBF,
        entity_id="banque-test",
        occurred_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        corpus="BCEAO", territory="CI",
    )
    process = engine.process(event)
    assert len(process.steps) == 8
    last = process.steps[-1]
    assert last.deadline_days == 180


def test_ratio_breach_requires_declaration_cbf():
    engine = _engine(RATIO_PRUDENTIEL_BREACH_CASCADE)
    event = LegalEvent(
        event_id="bceao-004",
        event_type=BceaoEventType.RATIO_PRUDENTIEL_BREACH,
        entity_id="banque-test",
        occurred_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        corpus="BCEAO", territory="CI",
    )
    process = engine.process(event)
    names = [s.name for s in process.steps]
    assert any("CBF" in n or "conformité" in n.lower() for n in names)


def test_past_soupcon_generates_critical_alert():
    engine = _engine(DECLARATION_SOUPCON_CASCADE)
    event = LegalEvent(
        event_id="bceao-005",
        event_type=BceaoEventType.DECLARATION_SOUPCON,
        entity_id="banque-test",
        occurred_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
        corpus="BCEAO", territory="CI",
    )
    process = engine.process(event)
    alerts = generate_alerts(process)
    assert len(alerts) > 0
    assert any(a.level in ("overdue", "critical") for a in alerts)
