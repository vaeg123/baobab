"""Contrat temporel commun aux réponses juridiques BAOBAB."""

from __future__ import annotations

from datetime import date
from typing import Any


TEMPORAL_PROMPT_CONTRACT = """
CONTRAT TEMPOREL BAOBAB — OBLIGATOIRE POUR TOUTE RÉPONSE :
Ajoute à la racine de l'objet JSON un objet `trajectoire` exactement structuré ainsi :
{
  "date_analyse": "YYYY-MM-DD",
  "passe": [{
    "date": "date ou période",
    "evenement": "origine, ancienne règle, modification ou interprétation antérieure",
    "relation": "ORIGINE|MODIFIE|ABROGE|REMPLACE|INTERPRETE|CONFIRME",
    "source_refs": ["référence présente dans le corpus"],
    "confiance": "ELEVE|MOYEN|FAIBLE"
  }],
  "present": {
    "regle_applicable": "règle applicable à la date d'analyse",
    "statut": "EN_VIGUEUR|PARTIELLEMENT_EN_VIGUEUR|ABROGE|INCERTAIN",
    "date_validite": "date ou période vérifiée",
    "personnes_concernees": ["catégorie concernée"],
    "exceptions": ["exception vérifiée"],
    "impact_pratique": ["conséquence concrète"]
  },
  "futur": [{
    "horizon": "date ou période",
    "evolution": "évolution identifiée",
    "nature": "TEXTE_ADOPTE_NON_APPLICABLE|PROJET_OFFICIEL|ANNONCE_OFFICIELLE|TENDANCE_JURISPRUDENTIELLE|SCENARIO_ANALYTIQUE",
    "certitude": "CERTAIN|ELEVE|MOYEN|FAIBLE",
    "source_refs": ["source justificative présente dans le corpus"],
    "declencheur": "étape qui rendrait cette évolution effective"
  }],
  "actions": [{
    "priorite": "IMMEDIATE|A_PLANIFIER|A_SURVEILLER",
    "action": "action professionnelle concrète",
    "echeance": "date, délai ou non déterminé",
    "fondement_refs": ["source justificative présente dans le corpus"]
  }],
  "limites_temporelles": "ce que le corpus ne permet pas d'établir"
}
RÈGLES :
- Le passé explique la filiation juridique, pas seulement une liste de dates.
- Le présent est toujours daté et indique la règle applicable, ses exceptions et son impact.
- Ne présente jamais une hypothèse comme du droit futur.
- Un futur CERTAIN exige un texte adopté et une source explicite dans le corpus.
- Sans évolution future officiellement sourcée, retourne `futur: []` et écris-le dans `limites_temporelles`.
- Chaque événement temporel doit citer une référence réellement fournie dans le corpus.
- N'invente jamais un nombre de décisions, une date, un projet, une réforme ou une citation.
"""


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _source_refs(documents: list[dict[str, Any]]) -> list[str]:
    refs: list[str] = []
    for document in documents:
        ref = _text(document.get("official_citation") or document.get("ref") or document.get("titre"))
        if ref and ref not in refs:
            refs.append(ref)
    return refs[:8]


def normalize_temporal_fiche(
    fiche: dict[str, Any],
    *,
    as_of: date | str | None,
    source_documents: list[dict[str, Any]],
) -> dict[str, Any]:
    """Garantit un contrat temporel minimal sans transformer une lacune en certitude."""
    if not isinstance(fiche, dict):
        return fiche

    analysis_date = _text(as_of) or date.today().isoformat()
    references = _source_refs(source_documents)
    trajectory = fiche.get("trajectoire")
    if not isinstance(trajectory, dict):
        trajectory = {}

    past = trajectory.get("passe")
    if not isinstance(past, list):
        legacy_past = fiche.get("passe") or fiche.get("historique") or []
        past = []
        for item in legacy_past if isinstance(legacy_past, list) else []:
            if not isinstance(item, dict):
                continue
            past.append({
                "date": _text(item.get("date") or item.get("annee")) or "Date non établie",
                "evenement": _text(item.get("evenement") or item.get("texte")),
                "relation": "ORIGINE",
                "source_refs": [],
                "confiance": "FAIBLE",
            })

    present = trajectory.get("present")
    if not isinstance(present, dict):
        legacy_present = fiche.get("present") if isinstance(fiche.get("present"), dict) else {}
        present = {
            "regle_applicable": _text(
                fiche.get("reponse_directe")
                or fiche.get("principe")
                or legacy_present.get("dispositif")
                or fiche.get("explication")
                or fiche.get("conclusion")
            ),
            "statut": "INCERTAIN",
            "date_validite": analysis_date,
            "personnes_concernees": [],
            "exceptions": [],
            "impact_pratique": [],
        }

    future = trajectory.get("futur")
    if not isinstance(future, list):
        # Les anciens champs « futur/usages » étaient génératifs et non suffisamment
        # sourcés. Ils ne sont volontairement pas promus en évolution juridique.
        future = []

    actions = trajectory.get("actions")
    if not isinstance(actions, list):
        actions = []
        for item in fiche.get("etapes", []) if isinstance(fiche.get("etapes"), list) else []:
            if isinstance(item, dict) and _text(item.get("titre") or item.get("detail")):
                actions.append({
                    "priorite": "A_PLANIFIER",
                    "action": _text(item.get("titre") or item.get("detail")),
                    "echeance": "Non déterminée",
                    "fondement_refs": [],
                })

    trajectory = {
        "date_analyse": _text(trajectory.get("date_analyse")) or analysis_date,
        "passe": past,
        "present": present,
        "futur": future,
        "actions": actions,
        "sources_disponibles": references,
        "limites_temporelles": _text(trajectory.get("limites_temporelles"))
        or "Aucune évolution future ne peut être affirmée sans source officielle explicite dans le corpus.",
    }
    fiche["trajectoire"] = trajectory
    return fiche
