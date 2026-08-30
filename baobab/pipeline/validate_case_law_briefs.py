"""Prévalidation factuelle et traçable des fiches de jurisprudence."""

from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter
from pathlib import Path

from baobab.api.routes.accounts import _connect_db

MIGRATION = Path(__file__).resolve().parents[1] / "db" / "migrations" / "016_case_brief_validation.sql"
ALGORITHM_VERSION = "document-check-v1"


def evaluate_brief(record: dict) -> tuple[int, dict[str, bool]]:
    checks = {
        "source_registered": bool(record.get("source_code")),
        "source_linked": bool(record.get("source_url") or record.get("original_file_uri")),
        "identity_present": bool(record.get("official_identifier") or record.get("legacy_ref")),
        "decision_date_present": bool(record.get("decision_date")),
        "jurisdiction_present": bool(record.get("jurisdiction_code") or record.get("legacy_jurisdiction")),
        "substantial_text": int(record.get("text_length") or 0) >= 500,
        "text_integrity_hashed": bool(record.get("normalized_sha256")),
        "solution_present": len((record.get("holding") or "").strip()) >= 40,
        "disposition_present": len((record.get("exact_disposition") or "").strip()) >= 20,
    }
    weights = {
        "source_registered": 10,
        "source_linked": 10,
        "identity_present": 10,
        "decision_date_present": 10,
        "jurisdiction_present": 10,
        "substantial_text": 15,
        "text_integrity_hashed": 15,
        "solution_present": 15,
        "disposition_present": 5,
    }
    return sum(weights[name] for name, passed in checks.items() if passed), checks


async def validate(*, apply: bool) -> dict:
    connection = await _connect_db()
    try:
        await connection.execute(MIGRATION.read_text(encoding="utf-8"))
        rows = await connection.fetch(
            """
            SELECT b.brief_id,b.holding,b.exact_disposition,d.source_code,d.source_url,
                   d.original_file_uri,d.official_identifier,
                   COALESCE(d.adoption_date,c.date_decision) AS decision_date,
                   d.jurisdiction_code,d.normalized_sha256,length(d.normalized_text) AS text_length,
                   c.ref AS legacy_ref,c.titre AS legacy_title,
                   c.juridiction AS legacy_jurisdiction,c.corpus,c.type AS legacy_type
            FROM legal_case_briefs b
            JOIN legal_documents d ON d.document_id=b.document_id
            LEFT JOIN legal_corpus c ON c.id=d.legacy_corpus_id
            WHERE b.editorial_status <> 'VALIDATED'
            """
        )
        outcomes = []
        failures: Counter[str] = Counter()
        review_groups: Counter[str] = Counter()
        review_examples: dict[str, list[dict]] = {}
        for row in rows:
            data = dict(row)
            score, checks = evaluate_brief(data)
            # Les contrôles fondamentaux doivent tous réussir. Le dispositif
            # exact reste un enrichissement distinct car certains avis n'en ont pas.
            fundamentals = all(checks[name] for name in (
                "source_registered", "identity_present", "decision_date_present",
                "jurisdiction_present", "substantial_text", "text_integrity_hashed",
                "solution_present",
            ))
            verified = fundamentals and score >= 80
            if not verified:
                group = f"{data.get('corpus') or 'unknown'}:{data.get('legacy_type') or 'unknown'}"
                review_groups[group] += 1
                examples = review_examples.setdefault(group, [])
                if len(examples) < 3:
                    examples.append({
                        "title": data.get("legacy_title"),
                        "ref": data.get("legacy_ref"),
                        "failed": [name for name, passed in checks.items() if not passed],
                    })
            for name, passed in checks.items():
                if not passed:
                    failures[name] += 1
            outcomes.append((data["brief_id"], score, checks, verified))

        report = {
            "algorithm_version": ALGORITHM_VERSION,
            "scanned": len(outcomes),
            "document_verified": sum(1 for *_, ok in outcomes if ok),
            "to_review": sum(1 for *_, ok in outcomes if not ok),
            "failed_checks": dict(failures),
            "review_groups": dict(review_groups.most_common(30)),
            "review_examples": review_examples,
            "legal_validation_performed": False,
        }
        if apply:
            async with connection.transaction():
                await connection.executemany(
                    """UPDATE legal_case_briefs
                       SET validation_score=$2,automated_validation=$3::jsonb,
                           editorial_status=CASE
                             WHEN editorial_status IN ('VALIDATED','IN_REVIEW') THEN editorial_status
                             WHEN $4 THEN 'DOCUMENT_VERIFIED' ELSE 'TO_REVIEW' END,
                           document_verified_at=CASE WHEN $4 THEN NOW() ELSE NULL END,
                           updated_at=NOW()
                       WHERE brief_id=$1""",
                    [
                        (brief_id, score, json.dumps(checks), verified)
                        for brief_id, score, checks, verified in outcomes
                    ],
                )
                await connection.execute(
                    """INSERT INTO legal_case_brief_validation_runs
                       (algorithm_version,status,briefs_scanned,briefs_document_verified,
                        briefs_to_review,report,completed_at)
                       VALUES($1,'COMPLETED',$2,$3,$4,$5::jsonb,NOW())""",
                    ALGORITHM_VERSION, report["scanned"], report["document_verified"],
                    report["to_review"], json.dumps(report),
                )
        return report
    finally:
        await connection.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Enregistre les résultats du contrôle")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(validate(apply=args.apply)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
