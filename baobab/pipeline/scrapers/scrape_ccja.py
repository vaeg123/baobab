#!/usr/bin/env python3
"""
Scraper CCJA — Cour Commune de Justice et d'Arbitrage (OHADA).
Source : https://www.juricaf.org (accès libre, 1325+ arrêts CCJA)

Usage:
    python -m baobab.pipeline.scrapers.scrape_ccja
    python -m baobab.pipeline.scrapers.scrape_ccja --pages 1-20
    python -m baobab.pipeline.scrapers.scrape_ccja --out /tmp/ccja.json
"""

import argparse
import asyncio
import json
import logging
import re
from pathlib import Path
from urllib.parse import urljoin, urlencode

import httpx
from bs4 import BeautifulSoup

JURICAF_BASE = "https://juricaf.org"
# CCJA sur JURICAF : terme de recherche "CCJA" + tri par date desc
# Pagination : ?tri=DESC&page=N (149 pages au total)
SEARCH_URL = f"{JURICAF_BASE}/recherche/CCJA?tri=DESC"

OUTPUT_DEFAULT = Path(__file__).parent.parent.parent.parent / "data" / "raw" / "ccja_arrets.json"

log = logging.getLogger("scrape_ccja")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9",
    "Accept": "text/html,application/xhtml+xml",
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


def parse_juricaf_list(html: str) -> list[dict]:
    """Parse une page de résultats JURICAF → liste de stubs."""
    soup = BeautifulSoup(html, "html.parser")
    items = []

    # JURICAF structure : liens /arret/ dans la page de résultats
    for a in soup.select("a[href*='/arret/']"):
        href = a.get("href", "")
        titre = a.get_text(strip=True)
        if not titre or len(titre) < 5:
            continue
        # Extraire date depuis le href : /arret/PAYS-JURIDICTION-AAAAMMJJ-NUM
        date_m = re.search(r"-(\d{8})-", href)
        date_str = ""
        if date_m:
            d = date_m.group(1)
            date_str = f"{d[:4]}-{d[4:6]}-{d[6:8]}"

        items.append({
            "titre": titre,
            "url": urljoin(JURICAF_BASE, href),
            "date_str": date_str,
            "ref": href.split("/")[-1],
        })

    return items


def parse_juricaf_detail(html: str, url: str) -> dict:
    """Parse une fiche JURICAF → dict arrêt complet."""
    soup = BeautifulSoup(html, "html.parser")

    titre = ""
    if h := soup.select_one("h1, .titre-arret, .decision-title"):
        titre = h.get_text(strip=True)

    # Métadonnées structurées
    def meta(sel: str) -> str:
        tag = soup.select_one(sel)
        return tag.get_text(strip=True) if tag else ""

    date_str = meta(".dateDecision, .date-decision, [itemprop='datePublished']")
    juridiction = meta(".juridiction, .cour, [itemprop='publisher']") or "CCJA"
    pays = meta(".pays, .country") or "OHADA"
    ref = meta(".numero, .reference, .numDecision")

    content = soup.select_one(".contenu-decision, .texte-arret, .decision-body, article .content")
    texte = content.get_text("\n", strip=True) if content else ""

    # Extraire parties
    parties_m = re.search(r"([A-Z][A-Z\s&]+)\s+c(?:ontre|/)\s+([A-Z][A-Z\s&]+)", texte)
    parties = {}
    if parties_m:
        parties = {"demandeur": parties_m.group(1).strip(), "defendeur": parties_m.group(2).strip()}

    # Articles cités
    arts = re.findall(
        r"Art(?:icle)?\.?\s*(\d+(?:\s*[à-]\s*\d+)?)\s*(?:de\s+l.Acte|AU|OHADA)?",
        texte, re.IGNORECASE
    )
    actes_m = re.findall(
        r"Acte\s+uniforme\s+(?:relatif\s+)?(?:au|à la|sur\s+le[s]?)\s+([^\.,;]{10,60})",
        texte, re.IGNORECASE
    )

    return {
        "ref": ref,
        "titre": titre,
        "date_str": date_str,
        "juridiction": juridiction,
        "pays": pays,
        "parties": parties,
        "texte_integral": texte[:50000],
        "articles_cites": list(set(arts)),
        "metadata": {"actes_uniformes": actes_m},
        "source_url": url,
        "source_pdf_url": "",
        "type": "arret_ccja",
        "corpus": "ohada",
        "domaine": "OHADA / Droit des affaires",
        "sanction": "",
    }


def next_page_url(html: str, current_page: int) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    # JURICAF pagination : /recherche/CCJA?tri=DESC&page=N
    for a in soup.select("a[href*='page=']"):
        href = a.get("href", "")
        m = re.search(r"page=(\d+)", href)
        if m and int(m.group(1)) == current_page + 1:
            return urljoin(JURICAF_BASE, href)
    # Fallback : incrémenter page manuellement
    # Page 1 n'a pas de paramètre page, pages suivantes ont &page=N
    next_p = current_page + 1
    return f"{JURICAF_BASE}/recherche/CCJA?tri=DESC&page={next_p}"


async def scrape(page_range: tuple[int, int] | None = None, out: Path = OUTPUT_DEFAULT) -> list[dict]:
    out.parent.mkdir(parents=True, exist_ok=True)
    arrets: list[dict] = []

    async with httpx.AsyncClient() as client:
        url = SEARCH_URL
        page_num = 1

        log.info(f"Démarrage scraping CCJA via JURICAF")

        while url:
            if page_range:
                lo, hi = page_range
                if page_num < lo:
                    page_num += 1
                    url = f"{SEARCH_URL}/page-{page_num}"
                    continue
                if page_num > hi:
                    break

            log.info(f"Page liste {page_num}: {url}")
            html = await fetch(client, url)
            if not html:
                log.error(f"Impossible de charger {url}")
                break

            stubs = parse_juricaf_list(html)
            log.info(f"  {len(stubs)} arrêts trouvés")

            if not stubs:
                log.warning("Aucun résultat — vérifier la structure HTML de la page")
                break

            for stub in stubs:
                detail_html = await fetch(client, stub["url"])
                if detail_html:
                    d = parse_juricaf_detail(detail_html, stub["url"])
                    d["date_str"] = d["date_str"] or stub["date_str"]
                    d["ref"] = d["ref"] or stub["ref"]
                    arrets.append(d)
                await asyncio.sleep(1.0)

            nxt = next_page_url(html, page_num)
            url = nxt
            page_num += 1
            await asyncio.sleep(1.5)

    log.info(f"Total arrêts CCJA collectés : {len(arrets)}")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(arrets, f, ensure_ascii=False, indent=2)
    log.info(f"Sauvegardé → {out}")
    return arrets


def main():
    parser = argparse.ArgumentParser(description="Scraper CCJA (OHADA via JURICAF)")
    parser.add_argument("--pages", help="Plage de pages, ex: 1-20", default=None)
    parser.add_argument("--out", help="Fichier JSON de sortie", default=str(OUTPUT_DEFAULT))
    args = parser.parse_args()

    page_range = None
    if args.pages:
        lo, hi = args.pages.split("-")
        page_range = (int(lo), int(hi))

    asyncio.run(scrape(page_range=page_range, out=Path(args.out)))


if __name__ == "__main__":
    main()
