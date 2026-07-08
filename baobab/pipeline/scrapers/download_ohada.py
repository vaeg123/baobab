#!/usr/bin/env python3
"""
Téléchargeur des Actes Uniformes OHADA.
Source : https://www.ohadalegis.com (PDFs librement accessibles)
16 actes uniformes officiels.

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

# 16 Actes Uniformes OHADA avec leurs URLs sur ohadalegis.com
ACTES_UNIFORMES = [
    {
        "code": "AU-DCG",
        "titre": "Acte Uniforme relatif au Droit Commercial Général",
        "domaine": "Droit commercial",
        "date": "2010-12-15",
        "url": "https://www.ohadalegis.com/textes/aucg2010fr.pdf",
    },
    {
        "code": "AU-SCCIV",
        "titre": "Acte Uniforme relatif au Droit des Sociétés Commerciales et du GIE",
        "domaine": "Droit des sociétés",
        "date": "2014-01-30",
        "url": "https://www.ohadalegis.com/textes/auscgie2014fr.pdf",
    },
    {
        "code": "AU-SUR",
        "titre": "Acte Uniforme portant organisation des Sûretés",
        "domaine": "Sûretés / Garanties",
        "date": "2010-12-15",
        "url": "https://www.ohadalegis.com/textes/ausur2010fr.pdf",
    },
    {
        "code": "AU-REC",
        "titre": "Acte Uniforme portant organisation des Procédures Simplifiées de Recouvrement",
        "domaine": "Recouvrement / Voies d'exécution",
        "date": "1996-04-10",
        "url": "https://www.ohadalegis.com/textes/aurecouvrement1996fr.pdf",
    },
    {
        "code": "AU-VEX",
        "titre": "Acte Uniforme portant organisation des Voies d'Exécution",
        "domaine": "Voies d'exécution",
        "date": "1998-04-10",
        "url": "https://www.ohadalegis.com/textes/auexecution1998fr.pdf",
    },
    {
        "code": "AU-PCAP",
        "titre": "Acte Uniforme portant organisation des Procédures Collectives d'Apurement du Passif",
        "domaine": "Procédures collectives / Faillite",
        "date": "2015-09-10",
        "url": "https://www.ohadalegis.com/textes/aupcap2015fr.pdf",
    },
    {
        "code": "AU-ARB",
        "titre": "Acte Uniforme relatif au Droit de l'Arbitrage",
        "domaine": "Arbitrage",
        "date": "2017-03-23",
        "url": "https://www.ohadalegis.com/textes/auarbitrage2017fr.pdf",
    },
    {
        "code": "AU-COMP",
        "titre": "Acte Uniforme relatif au Droit Comptable et à l'Information Financière",
        "domaine": "Comptabilité / Finance",
        "date": "2017-01-26",
        "url": "https://www.ohadalegis.com/textes/audcif2017fr.pdf",
    },
    {
        "code": "AU-TRANS",
        "titre": "Acte Uniforme relatif aux Contrats de Transport de Marchandises par Route",
        "domaine": "Transport",
        "date": "2003-03-22",
        "url": "https://www.ohadalegis.com/textes/autransport2003fr.pdf",
    },
    {
        "code": "AU-DROIT-SOC-COOP",
        "titre": "Acte Uniforme relatif au Droit des Sociétés Coopératives",
        "domaine": "Sociétés coopératives",
        "date": "2010-12-15",
        "url": "https://www.ohadalegis.com/textes/auscoop2010fr.pdf",
    },
    {
        "code": "AU-MED",
        "titre": "Acte Uniforme relatif à la Médiation",
        "domaine": "Médiation",
        "date": "2017-01-23",
        "url": "https://www.ohadalegis.com/textes/aumediation2017fr.pdf",
    },
    {
        "code": "TRAITE-OHADA",
        "titre": "Traité relatif à l'Harmonisation du Droit des Affaires en Afrique",
        "domaine": "Traité fondateur OHADA",
        "date": "2008-10-17",
        "url": "https://www.ohadalegis.com/textes/traiteohadafr.pdf",
    },
    {
        "code": "REG-ARB-CCJA",
        "titre": "Règlement d'Arbitrage de la CCJA",
        "domaine": "Arbitrage CCJA",
        "date": "2017-03-23",
        "url": "https://www.ohadalegis.com/textes/regarbitrageccja2017fr.pdf",
    },
    {
        "code": "REG-CCJA",
        "titre": "Règlement de Procédure de la CCJA",
        "domaine": "Procédure CCJA",
        "date": "2017-01-30",
        "url": "https://www.ohadalegis.com/textes/regprocedureccja2017fr.pdf",
    },
    {
        "code": "AU-DROIT-BAUX",
        "titre": "Acte Uniforme sur le Bail Commercial",
        "domaine": "Baux commerciaux",
        "date": "1997-04-17",
        "url": "https://www.ohadalegis.com/textes/aubail1997fr.pdf",
    },
    {
        "code": "AU-ECT",
        "titre": "Acte Uniforme relatif au Droit des Contrats",
        "domaine": "Droit des contrats",
        "date": "2010-12-15",
        "url": "https://www.ohadalegis.com/textes/audroitcontrats2010fr.pdf",
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
