"""
Extraction — identifie les articles, délais, sanctions dans un document juridique.
"""
from typing import Any


class ExtractPipeline:
    """Extrait les entités juridiques d'un texte brut."""

    def process(self, document: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": "extracted",
            "articles": [],
            "deadlines": [],
            "sanctions": [],
        }
