#!/usr/bin/env python3
"""OCR des Actes Uniformes OHADA image-based (AUDCG-2010, AUS-2010) via tesseract.
Usage: DATABASE_URL=... python ocr_ohada_au.py
"""
import asyncio, asyncpg, json, os, sys, io, urllib.request, pathlib
import fitz
import pytesseract
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DB = os.environ["DATABASE_URL"]
TESSDATA = "C:/tmp"
TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

TARGETS = [
    {"ref": "AUDCG-2010",      "explnum_id": 6,   "max_pages": 78},
    {"ref": "AUS-2010",        "explnum_id": 483,  "max_pages": 58},
    {"ref": "AUSCOOP-2010",    "explnum_id": 487,  "max_pages": 78},
    {"ref": "AUPSRVE-1998",    "explnum_id": 485,  "max_pages": 94},
    {"ref": "AUCTMR-2003",     "explnum_id": 482,  "max_pages": 20},
    {"ref": "Traité-OHADA-1993", "explnum_id": 12, "max_pages": 8},
]


def download_pdf(explnum_id: int) -> bytes:
    url = f"http://biblio.ohada.org/pmb/opac_css/doc_num.php?explnum_id={explnum_id}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def ocr_pdf(pdf_bytes: bytes, max_pages: int = 999) -> str:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = min(len(doc), max_pages)
    print(f"  OCR de {pages}/{len(doc)} pages…")
    parts = []
    for i in range(pages):
        pix = doc[i].get_pixmap(dpi=200)
        img_bytes = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_bytes))
        text = pytesseract.image_to_string(
            img,
            lang="fra",
            config=f"--tessdata-dir {TESSDATA}",
        )
        parts.append(text)
        if (i + 1) % 10 == 0:
            print(f"    page {i+1}/{pages} — {len(''.join(parts))} chars")
    doc.close()
    return "\n".join(parts)


async def run():
    conn = await asyncpg.connect(DB)
    for t in TARGETS:
        ref = t["ref"]
        print(f"\n=== {ref} (explnum_id={t['explnum_id']}) ===")

        # Check existing
        row = await conn.fetchrow(
            "SELECT id, length(texte_integral) as tlen FROM legal_corpus WHERE ref=$1", ref
        )
        if not row:
            print("  Pas trouvé en DB, skip")
            continue
        if row["tlen"] and row["tlen"] > 5000:
            print(f"  Déjà un texte ({row['tlen']} chars), skip")
            continue

        print(f"  Téléchargement PDF…")
        pdf_bytes = download_pdf(t["explnum_id"])
        print(f"  {len(pdf_bytes)//1024}KB téléchargé")

        text = ocr_pdf(pdf_bytes, t["max_pages"])
        total_chars = len(text.strip())
        print(f"  OCR terminé — {total_chars} chars")

        if total_chars < 500:
            print("  ATTENTION: très peu de texte, problème OCR?")
            continue

        await conn.execute(
            "UPDATE legal_corpus SET texte_integral=$1, resume=$2 WHERE ref=$3",
            text[:80000],
            text[:600],
            ref,
        )
        print(f"  DB mis à jour ✓")

    # Stats finales
    for t in TARGETS:
        row = await conn.fetchrow(
            "SELECT length(texte_integral) as tlen FROM legal_corpus WHERE ref=$1", t["ref"]
        )
        print(f"\n{t['ref']}: {row['tlen']} chars en DB")

    await conn.close()


asyncio.run(run())
