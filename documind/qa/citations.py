"""Citations and the citation check.

A citation names a chunk and quotes it. The check is strict on purpose: a citation is
valid only if its quote is an **exact span** of the cited chunk, i.e.
``chunk_text[start:end] == quote`` with a non-empty quote, and the chunk belongs to the
cited document. No fuzzy matching: a paraphrase, a quote with a changed letter or a
quote stitched from two places is invalid. This is what lets the UI highlight the
passage and what keeps an LLM from "citing" text that is not in the source.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass

# quote marks an LLM may wrap a quote in; stripped before the quote is located
_WRAPPERS = "\"'«»„“”‘’`"


@dataclass(frozen=True)
class Citation:
    document_id: str
    chunk_id: str
    quote: str
    start: int  # offsets into the chunk text: quote == chunk_text[start:end]
    end: int
    anchor: str | None = None  # element id in the source (lex.uz), if known
    link: str | None = None  # URL of the source, with #anchor when there is one


def check_citation(citation: Citation, chunk_text: str | None,
                   chunk_document_id: str | None) -> str | None:
    """Return None if the citation is valid, otherwise the reason it is not."""
    if chunk_text is None:
        return "unknown chunk"
    if chunk_document_id != citation.document_id:
        return "chunk is not in the cited document"
    if not citation.quote.strip():
        return "empty quote"
    if not 0 <= citation.start < citation.end <= len(chunk_text):
        return "offsets outside the chunk"
    if chunk_text[citation.start:citation.end] != citation.quote:
        return "quote is not the chunk text at its offsets"
    return None


def locate_quote(quote: str, chunk_text: str) -> tuple[int, int] | None:
    """Offsets of ``quote`` in ``chunk_text`` (first occurrence), exact match only.

    Surrounding whitespace and quote marks are removed first; nothing inside the quote
    is changed. Returns None if the quote does not occur verbatim.
    """
    q = quote.strip().strip(_WRAPPERS).strip()
    if not q:
        return None
    i = chunk_text.find(q)
    return (i, i + len(q)) if i >= 0 else None


@dataclass
class CheckReport:
    checked: int = 0
    valid: int = 0
    failures: Counter | None = None

    @property
    def correctness(self) -> float | None:
        return self.valid / self.checked if self.checked else None

    def as_dict(self) -> dict:
        return {"checked": self.checked, "valid": self.valid,
                "failures": dict(self.failures or {})}


def summarize(reasons: Iterable[str | None]) -> CheckReport:
    """Aggregate the results of ``check_citation`` (None = valid)."""
    report = CheckReport(failures=Counter())
    for reason in reasons:
        report.checked += 1
        if reason is None:
            report.valid += 1
        else:
            report.failures[reason] += 1
    return report
