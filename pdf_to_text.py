#!/usr/bin/env python3
"""Convert PDFs from the medicopdf directory into a JSON file.

The script reads every PDF in ``medicopdf/``, extracts textual content and
stores the result in ``output/medicopdf.json``.  It attempts to extract text
natively and falls back to OCR (using Tesseract) for scanned documents or
handwritten text.  Images such as logos or signatures are ignored.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List

import pdfplumber
import pytesseract
from pdf2image import convert_from_path
from PIL import Image

PDF_DIR = Path("medicopdf")
OUTPUT_FILE = Path("output/medicopdf.json")


def extract_text_from_pdf(pdf_path: Path) -> str:
    """Return the text content of a PDF file.

    The function first tries to extract text using ``pdfplumber``.  If the
    page contains little or no text, it falls back to OCR via Tesseract in
    order to support scanned documents and handwriting.
    """

    text_parts: List[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for index, page in enumerate(pdf.pages, start=1):
            txt = page.extract_text() or ""
            if not txt.strip():
                images = convert_from_path(str(pdf_path), first_page=index, last_page=index)
                ocr_chunks: List[str] = []
                for image in images:
                    ocr_chunks.append(
                        pytesseract.image_to_string(
                            image, lang="por", config="--oem 1 --psm 6"
                        )
                    )
                txt = "\n".join(ocr_chunks)
            text_parts.append(txt)
    return "\n".join(text_parts)


def main() -> None:
    data = {"medico": {"pdf": []}}

    if not PDF_DIR.exists():
        logging.warning("Diretório %s não encontrado; criando-o.", PDF_DIR)
        PDF_DIR.mkdir(parents=True, exist_ok=True)

    for pdf_file in sorted(PDF_DIR.glob("*.pdf")):
        try:
            text = extract_text_from_pdf(pdf_file)
        except Exception as exc:  # pragma: no cover - logging of failures only
            logging.error("Erro ao processar %s: %s", pdf_file.name, exc)
            text = ""
        data["medico"]["pdf"].append(
            {"nome_do_arquivo": pdf_file.name, "texto": text}
        )

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_FILE.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
