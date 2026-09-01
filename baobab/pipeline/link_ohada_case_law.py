"""Relie les décisions aux articles OHADA uniquement sur citation textuelle explicite."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import unicodedata

from baobab.api.routes.accounts import _connect_db
from baobab.pipeline.ohada_catalog import ACTS, is_applicable

ALIASES = {reference: metadata["aliases"] for reference, metadata in ACTS.items()}
ARTICLE_LIST_RE = re.compile(
    r"\bARTICLES?\s+(?:PREMIER|1ER|1ER\.|((?:\d+(?:[.-]\d+)?(?:\s*(?:,|;|ET|A|AU)\s*)?){1,20}))",
    re.IGNORECASE,
)


def normalized_text(text: str) -> str:
    value = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().upper()
    return re.sub(r"[ \t]+", " ", value)


def extract_explicit_citations(text: str, aliases: tuple[str, ...]) -> list[dict]:
    normalized = normalized_text(text or "")
    citations = {}
    for alias in aliases:
        for alias_match in re.finditer(rf"\b{re.escape(alias)}\b", normalized):
            start, end = max(0, alias_match.start() - 240), min(len(normalized), alias_match.end() + 240)
            window = normalized[start:end]
            for article_match in ARTICLE_LIST_RE.finditer(window):
                raw_numbers = article_match.group(1) or "1"
                for number in re.findall(r"\d+(?:[.-]\d+)?", raw_numbers):
                    evidence_start = max(0, start + article_match.start() - 50)
                    evidence_end = min(len(normalized), start + article_match.end() + 120)
                    citations.setdefault(number.rstrip("."), {
                        "number": number.rstrip("."),
                        "excerpt": normalized[evidence_start:evidence_end].strip(),
                        "alias": alias,
                    })
    return list(citations.values())


async def link(*, apply: bool) -> dict:
    connection = await _connect_db()
    try:
        acts = await connection.fetch(
            """SELECT c.id,c.ref,coalesce(c.publication_date,c.date_decision) AS effective_date,
                      array_agg(p.provision_number) AS article_numbers
               FROM legal_corpus c JOIN legal_provisions p ON p.document_id=c.id
               WHERE c.corpus='ohada' AND c.type='acte_uniforme'
                 AND p.verification_status='AUTOMATED_PARTIAL_SOURCE'
               GROUP BY c.id"""
        )
        decisions = await connection.fetch(
            """SELECT id,ref,date_decision,texte_integral FROM legal_corpus
               WHERE corpus='ohada' AND lower(type) ~ '(arret|arrêt|avis|ordonnance|decision|décision)'
                 AND coalesce(texte_integral,'')<>''"""
        )
        links = []
        for act in acts:
            aliases = ALIASES.get(act["ref"], ())
            if not aliases:
                continue
            available = set(act["article_numbers"] or [])
            for decision in decisions:
                if not is_applicable(act["ref"], decision["date_decision"], act["effective_date"]):
                    continue
                for citation in extract_explicit_citations(decision["texte_integral"], aliases):
                    if citation["number"] in available:
                        links.append((decision, act, citation))
        if apply:
            async with connection.transaction():
                await connection.execute(
                    "DELETE FROM legal_document_relations WHERE relation_type='EXPLICITLY_CITES_PROVISION' AND evidence->>'method'='DETERMINISTIC_OHADA_CITATION_V1'"
                )
                if links:
                    await connection.executemany(
                        """INSERT INTO legal_document_relations
                           (source_document_id,target_document_id,relation_type,provision_ref,
                            confidence_score,evidence)
                           VALUES($1,$2,'EXPLICITLY_CITES_PROVISION',$3,95,$4::jsonb)
                           ON CONFLICT(source_document_id,target_document_id,relation_type,provision_ref)
                           DO UPDATE SET confidence_score=EXCLUDED.confidence_score,evidence=EXCLUDED.evidence""",
                        [
                            (decision["id"], act["id"], f"Article {citation['number']}", json.dumps({
                                "method": "DETERMINISTIC_OHADA_CITATION_V1",
                                "alias": citation["alias"], "excerpt": citation["excerpt"],
                                "human_reviewed": False,
                            }))
                            for decision, act, citation in links
                        ],
                    )
        return {
            "acts_scanned": len(acts), "decisions_scanned": len(decisions),
            "explicit_links": len(links), "human_reviewed": False, "applied": apply,
        }
    finally:
        await connection.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(link(apply=args.apply)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
