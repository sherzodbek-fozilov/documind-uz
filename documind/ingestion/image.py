"""Scanned images (PNG / JPEG / TIFF, incl. multi-page TIFF) via OCR."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageSequence

from .ocr import ocr_image
from .types import ParsedDocument, ParsedPage

IMAGE_MIMES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
               ".tif": "image/tiff", ".tiff": "image/tiff"}


def parse_image(path: Path, *, ocr_langs: str) -> ParsedDocument:
    pages, warnings = [], []
    with Image.open(path) as img:
        for i, frame in enumerate(ImageSequence.Iterator(img), start=1):
            gray = frame.convert("L")
            blocks, conf = ocr_image(gray, ocr_langs)  # bboxes stay in pixels
            if not blocks:
                warnings.append(f"page {i}: OCR found no text")
            pages.append(ParsedPage(page_no=i, blocks=blocks, is_ocr=True, ocr_confidence=conf,
                                    width=float(gray.width), height=float(gray.height)))
    return ParsedDocument(filename=path.name, mime=IMAGE_MIMES[path.suffix.lower()],
                          pages=pages, warnings=warnings)
