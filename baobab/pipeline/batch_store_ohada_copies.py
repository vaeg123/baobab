"""Convertit et stocke les copies recherchables des PDF OHADA déjà acquis."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import tempfile
from pathlib import Path

from baobab.api.routes.accounts import _connect_db
from baobab.pipeline.build_searchable_legal_copy import build_copy
from baobab.pipeline.store_legal_ocr_bundle import store_bundle

TYPE_PREFIXES = {
    "arret-ccja-": "arret_ccja",
    "ordonnance-ccja-": "ordonnance_ccja",
    "avis-ccja-": "avis_ccja",
}


def source_url_index(input_dir: Path) -> dict[str, str]:
    manifest = input_dir.with_suffix(".json")
    if not manifest.exists():
        return {}
    records = json.loads(manifest.read_text(encoding="utf-8"))
    return {
        Path(record["local_pdf"]).name: record["source_url"]
        for record in records
        if record.get("local_pdf") and record.get("source_url")
    }


def identity_from_filename(path: Path) -> tuple[str, str, str] | None:
    stem = path.stem
    document_type = next((kind for prefix, kind in TYPE_PREFIXES.items() if stem.startswith(prefix)), None)
    if not document_type:
        return None
    match = re.search(r"CCJA-(\d{1,4})-(\d{4})(?:-|$)", stem, re.IGNORECASE)
    if not match:
        return None
    number = match.group(1).lstrip("0") or "0"
    return document_type, number, match.group(2)


async def resolve_document(connection, path: Path, source_urls: dict[str, str] | None = None):
    source_url = (source_urls or {}).get(path.name)
    if source_url:
        row = await connection.fetchrow(
            """SELECT d.document_id,c.id AS corpus_id,c.ref,c.titre,
                      EXISTS(SELECT 1 FROM legal_document_renditions r
                             WHERE r.document_id=d.document_id AND r.rendition_type='SEARCHABLE_PDF') AS stored
               FROM legal_documents d JOIN legal_corpus c ON c.id=d.legacy_corpus_id
               WHERE c.source_url=$1
               ORDER BY c.created_at LIMIT 1""",
            source_url,
        )
        if row:
            return dict(row)
    identity = identity_from_filename(path)
    if not identity:
        return None
    document_type, number, year = identity
    rows = await connection.fetch(
        """SELECT d.document_id,c.id AS corpus_id,c.ref,c.titre,
                  EXISTS(SELECT 1 FROM legal_document_renditions r
                         WHERE r.document_id=d.document_id AND r.rendition_type='SEARCHABLE_PDF') AS stored
           FROM legal_documents d JOIN legal_corpus c ON c.id=d.legacy_corpus_id
           WHERE c.type=$1 AND EXTRACT(YEAR FROM c.date_decision)=$2::int
             AND (c.ref ~* $3 OR c.titre ~* $3)
           ORDER BY CASE WHEN c.ref ~* $4 THEN 0 ELSE 1 END,c.created_at LIMIT 5""",
        document_type, int(year), rf"(^|[^0-9])0*{re.escape(number)}([^0-9]|$)",
        rf"CCJA[^0-9]*0*{re.escape(number)}[/\-]{year}",
    )
    return dict(rows[0]) if rows else None


async def repair_mislinked_renditions(connection, files: list[Path], source_urls: dict[str, str]) -> int:
    expected_by_sha: dict[str, set[str]] = {}
    for path in files:
        expected = await resolve_document(connection, path, source_urls)
        if expected:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            expected_by_sha.setdefault(digest, set()).add(str(expected["document_id"]))
    removed = 0
    for digest, expected_ids in expected_by_sha.items():
        rows = await connection.fetch(
            """SELECT rendition_id,document_id::text AS document_id
               FROM legal_document_renditions WHERE metadata->>'original_sha256'=$1""",
            digest,
        )
        incorrect_ids = [row["rendition_id"] for row in rows if row["document_id"] not in expected_ids]
        if incorrect_ids:
            result = await connection.execute(
                "DELETE FROM legal_document_renditions WHERE rendition_id=ANY($1::uuid[])",
                incorrect_ids,
            )
            removed += int(result.rsplit(" ", 1)[-1])
    return removed


async def canonical_coverage(connection, files: list[Path], source_urls: dict[str, str]) -> tuple[int, int]:
    expected_ids = set()
    for path in files:
        document = await resolve_document(connection, path, source_urls)
        if document:
            expected_ids.add(str(document["document_id"]))
    if not expected_ids:
        return 0, 0
    covered = await connection.fetchval(
        """SELECT count(DISTINCT document_id) FROM legal_document_renditions
           WHERE rendition_type='SEARCHABLE_PDF' AND document_id=ANY($1::uuid[])""",
        list(expected_ids),
    )
    return len(expected_ids), int(covered)


async def run_batch(
    input_dir: Path, tessdata_dir: Path, *, dpi: int = 180, repair_mislinked: bool = False,
) -> dict:
    files = sorted(input_dir.glob("*.pdf"))
    source_urls = source_url_index(input_dir)
    report = {"scanned": len(files), "stored": 0, "skipped": 0, "unmatched": 0,
              "failed": 0, "mislinked_renditions_removed": 0, "errors": []}
    connection = await _connect_db()
    try:
        if repair_mislinked:
            report["mislinked_renditions_removed"] = await repair_mislinked_renditions(
                connection, files, source_urls,
            )
        for index, path in enumerate(files, start=1):
            try:
                document = await resolve_document(connection, path, source_urls)
                if not document:
                    report["unmatched"] += 1
                    print(f"[{index}/{len(files)}] UNMATCHED {path.name}", flush=True)
                    continue
                if document["stored"]:
                    report["skipped"] += 1
                    print(f"[{index}/{len(files)}] SKIP {path.name}", flush=True)
                    continue
                with tempfile.TemporaryDirectory(prefix="baobab-ocr-") as temporary:
                    bundle_dir = Path(temporary)
                    build_copy(path, bundle_dir, language="fra+eng", dpi=dpi, tessdata_dir=tessdata_dir)
                    await store_bundle(str(document["document_id"]), path, bundle_dir)
                report["stored"] += 1
                print(f"[{index}/{len(files)}] STORED {path.name}", flush=True)
            except Exception as exc:
                report["failed"] += 1
                report["errors"].append({"file": path.name, "error": f"{type(exc).__name__}: {exc}"[:500]})
                print(f"[{index}/{len(files)}] FAILED {path.name}: {type(exc).__name__}", flush=True)
    finally:
        expected, covered = await canonical_coverage(connection, files, source_urls)
        report["canonical_documents"] = expected
        report["canonical_documents_covered"] = covered
        await connection.close()
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("--tessdata-dir", type=Path, required=True)
    parser.add_argument("--dpi", type=int, default=180)
    parser.add_argument("--repair-mislinked", action="store_true")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run_batch(
        args.input_dir, args.tessdata_dir, dpi=args.dpi, repair_mislinked=args.repair_mislinked,
    )), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
