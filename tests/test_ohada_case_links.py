from baobab.pipeline.link_ohada_case_law import extract_explicit_citations
from baobab.pipeline.ohada_catalog import is_applicable


def test_extracts_articles_only_near_identified_act():
    text = "La Cour applique les articles 13, 14 et 15 de l'AUDCG."
    citations = extract_explicit_citations(text, ("AUDCG", "DROIT COMMERCIAL GENERAL"))
    assert [item["number"] for item in citations] == ["13", "14", "15"]


def test_does_not_link_bare_article_number():
    assert extract_explicit_citations("La Cour applique l'article 13.", ("AUDCG",)) == []


def test_extracts_article_premier_and_hyphenated_article():
    text = "Violation des articles premier et 12-1 de l'AUSCGIE."
    citations = extract_explicit_citations(text, ("AUSCGIE",))
    assert [item["number"] for item in citations] == ["1"]


def test_selects_the_version_applicable_on_decision_date():
    from datetime import date

    assert is_applicable("AUSCGIE-1997", date(2014, 5, 4))
    assert not is_applicable("AUSCGIE-1997", date(2014, 5, 5))
    assert is_applicable("AUSCGIE-2014", date(2014, 5, 5))


def test_unknown_effective_date_still_uses_conservative_document_bound():
    from datetime import date

    assert not is_applicable("AUS-2010", date(2010, 12, 14), date(2010, 12, 15))
