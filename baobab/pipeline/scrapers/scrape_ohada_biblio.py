#!/usr/bin/env python3
"""
Scraper Bibliothèque Numérique OHADA — arrêts CCJA.
Source : https://biblio.ohada.org

Arrêts CCJA accessibles sans compte, avec PDFs téléchargeables.
~1200+ arrêts disponibles (2006–2026).

Usage:
    python -m baobab.pipeline.scrapers.scrape_ohada_biblio
    python -m baobab.pipeline.scrapers.scrape_ohada_biblio --pages 1-10
    python -m baobab.pipeline.scrapers.scrape_ohada_biblio --out /tmp/ccja.json
"""

import argparse
import asyncio
import json
import logging
import re
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

BASE = "https://biblio.ohada.org"
SEARCH_URL = f"{BASE}/index.php?search_type_asked=simple_search&look_for=arret+CCJA"

OUTPUT_DEFAULT = Path(__file__).parent.parent.parent.parent / "data" / "raw" / "ccja_biblio.json"

log = logging.getLogger("scrape_ohada_biblio")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
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
            log.warning(f"[{attempt+1}/{retries}] {url[-60:]} -> {exc}")
            await asyncio.sleep(2 ** attempt)
    return None


def extract_notice_ids(html: str) -> list[int]:
    """Extrait les IDs de notices uniques d'une page de résultats."""
    soup = BeautifulSoup(html, "html.parser")
    ids = set()
    for a in soup.select("a[href*='notice_display&id=']"):
        m = re.search(r"id=(\d+)", a["href"])
        if m:
            ids.add(int(m.group(1)))
    return sorted(ids, reverse=True)


def parse_notice(html: str, notice_id: int) -> dict | None:
    """Parse une fiche notice CCJA → dict structuré."""
    soup = BeautifulSoup(html, "html.parser")

    # Extraction par pattern "Libellé :\nValeur" dans le HTML texte
    full_text = soup.get_text("\n", strip=True)

    def field(label: str) -> str:
        m = re.search(rf"{re.escape(label)}\s*:?\s*\n(.+)", full_text)
        return m.group(1).strip() if m else ""

    titre = field("Titre")
    auteurs = field("Auteurs")
    date_str = field("Date d'audience")
    affaire = field("Affaire")
    tags_raw = field("Tags")
    categories = field("Catégories")

    # Fallback titre depuis <h2>/<h3> ou balise forte
    if not titre:
        for sel in ["h2", "h3", ".notice_title", ".titre_notice"]:
            tag = soup.select_one(sel)
            if tag and "Arrêt" in tag.get_text():
                titre = tag.get_text(strip=True)
                break

    # Numéro d'arrêt
    ref_m = re.search(r"Arr[eê]t\s+N[°o]?\s*([\w/\-]+)", titre or full_text, re.IGNORECASE)
    ref = f"Arrêt N°{ref_m.group(1)}" if ref_m else f"Notice-{notice_id}"

    # Tags → mots-clés + articles cités
    mots_cles = [t.strip() for t in tags_raw.split(";") if t.strip()] if tags_raw else []
    arts = re.findall(r"(AU\w+,?\s+ARTICLE\s+\d+)", tags_raw, re.IGNORECASE)

    # Pays depuis tags ou affaire
    pays_m = re.search(
        r"\b(SENEGAL|COTE\s+D.IVOIRE|CAMEROUN|GABON|MALI|BURKINA|TOGO|BENIN"
        r"|CONGO|CENTRAFRIQUE|COMORES|GUINEE|NIGER|TCHAD)\b",
        tags_raw + " " + affaire, re.IGNORECASE
    )
    pays = pays_m.group(0).title() if pays_m else "OHADA"

    # Domaine depuis catégories ou tags
    domaine = "Droit des affaires OHADA / CCJA"
    for kw, dom in [
        ("SOCIETE", "Droit des sociétés"), ("SURETE", "Sûretés"), ("ARBITRAGE", "Arbitrage"),
        ("RECOUVREMENT", "Recouvrement"), ("FAILLITE", "Procédures collectives"),
        ("TRANSPORT", "Transport"), ("COMPTABLE", "Comptabilité"),
    ]:
        if kw in tags_raw.upper():
            domaine = dom
            break

    # PDF link : a[href*=doc_num]
    pdf_a = soup.select_one("a[href*='doc_num.php']")
    pdf_url = pdf_a["href"] if pdf_a else ""
    if pdf_url and not pdf_url.startswith("http"):
        pdf_url = BASE + "/" + pdf_url.lstrip("./")

    # Résumé = concaténation titre + affaire + tags principaux
    resume = f"{titre}. Affaire : {affaire}. {'; '.join(mots_cles[:4])}"

    if not titre or "BIBLIOTHEQUE" in titre.upper():
        return None

    return {
        "ref": ref,
        "titre": titre,
        "date_str": date_str,
        "type": "arret_ccja",
        "corpus": "ohada",
        "juridiction": "CCJA",
        "pays": pays,
        "domaine": domaine,
        "resume": resume[:500],
        "texte_integral": "",  # téléchargement PDF optionnel
        "mots_cles": mots_cles[:15],
        "source_url": f"{BASE}/index.php?lvl=notice_display&id={notice_id}",
        "source_pdf_url": pdf_url,
        "sanction": "",
        "articles_cites": arts,
        "parties": {"affaire": affaire},
        "metadata": {"notice_id": notice_id, "categories": categories, "auteurs": auteurs},
    }


async def scrape(
    page_range: tuple[int, int] | None = None,
    out: Path = OUTPUT_DEFAULT,
) -> list[dict]:
    out.parent.mkdir(parents=True, exist_ok=True)
    arrets: list[dict] = []
    seen_ids: set[int] = set()

    async with httpx.AsyncClient() as client:
        page = 1
        max_page = page_range[1] if page_range else 200

        log.info(f"Démarrage scraping CCJA sur biblio.ohada.org (max {max_page} pages)")

        while page <= max_page:
            if page_range and page < page_range[0]:
                page += 1
                continue

            url = SEARCH_URL if page == 1 else f"{SEARCH_URL}&page={page}"
            log.info(f"Page {page}: {url[-70:]}")

            html = await fetch(client, url)
            if not html:
                log.error(f"Échec page {page}")
                break

            ids = extract_notice_ids(html)
            new_ids = [i for i in ids if i not in seen_ids]
            log.info(f"  {len(ids)} IDs trouvés, {len(new_ids)} nouveaux")

            if not new_ids:
                log.info("Fin de pagination — plus de nouveaux résultats")
                break

            for nid in new_ids:
                seen_ids.add(nid)
                notice_html = await fetch(client, f"{BASE}/index.php?lvl=notice_display&id={nid}")
                if notice_html:
                    doc = parse_notice(notice_html, nid)
                    if doc:
                        arrets.append(doc)
                        log.info(f"  [{nid}] {doc['ref']} — {doc['pays']}")
                await asyncio.sleep(0.8)

            page += 1
            await asyncio.sleep(1.5)

    log.info(f"Total arrêts CCJA collectés : {len(arrets)}")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(arrets, f, ensure_ascii=False, indent=2)
    log.info(f"Sauvegardé -> {out}")
    return arrets


def main():
    parser = argparse.ArgumentParser(description="Scraper CCJA — biblio.ohada.org")
    parser.add_argument("--pages", default=None, help="Plage pages, ex: 1-20")
    parser.add_argument("--out", default=str(OUTPUT_DEFAULT))
    args = parser.parse_args()
    pr = None
    if args.pages:
        lo, hi = args.pages.split("-")
        pr = (int(lo), int(hi))
    asyncio.run(scrape(page_range=pr, out=Path(args.out)))


if __name__ == "__main__":
    main()
