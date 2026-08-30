from pathlib import Path

from baobab.api.routes.legal import _json_field


def test_json_field_normalizes_asyncpg_json_text():
    assert _json_field('[{"type":"SOURCE_DOCUMENT"}]', []) == [
        {"type": "SOURCE_DOCUMENT"}
    ]
    assert _json_field("invalid", []) == []
    assert _json_field(None, {}) == {}


def test_case_brief_migration_keeps_machine_work_to_review():
    migration = (
        Path(__file__).parents[1]
        / "baobab"
        / "db"
        / "migrations"
        / "015_case_law_briefs.sql"
    ).read_text(encoding="utf-8")
    assert "legal_case_briefs" in migration
    assert "LEGACY_METADATA', 'TO_REVIEW'" in migration
    assert "future_evidence" in migration
    assert "reviewed_by" in migration
