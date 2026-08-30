from pathlib import Path

from baobab.api.routes.sources import SourceUpdate


def test_source_authority_grade_is_constrained():
    assert SourceUpdate(authority_grade="A").authority_grade == "A"


def test_cameroon_sources_separate_authority_and_applicability():
    sql = (
        Path(__file__).parents[1] / "baobab" / "db" / "migrations"
        / "017_cameroon_source_authority.sql"
    ).read_text(encoding="utf-8")
    assert "authenticity_status" in sql
    assert "coverage_status" in sql
    assert "applicability_status" in sql
    assert "CM.JO" in sql
    assert "CM.MINJUSTICE.LEGALIS" in sql
