"""
Atomisation — transforme un extrait classifié en Legal Atom immuable.
"""
from typing import Any


class AtomizePipeline:
    """Transforme un extrait classifié en Legal Atom versionnée."""

    def process(self, classified: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": "atomized",
            "atom_id": None,
            "atom": None,
        }
