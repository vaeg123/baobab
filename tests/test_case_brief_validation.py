from baobab.pipeline.validate_case_law_briefs import evaluate_brief


def complete_record():
    return {
        "source_code": "OHADA.BIBLIO",
        "source_url": "https://biblio.ohada.org/notice",
        "official_identifier": "CCJA-001/2024",
        "decision_date": "2024-01-01",
        "jurisdiction_code": "OHADA.CCJA",
        "text_length": 3000,
        "normalized_sha256": "a" * 64,
        "holding": "La Cour rejette le pourvoi après examen des moyens invoqués.",
        "exact_disposition": "Le pourvoi est rejeté.",
    }


def test_complete_brief_reaches_full_documentary_score():
    score, checks = evaluate_brief(complete_record())
    assert score == 100
    assert all(checks.values())


def test_missing_text_and_identity_cannot_look_verified():
    record = complete_record()
    record.update(official_identifier=None, legacy_ref=None, text_length=0, normalized_sha256=None)
    score, checks = evaluate_brief(record)
    assert score < 80
    assert checks["identity_present"] is False
    assert checks["substantial_text"] is False
    assert checks["text_integrity_hashed"] is False


def test_disposition_is_scored_but_not_a_fundamental_identity_check():
    record = complete_record()
    record["exact_disposition"] = None
    score, checks = evaluate_brief(record)
    assert score == 95
    assert checks["disposition_present"] is False
