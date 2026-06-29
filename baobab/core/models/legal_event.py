from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class EventStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


@dataclass
class LegalEvent:
    """
    Observable modification de réalité produisant des effets juridiques.
    Déclenche automatiquement une cascade d'obligations calculées.
    """
    event_id: str
    event_type: str              # SINISTRE_INCENDIE, SINISTRE_AUTO, FUSION, etc.
    entity_id: str               # Organisation assujettie
    occurred_at: datetime
    corpus: str                  # CIMA, OHADA, BCEAO
    territory: str               # CI, SN, CM
    metadata: dict[str, Any] = field(default_factory=dict)
    status: EventStatus = EventStatus.PENDING
    cascade_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
