from pathlib import Path

from baobab.pipeline.build_ohada_provisions import extract_articles, identity_matches
from baobab.pipeline.ohada_catalog import effective_bounds


def test_act_identity_must_match_reference_marker():
    assert identity_matches("AUS-2010", "ACTE UNIFORME PORTANT ORGANISATION DES SÛRETÉS")
    assert not identity_matches("AUCTMR-2003", "ACTE UNIFORME PORTANT ORGANISATION DES SÛRETÉS")


def test_articles_are_split_and_duplicates_rejected():
    text = "Article premier\nTexte du premier article suffisamment long.\nArticle 2\nTexte du deuxième article suffisamment long.\nArticle 2\nCopie répétée suffisamment longue."
    articles = extract_articles(text)
    assert [article["number"] for article in articles] == ["1", "2"]
    assert "premier article" in articles[0]["content"]


def test_ohada_codes_are_visible_and_clearly_partial():
    html = (Path(__file__).parents[1] / "baobab" / "static" / "index.html").read_text(
        encoding="utf-8"
    )
    assert "Codes OHADA" in html
    assert "Source partielle · à vérifier" in html
    assert "/api/v1/legal/ohada/codes" in html
    assert "loadOhadaArticles" in html
    switch_view = html[html.index("function switchOhadaView"):html.index("function switchCreationTab")]
    assert "if (view === 'codes') loadOhadaCodes();" in switch_view
    assert "select.value = data.results[0].id" in html
    assert "query ? `&query=${encodeURIComponent(query)}` : ''" in html


def test_verified_effective_date_is_not_confused_with_adoption_date():
    valid_from, valid_until = effective_bounds("AUSCGIE-2014")
    assert str(valid_from) == "2014-05-05"
    assert valid_until is None


def test_unknown_effective_date_is_not_invented_from_fallback():
    from datetime import date

    valid_from, valid_until = effective_bounds("AUS-2010", date(2010, 12, 15))
    assert valid_from is None
    assert valid_until is None
