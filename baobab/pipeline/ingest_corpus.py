#!/usr/bin/env python3
"""
Pipeline d'ingestion du corpus juridique dans PostgreSQL / pgvector.

Sources supportées :
  - data/raw/crca_decisions.json  (scraper CRCA)
  - data/raw/ccja_arrets.json     (scraper CCJA)
  - data/raw/ohada_actes.json     (downloader OHADA, PDFs locaux)

Usage:
    python -m baobab.pipeline.ingest_corpus
    python -m baobab.pipeline.ingest_corpus --source crca
    python -m baobab.pipeline.ingest_corpus --source ohada --embed
"""

import argparse
import asyncio
import json
import logging
import os
import re
from datetime import date
from pathlib import Path
from typing import Any

import asyncpg

log = logging.getLogger("ingest_corpus")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "raw"
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://baobab:baobab@localhost:5432/baobab")


def parse_date(s: str) -> date | None:
    if not s:
        return None
    for pat in [
        r"(\d{4})-(\d{2})-(\d{2})",
        r"(\d{2})/(\d{2})/(\d{4})",
        r"(\d{2})-(\d{2})-(\d{4})",
        r"(\d{4})",
    ]:
        m = re.search(pat, str(s))
        if m:
            g = m.groups()
            if len(g) == 3:
                try:
                    if len(g[0]) == 4:
                        return date(int(g[0]), int(g[1]), int(g[2]))
                    else:
                        return date(int(g[2]), int(g[1]), int(g[0]))
                except ValueError:
                    continue
            elif len(g) == 1:
                return date(int(g[0]), 1, 1)
    return None


def extract_pdf_text(pdf_path: str) -> str:
    """Extrait le texte d'un PDF local via pdfplumber (optionnel)."""
    if not pdf_path or not Path(pdf_path).exists():
        return ""
    try:
        import pdfplumber
        text_parts = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages[:100]:  # cap à 100 pages
                t = page.extract_text()
                if t:
                    text_parts.append(t)
        return "\n".join(text_parts)[:100_000]
    except ImportError:
        log.warning("pdfplumber non installé — texte PDF non extrait")
        return ""
    except Exception as exc:
        log.warning(f"Erreur extraction PDF {pdf_path}: {exc}")
        return ""


def record_from_raw(raw: dict) -> dict:
    """Normalise un enregistrement brut en record prêt pour legal_corpus."""
    texte = raw.get("texte_integral", "")
    # Enrichir avec texte PDF si disponible et texte absent
    if not texte and raw.get("local_pdf"):
        texte = extract_pdf_text(raw["local_pdf"])

    # Mots-clés auto depuis domaine + titre
    mots_cles = raw.get("mots_cles") or []
    if not mots_cles and raw.get("domaine"):
        mots_cles = [kw.strip() for kw in re.split(r"[/,;]", raw["domaine"]) if kw.strip()]

    return {
        "ref": raw.get("ref", "") or "",
        "type": raw.get("type", ""),
        "corpus": raw.get("corpus", ""),
        "juridiction": raw.get("juridiction", ""),
        "titre": raw.get("titre", "") or "",
        "date_decision": parse_date(raw.get("date_str") or raw.get("date") or ""),
        "parties": json.dumps(raw.get("parties") or {}),
        "pays": raw.get("pays", "") or "",
        "domaine": raw.get("domaine", "") or "",
        "resume": raw.get("resume", "") or "",
        "texte_integral": texte,
        "mots_cles": mots_cles,
        "source_url": raw.get("source_url", "") or "",
        "source_pdf_url": raw.get("source_pdf_url", "") or "",
        "sanction": raw.get("sanction", "") or "",
        "articles_cites": raw.get("articles_cites") or [],
        "metadata": json.dumps(raw.get("metadata") or {}),
    }


INSERT_SQL = """
INSERT INTO legal_corpus (
    ref, type, corpus, juridiction, titre, date_decision,
    parties, pays, domaine, resume, texte_integral,
    mots_cles, source_url, source_pdf_url, sanction,
    articles_cites, metadata
) VALUES (
    $1, $2, $3, $4, $5, $6,
    $7::jsonb, $8, $9, $10, $11,
    $12::text[], $13, $14, $15,
    $16::text[], $17::jsonb
)
ON CONFLICT DO NOTHING
"""


async def ingest_file(conn: asyncpg.Connection, path: Path) -> int:
    if not path.exists():
        log.warning(f"Fichier introuvable : {path}")
        return 0

    with open(path, encoding="utf-8") as f:
        records = json.load(f)

    log.info(f"Ingestion {path.name} : {len(records)} enregistrements")
    count = 0
    for raw in records:
        rec = record_from_raw(raw)
        try:
            await conn.execute(
                INSERT_SQL,
                rec["ref"], rec["type"], rec["corpus"], rec["juridiction"],
                rec["titre"], rec["date_decision"],
                rec["parties"], rec["pays"], rec["domaine"],
                rec["resume"], rec["texte_integral"],
                rec["mots_cles"], rec["source_url"], rec["source_pdf_url"],
                rec["sanction"], rec["articles_cites"], rec["metadata"],
            )
            count += 1
        except Exception as exc:
            log.warning(f"  Erreur insert {rec['ref']}: {exc}")

    log.info(f"  {count} / {len(records)} insérés")
    return count


async def run(source: str | None = None):
    files = {
        "crca": DATA_DIR / "crca_decisions.json",
        "ccja": DATA_DIR / "ccja_arrets.json",
        "ohada": DATA_DIR / "ohada_actes.json",
    }

    to_ingest = [files[source]] if source and source in files else list(files.values())

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        total = 0
        for path in to_ingest:
            total += await ingest_file(conn, path)
        log.info(f"Ingestion terminée : {total} enregistrements insérés au total")
    finally:
        await conn.close()


def main():
    parser = argparse.ArgumentParser(description="Ingestion corpus juridique → PostgreSQL")
    parser.add_argument(
        "--source", choices=["crca", "ccja", "ohada"],
        help="Source à ingérer (défaut: toutes)", default=None
    )
    args = parser.parse_args()
    asyncio.run(run(source=args.source))


if __name__ == "__main__":
    main()
