from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class StepStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    OVERDUE = "overdue"
    SKIPPED = "skipped"


@dataclass
class ProcessStep:
    step_id: str
    name: str
    rule_id: str
    deadline_days: int | None
    status: StepStatus = StepStatus.PENDING
    due_date: datetime | None = None
    completed_at: datetime | None = None
    notes: str = ""


@dataclass
class LegalProcess:
    """
    Séquence d'événements ordonnés déclenchés par un Legal Event.
    Représente la cascade complète associée à un sinistre, une fusion, etc.
    """
    process_id: str
    process_type: str
    entity_id: str
    trigger_event_id: str
    steps: list[ProcessStep] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None

    @property
    def overdue_steps(self) -> list[ProcessStep]:
        return [s for s in self.steps if s.status == StepStatus.OVERDUE]

    @property
    def next_pending(self) -> ProcessStep | None:
        return next((s for s in self.steps if s.status == StepStatus.PENDING), None)
