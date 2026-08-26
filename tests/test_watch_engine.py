from datetime import date

import pytest
from fastapi import HTTPException

from baobab.api.routes import watch
from baobab.watch_engine import (
    Artifact,
    WATCH_SOURCES,
    _parse_french_date,
    parse_cima_crca,
    parse_ohada_biblio,
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
