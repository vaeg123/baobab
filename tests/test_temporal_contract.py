from datetime import date

from baobab.core.temporal import TEMPORAL_PROMPT_CONTRACT, normalize_temporal_fiche


def test_prompt_contract_forbids_unsourced_future_claims():
    assert "Un futur CERTAIN exige un texte adopté" in TEMPORAL_PROMPT_CONTRACT
    assert "N'invente jamais" in TEMPORAL_PROMPT_CONTRACT


def test_normalizer_adds_temporal_contract_to_legacy_question():
    fiche = {
        "type": "question",
        "reponse_directe": "La formalité est obligatoire.",
        "etapes": [{"numero": 1, "titre": "Déposer le dossier", "detail": "Au greffe."}],
    }
    result = normalize_temporal_fiche(
        fiche,
        as_of=date(2026, 8, 29),
        source_documents=[{"official_citation": "Art. 10 Loi X"}],
    )

    trajectory = result["trajectoire"]
    assert trajectory["date_analyse"] == "2026-08-29"
    assert trajectory["present"]["regle_applicable"] == "La formalité est obligatoire."
    assert trajectory["present"]["statut"] == "INCERTAIN"
    assert trajectory["futur"] == []
    assert trajectory["actions"][0]["action"] == "Déposer le dossier"
    assert trajectory["sources_disponibles"] == ["Art. 10 Loi X"]


def test_legacy_generated_future_is_not_promoted_to_verified_future():
    fiche = {
        "principe": "Principe actuel",
        "futur": {"usages": [{"annee": "2027", "texte": "Usage supposé"}]},
    }
    result = normalize_temporal_fiche(fiche, as_of=None, source_documents=[])
    assert result["trajectoire"]["futur"] == []


def test_existing_structured_future_is_preserved():
    future = [{
        "horizon": "2027-01-01",
        "evolution": "Entrée en vigueur",
        "nature": "TEXTE_ADOPTE_NON_APPLICABLE",
        "certitude": "CERTAIN",
        "source_refs": ["Loi X"],
        "declencheur": "Date légale",
    }]
    fiche = {"trajectoire": {"present": {}, "passe": [], "futur": future, "actions": []}}
    result = normalize_temporal_fiche(fiche, as_of="2026-08-29", source_documents=[])
    assert result["trajectoire"]["futur"] == future
