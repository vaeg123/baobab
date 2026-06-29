from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ReasoningOutput:
    """Résultat traçable du moteur de raisonnement."""
    query: str
    conclusion: str
    sources: list[str]
    exceptions: list[str]
    risks: list[str]
    scenarios: list[dict]
    applicable_obligations: list[str]
    confidence: float
    generated_at: datetime = field(default_factory=datetime.utcnow)


class ReasoningEngine:
    """
    Construit un raisonnement juridique tracé à partir de Legal Atoms.
    Tout output est explicable — sources + exceptions + risques inclus.
    """

    def reason(
        self,
        query: str,
        context_entity_id: str,
        relevant_atoms: list[str],
    ) -> ReasoningOutput:
        # Stub — sera connecté au LLM guidé + chaînes de raisonnement
        return ReasoningOutput(
            query=query,
            conclusion="Raisonnement en cours de construction.",
            sources=relevant_atoms,
            exceptions=[],
            risks=[],
            scenarios=[],
            applicable_obligations=[],
            confidence=0.0,
        )
