from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
import uuid


@dataclass
class LegalAtom:
    """
    Unité minimale de connaissance juridique avec identifiant permanent.
    Exemple d'identifiant : CI.OHADA.AUSCGIE.ART247.V2024
    Immuable : toute modification crée une nouvelle version.
    """
    id: str                          # CI.CIMA.CODE.ART260.V2022
    source_text: str                 # Texte brut de la disposition
    territory: str                   # CI, SN, CM, OHADA, CIMA...
    corpus: str                      # CIMA, OHADA, BCEAO, NATIONAL
    article_ref: str                 # ART260
    version: str                     # V2022
    effective_date: datetime
    language: str = "fr"
    abrogated: bool = False
    abrogated_by: str | None = None
    relations: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def atom_id(self) -> str:
        return f"{self.territory}.{self.corpus}.{self.article_ref}.{self.version}"

    def add_relation(self, relation_type: str, target_id: str) -> None:
        self.relations.append({"type": relation_type, "target": target_id})
