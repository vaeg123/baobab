from baobab.core.models.legal_event import LegalEvent, EventStatus
from baobab.engines.event_engine.cascade import CascadeEngine, CascadeDefinition
from baobab.core.models.legal_process import LegalProcess


class LegalEventEngine:
    """
    Moteur central : reçoit un événement juridique et produit la cascade complète.
    """

    def __init__(self) -> None:
        self.cascade_engine = CascadeEngine()

    def register_cascade(self, definition: CascadeDefinition) -> None:
        self.cascade_engine.register(definition)

    def process(self, event: LegalEvent) -> LegalProcess:
        event.status = EventStatus.ACTIVE
        process = self.cascade_engine.build_process(event)
        return process
