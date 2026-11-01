"""Load the chunks of one corpus ("real" or "synthetic") from the database."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..storage import models


@dataclass(frozen=True)
class CorpusChunk:
    id: str
    doc_id: str
    split: str
    language: str
    text: str
    section_title: str | None
    chunker_version: str

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
        select(models.Chunk, models.Document.split, models.Document.chunker_version)
        .join(models.Document)
        .where(models.Document.is_synthetic.is_(kind == "synthetic"))
        .order_by(models.Chunk.document_id, models.Chunk.idx)).all()
    return [CorpusChunk(c.id, c.document_id, split, c.language, c.text, c.section_title, cv)
            for c, split, cv in rows]
