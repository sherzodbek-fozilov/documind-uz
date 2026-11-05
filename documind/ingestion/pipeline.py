"""Ingest one file: parse → chunk → store (original file on disk, rows in the database)."""

from __future__ import annotations

import hashlib
import re
import shutil
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings
from ..split import assign_split, document_split, load_overrides, split_group_of
from ..storage import models
from .chunking import chunk_document, chunker_version
from .docx_parser import parse_docx
from .image import IMAGE_MIMES, parse_image
from .lexuz_html import is_lexuz_html, parse_lexuz_html
from .pdf import parse_pdf
from .text import script_counts
from .types import ParsedDocument

SUPPORTED_SUFFIXES = {".pdf", ".docx", ".html", *IMAGE_MIMES}


@dataclass
class IngestResult:
    doc_id: str
    status: str  # "ingested" | "duplicate"
    n_pages: int = 0
    n_ocr_pages: int = 0
    n_chunks: int = 0
    language: str = ""
    split: str = ""
    warnings: list[str] = field(default_factory=list)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def slugify(name: str) -> str:
    slug = re.sub(r"[^\w-]+", "-", name.lower()).strip("-_")
    return slug[:100]


def parse_file(path: Path, settings: Settings, *, force_ocr: bool = False) -> ParsedDocument:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return parse_pdf(path, ocr_langs=settings.ocr_langs, ocr_dpi=settings.ocr_dpi,
                         min_text_chars=settings.ocr_min_text_chars, force_ocr=force_ocr)
    if suffix == ".docx":
        return parse_docx(path)
    if suffix in IMAGE_MIMES:
        return parse_image(path, ocr_langs=settings.ocr_langs)
    if suffix == ".html":
        if not is_lexuz_html(path):
            raise ValueError(f"{path.name}: only lex.uz act pages are supported as HTML")
        return parse_lexuz_html(path)
    raise ValueError(f"unsupported file type: {path.name} (supported: "
                     f"{', '.join(sorted(SUPPORTED_SUFFIXES))})")


def ingest_file(path: Path, session: Session, settings: Settings, *, doc_id: str | None = None,
                group_id: str | None = None, is_synthetic: bool = False,
                source: str | None = None, force_ocr: bool = False,
                split_unit: str = "document", meta: dict | None = None,
                filename: str | None = None) -> IngestResult:
    """``filename``: name stored in ``documents.filename`` (default: the file's own name),
    e.g. the sanitized original name of an upload saved under a temporary name."""
    path = Path(path)
    sha = sha256_file(path)
    existing = session.scalar(select(models.Document).where(models.Document.sha256 == sha))
    if existing is not None:
        return IngestResult(doc_id=existing.id, status="duplicate", split=existing.split)

    doc_id = doc_id or slugify(path.stem) or f"doc-{sha[:12]}"
    if session.get(models.Document, doc_id) is not None:  # same name, different content
        doc_id = f"{doc_id}-{sha[:8]}"
    group_id = group_id or doc_id

    parsed = parse_file(path, settings, force_ocr=force_ocr)
    text, spans, chunks = chunk_document(parsed, max_words=settings.chunk_max_words)

    lang_words: Counter[str] = Counter()
    for c in chunks:
        lang_words[c.language] += c.n_words
    known = {k: v for k, v in lang_words.items() if k != "unknown"}
    language = max(known, key=known.get) if known else "unknown"
    overrides = load_overrides(settings.splits_file)
    chunk_groups = [split_group_of(group_id, split_unit, c.chapter) for c in chunks]
    chunk_splits = [assign_split(g, settings.test_fraction, overrides) for g in chunk_groups]
    split = (assign_split(group_id, settings.test_fraction, overrides)
             if split_unit == "document" else document_split(chunk_splits, "train"))

    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    stored = settings.storage_dir / f"{sha}{path.suffix.lower()}"
    if not stored.exists():
        shutil.copyfile(path, stored)

    pages_by_no = {p.page_no: p for p in parsed.pages}
    doc = models.Document(
        id=doc_id, group_id=group_id, filename=filename or path.name, mime=parsed.mime, sha256=sha,
        storage_path=str(stored), n_pages=len(parsed.pages),
        n_ocr_pages=sum(p.is_ocr for p in parsed.pages), language=language,
        script_stats={**script_counts(text), "chunk_words_by_language": dict(lang_words)},
        split=split, split_unit=split_unit, is_synthetic=is_synthetic, source=source,
        meta={**parsed.meta, **(meta or {})},
        chunker_version=chunker_version(settings.chunk_max_words),
        warnings=parsed.warnings, text=text,
        pages=[models.Page(page_no=s.page_no, char_start=s.char_start, char_end=s.char_end,
                           is_ocr=pages_by_no[s.page_no].is_ocr,
                           ocr_confidence=pages_by_no[s.page_no].ocr_confidence,
                           width=pages_by_no[s.page_no].width,
                           height=pages_by_no[s.page_no].height, blocks=s.blocks)
               for s in spans],
        chunks=[models.Chunk(id=f"{doc_id}#c{c.idx:04d}", idx=c.idx, char_start=c.char_start,
                             char_end=c.char_end, page_start=c.page_start, page_end=c.page_end,
                             section_title=c.section_title, language=c.language,
                             n_words=c.n_words, chapter=c.chapter, split_group=g, split=sp,
                             text=c.text)
                for c, g, sp in zip(chunks, chunk_groups, chunk_splits, strict=True)],
    )
    session.add(doc)
    session.commit()
    return IngestResult(doc_id=doc_id, status="ingested", n_pages=doc.n_pages,
                        n_ocr_pages=doc.n_ocr_pages, n_chunks=len(chunks), language=language,
                        split=split, warnings=parsed.warnings)
