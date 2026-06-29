from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable

from baobab.core.models.legal_event import LegalEvent
from baobab.core.models.legal_process import LegalProcess, ProcessStep, StepStatus


@dataclass
class CascadeStep:
    name: str
    rule_id: str
    deadline_days: int | None
    condition: Callable[[dict], bool] | None = None
    sanction: str | None = None


@dataclass
class CascadeDefinition:
    cascade_id: str
    event_type: str
    corpus: str
    steps: list[CascadeStep]
    description: str = ""


class CascadeEngine:
    """
    Transforme un Legal Event en processus calculé.
    Chaque étape hérite de la date de l'événement déclencheur.
    """

    def __init__(self) -> None:
        self._definitions: dict[str, CascadeDefinition] = {}

    def register(self, definition: CascadeDefinition) -> None:
        self._definitions[definition.event_type] = definition

    def build_process(self, event: LegalEvent) -> LegalProcess:
        definition = self._definitions.get(event.event_type)
        if not definition:
            raise ValueError(f"No cascade registered for event type: {event.event_type}")

        steps: list[ProcessStep] = []
        ref_date = event.occurred_at
        if ref_date.tzinfo is None:
            ref_date = ref_date.replace(tzinfo=timezone.utc)

        for i, cascade_step in enumerate(definition.steps):
            due_date = None
            if cascade_step.deadline_days is not None:
                due_date = ref_date + timedelta(days=cascade_step.deadline_days)

            step = ProcessStep(
                step_id=f"{event.event_id}-step-{i:02d}",
                name=cascade_step.name,
                rule_id=cascade_step.rule_id,
                deadline_days=cascade_step.deadline_days,
                status=StepStatus.PENDING,
                due_date=due_date,
            )
            steps.append(step)

        return LegalProcess(
            process_id=f"proc-{event.event_id}",
            process_type=definition.cascade_id,
            entity_id=event.entity_id,
            trigger_event_id=event.event_id,
            steps=steps,
        )
