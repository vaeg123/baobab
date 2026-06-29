from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from baobab.core.models.legal_process import LegalProcess, ProcessStep, StepStatus


class AlertLevel(str, Enum):
    INFO     = "info"
    WARNING  = "warning"
    CRITICAL = "critical"
    OVERDUE  = "overdue"


@dataclass
class Alert:
    alert_id: str
    process_id: str
    step_id: str
    entity_id: str
    level: AlertLevel
    message: str
    due_date: datetime | None
    created_at: datetime


def generate_alerts(process: LegalProcess, warning_threshold_days: int = 5) -> list[Alert]:
    alerts: list[Alert] = []
    now = datetime.now(timezone.utc)

    for step in process.steps:
        if step.status in (StepStatus.COMPLETED, StepStatus.SKIPPED):
            continue

        if step.due_date is None:
            continue

        days_remaining = (step.due_date - now).days

        if step.due_date < now:
            level = AlertLevel.OVERDUE
            message = f"DÉPASSÉ : {step.name} — échéance dépassée depuis {abs(days_remaining)} jour(s)"
        elif days_remaining <= warning_threshold_days:
            level = AlertLevel.CRITICAL
            message = f"CRITIQUE : {step.name} — {days_remaining} jour(s) restant(s)"
        elif days_remaining <= warning_threshold_days * 3:
            level = AlertLevel.WARNING
            message = f"ATTENTION : {step.name} — {days_remaining} jour(s) restant(s)"
        else:
            continue

        alerts.append(Alert(
            alert_id=f"alert-{step.step_id}",
            process_id=process.process_id,
            step_id=step.step_id,
            entity_id=process.entity_id,
            level=level,
            message=message,
            due_date=step.due_date,
            created_at=now,
        ))

    return alerts
