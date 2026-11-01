from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

JSONType = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    pass


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    # documents with the same group (e.g. translations of one law) always share a split
    group_id: Mapped[str] = mapped_column(String(128), index=True)
    filename: Mapped[str] = mapped_column(String(512))
    mime: Mapped[str] = mapped_column(String(128))
    sha256: Mapped[str] = mapped_column(String(64), unique=True)
    storage_path: Mapped[str] = mapped_column(String(1024))
    n_pages: Mapped[int] = mapped_column(Integer)
    n_ocr_pages: Mapped[int] = mapped_column(Integer, default=0)
    language: Mapped[str] = mapped_column(String(16))
    script_stats: Mapped[dict] = mapped_column(JSONType, default=dict)
    split: Mapped[str] = mapped_column(String(8), index=True)  # "train" | "test"
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    chunker_version: Mapped[str] = mapped_column(String(64))
    warnings: Mapped[list] = mapped_column(JSONType, default=list)
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC))

    pages: Mapped[list[Page]] = relationship(back_populates="document", order_by="Page.page_no",
                                             cascade="all, delete-orphan")
    chunks: Mapped[list[Chunk]] = relationship(back_populates="document", order_by="Chunk.idx",
                                               cascade="all, delete-orphan")


class Page(Base):
    __tablename__ = "pages"
    __table_args__ = (UniqueConstraint("document_id", "page_no"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"),
                                             index=True)
    page_no: Mapped[int] = mapped_column(Integer)
    char_start: Mapped[int] = mapped_column(Integer)  # offsets into Document.text
    char_end: Mapped[int] = mapped_column(Integer)
    is_ocr: Mapped[bool] = mapped_column(Boolean, default=False)
    ocr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    width: Mapped[float | None] = mapped_column(Float, nullable=True)
    height: Mapped[float | None] = mapped_column(Float, nullable=True)
    # [{"start", "end", "kind", "bbox"}] with offsets relative to the page text
    blocks: Mapped[list] = mapped_column(JSONType, default=list)

    document: Mapped[Document] = relationship(back_populates="pages")


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (UniqueConstraint("document_id", "idx"),)

    id: Mapped[str] = mapped_column(String(160), primary_key=True)  # "<doc_id>#c0007"
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"),
                                             index=True)
    idx: Mapped[int] = mapped_column(Integer)
    char_start: Mapped[int] = mapped_column(Integer)
    char_end: Mapped[int] = mapped_column(Integer)
    page_start: Mapped[int] = mapped_column(Integer)
    page_end: Mapped[int] = mapped_column(Integer)
    section_title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    language: Mapped[str] = mapped_column(String(16), index=True)
    n_words: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)

    document: Mapped[Document] = relationship(back_populates="chunks")
