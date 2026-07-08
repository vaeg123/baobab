#!/usr/bin/env python3
"""
Téléchargeur des Actes Uniformes OHADA.
Source : https://www.ohada.com/actes-uniformes.html (PDFs librement accessibles)
18 actes uniformes officiels.

Usage:
    python -m baobab.pipeline.scrapers.download_ohada
    python -m baobab.pipeline.scrapers.download_ohada --out /tmp/ohada/
"""

import argparse
import asyncio
import json
import logging
import re
from pathlib import Path

import httpx

OUTPUT_DIR = Path(__file__).parent.parent.parent.parent / "data" / "raw" / "ohada_actes"
OUTPUT_JSON = Path(__file__).parent.parent.parent.parent / "data" / "raw" / "ohada_actes.json"

log = logging.getLogger("download_ohada")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    ),
}

# 18 Actes Uniformes OHADA — source : https://www.ohada.com/actes-uniformes.html
OHADA_BASE = "https://www.ohada.com"

ACTES_UNIFORMES = [
    {
        "code": "AUPSRVE-2023",
        "titre": "Acte Uniforme portant organisation des Procédures Simplifiées de Recouvrement et des Voies d'Exécution (révisé 2023)",
        "domaine": "Recouvrement / Voies d'exécution",
        "date": "2023-01-01",
        "url": f"{OHADA_BASE}/telechargement/actes-uniformes/AUPSRVE-2023_fr.pdf",
    },
    {
        "code": "SYCEBNL-2022",
        "titre": "Acte Uniforme relatif au Droit des Sociétés Coopératives et des Mutuelles (SYCEBNL 2022)",
        "domaine": "Sociétés coopératives / Mutuelles",
        "date": "2022-01-01",
        "url": f"{OHADA_BASE}/telechargement/actes-uniformes/SYCEBNL-2022_fr.pdf",
    },
    {
        "code": "AUA-2017",
        "titre": "Acte Uniforme relatif au Droit de l'Arbitrage (2017)",
        "domaine": "Arbitrage",
        "date": "2017-03-23",
        "url": f"{OHADA_BASE}/telechargement/actes-uniformes/AUA-2017_fr.pdf",
    },
    {
        "code": "AUM-2017",
        "titre": "Acte Uniforme relatif à la Médiation (2017)",
        "domaine": "Médiation",
        "date": "2017-01-23",
        "url": f"{OHADA_BASE}/telechargement/actes-uniformes/AUM-2017_fr.pdf",
    },
    {
        "code": "AUDCIF-2017",
        "titre": "Acte Uniforme relatif au Droit Comptable et à l'Information Financière (2017)",
        "domaine": "Comptabilité / Finance",
        "date": "2017-01-26",
        "url": f"{OHADA_BASE}/telechargement/actes-uniformes/AUDCIF-2017_fr.pdf",
    },
    {
        "code": "AUPCAP-2015",
        "titre": "Acte Uniforme portant organisation des Procédures Collectives d'Apurement du Passif (2015)",
        "domaine": "Procédures collectives / Faillite",
        "date": "2015-09-10",
        "url": f"{OHADA_BASE}/telechargement/actes-uniformes/AUPCAP-2015_fr.pdf",
    },
    {
        "code": "AUSCGIE-2014",
        "titre": "Acte Uniforme relatif au Droit des Sociétés Commerciales et du GIE (2014)",
        "domaine": "Droit des sociétés",
        "date": "2014-01-30",
        "url": f"{OHADA_BASE}/telechargement/actes-uniformes/AUSCGIE-2014_fr.pdf",
    },
    {
        "code": "AUS-2010",
        "titre": "Acte Uniforme portant organisation des Sûretés (2010)",
        "domaine": "Suretés / Garanties",
        "date": "2010-12-15",
        "url": f"{OHADA_BASE}/telechargement/actes-uniformes/AUS-2010_fr.pdf",
    },
    {
        "code": "AUSCOOP-2010",
        "titre": "Acte Uniforme relatif au Droit des Sociétés Coopératives (2010)",
        "domaine": "Sociétés coopératives",
        "date": "2010-12-15",
        "url": f"{OHADA_BASE}/telechargement/actes-uniformes/AUSCOOP-2010_fr.pdf",
    },
    {
        "code": "AUDCG-2010",
        "titre": "Acte Uniforme relatif au Droit Commercial Général (2010)",
        "domaine": "Droit commercial",
        "date": "2010-12-15",
        "url": f"{OHADA_BASE}/telechargement/actes-uniformes/AUDCG-2010_fr.pdf",
    },
    {
        "code": "AUCTMR-2003",
        "titre": "Acte Uniforme relatif aux Contrats de Transport de Marchandises par Route (2003)",
        "domaine": "Transport",
        "date": "2003-03-22",
        "url": f"{OHADA_BASE}/telechargement/actes-uniformes/AUCTMR-2003_fr.pdf",
    },
    {
        "code": "AUCE-2000",
        "titre": "Acte Uniforme relatif au Droit des Contrats (2000)",
        "domaine": "Droit des contrats",
        "date": "2000-01-01",
        "url": f"{OHADA_BASE}/telechargement/actes-uniformes/AUCE-2000_fr.pdf",
    },
    {
        "code": "AUA-1999",
        "titre": "Acte Uniforme relatif au Droit de l'Arbitrage (1999)",
        "domaine": "Arbitrage",
        "date": "1999-03-11",
        "url": f"{OHADA_BASE}/telechargement/actes-uniformes/AUA-1999_fr.pdf",
    },
    {
        "code": "AUPSRVE-1998",
        "titre": "Acte Uniforme portant organisation des Procédures Simplifiées de Recouvrement (1998)",
        "domaine": "Recouvrement / Voies d'exécution",
        "date": "1998-04-10",
        "url": f"{OHADA_BASE}/telechargement/actes-uniformes/AUPSRVE-1998_fr.pdf",
    },
    {
        "code": "AUPCAP-1998",
        "titre": "Acte Uniforme portant organisation des Procédures Collectives d'Apurement du Passif (1998)",
        "domaine": "Procédures collectives / Faillite",
        "date": "1998-04-10",
        "url": f"{OHADA_BASE}/telechargement/actes-uniformes/AUPCAP-1998_fr.pdf",
    },
    {
        "code": "AUDCG-1997",
        "titre": "Acte Uniforme relatif au Droit Commercial Général (1997)",
        "domaine": "Droit commercial",
        "date": "1997-04-17",
        "url": f"{OHADA_BASE}/telechargement/actes-uniformes/AUDCG-1997_fr.pdf",
    },
    {
        "code": "AUSCGIE-1997",
        "titre": "Acte Uniforme relatif au Droit des Sociétés Commerciales et du GIE (1997)",
        "domaine": "Droit des sociétés",
        "date": "1997-04-17",
        "url": f"{OHADA_BASE}/telechargement/actes-uniformes/AUSCGIE-1997_fr.pdf",
    },
    {
        "code": "AUS-1997",
        "titre": "Acte Uniforme portant organisation des Sûretés (1997)",
        "domaine": "Suretés / Garanties",
        "date": "1997-04-17",
        "url": f"{OHADA_BASE}/telechargement/actes-uniformes/AUS-1997_fr.pdf",
    },
]


async def download_pdf(client: httpx.AsyncClient, url: str, dest: Path) -> bool:
    if dest.exists():
        log.info(f"  Déjà téléchargé : {dest.name}")
        return True
    try:
        r = await client.get(url, headers=HEADERS, timeout=60, follow_redirects=True)
        r.raise_for_status()
        dest.write_bytes(r.content)
        log.info(f"  Téléchargé ({len(r.content)//1024} Ko) → {dest.name}")
        return True
    except Exception as exc:
        log.warning(f"  Échec {url}: {exc}")
        return False


async def download_all(out_dir: Path = OUTPUT_DIR, out_json: Path = OUTPUT_JSON) -> list[dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []

    async with httpx.AsyncClient() as client:
        for acte in ACTES_UNIFORMES:
            log.info(f"[{acte['code']}] {acte['titre'][:60]}")
            pdf_path = out_dir / f"{acte['code']}.pdf"
            success = await download_pdf(client, acte["url"], pdf_path)

            entry = {
                **acte,
                "type": "acte_uniforme",
                "corpus": "ohada",
                "juridiction": "OHADA",
                "pays": "Afrique subsaharienne (17 États)",
                "source_url": acte["url"],
                "source_pdf_url": acte["url"],
                "local_pdf": str(pdf_path) if success else "",
                "texte_integral": "",  # sera extrait par ingest_corpus.py
                "ref": acte["code"],
                "parties": {},
                "sanction": "",
                "articles_cites": [],
                "mots_cles": acte["domaine"].split(" / "),
                "resume": f"Texte officiel OHADA : {acte['titre']}",
            }
            results.append(entry)
            await asyncio.sleep(0.5)

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    log.info(f"Index sauvegardé → {out_json}")
    return results


def main():
    parser = argparse.ArgumentParser(description="Téléchargeur Actes Uniformes OHADA")
    parser.add_argument("--out", help="Dossier de sortie PDFs", default=str(OUTPUT_DIR))
    args = parser.parse_args()
    asyncio.run(download_all(out_dir=Path(args.out)))


if __name__ == "__main__":
    main()
