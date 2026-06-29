"""
Triggers — Conditions de déclenchement automatique de cascades.
"""
from typing import Callable
from baobab.core.models.legal_event import LegalEvent


TriggerFn = Callable[[LegalEvent], bool]


def always_trigger(event: LegalEvent) -> bool:
    """Déclenche toujours — trigger par défaut."""
    return True


def territory_trigger(territory: str) -> TriggerFn:
    """Déclenche uniquement pour un territoire donné."""
    def fn(event: LegalEvent) -> bool:
        return event.territory == territory
    return fn


def corpus_trigger(corpus: str) -> TriggerFn:
    """Déclenche uniquement pour un corpus juridique donné."""
    def fn(event: LegalEvent) -> bool:
        return event.corpus == corpus
    return fn
