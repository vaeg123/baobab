"""Répare uniquement les erreurs déterministes des fiches jurisprudentielles."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re

from baobab.api.routes.accounts import _connect_db

DISPOSITION_RE = re.compile(
    r"\b(?:PAR\s+CES\s+(?:MOTIFS|CAUSES)|D[ÉE]CIDE|LA\s+COUR[^\n]{0,80}(?:STATUANT|D[ÉE]CIDE))\b[\s\S]{0,2200}",
    re.IGNORECASE,
)


def extract_disposition(text: str | None) -> str:
    if not text:
        return ""
    match = DISPOSITION_RE.search(text.replace("\r", ""))
    return match.group(0).strip() if match else ""


async def repair(*, apply: bool) -> dict:
    connection = await _connect_db()
    try:
        false_case_ids = await connection.fetch(
            """
            SELECT b.brief_id
            FROM legal_case_briefs b
            JOIN legal_documents d ON d.document_id=b.document_id
            JOIN legal_corpus c ON c.id=d.legacy_corpus_id
            WHERE (c.corpus='cm' AND lower(c.type)='ordonnance')
               OR (c.corpus='ohada' AND lower(c.type)='arret_ccja' AND
                   c.titre ~* '(comment[ée]s|regards critiques|chronique|analyse crois[ée]e)')
            """
        )
        source_ids = await connection.fetch(
            """
            SELECT d.document_id
            FROM legal_documents d JOIN legal_corpus c ON c.id=d.legacy_corpus_id
            WHERE d.source_code IS NULL AND c.corpus='ohada'
              AND c.source_url LIKE 'https://biblio.ohada.org/%'
            """
        )
        text_rows = await connection.fetch(
            """
            SELECT b.brief_id,d.document_id,c.texte_integral
            FROM legal_case_briefs b
            JOIN legal_documents d ON d.document_id=b.document_id
            JOIN legal_corpus c ON c.id=d.legacy_corpus_id
            WHERE coalesce(c.texte_integral,'')<>''
              AND (coalesce(b.holding,'')='' OR coalesce(b.exact_disposition,'')='')
            """
        )
        extracted = []
        for row in text_rows:
            disposition = extract_disposition(row["texte_integral"])
            if disposition:
                extracted.append((row["brief_id"], row["document_id"], disposition))

        synced_texts = await connection.fetch(
            """
            SELECT d.document_id,c.texte_integral
            FROM legal_documents d JOIN legal_corpus c ON c.id=d.legacy_corpus_id
            WHERE coalesce(c.texte_integral,'')<>'' AND (
                coalesce(d.normalized_text,'')<>c.texte_integral OR d.normalized_sha256 IS NULL
            )
            """
        )
        report = {
            "not_case_law_removed": len(false_case_ids),
            "official_sources_reattached": len(source_ids),
            "dispositions_extracted": len(extracted),
            "canonical_texts_synced": len(synced_texts),
            "legal_interpretation_performed": False,
        }
        if apply:
            async with connection.transaction():
                if false_case_ids:
                    await connection.execute(
                        "DELETE FROM legal_case_briefs WHERE brief_id=ANY($1::uuid[])",
                        [row["brief_id"] for row in false_case_ids],
                    )
                if source_ids:
                    await connection.execute(
                        """UPDATE legal_documents SET source_code='OHADA.BIBLIO',updated_at=NOW()
                           WHERE document_id=ANY($1::uuid[])""",
                        [row["document_id"] for row in source_ids],
                    )
                if extracted:
                    await connection.executemany(
                        """UPDATE legal_case_briefs
                           SET exact_disposition=COALESCE(NULLIF(exact_disposition,''),$3),
                               holding=COALESCE(NULLIF(holding,''),$3),
                               extraction_method='DETERMINISTIC_SOURCE_EXTRACTION',
                               evidence_refs=evidence_refs || $4::jsonb,updated_at=NOW()
                           WHERE brief_id=$1 AND document_id=$2""",
                        [
                            (brief_id, document_id, disposition, json.dumps([{
                                "type": "EXACT_SOURCE_EXTRACT",
                                "document_id": str(document_id),
                                "marker": disposition[:80],
                            }]))
                            for brief_id, document_id, disposition in extracted
                        ],
                    )
                if synced_texts:
                    await connection.executemany(
                        """UPDATE legal_documents SET normalized_text=$2,
                           normalized_sha256=$3,updated_at=NOW() WHERE document_id=$1""",
                        [
                            (row["document_id"], row["texte_integral"],
                             hashlib.sha256(row["texte_integral"].encode("utf-8")).hexdigest())
                            for row in synced_texts
                        ],
                    )
        return report
    finally:
        await connection.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(repair(apply=args.apply)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
