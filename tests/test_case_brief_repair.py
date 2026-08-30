from baobab.pipeline.repair_case_law_briefs import extract_disposition


def test_extract_disposition_uses_explicit_source_marker():
    text = "Moyens examinés.\nPAR CES MOTIFS\nLa Cour casse et annule l'arrêt attaqué."
    assert extract_disposition(text).startswith("PAR CES MOTIFS")
    assert "casse et annule" in extract_disposition(text)


def test_extract_disposition_does_not_invent_missing_holding():
    assert extract_disposition("Exposé doctrinal sans dispositif juridictionnel.") == ""
