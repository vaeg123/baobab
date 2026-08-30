from datetime import date

import pytest
from fastapi import HTTPException

from baobab.api.routes import watch
from baobab.watch_engine import (
    Artifact,
    WATCH_SOURCES,
    _parse_french_date,
    extract_official_reference,
    infer_change_type,
    parse_cima_crca,
    parse_cameroon_minjustice,
    parse_cameroon_official_acts,
    parse_cameroon_prc,
    parse_juricaf_cm,
    parse_ohada_biblio,
    score_artifact_validation,
    watch_matches_artifact,
)


def _source(code: str):
    return next(source for source in WATCH_SOURCES if source.code == code)


def test_parse_ohada_biblio_deduplicates_notice_links():
    html = """
    <a href="index.php?lvl=notice_display&id=42">Arrêt CCJA n° 42/2026</a>
    <a href="./index.php?lvl=notice_display&id=42">Plus d'information...</a>
    <a href="index.php?lvl=notice_display&id=43">Arrêt CCJA n° 43/2026</a>
    """
    artifacts = parse_ohada_biblio(html, _source("OHADA.BIBLIO"))
    assert len(artifacts) == 2
    assert artifacts[0].source_code == "OHADA.BIBLIO"
    assert all(item.url.startswith("https://biblio.ohada.org/") for item in artifacts)
    assert all(item.legal_date == date(2026, 1, 1) for item in artifacts)
    assert all(item.date_precision == "YEAR" for item in artifacts)


def test_parse_cima_crca_extracts_pdf_and_precise_date():
    html = """
    <table><tr><td>13 décembre 2025</td><td>
      <a href="/docs/decision-17.pdf">Décision CRCA n° 17</a>
    </td></tr></table>
    """
    artifacts = parse_cima_crca(html, _source("CIMA.OFFICIAL"))
    assert len(artifacts) == 1
    assert artifacts[0].legal_date == date(2025, 12, 13)
    assert artifacts[0].date_precision == "DAY"
    assert artifacts[0].url == "https://www.cima-afrique.org/docs/decision-17.pdf"


def test_parse_cima_official_fallback_cards():
    html = '<article><a href="/document/decision-n-12-2025/">Décision N° 12/2025 de la CRCA</a></article>'
    artifacts = parse_cima_crca(html, _source("CIMA.OFFICIAL"))
    assert len(artifacts) == 1
    assert artifacts[0].url == "https://www.cima-afrique.org/document/decision-n-12-2025/"
    assert artifacts[0].legal_date == date(2025, 1, 1)


def test_validation_requires_two_stable_observations_and_quality_signals():
    artifact = Artifact(
        "CIMA.OFFICIAL", "cima", "https://cima-afrique.org/d/12",
        "Décision N° 12/2025 de la CRCA", date(2025, 1, 1), "YEAR",
    )
    first_score, first_reasons = score_artifact_validation(artifact, 1)
    stable_score, stable_reasons = score_artifact_validation(artifact, 2)
    assert first_score == 80
    assert "SECONDE_OBSERVATION_REQUISE:+0" in first_reasons
    assert stable_score == 100
    assert "DOCUMENT_STABLE_SUR_2_CYCLES:+20" in stable_reasons


def test_validation_rejects_generic_undated_artifact():
    artifact = Artifact("CIMA.OFFICIAL", "cima", "https://cima-afrique.org/document", "Document")
    score, _ = score_artifact_validation(artifact, 3)
    assert score < 85


def test_parse_cameroon_prc_extracts_only_official_act_cards():
    source = _source("CM.PRC.LOIS")
    html = """
      <nav><a href="/fr/actualites/actes/lois">Lois</a></nav>
      <h4><a href="/fr/actualites/actes/lois/8246-loi-2026-004">
        Loi N°2026/004 du 14 avril 2026 portant organisation
      </a></h4>
      <h4><a href="https://example.com/faux">Loi N°2026/999 du 14 avril 2026</a></h4>
    """
    artifacts = parse_cameroon_prc(html, source)
    assert len(artifacts) == 1
    assert artifacts[0].legal_date == date(2026, 4, 14)
    assert artifacts[0].url.startswith("https://www.prc.cm/fr/actualites/actes/lois/")


def test_parse_cameroon_minjustice_rejects_navigation_and_keeps_decision():
    source = _source("CM.MINJUSTICE.CASELAW")
    html = """
      <a href="/index.php/fr/e-justice/decisions-de-justice">Décisions de justice</a>
      <a href="/documents/jugement-commercial-2025-12.pdf">
        Jugement N°12 du 24 mars 2025 — Tribunal de grande instance
      </a>
    """
    artifacts = parse_cameroon_minjustice(html, source)
    assert len(artifacts) == 1
    assert artifacts[0].legal_date == date(2025, 3, 24)


def test_parse_spm_keeps_numbered_official_act_and_rejects_navigation():
    source = _source("CM.SPM.ACTES")
    html = """
      <nav><a href="/site/?q=fr/documentation/lois-et-règlements">Lois et règlements</a></nav>
      <article><a href="/site/sites/default/files/decret-2026-635.pdf">
        Décret N° 2026/00635/PM du 18 mars 2026 régissant l'aquaculture
      </a></article>
      <a href="https://example.org/decret.pdf">Décret N°2026/999 du 1 janvier 2026</a>
    """
    artifacts = parse_cameroon_official_acts(html, source)
    assert len(artifacts) == 1
    assert artifacts[0].legal_date == date(2026, 3, 18)
    assert "spm.gov.cm" in artifacts[0].url


def test_parse_legalis_uses_parent_text_for_pdf_link():
    source = _source("CM.MINJUSTICE.LEGALIS")
    html = """
      <div class="document"><h3>Loi N°2024/017 du 23 décembre 2024 relative aux données</h3>
        <a href="/documents/loi-2024-017.pdf">Télécharger</a></div>
    """
    artifacts = parse_cameroon_official_acts(html, source)
    assert len(artifacts) == 1
    assert artifacts[0].legal_date == date(2024, 12, 23)


def test_spm_uses_page_pagination_parameter():
    assert _source("CM.SPM.ACTES").pagination_parameter == "page"


def test_slow_cameroon_sources_keep_https_fallbacks():
    for code in ("CM.SPM.ACTES", "CM.MINJUSTICE.LEGALIS", "CM.MINJUSTICE.CASELAW"):
        source = _source(code)
        assert source.fallback_urls
        assert all(url.startswith("https://") for url in source.fallback_urls)


def test_cameroon_official_law_reaches_validation_threshold_when_stable():
    artifact = Artifact(
        "CM.PRC.LOIS", "cm", "https://www.prc.cm/fr/actualites/actes/lois/8246",
        "Loi N°2026/004 du 14 avril 2026 portant organisation", date(2026, 4, 14), "DAY",
    )
    score, reasons = score_artifact_validation(artifact, 2)
    assert score == 100
    assert "REFERENCE_JURIDIQUE_RECONNUE:+15" in reasons


@pytest.mark.parametrize(
    ("title", "reference", "change_type"),
    [
        ("Loi N°2026/004 du 14 avril 2026 modifiant le Conseil constitutionnel",
         "Loi N°2026/004", "AMENDS"),
        ("Ordonnance n°2025/002 fixant les incitations à l'investissement",
         "Ordonnance n°2025/002", None),
        ("Loi N°2025/015 portant ratification de l'ordonnance n°2025/002",
         "Loi N°2025/015", "RATIFIES"),
    ],
)
def test_cameroon_reference_and_change_extraction(title, reference, change_type):
    assert extract_official_reference(title) == reference
    assert infer_change_type(title) == change_type


@pytest.mark.parametrize(
    ("raw", "expected_date", "precision"),
    [
        ("24 mars 2025", date(2025, 3, 24), "DAY"),
        ("2025-03-24", date(2025, 3, 24), "DAY"),
        ("Décision 2025", date(2025, 1, 1), "YEAR"),
        ("sans date", None, "UNKNOWN"),
    ],
)
def test_parse_legal_date_precision(raw, expected_date, precision):
    assert _parse_french_date(raw) == (expected_date, precision)


def test_watch_matching_respects_corpus_and_keywords():
    artifact = Artifact(
        "CIMA.OFFICIAL",
        "cima",
        "https://cima-afrique.org/retrait.pdf",
        "Retrait d'agrément d'une société d'assurance",
    )
    assert watch_matches_artifact({"corpus": "cima", "query": "agrément; solvabilité"}, artifact)
    assert not watch_matches_artifact({"corpus": "ohada", "query": "agrément"}, artifact)
    assert not watch_matches_artifact({"corpus": "cima", "query": "fusion, arbitrage"}, artifact)


def test_parse_juricaf_cm_extracts_cameroon_arrets():
    source = _source("CM.JURICAF.SEARCH")
    html = """
    <html><body>
      <a href="/arret/CAMEROUN-COURSUPREMEDUCAMEROUN-20230315-AB12345">
        Arrêt N°AB/12345 du 15 mars 2023 — Cour Suprême du Cameroun
      </a>
      <a href="/arret/CAMEROUN-COURSUPREMEDUCAMEROUN-20210610-CD67890">
        Arrêt N°CD/67890 du 10 juin 2021 — Chambre civile et commerciale
      </a>
      <a href="/arret/SENEGAL-COURSUPREMEDUSENEGAL-20220101-XY999">
        Arrêt Sénégal — ne doit pas être inclus
      </a>
      <a href="/recherche/pays:cameroun">Navigation — à ignorer</a>
      <a href="https://juricaf.org/arret/CAMEROUN-TRIBUNAL-20240101-ZZ001">Arrêt TGI 2024</a>
    </body></html>
    """
    artifacts = parse_juricaf_cm(html, source)
    assert len(artifacts) == 3
    urls = [a.url for a in artifacts]
    assert all("cameroun" in url.lower() for url in urls)
    assert not any("senegal" in url.lower() for url in urls)
    assert all(a.corpus == "cm" for a in artifacts)
    # Les dates sont extraites du titre
    dated = [a for a in artifacts if a.legal_date is not None]
    assert len(dated) >= 2


def test_parse_juricaf_cm_rejects_navigation_links():
    source = _source("CM.JURICAF.SEARCH")
    html = """
    <html><body>
      <nav>
        <a href="/recherche/pays:cameroun">Retour aux résultats</a>
        <a href="/">Accueil</a>
        <a href="/contact">Contact</a>
      </nav>
      <a href="/arret/CAMEROUN-CS-20251201-RR001">
        Arrêt N°RR/001 du 1er décembre 2025 — Cour Suprême
      </a>
    </body></html>
    """
    artifacts = parse_juricaf_cm(html, source)
    assert len(artifacts) == 1
    assert artifacts[0].legal_date == date(2025, 12, 1)


def test_parse_juricaf_cm_deduplicates_same_url():
    source = _source("CM.JURICAF.SEARCH")
    html = """
    <a href="/arret/CAMEROUN-CS-20240301-AA001">Arrêt N°AA/001 du 1 mars 2024</a>
    <a href="/arret/CAMEROUN-CS-20240301-AA001">Même arrêt — doublon à ignorer</a>
    """
    artifacts = parse_juricaf_cm(html, source)
    assert len(artifacts) == 1


def test_juricaf_source_registered_in_watch_sources():
    """CM.JURICAF.SEARCH doit être présent dans WATCH_SOURCES avec le bon parseur."""
    juricaf = _source("CM.JURICAF.SEARCH")
    assert juricaf.corpus == "cm"
    assert juricaf.country_code == "CM"
    assert juricaf.parser == "juricaf_cm"
    assert "juricaf.org" in juricaf.discovery_url
    assert juricaf.official_source is False


def test_secondary_source_cannot_reach_auto_validation_threshold():
    artifact = Artifact(
        "CM.JURICAF.SEARCH", "cm", "https://juricaf.org/arret/CAMEROUN-1",
        "Arrêt N°12/2025 du 24 mars 2025", date(2025, 3, 24), "DAY",
    )
    score, reasons = score_artifact_validation(artifact, 3, official_source=False)
    assert score < 85
    assert not any(reason.startswith("SOURCE_OFFICIELLE") for reason in reasons)


def test_juricaf_matches_cameroon_corpus_in_watch():
    """Un artefact JURICAF doit matcher les alertes veille 'cameroun' et 'cm'."""
    artifact = Artifact(
        "CM.JURICAF.SEARCH", "cm",
        "https://juricaf.org/arret/CAMEROUN-CS-20240301-AA001",
        "Arrêt Cour Suprême du Cameroun — licenciement abusif",
        date(2024, 3, 1), "DAY",
    )
    assert watch_matches_artifact({"corpus": "cameroun", "query": ""}, artifact)
    assert watch_matches_artifact({"corpus": "cm", "query": "licenciement"}, artifact)
    assert not watch_matches_artifact({"corpus": "ohada", "query": ""}, artifact)


@pytest.mark.asyncio
async def test_cron_endpoint_rejects_missing_configuration(monkeypatch):
    monkeypatch.setattr(watch.settings, "cron_secret", "")
    with pytest.raises(HTTPException) as exc:
        await watch.run_watch_engine(authorization="Bearer anything")
    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_cron_endpoint_rejects_wrong_secret(monkeypatch):
    monkeypatch.setattr(watch.settings, "cron_secret", "a" * 32)
    with pytest.raises(HTTPException) as exc:
        await watch.run_watch_engine(authorization="Bearer wrong")
    assert exc.value.status_code == 401
