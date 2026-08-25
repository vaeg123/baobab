from fastapi.testclient import TestClient

from baobab.api.main import app
from baobab.api.routes.legal import AnalyzeRequest, SearchRequest
from baobab.core.jurisdictions import JURISDICTION_BY_CODE, SOURCE_BY_CODE

client = TestClient(app)


def test_registry_contains_france_europe_echr_and_ohada():
    for code in ("FR", "EU", "ECHR", "OHADA", "CIMA", "UN.ICJ"):
        assert code in JURISDICTION_BY_CODE


def test_official_sources_have_explicit_jurisdiction():
    assert SOURCE_BY_CODE["FR.LEGIFRANCE"].jurisdiction_code == "FR"
    assert SOURCE_BY_CODE["FR.JUDILIBRE"].jurisdiction_code == "FR.CASS"
    assert SOURCE_BY_CODE["EU.EURLEX"].jurisdiction_code == "EU"
    assert SOURCE_BY_CODE["ECHR.HUDOC"].jurisdiction_code == "ECHR.COURT"


def test_jurisdiction_discovery_endpoint_filters_france_pack():
    response = client.get("/api/v1/legal/jurisdictions", params={"pack": "france"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 4
    assert {item["code"] for item in payload["results"]} >= {"FR", "FR.CASS", "FR.CE", "FR.CC"}


def test_source_discovery_endpoint_exposes_only_public_metadata():
    response = client.get("/api/v1/legal/sources", params={"jurisdiction": "FR"})
    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result["code"] == "FR.LEGIFRANCE"
    assert "password" not in result
    assert "secret" not in result


def test_search_contract_accepts_international_legal_context():
    request = SearchRequest(
        query="responsabilité du fait des produits",
        corpus="fr",
        country_code="FR",
        jurisdiction_code="FR.CASS",
        language_code="fr",
        legal_status="IN_FORCE",
        as_of="2026-08-25",
    )
    assert request.jurisdiction_code == "FR.CASS"
    assert request.as_of == "2026-08-25"


def test_analyze_contract_carries_jurisdiction_and_temporal_context():
    request = AnalyzeRequest(
        question="Quelle règle était applicable à la date des faits ?",
        jurisdiction_code="FR",
        country_code="FR",
        as_of="2025-01-15",
    )
    assert request.country_code == "FR"
    assert request.as_of == "2025-01-15"
