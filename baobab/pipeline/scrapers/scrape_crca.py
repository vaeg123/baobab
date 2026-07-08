#!/usr/bin/env python3
"""
Scraper CRCA — Conseil Régional de Contrôle des Assurances (CIMA).
Source : https://www.cima-afrique.org/decisions-de-la-crca/
~700 décisions sur 67 pages.

Usage:
    python -m baobab.pipeline.scrapers.scrape_crca
    python -m baobab.pipeline.scrapers.scrape_crca --pages 1-5
    python -m baobab.pipeline.scrapers.scrape_crca --out /tmp/crca_raw.json
"""

import argparse
import asyncio
import json
import logging
import re
import time
from pathlib import Path
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

BASE_URL = "https://www.cima-afrique.org"
LIST_URL = f"{BASE_URL}/decisions-de-la-crca/"
OUTPUT_DEFAULT = Path(__file__).parent.parent.parent.parent / "data" / "raw" / "crca_decisions.json"

log = logging.getLogger("scrape_crca")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9",
}


async def fetch(client: httpx.AsyncClient, url: str, retries: int = 3) -> str | None:
    for attempt in range(retries):
        try:
            r = await client.get(url, headers=HEADERS, timeout=30, follow_redirects=True)
            r.raise_for_status()
            return r.text
        except Exception as exc:
            log.warning(f"[{attempt+1}/{retries}] {url} → {exc}")
            await asyncio.sleep(2 ** attempt)
    return None


def parse_decision_list(html: str) -> list[dict]:
    """Parse une page de liste CRCA.

    Le site cima-afrique.org présente les décisions dans un tableau HTML :
    chaque <tr> contient date + titre + lien PDF direct.
    """
    soup = BeautifulSoup(html, "html.parser")
    items = []

    for row in soup.select("tr"):
        a = row.select_one("a[href$='.pdf']")
        if not a:
            continue
        href = a["href"]
        full_text = row.get_text(" ", strip=True)

        # Date en début de cellule (ex: "13 décembre 2025")
        date_m = re.search(
            r"(\d{1,2}\s+(?:janvier|février|mars|avril|mai|juin|juillet|août"
            r"|septembre|octobre|novembre|décembre)\s+\d{4}|\d{4})",
            full_text, re.IGNORECASE
        )
        date_str = date_m.group(0) if date_m else ""

        # Titre = texte du lien ou contenu de la cellule
        titre = a.get_text(strip=True) or full_text[:120]

        # Référence n°XXX-YY extraite du nom de fichier ou titre
        ref_m = re.search(r"[Dd]écision[\s_-]*n[°o]?[\s_-]*([\w\-]+)", titre + " " + href)
        ref = f"n°{ref_m.group(1)}" if ref_m else ""

        # Sanction détectée dans le titre
        sanction_m = re.search(
            r"(retrait\s+d.agr[eé]ment|amende|bl[âa]me|avertissement"
            r"|surveillance permanente|liquidation|approbation|levée|agrément)",
            titre, re.IGNORECASE
        )
        sanction = sanction_m.group(0).strip() if sanction_m else ""

        items.append({
            "titre": titre,
            "url": urljoin(BASE_URL, href),
            "date_str": date_str,
            "ref": ref,
            "sanction": sanction,
            "is_pdf": True,
        })

    return items


def parse_decision_detail(html: str, url: str) -> dict:
    """Parse une page de détail CRCA → dict complet."""
    soup = BeautifulSoup(html, "html.parser")

    titre = ""
    if h := soup.select_one("h1, .entry-title, .decision-title"):
        titre = h.get_text(strip=True)

    # Contenu principal
    content_div = soup.select_one(".entry-content, .post-content, article .content, main")
    texte = content_div.get_text("\n", strip=True) if content_div else ""

    # Extraire date, référence, sanction, pays du texte
    ref_m = re.search(r"(N°|Décision|Arrêté)\s*([\w\-/]+)", texte)
    ref = ref_m.group(0) if ref_m else ""

    date_m = re.search(r"\b(\d{1,2}[/\-]\d{1,2}[/\-]\d{4}|\d{4})\b", texte)
    date_str = date_m.group(0) if date_m else ""

    sanction_m = re.search(
        r"(retrait\s+d.agr[eé]ment|amende|bl[âa]me|avertissement|mise\s+sous\s+surveillance"
        r"|suspension|liquidation)", texte, re.IGNORECASE
    )
    sanction = sanction_m.group(0).strip() if sanction_m else ""

    pays_m = re.search(
        r"(Côte d.Ivoire|Sénégal|Cameroun|Gabon|Mali|Burkina Faso|Togo|Bénin"
        r"|Congo|RDC|Centrafrique|Comores|Guinée|Niger|Tchad)", texte, re.IGNORECASE
    )
    pays = pays_m.group(0) if pays_m else ""

    arts = re.findall(r"Art(?:icle)?\.?\s*(\d+(?:\s*[à-]\s*\d+)?)\s*(?:du\s+Code|CIMA)?", texte)

    pdf_urls = [
        urljoin(BASE_URL, a["href"])
        for a in soup.select("a[href$='.pdf']")
        if a.get("href")
    ]

    return {
        "ref": ref,
        "titre": titre,
        "date_str": date_str,
        "texte_integral": texte[:50000],  # cap at 50k chars
        "sanction": sanction,
        "pays": pays,
        "articles_cites": list(set(arts)),
        "source_url": url,
        "source_pdf_url": pdf_urls[0] if pdf_urls else "",
        "type": "decision_crca",
        "corpus": "cima",
        "juridiction": "CRCA",
        "domaine": "Assurances / Contrôle prudentiel",
    }


def next_page_url(html: str, current_url: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    nxt = soup.select_one("a.next, a[rel='next'], .pagination .next a, .nav-next a")
    if nxt and nxt.get("href"):
        return urljoin(BASE_URL, nxt["href"])
    return None


async def get_year_filter_urls(client: httpx.AsyncClient) -> list[str]:
    """Récupère les URLs de filtre par année depuis la page principale."""
    html = await fetch(client, LIST_URL)
    if not html:
        return [LIST_URL]
    soup = BeautifulSoup(html, "html.parser")
    # Liens avec paramètre ?y= (filtres par année sur cima-afrique.org)
    year_links = [
        urljoin(BASE_URL, a["href"])
        for a in soup.select("a[href*='?y=']")
        if a.get("href")
    ]
    # Toujours inclure la page principale
    return [LIST_URL] + list(dict.fromkeys(year_links))


async def scrape(page_range: tuple[int, int] | None = None, out: Path = OUTPUT_DEFAULT) -> list[dict]:
    out.parent.mkdir(parents=True, exist_ok=True)
    decisions: list[dict] = []
    seen_pdfs: set[str] = set()

    async with httpx.AsyncClient() as client:
        log.info(f"Démarrage scraping CRCA depuis {LIST_URL}")

        # Le site CIMA liste les décisions sur une page principale + filtres par année
        urls_to_scrape = await get_year_filter_urls(client)
        log.info(f"URLs à scraper : {len(urls_to_scrape)} (page principale + filtres annuels)")

        for url in urls_to_scrape:
            log.info(f"Scraping : {url}")
            html = await fetch(client, url)
            if not html:
                log.warning(f"Impossible de charger {url}")
                continue

            stubs = parse_decision_list(html)
            log.info(f"  {len(stubs)} décisions trouvées")

            for stub in stubs:
                pdf_url = stub["url"]
                if pdf_url in seen_pdfs:
                    continue
                seen_pdfs.add(pdf_url)

                decisions.append({
                    "ref": stub.get("ref", ""),
                    "titre": stub["titre"],
                    "date_str": stub["date_str"],
                    "sanction": stub.get("sanction", ""),
                    "pays": "",
                    "articles_cites": [],
                    "texte_integral": "",
                    "resume": stub["titre"],
                    "mots_cles": [stub.get("sanction", "")] if stub.get("sanction") else [],
                    "parties": {},
                    "metadata": {},
                    "source_url": pdf_url,
                    "source_pdf_url": pdf_url,
                    "type": "decision_crca",
                    "corpus": "cima",
                    "juridiction": "CRCA",
                    "domaine": "Assurances / Contrôle prudentiel",
                })

            await asyncio.sleep(1.0)

    log.info(f"Total décisions CRCA collectées : {len(decisions)}")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(decisions, f, ensure_ascii=False, indent=2)
    log.info(f"Sauvegardé → {out}")
    return decisions


def main():
    parser = argparse.ArgumentParser(description="Scraper CRCA (CIMA)")
    parser.add_argument("--pages", help="Plage de pages, ex: 1-10", default=None)
    parser.add_argument("--out", help="Fichier JSON de sortie", default=str(OUTPUT_DEFAULT))
    args = parser.parse_args()

    page_range = None
    if args.pages:
        lo, hi = args.pages.split("-")
        page_range = (int(lo), int(hi))

    asyncio.run(scrape(page_range=page_range, out=Path(args.out)))


if __name__ == "__main__":
    main()
