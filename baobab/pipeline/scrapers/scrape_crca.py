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
    """Parse une page de liste CRCA → liste de stubs {titre, url, date, ref}."""
    soup = BeautifulSoup(html, "html.parser")
    items = []

    # Le site CIMA affiche les décisions dans des articles / divs de liste
    for article in soup.select("article, .decision-item, .entry-item, li.decision"):
        title_tag = article.select_one("h2 a, h3 a, .entry-title a, a")
        if not title_tag:
            continue
        href = title_tag.get("href", "")
        if not href:
            continue
        titre = title_tag.get_text(strip=True)
        date_tag = article.select_one("time, .entry-date, .date")
        date_str = date_tag.get("datetime", date_tag.get_text(strip=True)) if date_tag else ""
        items.append({
            "titre": titre,
            "url": urljoin(BASE_URL, href),
            "date_str": date_str,
        })

    # Fallback : liens directs vers PDFs listés dans la page
    if not items:
        for a in soup.select("a[href*='.pdf'], a[href*='decision']"):
            titre = a.get_text(strip=True) or a["href"].split("/")[-1]
            items.append({
                "titre": titre,
                "url": urljoin(BASE_URL, a["href"]),
                "date_str": "",
                "is_pdf": a["href"].endswith(".pdf"),
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


async def scrape(page_range: tuple[int, int] | None = None, out: Path = OUTPUT_DEFAULT) -> list[dict]:
    out.parent.mkdir(parents=True, exist_ok=True)
    decisions: list[dict] = []

    async with httpx.AsyncClient() as client:
        url = LIST_URL
        page_num = 1

        log.info(f"Démarrage scraping CRCA depuis {LIST_URL}")

        while url:
            if page_range:
                lo, hi = page_range
                if page_num < lo:
                    page_num += 1
                    url = f"{LIST_URL}page/{page_num}/"
                    continue
                if page_num > hi:
                    break

            log.info(f"Page liste {page_num}: {url}")
            html = await fetch(client, url)
            if not html:
                log.error(f"Impossible de charger {url}")
                break

            stubs = parse_decision_list(html)
            log.info(f"  {len(stubs)} décisions trouvées")

            for stub in stubs:
                detail_url = stub["url"]
                if stub.get("is_pdf"):
                    # Décision = fichier PDF direct, pas de page détail
                    decisions.append({
                        **stub,
                        "type": "decision_crca",
                        "corpus": "cima",
                        "juridiction": "CRCA",
                        "texte_integral": "",
                        "source_url": detail_url,
                        "source_pdf_url": detail_url,
                    })
                else:
                    detail_html = await fetch(client, detail_url)
                    if detail_html:
                        d = parse_decision_detail(detail_html, detail_url)
                        d["date_str"] = d["date_str"] or stub["date_str"]
                        decisions.append(d)
                    await asyncio.sleep(0.8)

            nxt = next_page_url(html, url)
            url = nxt
            page_num += 1
            await asyncio.sleep(1.2)

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
