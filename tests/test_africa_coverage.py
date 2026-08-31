from pathlib import Path

from baobab.core.africa import AFRICAN_COUNTRIES, OHADA_COUNTRY_CODES, africa_country_payload


def test_africa_registry_contains_54_unique_countries():
    codes = [code for code, _ in AFRICAN_COUNTRIES]
    assert len(codes) == 54
    assert len(set(codes)) == 54


def test_ohada_registry_contains_17_members_and_cameroon():
    assert len(OHADA_COUNTRY_CODES) == 17
    assert {"CM", "CI", "SN", "CD"}.issubset(OHADA_COUNTRY_CODES)
    cameroon = next(item for item in africa_country_payload() if item["code"] == "CM")
    assert cameroon == {"code": "CM", "name": "Cameroun", "ohada_member": True}


def test_client_has_country_coverage_and_ohada_matter_views():
    html = (Path(__file__).parents[1] / "baobab" / "static" / "index.html").read_text(
        encoding="utf-8"
    )
    assert 'id="tab-afrique"' in html
    assert "Sélectionnez un pays" in html
    assert "loadAfricaCoverage" in html
    assert "/api/v1/legal/africa/coverage" in html
    assert "/api/v1/legal/ohada/coverage" in html
