"""
Ingestion pipeline — point d'entrée pour les documents juridiques.
"""
from typing import Any


class IngestPipeline:
    """Ingère un document juridique brut et le soumet au pipeline d'extraction."""

    def process(self, document: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": "ingested",
            "document_id": document.get("id"),
            "source": document.get("source"),
        }
