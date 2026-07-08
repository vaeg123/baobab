#!/usr/bin/env python3
"""
Ingestion des 113 fiches juridiques du dossier lumierejuridiqueabidjan.
Source : C:/Users/yboul/Desktop/lumierejuridiqueabidjan/

Chaque fichier .md est inséré comme un document dans legal_corpus.
Type détecté selon le dossier parent.

Usage:
    python -m baobab.pipeline.ingest_lumiere
"""

import asyncio
import json
import logging
import os
import re
from pathlib import Path

import asyncpg

log = logging.getLogger("ingest_lumiere")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

SOURCE_DIR = Path("C:/Users/yboul/Desktop/lumierejuridiqueabidjan")
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://baobab:baobab@localhost:5432/baobab")

# Mappage dossier → (type, corpus)
FOLDER_MAP = {
    "01_Droit_des_entreprises_Cote_dIvoire": ("synthese", "ci"),
    "02_Droit_OHADA": ("synthese", "ohada"),
    "03_Droit_CIMA": ("synthese", "cima"),
    "04_Jurisprudence_generale": ("decision_tca", "ci"),
    "05_Doctrine_et_recherche": ("doctrine", "ci"),
    "06_Fiches_pratiques": ("synthese", "ci"),
    "07_Modeles_actes_et_documents": ("modele", "ci"),
    "08_Bibliographie_et_sources": ("doctrine", "ci"),
    "09_Droit_famille_patrimoine": ("synthese", "ci"),
}

# Affiner selon le contenu du chemin
def detect_type_corpus(path: Path) -> tuple[str, str]:
    parts = [p.lower() for p in path.parts]
    # CIMA
    if any("cima" in p or "crca" in p or "assurance" in p for p in parts):
        return ("decision_crca" if "crca" in str(path).lower() else "synthese", "cima")
    # OHADA
    if any("ohada" in p or "ccja" in p or "acte_uniforme" in p for p in parts):
        return ("arret_ccja" if "ccja" in str(path).lower() else "synthese", "ohada")
    # TCA / jurisprudence CI
    if "jurisprudence" in str(path).lower() or "04_" in str(path):
        return ("decision_tca", "ci")
    # Défaut
    for folder, mapping in FOLDER_MAP.items():
        if folder.lower() in str(path).lower():
            return mapping
    return ("synthese", "ci")


def detect_domaine(path: Path) -> str:
    s = str(path).lower()
    if "bail" in s:
        return "Bail commercial / Fonds de commerce"
    if "recouvrement" in s or "creance" in s:
        return "Recouvrement de créances"
    if "societe" in s or "sa_" in s or "sarl" in s:
        return "Droit des sociétés"
    if "caution" in s or "assurance" in s:
        return "Cautions / Assurances"
    if "crca" in s or "cima" in s:
        return "Assurances / Contrôle prudentiel CIMA"
    if "ohada" in s or "audcg" in s:
        return "Droit des affaires OHADA"
    if "famille" in s or "succession" in s or "mariage" in s:
        return "Droit de la famille et du patrimoine"
    if "fiscal" in s or "impot" in s:
        return "Fiscalité"
    if "entreprise" in s:
        return "Droit des entreprises"
    return "Droit général"


def parse_md(path: Path) -> dict:
    content = path.read_text(encoding="utf-8", errors="replace")

    # Titre depuis le premier heading H1/H2 ou nom de fichier
    titre_m = re.search(r"^#{1,2}\s+(.+)$", content, re.MULTILINE)
    titre = titre_m.group(1).strip() if titre_m else path.stem.replace("_", " ")

    # Référence depuis le nom de fichier (ex: 01_RG_N°4317_2023_bail → N°4317_2023)
    ref_m = re.search(r"[NnRr][°Gg][\s_]?([\w°\-/]+)", path.name)
    ref = ref_m.group(0).replace("_", " ") if ref_m else path.stem[:30]

    # Date
    date_m = re.search(r"\b(\d{4})\b", path.name)
    date_str = date_m.group(1) if date_m else ""

    # Pays
    pays = "Côte d'Ivoire"
    if "ohada" in str(path).lower() or "ccja" in str(path).lower():
        pays = "OHADA (17 États)"
    if "cima" in str(path).lower() or "crca" in str(path).lower():
        pays = "Zone CIMA (14 États)"

    # Mots-clés depuis les sous-dossiers
    folder_parts = [p for p in path.parts if not p.startswith("0") or len(p) > 3]
    mots_cles = [p.replace("_", " ") for p in path.parts[-3:-1] if len(p) > 3]

    doc_type, corpus = detect_type_corpus(path)
    domaine = detect_domaine(path)

    # Résumé : premier paragraphe non-heading
    resume = ""
    for line in content.split("\n"):
        line = line.strip()
        if line and not line.startswith("#") and not line.startswith("|") and len(line) > 40:
            resume = line[:500]
            break

    return {
        "ref": ref,
        "titre": titre,
        "date_str": date_str,
        "type": doc_type,
        "corpus": corpus,
        "juridiction": "TCA Abidjan" if doc_type == "decision_tca" else "CRCA" if "crca" in doc_type else "OHADA/CCJA" if corpus == "ohada" else "CI",
        "pays": pays,
        "domaine": domaine,
        "resume": resume,
        "texte_integral": content[:80_000],
        "mots_cles": mots_cles,
        "source_url": "",
        "source_pdf_url": "",
        "sanction": "",
        "articles_cites": re.findall(r"Art(?:icle)?\.?\s*(\d+)", content),
        "parties": {},
        "metadata": {"source_file": str(path.relative_to(SOURCE_DIR))},
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

def parse_date(s):
    if not s:
        return None
    try:
        from datetime import date
        return date(int(s[:4]), 1, 1)
    except:
        return None


async def run():
    md_files = list(SOURCE_DIR.rglob("*.md"))
    log.info(f"Fichiers MD trouvés : {len(md_files)}")

    conn = await asyncpg.connect(DATABASE_URL)
    count = 0
    try:
        for path in md_files:
            rec = parse_md(path)
            try:
                await conn.execute(
                    INSERT_SQL,
                    rec["ref"], rec["type"], rec["corpus"], rec["juridiction"],
                    rec["titre"], parse_date(rec["date_str"]),
                    json.dumps(rec["parties"]), rec["pays"], rec["domaine"],
                    rec["resume"], rec["texte_integral"],
                    rec["mots_cles"], rec["source_url"], rec["source_pdf_url"],
                    rec["sanction"],
                    list(set(rec["articles_cites"])),
                    json.dumps(rec["metadata"]),
                )
                count += 1
                log.info(f"  [{rec['type']}/{rec['corpus']}] {rec['titre'][:60]}")
            except Exception as e:
                log.warning(f"  Erreur {path.name}: {e}")
    finally:
        await conn.close()

    log.info(f"Ingestion terminée : {count} / {len(md_files)} fiches insérées")


if __name__ == "__main__":
    asyncio.run(run())
