"""Load the chunks of one corpus ("real" or "synthetic") from the database."""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..storage import models

# last article heading in a section title: "386-modda. ..." or "Статья 386. ..."
_ARTICLE_RE = re.compile(r"(?:^|/ )\s*(?:(\d{1,5})\s*-\s*(?:modda|модда)\b|статья\s+(\d{1,5})\b)",
                         re.IGNORECASE)


def article_number(section_title: str | None) -> int | None:
    found = _ARTICLE_RE.findall(section_title or "")
    return int(found[-1][0] or found[-1][1]) if found else None


@dataclass(frozen=True)
class CorpusChunk:
    id: str
    doc_id: str
    split: str  # the chunk's own split (document split, or chapter-group split)
    language: str
    text: str
    section_title: str | None
    chunker_version: str
    group_id: str | None = None  # the act / document group (same for all language versions)
    split_group: str | None = None  # the split unit: document group or "<act>/ch<N>"

    @property
    def article_key(self) -> tuple[str, int] | None:
        """(group, article number), equal for all chunks and all language versions of one
        article; None when the chunk is not inside a numbered article."""
        n = article_number(self.section_title)
        return (self.group_id or self.doc_id, n) if n is not None else None

    @property
    def index_text(self) -> str:
        """Text used for indexing: the section title is prepended when the chunk is a
        continuation of a section whose heading it does not contain."""
        if self.section_title and not self.text.startswith(self.section_title.split(" / ")[-1]):
            return f"{self.section_title}\n{self.text}"
        return self.text


KINDS = ("real", "synthetic")


def load_corpus(session: Session, kind: str) -> list[CorpusChunk]:
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}")
    rows = session.execute(
        select(models.Chunk, models.Chunk.split, models.Document.chunker_version,
               models.Document.group_id, models.Chunk.split_group)
        .join(models.Document)
        .where(models.Document.is_synthetic.is_(kind == "synthetic"))
        .order_by(models.Chunk.document_id, models.Chunk.idx)).all()
    return [CorpusChunk(c.id, c.document_id, split, c.language, c.text, c.section_title, cv,
                        g, sg)
            for c, split, cv, g, sg in rows]
