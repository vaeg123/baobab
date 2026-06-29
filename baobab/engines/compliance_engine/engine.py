from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from baobab.core.models.legal_process import LegalProcess, StepStatus


class ComplianceStatus(str, Enum):
    COMPLIANT     = "compliant"
    PENDING       = "pending"
    AT_RISK       = "at_risk"
    NON_COMPLIANT = "non_compliant"


@dataclass
class ComplianceReport:
    entity_id: str
    process_id: str
    score: float                  # 0.0 – 1.0
    status: ComplianceStatus
    overdue_count: int
    total_steps: int
    generated_at: datetime


class ComplianceEngine:
    """
    Calcule un score de conformité sur la base des processus actifs.
    """

    def evaluate(self, process: LegalProcess) -> ComplianceReport:
        total = len(process.steps)
        overdue = len(process.overdue_steps)
        completed = sum(1 for s in process.steps if s.status == StepStatus.COMPLETED)

        score = completed / total if total > 0 else 1.0

        if overdue > 0:
            status = ComplianceStatus.NON_COMPLIANT
        elif score >= 0.8:
            status = ComplianceStatus.COMPLIANT
        elif score >= 0.5:
            status = ComplianceStatus.AT_RISK
        else:
            status = ComplianceStatus.PENDING

        return ComplianceReport(
            entity_id=process.entity_id,
            process_id=process.process_id,
            score=round(score, 3),
            status=status,
            overdue_count=overdue,
            total_steps=total,
            generated_at=datetime.now(timezone.utc),
        )
