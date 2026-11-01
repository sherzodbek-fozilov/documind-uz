"""DOCX parsing: paragraphs and tables in document order.

DOCX files have no fixed pagination, so the whole document is one logical page (page 1).
"""

from __future__ import annotations

from pathlib import Path

import docx
from docx.table import Table
from docx.text.paragraph import Paragraph

from .text import normalize_block
from .types import Block, ParsedDocument, ParsedPage

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _iter_body(document):
    for child in document.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            yield Paragraph(child, document)
        elif tag == "tbl":
            yield Table(child, document)


def _is_heading(par: Paragraph) -> bool:
    name = (par.style.name or "").lower() if par.style is not None else ""
    return name.startswith("heading") or name == "title"


def parse_docx(path: Path) -> ParsedDocument:
    document = docx.Document(str(path))
    blocks: list[Block] = []
    for item in _iter_body(document):
        if isinstance(item, Paragraph):
            text = normalize_block(item.text)
            if text:
                blocks.append(Block(text=text, kind="heading" if _is_heading(item) else "text"))
        else:
            for row in item.rows:
                cells: list[str] = []
                for cell in row.cells:  # merged cells repeat; keep the first occurrence
                    t = normalize_block(cell.text)
                    if t and (not cells or cells[-1] != t):
                        cells.append(t)
                if cells:
                    blocks.append(Block(text=" | ".join(cells), kind="table"))
    return ParsedDocument(filename=path.name, mime=DOCX_MIME,
                          pages=[ParsedPage(page_no=1, blocks=blocks)])
