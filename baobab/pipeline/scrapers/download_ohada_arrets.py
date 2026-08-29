#!/usr/bin/env python3
"""Collecte les arrêts d'une étagère de la Bibliothèque numérique OHADA.

La collecte conserve la notice officielle, le PDF original, une empreinte SHA-256
et un manifeste JSON exploitable par le pipeline Baobab.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import re
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

BASE_URL = "https://biblio.ohada.org/"
DEFAULT_SHELF_ID = 22
JURISPRUDENCE_SHELVES = {
    22: ("Arrêt", "arret_ccja"),
    21: ("Ordonnance", "ordonnance_ccja"),
    20: ("Avis", "avis_ccja"),
}
ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_DIR = ROOT / "data" / "raw" / "ohada_arrets"
DEFAULT_MANIFEST = ROOT / "data" / "raw" / "ohada_arrets.json"

HEADERS = {
    "User-Agent": "BaobabLegalResearch/1.0 (+https://www.vaegbaobab.com)",
    "Accept-Language": "fr-FR,fr;q=0.9",
}

log = logging.getLogger("download_ohada_arrets")


def _query_id(url: str, name: str) -> int | None:
    values = parse_qs(urlparse(url).query).get(name, [])
    return int(values[0]) if values and values[0].isdigit() else None


def extract_notice_ids(html: str, document_label: str = "Arrêt") -> list[int]:
    """Retourne les notices dans l'ordre de l'étagère, sans doublons."""
    soup = BeautifulSoup(html, "html.parser")
    result: list[int] = []
    seen: set[int] = set()
    for anchor in soup.select("a[href*='lvl=notice_display']"):
        label_pattern = "arr[êe]t" if document_label.casefold() == "arrêt" else re.escape(document_label)
        if not re.search(rf"\b{label_pattern}\b", anchor.get_text(" ", strip=True), re.IGNORECASE):
            continue
        notice_id = _query_id(urljoin(BASE_URL, anchor.get("href", "")), "id")
        if notice_id is not None and notice_id not in seen:
            result.append(notice_id)
            seen.add(notice_id)
    return result


def _label_value(soup: BeautifulSoup, label: str) -> str:
    pattern = re.compile(rf"^{re.escape(label)}\s*:\s*$", re.IGNORECASE)
    node = soup.find(string=pattern)
    if node is None:
        return ""
    parent = node.parent
    values: list[str] = []
    for sibling in parent.next_siblings:
        text = sibling.get_text(" ", strip=True) if hasattr(sibling, "get_text") else str(sibling).strip()
        if text:
            values.append(text)
            break
    if values:
        return values[0]
    text = parent.get_text(" ", strip=True)
    return re.sub(pattern, "", text).strip()


def parse_notice(html: str, notice_id: int, document_type: str = "arret_ccja") -> dict:
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)

    def field(label: str) -> str:
        direct = _label_value(soup, label)
        if direct:
            return direct
        match = re.search(rf"(?:^|\n){re.escape(label)}\s*:\s*([^\n]+)", text, re.IGNORECASE)
        return match.group(1).strip() if match else ""

    title = field("Titre")
    pdf_anchor = soup.select_one("a[href*='doc_num.php?explnum_id=']")
    pdf_url = urljoin(BASE_URL, pdf_anchor.get("href", "")) if pdf_anchor else ""
    pdf_id = _query_id(pdf_url, "explnum_id") if pdf_url else None
    reference_match = re.search(
        r"(?:Arr[êe]t|Ordonnance|Avis)\s+(?:N[°o]\s*)?([\w./-]+)", title, re.IGNORECASE
    )
    date_match = re.search(r"(\d{2})/(\d{2})/(\d{4})", field("Date d'audience"))
    iso_date = f"{date_match.group(3)}-{date_match.group(2)}-{date_match.group(1)}" if date_match else ""
    tags = [a.get_text(" ", strip=True) for a in soup.select("a[href*='indexint_see']")]

    return {
        "ref": f"CCJA-{reference_match.group(1)}" if reference_match else f"CCJA-NOTICE-{notice_id}",
        "titre": title,
        "date_str": iso_date,
        "type": document_type,
        "corpus": "ohada",
        "juridiction": "CCJA",
        "pays": "OHADA",
        "domaine": "Droit des affaires OHADA",
        "resume": field("Affaire") or title,
        "texte_integral": "",
        "mots_cles": list(dict.fromkeys(tags)),
        "source_url": f"{BASE_URL}index.php?lvl=notice_display&id={notice_id}",
        "source_pdf_url": pdf_url,
        "local_pdf": "",
        "sha256": "",
        "articles_cites": [tag for tag in tags if "ARTICLE" in tag.upper()],
        "parties": {"affaire": field("Affaire")},
        "metadata": {
            "notice_id": notice_id,
            "document_numerique_id": pdf_id,
            "auteurs": field("Auteurs"),
            "source_officielle": "Bibliothèque numérique de l'OHADA",
        },
    }


def safe_filename(record: dict) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", record["ref"]).strip("-.")
    nature = re.sub(r"[^a-z0-9-]+", "-", record.get("type", "decision").lower()).strip("-")
    return f"{nature}-{value or 'ccja-notice-' + str(record['metadata']['notice_id'])}.pdf"


async def _get(client: httpx.AsyncClient, url: str, attempts: int = 3) -> httpx.Response:
    error: Exception | None = None
    for attempt in range(attempts):
        try:
            response = await client.get(url, timeout=60, follow_redirects=True)
            response.raise_for_status()
            return response
        except Exception as exc:
            error = exc
            await asyncio.sleep(2**attempt)
    raise RuntimeError(f"Échec du téléchargement de {url}") from error


async def collect_shelf(
    shelf_id: int = DEFAULT_SHELF_ID,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    manifest_path: Path = DEFAULT_MANIFEST,
    document_label: str | None = None,
    document_type: str | None = None,
) -> list[dict]:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    shelf_url = f"{BASE_URL}index.php?lvl=etagere_see&id={shelf_id}"

    async with httpx.AsyncClient(headers=HEADERS) as client:
        shelf = await _get(client, shelf_url)
        configured_label, configured_type = JURISPRUDENCE_SHELVES.get(
            shelf_id, (document_label or "Arrêt", document_type or "arret_ccja")
        )
        label = document_label or configured_label
        kind = document_type or configured_type
        notice_ids = extract_notice_ids(shelf.text, label)
        if not notice_ids:
            raise RuntimeError(f"Aucune notice trouvée sur l'étagère OHADA {shelf_id}")
        log.info("Étagère %s : %s notices", shelf_id, len(notice_ids))

        records: list[dict] = []
        for position, notice_id in enumerate(notice_ids, start=1):
            notice = await _get(client, f"{BASE_URL}index.php?lvl=notice_display&id={notice_id}")
            record = parse_notice(notice.text, notice_id, kind)
            record["metadata"]["shelf_id"] = shelf_id
            record["metadata"]["shelf_position"] = position
            if record["source_pdf_url"]:
                pdf = await _get(client, record["source_pdf_url"])
                if not pdf.content.startswith(b"%PDF"):
                    raise RuntimeError(f"Le document de la notice {notice_id} n'est pas un PDF")
                destination = output_dir / safe_filename(record)
                destination.write_bytes(pdf.content)
                record["local_pdf"] = destination.relative_to(ROOT).as_posix()
                record["sha256"] = hashlib.sha256(pdf.content).hexdigest()
                record["metadata"]["pdf_bytes"] = len(pdf.content)
            else:
                record["metadata"]["download_error"] = "Aucun PDF indiqué dans la notice"
            records.append(record)
            log.info("[%s/%s] %s", position, len(notice_ids), record["titre"])
            await asyncio.sleep(0.4)

    manifest_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    return records


async def collect_all_jurisprudence(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    manifest_path: Path = DEFAULT_MANIFEST,
) -> list[dict]:
    """Collecte les trois collections officielles sans écrire de manifestes intermédiaires."""
    all_records: list[dict] = []
    for shelf_id, (label, document_type) in JURISPRUDENCE_SHELVES.items():
        temporary_manifest = manifest_path.with_name(f".{manifest_path.stem}-{shelf_id}.json")
        records = await collect_shelf(
            shelf_id,
            output_dir,
            temporary_manifest,
            document_label=label,
            document_type=document_type,
        )
        temporary_manifest.unlink(missing_ok=True)
        all_records.extend(records)
    manifest_path.write_text(json.dumps(all_records, ensure_ascii=False, indent=2), encoding="utf-8")
    return all_records


def main() -> None:
    parser = argparse.ArgumentParser(description="Télécharge les arrêts d'une étagère OHADA")
    parser.add_argument("--shelf-id", type=int, default=DEFAULT_SHELF_ID)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--all-jurisprudence", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.all_jurisprudence:
        records = asyncio.run(collect_all_jurisprudence(args.output_dir, args.manifest))
    else:
        records = asyncio.run(collect_shelf(args.shelf_id, args.output_dir, args.manifest))
    downloaded = sum(bool(record["local_pdf"]) for record in records)
    print(f"{len(records)} notices collectées, {downloaded} PDF téléchargés")


if __name__ == "__main__":
    main()
