"""Transforme un PDF/image juridique en copie visuelle avec texte OCR recherchable.

Le fichier original n'est jamais modifié. Le PDF produit conserve chaque page
sous forme d'image et ajoute une couche texte invisible générée par Tesseract.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path

MAX_INPUT_BYTES = 250 * 1024 * 1024
MAX_PAGES = 1000


@dataclass(frozen=True)
class PageResult:
    page: int
    image: str
    text: str
    method: str
    confidence: float | None
    characters: int
    requires_review: bool


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def normalize_ocr_text(value: str) -> str:
    """Nettoyage conservateur : aucun mot ni caractère juridique n'est réécrit."""
    value = value.replace("\r\n", "\n").replace("\r", "\n").replace("\x0c", "")
    value = "\n".join(line.rstrip() for line in value.splitlines())
    return re.sub(r"\n{4,}", "\n\n\n", value).strip()


def page_requires_review(text: str, confidence: float | None) -> bool:
    return len(text.strip()) < 40 or (confidence is not None and confidence < 80)


def configure_tesseract(language: str, tessdata_dir: Path | None = None) -> str:
    import pytesseract

    if not shutil.which("tesseract"):
        windows_binary = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
        if windows_binary.exists():
            pytesseract.pytesseract.tesseract_cmd = str(windows_binary)
    config = "--oem 1 --psm 6"
    if tessdata_dir:
        if not tessdata_dir.is_dir():
            raise ValueError("Dossier tessdata introuvable")
        resolved_tessdata = tessdata_dir.resolve().as_posix()
        if " " in resolved_tessdata:
            raise ValueError("Le chemin tessdata ne doit pas contenir d'espace sous Windows")
        config += f" --tessdata-dir {resolved_tessdata}"
    available = set(pytesseract.get_languages(config=config))
    required = set(language.split("+"))
    missing = sorted(required - available)
    if missing:
        raise RuntimeError(
            "Modèles OCR manquants : " + ", ".join(missing)
            + ". Installez les fichiers .traineddata correspondants avant conversion."
        )
    return config


def _ocr_page(image, language: str, config: str):
    import pytesseract

    data = pytesseract.image_to_data(
        image, lang=language, config=config,
        output_type=pytesseract.Output.DICT,
    )
    confidences = [float(v) for v in data.get("conf", []) if str(v) not in {"-1", ""}]
    confidence = round(sum(confidences) / len(confidences), 2) if confidences else None
    text = normalize_ocr_text(pytesseract.image_to_string(image, lang=language, config=config))
    words = []
    for index, value in enumerate(data.get("text", [])):
        word = str(value).strip()
        if not word:
            continue
        words.append({
            "text": word,
            "left": int(data["left"][index]), "top": int(data["top"][index]),
            "width": int(data["width"][index]), "height": int(data["height"][index]),
        })
    return text, confidence, words


def build_copy(
    input_path: Path, output_dir: Path, *, language: str = "fra+eng", dpi: int = 220,
    tessdata_dir: Path | None = None,
) -> dict:
    import fitz
    from PIL import Image

    config = configure_tesseract(language, tessdata_dir)
    original = input_path.read_bytes()
    if not original or len(original) > MAX_INPUT_BYTES:
        raise ValueError("Fichier vide ou supérieur à 250 Mo")
    output_dir.mkdir(parents=True, exist_ok=True)
    pages_dir = output_dir / "pages"
    text_dir = output_dir / "text"
    pages_dir.mkdir(exist_ok=True)
    text_dir.mkdir(exist_ok=True)

    if original.startswith(b"%PDF"):
        source = fitz.open(stream=original, filetype="pdf")
    else:
        image = Image.open(input_path)
        image.verify()
        source = fitz.open()
        page = source.new_page(width=image.width, height=image.height)
        page.insert_image(page.rect, filename=str(input_path))
    if source.page_count > MAX_PAGES:
        raise ValueError("Document supérieur à 1 000 pages")

    searchable = fitz.open()
    results: list[PageResult] = []
    zoom = dpi / 72
    for index, page in enumerate(source, start=1):
        pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False, colorspace=fitz.csRGB)
        image_path = pages_dir / f"page-{index:04d}.png"
        pixmap.save(str(image_path))
        image = Image.open(image_path)
        text, confidence, words = _ocr_page(image, language, config)
        text_path = text_dir / f"page-{index:04d}.txt"
        text_path.write_text(text, encoding="utf-8")
        output_page = searchable.new_page(width=image.width, height=image.height)
        output_page.insert_image(output_page.rect, filename=str(image_path))
        for word in words:
            try:
                output_page.insert_text(
                    fitz.Point(word["left"], word["top"] + word["height"]),
                    word["text"], fontsize=max(4, word["height"] * 0.8),
                    fontname="helv", render_mode=3, overlay=True,
                )
            except (RuntimeError, UnicodeEncodeError):
                # L'image reste la référence. Un glyphe non pris en charge ne
                # doit jamais interrompre ni altérer la copie visuelle.
                continue
        results.append(PageResult(
            page=index,
            image=image_path.relative_to(output_dir).as_posix(),
            text=text_path.relative_to(output_dir).as_posix(),
            method="TESSERACT_IMAGE_TEXT_LAYER",
            confidence=confidence,
            characters=len(text),
            requires_review=page_requires_review(text, confidence),
        ))

    pdf_path = output_dir / "copie-fidele-recherchable.pdf"
    searchable.save(str(pdf_path), garbage=4, deflate=True)
    pdf_bytes = pdf_path.read_bytes()
    manifest = {
        "schema": "baobab-ocr-copy-v1",
        "original": {
            "filename": input_path.name,
            "sha256": sha256_bytes(original),
            "bytes": len(original),
        },
        "searchable_pdf": {
            "filename": pdf_path.name,
            "sha256": sha256_bytes(pdf_bytes),
            "bytes": len(pdf_bytes),
            "visual_fidelity": "PAGE_IMAGE",
            "text_layer": "OCR_INVISIBLE",
        },
        "language": language,
        "dpi": dpi,
        "pages": [asdict(result) for result in results],
        "pages_total": len(results),
        "pages_to_review": sum(result.requires_review for result in results),
        "legal_validation_performed": False,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--language", default="fra+eng")
    parser.add_argument("--dpi", type=int, default=220, choices=range(150, 401))
    parser.add_argument("--tessdata-dir", type=Path)
    args = parser.parse_args()
    print(json.dumps(build_copy(
        args.input, args.output, language=args.language, dpi=args.dpi,
        tessdata_dir=args.tessdata_dir,
    ), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
