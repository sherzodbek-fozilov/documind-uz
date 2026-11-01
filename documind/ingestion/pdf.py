"""PDF parsing: the text layer where it exists, OCR for pages that look scanned."""

from __future__ import annotations

from pathlib import Path

import pymupdf
from PIL import Image

from .ocr import ocr_image
from .text import normalize_block
from .types import Block, ParsedDocument, ParsedPage


def _text_blocks(page: pymupdf.Page) -> list[Block]:
    blocks = []
    for x0, y0, x1, y1, text, _no, block_type in page.get_text("blocks", sort=True):
        if block_type != 0:  # 1 = image block
            continue
        text = normalize_block(text)
        if text:
            blocks.append(Block(text=text, bbox=(x0, y0, x1, y1)))
    return blocks


def render_page(page: pymupdf.Page, dpi: int) -> Image.Image:
    pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)
    return Image.frombytes("L", (pix.width, pix.height), pix.samples)


def parse_pdf(path: Path, *, ocr_langs: str, ocr_dpi: int = 300, min_text_chars: int = 30,
              force_ocr: bool = False, ocr_enabled: bool = True) -> ParsedDocument:
    """Parse a PDF page by page.

    A page whose text layer has fewer than ``min_text_chars`` characters is treated as a
    scan and OCR'd (unless ``ocr_enabled`` is False, in which case a warning is recorded).
    """
    pages: list[ParsedPage] = []
    warnings: list[str] = []
    with pymupdf.open(path) as doc:
        for i, page in enumerate(doc, start=1):
            blocks = [] if force_ocr else _text_blocks(page)
            n_chars = sum(len(b.text) for b in blocks)
            parsed = ParsedPage(page_no=i, blocks=blocks,
                                width=page.rect.width, height=page.rect.height)
            if force_ocr or n_chars < min_text_chars:
                if ocr_enabled:
                    image = render_page(page, ocr_dpi)
                    parsed.blocks, parsed.ocr_confidence = ocr_image(
                        image, ocr_langs, scale=72.0 / ocr_dpi)
                    parsed.is_ocr = True
                    if not parsed.blocks:
                        warnings.append(f"page {i}: OCR found no text")
                else:
                    warnings.append(f"page {i}: looks scanned but OCR is disabled")
            pages.append(parsed)
    return ParsedDocument(filename=path.name, mime="application/pdf", pages=pages,
                          warnings=warnings)
