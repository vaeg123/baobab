"""Audit et projection progressive de legal_corpus vers Baobab Sources."""

from __future__ import annotations

import argparse
import asyncio
import json
import os

import asyncpg
from dotenv import load_dotenv


MIRROR_SQL = """
INSERT INTO legal_documents (
    legacy_corpus_id,source_code,jurisdiction_code,official_identifier,official_citation,
    document_type,title,issuing_institution,country_code,language_code,publication_date,
    effective_from,effective_to,legal_status,authority_level,editorial_status,
    validation_level,source_url,original_file_uri,normalized_text,normalized_sha256,
    license_name,rights_snapshot,metadata,first_received_at,last_verified_at
)
SELECT c.id,
       CASE WHEN s.code IS NOT NULL THEN c.source_code ELSE NULL END,
       c.jurisdiction_code,c.official_identifier,c.official_citation,c.type,
       COALESCE(NULLIF(c.titre,''),NULLIF(c.ref,''),'Document sans titre'),c.juridiction,
       c.country_code,c.language_code,c.publication_date,c.effective_from,c.effective_to,
       c.legal_status,
       CASE
         WHEN c.jurisdiction_code LIKE '%.CCJA' THEN 'REGIONAL_SUPREME_COURT'
         WHEN c.type ILIKE '%loi%' OR c.type ILIKE '%acte_uniforme%' THEN 'LEGISLATION'
         ELSE 'UNCLASSIFIED'
       END,
       c.editorial_status,
       CASE
         WHEN c.source_tier='OFFICIAL_PRIMARY' AND c.source_verified_at IS NOT NULL THEN 'SOURCE_VERIFIED'
         WHEN c.source_tier='OFFICIAL_PRIMARY' THEN 'OFFICIAL_ORIGIN_TO_VERIFY'
         ELSE 'UNVERIFIED'
       END,
       c.source_url,c.source_pdf_url,c.texte_integral,c.content_checksum,c.source_license,
       jsonb_build_object(
          'display',COALESCE(s.display_rights,'UNKNOWN'),
          'indexing',COALESCE(s.indexing_rights,'UNKNOWN'),
          'analysis',COALESCE(s.analysis_rights,'UNKNOWN'),
          'agreement_status',COALESCE(s.agreement_status,'TO_REVIEW')
       ),
       COALESCE(c.metadata,'{}'::jsonb) || jsonb_build_object('legacy_ref',c.ref,'migration','legal_corpus'),
       c.created_at,c.source_verified_at
FROM legal_corpus c
LEFT JOIN legal_sources s ON s.code=c.source_code
ON CONFLICT (legacy_corpus_id) DO UPDATE SET
    source_code=EXCLUDED.source_code,
    jurisdiction_code=EXCLUDED.jurisdiction_code,
    official_identifier=EXCLUDED.official_identifier,
    title=EXCLUDED.title,
    normalized_text=EXCLUDED.normalized_text,
    normalized_sha256=EXCLUDED.normalized_sha256,
    rights_snapshot=EXCLUDED.rights_snapshot,
    updated_at=NOW()
"""


async def run(apply: bool = False) -> dict:
    load_dotenv(".env.local")
    load_dotenv(".env")
    connection = await asyncpg.connect(os.environ["DATABASE_URL"])
    try:
        metrics = await connection.fetchrow(
            """
            SELECT count(*) AS scanned,
                   count(*) FILTER (WHERE coalesce(titre,'')<>'' AND coalesce(texte_integral,'')<>'') AS usable,
                   count(*) FILTER (WHERE coalesce(texte_integral,'')='') AS incomplete,
                   count(*) FILTER (WHERE coalesce(source_license,'')='' OR source_tier='UNVERIFIED') AS rights_review,
                   count(*) FILTER (WHERE coalesce(source_url,'')='') AS without_source_url,
                   count(*) FILTER (WHERE content_checksum IS NOT NULL) AS checksummed
            FROM legal_corpus
            """
        )
        duplicates = await connection.fetchval(
            """
            SELECT COALESCE(sum(n-1),0)::int FROM (
                SELECT count(*) AS n FROM legal_corpus
                WHERE coalesce(source_url,'')<>'' GROUP BY source_url HAVING count(*)>1
            ) duplicate_groups
            """
        )
        by_source = await connection.fetch(
            """
            SELECT COALESCE(source_code,'UNMAPPED') AS source_code,count(*) AS documents
            FROM legal_corpus GROUP BY COALESCE(source_code,'UNMAPPED') ORDER BY documents DESC
            """
        )
        report = {
            **dict(metrics),
            "duplicates_suspected": duplicates,
            "by_source": [dict(row) for row in by_source],
            "projection_applied": apply,
        }
        if not apply:
            return report

        async with connection.transaction():
            await connection.execute(MIRROR_SQL)
            await connection.execute(
                """
                INSERT INTO legal_source_acquisitions (
                    source_code,document_id,external_document_id,channel,received_by,original_uri,
                    original_sha256,integrity_status,rights_status,processing_status,transformations
                )
                SELECT d.source_code,d.document_id,COALESCE(d.official_identifier,d.document_id::text),
                       'LEGACY_IMPORT','baobab-migration',d.original_file_uri,d.original_sha256,
                       CASE WHEN d.original_sha256 IS NULL THEN 'TO_VERIFY' ELSE 'HASH_RECORDED' END,
                       CASE WHEN d.rights_snapshot->>'agreement_status'='ACTIVE' THEN 'AUTHORIZED' ELSE 'TO_REVIEW' END,
                       'MIGRATED',jsonb_build_array('LEGACY_CORPUS_PROJECTION')
                FROM legal_documents d
                WHERE d.legacy_corpus_id IS NOT NULL
                  AND NOT EXISTS (
                    SELECT 1 FROM legal_source_acquisitions a
                    WHERE a.document_id=d.document_id AND a.channel='LEGACY_IMPORT'
                  )
                """
            )
            await connection.execute(
                """
                INSERT INTO legal_corpus_audit_runs (
                    scope,status,documents_scanned,documents_usable,documents_incomplete,
                    documents_rights_review,duplicates_suspected,report,completed_at
                ) VALUES ('{"source":"legal_corpus","mode":"foundation"}'::jsonb,'COMPLETED',$1,$2,$3,$4,$5,$6::jsonb,NOW())
                """,
                metrics["scanned"], metrics["usable"], metrics["incomplete"],
                metrics["rights_review"], duplicates, json.dumps(report),
            )
        return report
    finally:
        await connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit du corpus et projection vers Baobab Sources")
    parser.add_argument("--apply", action="store_true", help="Projette legal_corpus dans le modèle canonique")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(args.apply)), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
