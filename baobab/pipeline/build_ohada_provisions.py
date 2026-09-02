"""Découpe les Actes uniformes OHADA identifiés en articles traçables."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import unicodedata

from baobab.api.routes.accounts import _connect_db
from baobab.pipeline.ohada_catalog import ACTS, effective_bounds

ARTICLE_RE = re.compile(r"(?im)^\s*Article\s+(premier|\d+[A-Za-z.-]*)\b[^\n]*")
EXPECTED_MARKERS = {
    reference: tuple(metadata.get("identity_markers", metadata["aliases"][1:]))
    for reference, metadata in ACTS.items()
}


def normalized_identity(text: str) -> str:
    value = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().upper()
    return re.sub(r"[^A-Z0-9]+", " ", value)


def identity_matches(reference: str, text: str) -> bool:
    markers = EXPECTED_MARKERS.get(reference)
    if not markers:
        return False
    head = normalized_identity(text[:5000])
    return all(marker in head for marker in markers)


def extract_articles(text: str) -> list[dict]:
    matches = list(ARTICLE_RE.finditer(text or ""))
    articles = []
    seen = set()
    for index, match in enumerate(matches):
        number = match.group(1).lower().rstrip(".-")
        number = "1" if number == "premier" else number
        if number in seen:
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        content = text[match.end():end].strip()
        if len(content) < 20:
            continue
        seen.add(number)
        articles.append({"number": number, "heading": match.group(0).strip(), "content": content})
    return articles


async def build(*, apply: bool) -> dict:
    connection = await _connect_db()
    try:
        rows = await connection.fetch(
            """SELECT id,ref,titre,texte_integral,publication_date,date_decision,source_url
               FROM legal_corpus WHERE corpus='ohada' AND type='acte_uniforme'
                 AND coalesce(texte_integral,'')<>'' ORDER BY ref"""
        )
        accepted, rejected, article_total = [], [], 0
        for row in rows:
            text = row["texte_integral"] or ""
            if not identity_matches(row["ref"], text):
                rejected.append({"ref": row["ref"], "reason": "IDENTITY_MISMATCH"})
                continue
            articles = extract_articles(text)
            if not articles:
                rejected.append({"ref": row["ref"], "reason": "NO_ARTICLES"})
                continue
            accepted.append((row, articles))
            article_total += len(articles)

        if apply:
            async with connection.transaction():
                for row, articles in accepted:
                    valid_from, valid_until = effective_bounds(
                        row["ref"], row["publication_date"] or row["date_decision"]
                    )
                    await connection.execute(
                        "DELETE FROM legal_provisions WHERE document_id=$1 AND verification_status='AUTOMATED_PARTIAL_SOURCE'",
                        row["id"],
                    )
                    await connection.executemany(
                        """INSERT INTO legal_provisions
                           (document_id,provision_number,heading,content,valid_from,valid_until,status,
                            source_url,verification_status,content_checksum)
                           VALUES($1,$2,$3,$4,$5,$6,'PARTIAL_SOURCE',$7,
                                  'AUTOMATED_PARTIAL_SOURCE',$8)""",
                        [
                            (row["id"], article["number"], article["heading"], article["content"],
                             valid_from, valid_until, row["source_url"],
                             hashlib.sha256(article["content"].encode()).hexdigest())
                            for article in articles
                        ],
                    )
        return {
            "documents_scanned": len(rows), "documents_accepted": len(accepted),
            "documents_rejected": rejected, "articles_extracted": article_total,
            "coverage_complete": False, "applied": apply,
        }
    finally:
        await connection.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(build(apply=args.apply)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
