from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class LegalRule:
    """
    Norme applicable dans un contexte donné.
    Rattachée à un ou plusieurs Legal Atoms source.
    """
    rule_id: str
    title: str
    corpus: str
    article_ref: str
    condition: str               # Condition d'application (texte ou expression)
    obligation: str              # Ce que la règle impose
    deadline_days: int | None    # Délai en jours ouvrés (None = pas de délai fixe)
    sanction: str | None         # Sanction en cas de non-respect
    source_atom_ids: list[str] = field(default_factory=list)
    territory: str = "OHADA"
    effective_date: datetime = field(default_factory=datetime.utcnow)
