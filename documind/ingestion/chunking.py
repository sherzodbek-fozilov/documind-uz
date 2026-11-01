"""Structure-aware chunking for legal documents.

1. Pages and blocks are concatenated into one document text; every block keeps its
   character offsets, so a chunk is always an exact span ``doc_text[start:end]``. This
   is what makes citation checks and passage highlighting possible later.
2. Headings (articles "5-modda" / "5-модда" / "Статья 5", chapters "I bob" / "Глава 1",
   numbered upper-case section titles, DOCX heading styles) start a new section.
3. Blocks of a section are packed greedily up to ``max_words``. A chunk never crosses a
   section boundary. Blocks longer than ``max_words`` are split at sentence ends, and a
   sentence longer than ``max_words`` is split at word boundaries. A heading is always
   kept together with the text that follows it (this may exceed ``max_words`` slightly).
4. No overlap between chunks: each passage belongs to exactly one chunk, so a gold label
   (``gold_chunk``) is unambiguous.
"""

from __future__ import annotations

import bisect
import re
from dataclasses import dataclass

from .text import detect_language, word_count
from .types import Chunk, PageSpan, ParsedDocument

BLOCK_SEP = "\n\n"
CHUNKER_NAME = "struct-v1"

_HEADING_RE = re.compile(
    r"""^(
        \d{1,3}\s*-\s*(modda|модда|bob|боб|bo[ʻ']?lim|бўлим|band|банд)\b   # 5-modda, 2-bob
      | (статья|глава|раздел|modda|модда)\s+\d{1,3}\b                      # Статья 5
      | [IVXLC]{1,6}\s*[.\-]?\s*(bob|боб|глава|раздел|bo[ʻ']?lim|бўлим)\b   # II bob, IV глава
      | (глава|раздел|bob|боб)\s+[IVXLC]{1,6}\b                             # Глава IV
    )""",
    re.IGNORECASE | re.VERBOSE,
)
_NUMBERED_RE = re.compile(r"^\d{1,2}\.?\s+\S")  # "1. PREDMET" (but not "1.1. ...")
# split after . ! ? ; : preceded by a letter, so clause numbers like "1.1." stay attached
_SENTENCE_END_RE = re.compile(r"(?<=[^\W\d_][.!?;:])\s+(?=\S)")
MAX_HEADING_CHARS = 120


def _upper_ratio(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    return sum(c.isupper() for c in letters) / len(letters) if letters else 0.0


def is_heading(text: str, kind: str = "text") -> bool:
    if kind == "heading":
        return True
    if kind == "table" or len(text) > MAX_HEADING_CHARS:
        return False
    if _HEADING_RE.match(text):
        return True
    if _NUMBERED_RE.match(text) and _upper_ratio(text) > 0.6:
        return True
    return len(text) >= 4 and word_count(text) <= 12 and _upper_ratio(text) > 0.8


@dataclass
class _Unit:
    start: int
    end: int
    words: int
    heading: bool


def assemble(doc: ParsedDocument) -> tuple[str, list[PageSpan], list[_Unit]]:
    """Concatenate all blocks into one text and record page and block offsets."""
    parts: list[str] = []
    pos = 0
    spans: list[PageSpan] = []
    units: list[_Unit] = []
    for page in doc.pages:
        page_start = pos
        block_meta: list[dict] = []
        for block in page.blocks:
            if parts:
                parts.append(BLOCK_SEP)
                pos += len(BLOCK_SEP)
                if not block_meta:  # first block on this page: page starts after separator
                    page_start = pos
            start, end = pos, pos + len(block.text)
            parts.append(block.text)
            pos = end
            block_meta.append({"start": start - page_start, "end": end - page_start,
                               "kind": block.kind,
                               "bbox": list(block.bbox) if block.bbox else None})
            units.append(_Unit(start, end, word_count(block.text),
                               is_heading(block.text, block.kind)))
        spans.append(PageSpan(page.page_no, page_start, pos if block_meta else page_start,
                              block_meta))
    return "".join(parts), spans, units


def _split_long(text: str, unit: _Unit, max_words: int) -> list[_Unit]:
    """Split one oversized block into sentence- (then word-) level units."""
    local = text[unit.start:unit.end]
    pieces: list[tuple[int, int]] = []
    prev = 0
    for m in _SENTENCE_END_RE.finditer(local):
        pieces.append((prev, m.start()))
        prev = m.end()
    pieces.append((prev, len(local)))
    out: list[_Unit] = []
    for s, e in pieces:
        words = list(re.finditer(r"\S+", local[s:e]))
        for i in range(0, len(words), max_words):
            group = words[i:i + max_words]
            ws, we = s + group[0].start(), s + group[-1].end()
            out.append(_Unit(unit.start + ws, unit.start + we, len(group), False))
    return out


PREAMBLE_MAX_WORDS = 20


def _sections(units: list[_Unit]) -> list[list[_Unit]]:
    sections: list[list[_Unit]] = []
    for u in units:
        if u.heading:
            # consecutive headings ("II BOB" then "5-modda. ...") form one section title
            if sections and all(x.heading for x in sections[-1]):
                sections[-1].append(u)
            else:
                sections.append([u])
        else:
            if not sections:
                sections.append([])
            sections[-1].append(u)
    # a short heading-less preamble (e.g. a header line) joins the following section
    if (len(sections) > 1 and not any(u.heading for u in sections[0])
            and sum(u.words for u in sections[0]) < PREAMBLE_MAX_WORDS):
        sections[1] = sections[0] + sections[1]
        sections.pop(0)
    return sections


def chunk_document(doc: ParsedDocument, max_words: int = 180) -> tuple[str, list[PageSpan],
                                                                         list[Chunk]]:
    text, spans, units = assemble(doc)
    page_starts = [s.char_start for s in spans]

    def page_at(offset: int) -> int:
        i = max(bisect.bisect_right(page_starts, offset) - 1, 0)
        return spans[i].page_no

    chunks: list[Chunk] = []
    for section in _sections(units):
        title_units = [u for u in section if u.heading]  # may be preceded by a preamble
        title = " / ".join(text[u.start:u.end] for u in title_units)[:300] or None
        expanded: list[_Unit] = []
        for u in section:
            expanded.extend(_split_long(text, u, max_words) if u.words > max_words else [u])
        group: list[_Unit] = []
        for u in expanded + [None]:
            fits = sum(g.words for g in group) + (u.words if u else 0) <= max_words
            # a heading is never the last unit of a chunk: it takes the next unit along
            ends_with_heading = bool(group) and group[-1].heading
            if u is not None and (not group or fits or ends_with_heading):
                group.append(u)
                continue
            start, end = group[0].start, group[-1].end
            body = text[start:end]
            chunks.append(Chunk(idx=len(chunks), char_start=start, char_end=end, text=body,
                                page_start=page_at(start), page_end=page_at(end - 1),
                                section_title=title, language=detect_language(body),
                                n_words=word_count(body)))
            group = [u] if u is not None else []
    return text, spans, chunks


def chunker_version(max_words: int) -> str:
    return f"{CHUNKER_NAME}-w{max_words}"
