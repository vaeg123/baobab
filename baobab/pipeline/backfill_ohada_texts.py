"""Complète les textes manquants du corpus OHADA depuis les PDF officiels."""

from __future__ import annotations

import asyncio
import io
import os
from collections import Counter
from urllib.parse import urljoin

import asyncpg
import httpx
import pdfplumber
from bs4 import BeautifulSoup
from dotenv import load_dotenv

BASE_URL = "https://biblio.ohada.org/"
HEADERS = {"User-Agent": "BaobabLegalResearch/1.0 (+https://www.vaegbaobab.com)"}


def extract_text(content: bytes) -> str:
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages[:100]).strip()[:100_000]


async def main() -> None:
    load_dotenv(".env.local")
    load_dotenv(".env")
    connection = await asyncpg.connect(os.environ["DATABASE_URL"])
    rows = await connection.fetch(
        """
        SELECT id, source_url, source_pdf_url
        FROM legal_corpus
        WHERE corpus = 'ohada'
          AND type = ANY($1::varchar[])
          AND source_url LIKE 'https://biblio.ohada.org/%'
          AND coalesce(length(texte_integral), 0) = 0
        ORDER BY source_url
        """,
        ["arret_ccja", "ordonnance_ccja", "avis_ccja"],
    )
    updated = 0
    unavailable = 0
    failed = 0
    failure_reasons: Counter[str] = Counter()
    semaphore = asyncio.Semaphore(3)
    database_lock = asyncio.Lock()

    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=60) as client:
        async def process(row) -> None:
            nonlocal updated, unavailable, failed
            async with semaphore:
                try:
                    pdf_url = row["source_pdf_url"] or ""
                    # La notice fait autorité : certains anciens liens stockés sont
                    # relatifs, expirés ou mal encodés.
                    notice = await client.get(row["source_url"])
                    notice.raise_for_status()
                    anchor = BeautifulSoup(notice.text, "html.parser").select_one(
                        "a[href*='doc_num.php?explnum_id=']"
                    )
                    if anchor:
                        pdf_url = urljoin(BASE_URL, anchor.get("href", ""))
                    if not pdf_url:
                        unavailable += 1
                        return
                    pdf_url = urljoin(BASE_URL, pdf_url)
                    response = await client.get(pdf_url)
                    response.raise_for_status()
                    if not response.content.startswith(b"%PDF"):
                        failed += 1
                        failure_reasons[f"non_pdf_http_{response.status_code}"] += 1
                        return
                    text = await asyncio.to_thread(extract_text, response.content)
                    if not text:
                        failed += 1
                        failure_reasons["image_pdf_without_text_layer"] += 1
                        return
                    async with database_lock:
                        await connection.execute(
                            """
                            UPDATE legal_corpus
                            SET texte_integral = $2, source_pdf_url = $3, updated_at = now()
                            WHERE id = $1
                            """,
                            row["id"],
                            text,
                            pdf_url,
                        )
                    updated += 1
                except Exception as exc:
                    failed += 1
                    failure_reasons[type(exc).__name__] += 1
                finally:
                    await asyncio.sleep(0.15)

        await asyncio.gather(*(process(row) for row in rows))

    await connection.close()
    print(f"SCANNED={len(rows)}")
    print(f"UPDATED={updated}")
    print(f"WITHOUT_OFFICIAL_PDF={unavailable}")
    print(f"FAILED={failed}")
    print("FAILURE_REASONS=" + ",".join(f"{key}:{value}" for key, value in failure_reasons.items()))


if __name__ == "__main__":
    asyncio.run(main())
