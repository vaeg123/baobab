from dataclasses import dataclass
from datetime import datetime


@dataclass
class RiskScore:
    entity_id: str
    probability: float       # 0–1
    severity: float          # 0–1
    urgency: float           # 0–1
    financial_impact: float  # estimation EUR/FCFA
    regulatory_impact: float
    reputational_impact: float
    composite_score: float
    generated_at: datetime


class RiskEngine:
    """
    Évalue le risque juridique d'une organisation.
    Le score composite combine probabilité × gravité × urgence.
    """

    def evaluate(
        self,
        entity_id: str,
        probability: float,
        severity: float,
        urgency: float,
        financial_impact: float = 0.0,
        regulatory_impact: float = 0.0,
        reputational_impact: float = 0.0,
    ) -> RiskScore:
        composite = probability * severity * urgency
        return RiskScore(
            entity_id=entity_id,
            probability=probability,
            severity=severity,
            urgency=urgency,
            financial_impact=financial_impact,
            regulatory_impact=regulatory_impact,
            reputational_impact=reputational_impact,
            composite_score=round(composite, 4),
            generated_at=datetime.utcnow(),
        )
