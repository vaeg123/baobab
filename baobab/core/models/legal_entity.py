from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class EntityType(str, Enum):
    COMPANY = "company"
    INSURER = "insurer"
    BANK = "bank"
    REGULATOR = "regulator"
    INDIVIDUAL = "individual"


@dataclass
class LegalEntity:
    """
    Personne morale ou physique titulaire de droits et d'obligations.
    Nœud central du Digital Legal Twin.
    """
    entity_id: str
    name: str
    entity_type: EntityType
    territory: str
    registration_number: str | None = None
    regulated_by: list[str] = field(default_factory=list)   # ["CIMA", "BCEAO"]
    active_obligations: list[str] = field(default_factory=list)
    compliance_score: float | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
