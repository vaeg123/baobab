"""
Classification — assigne corpus, territoire, type juridique à chaque extrait.
"""
from typing import Any


class ClassifyPipeline:
    """Classifie un extrait juridique (corpus, territoire, type)."""

    def process(self, extracted: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": "classified",
            "corpus": None,
            "territory": None,
            "legal_type": None,
        }
