"""Extractive quotes: the best sentence(s) of a retrieved chunk, as an exact span.

A chunk is made of source blocks (lex.uz elements, PDF text blocks, DOCX paragraphs).
The quote is chosen inside one block, so it has one source anchor:

1. Split each non-heading block of the chunk into sentences (same rule as the chunker).
2. Score every window of 1..``max_sentences`` consecutive sentences of one block by the
   summed BM25 idf of the distinct query terms it contains (same analyzer as BM25).
3. Take the best window; ties go to fewer sentences, then to the earlier one. If no
   window shares a term with the query (e.g. a dense hit in the other language), the
   first sentence of the first text block is quoted.

The quote is always ``chunk_text[start:end]``; nothing is rewritten.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from ..ingestion.chunking import _SENTENCE_END_RE

LEXUZ_PREFIXES = ("https://lex.uz/", "https://www.lex.uz/")


@dataclass(frozen=True)
class Segment:
    """One source block (or the part of it) inside a chunk; offsets into the chunk text."""

    start: int
    end: int
    kind: str = "text"
    anchor: str | None = None


def chunk_segments(chunk_start: int, chunk_end: int,
                   pages: Sequence[tuple[int, list[dict]]]) -> list[Segment]:
    """Blocks overlapping the chunk, clipped to it. ``pages``: (page char_start, blocks)
    with block offsets relative to the page, as stored in ``pages.blocks``."""
    out = []
    for page_start, blocks in pages:
        for b in blocks:
            s, e = page_start + b["start"], page_start + b["end"]
            s, e = max(s, chunk_start), min(e, chunk_end)
            if s < e:
                out.append(Segment(s - chunk_start, e - chunk_start, b.get("kind", "text"),
                                   b.get("anchor")))
    return out or [Segment(0, chunk_end - chunk_start)]


def sentence_spans(text: str, start: int, end: int) -> list[tuple[int, int]]:
    """Sentences of ``text[start:end]`` as (start, end) offsets into ``text``, trimmed."""
    spans, prev = [], start
    for m in _SENTENCE_END_RE.finditer(text, start, end):
        spans.append((prev, m.start()))
        prev = m.end()
    spans.append((prev, end))
    out = []
    for s, e in spans:
        piece = text[s:e]
        s += len(piece) - len(piece.lstrip())
        e -= len(piece) - len(piece.rstrip())
        if s < e:
            out.append((s, e))
    return out


def select_quote(text: str, segments: Sequence[Segment], query: str,
                 analyze: Callable[[str], list[str]], idf: dict[str, float],
                 max_sentences: int = 2) -> tuple[int, int, str | None]:
    """(start, end, anchor) of the best quote in ``text`` for ``query``."""
    terms = set(analyze(query))
    body = [s for s in segments if s.kind != "heading"] or list(segments)
    best: tuple | None = None
    fallback: tuple[int, int, str | None] | None = None
    for seg in body:
        sents = sentence_spans(text, seg.start, seg.end)
        if sents and fallback is None:
            fallback = (sents[0][0], sents[0][1], seg.anchor)
        cover = [set(analyze(text[s:e])) & terms for s, e in sents]
        for i in range(len(sents)):
            matched: set[str] = set()
            for n in range(1, max_sentences + 1):
                if i + n > len(sents):
                    break
                matched |= cover[i + n - 1]
                score = sum(idf.get(t, 0.0) for t in matched)
                key = (-round(score, 9), n, sents[i][0])
                if score > 0 and (best is None or key < best[0]):
                    best = (key, (sents[i][0], sents[i + n - 1][1], seg.anchor))
    if best is not None:
        return best[1]
    if fallback is not None:
        return fallback
    return 0, len(text), None


def source_link(source: str | None, anchor: str | None) -> str | None:
    """Link to the cited place: ``<lex.uz page>#<element id>``; the plain URL for other web
    sources; None for non-URL sources (synthetic documents, uploads)."""
    if not source or not source.startswith(("https://", "http://")):
        return None
    if anchor and source.startswith(LEXUZ_PREFIXES):
        return f"{source.split('#', 1)[0]}#{anchor}"
    return source
