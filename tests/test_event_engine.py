from datetime import datetime, timezone
from baobab.core.models.legal_event import LegalEvent
from baobab.engines.event_engine.engine import LegalEventEngine
from baobab.verticals.cima.cascades import SINISTRE_INCENDIE_CASCADE
from baobab.verticals.cima.events import CimaEventType


def test_sinistre_incendie_cascade():
    engine = LegalEventEngine()
    engine.register_cascade(SINISTRE_INCENDIE_CASCADE)

    event = LegalEvent(
        event_id="test-001",
        event_type=CimaEventType.SINISTRE_INCENDIE,
        entity_id="entity-abc",
        occurred_at=datetime(2024, 6, 1, tzinfo=timezone.utc),
        corpus="CIMA",
        territory="CI",
    )

    process = engine.process(event)

    assert process.entity_id == "entity-abc"
    assert len(process.steps) == 7
    assert process.steps[0].name == "Déclaration sinistre"
    assert process.steps[0].deadline_days == 5


def test_cascade_due_dates_are_calculated():
    engine = LegalEventEngine()
    engine.register_cascade(SINISTRE_INCENDIE_CASCADE)

    event = LegalEvent(
        event_id="test-002",
        event_type=CimaEventType.SINISTRE_INCENDIE,
        entity_id="entity-xyz",
        occurred_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        corpus="CIMA",
        territory="CI",
    )

    process = engine.process(event)
    declaration_step = process.steps[0]
    assert declaration_step.due_date is not None
    # 5 jours après le 1er janvier
    assert declaration_step.due_date.day == 6
