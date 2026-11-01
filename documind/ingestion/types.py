"""Plain data structures shared by parsers, the chunker and storage."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Block:
    """A paragraph-like unit of text on a page, in reading order."""

    text: str
    kind: str = "text"  # "text" | "heading" | "table"
    # (x0, y0, x1, y1) in PDF points; None for DOCX
    bbox: tuple[float, float, float, float] | None = None


@dataclass
class ParsedPage:
    page_no: int  # 1-based
    blocks: list[Block]
    is_ocr: bool = False
    ocr_confidence: float | None = None  # mean word confidence 0..100, OCR pages only
    width: float | None = None
    height: float | None = None


@dataclass
class ParsedDocument:
    filename: str
    mime: str
    pages: list[ParsedPage]
    warnings: list[str] = field(default_factory=list)


@dataclass
class PageSpan:
    """Where a page lives inside the concatenated document text."""

    page_no: int
    char_start: int
    char_end: int
    # per block: [start, end] offsets relative to the page text, plus bbox and kind
    blocks: list[dict]


@dataclass
class Chunk:
    idx: int
    char_start: int  # offsets into the document text: text == doc_text[char_start:char_end]
    char_end: int
    text: str
    page_start: int
    page_end: int
    section_title: str | None
    language: str
    n_words: int
