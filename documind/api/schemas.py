"""Request and response models of the API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from ..qa.citations import Citation
from ..qa.service import AskResult, Passage


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    corpus: Literal["real", "synthetic", "user"] = "real"
    # restrict the search to one document ("document" scope); None = whole corpus
    document_id: str | None = None
    top_k: int | None = Field(None, ge=1, le=10)


class CitationOut(BaseModel):
    document_id: str
    chunk_id: str
    quote: str = Field(description="exact span of the chunk text: text[quote_start:quote_end]")
    quote_start: int
    quote_end: int
    anchor: str | None = Field(None, description="element id in the source (lex.uz)")
    link: str | None = Field(None, description="source URL, with #anchor for lex.uz")

    @classmethod
    def of(cls, c: Citation) -> CitationOut:
        return cls(document_id=c.document_id, chunk_id=c.chunk_id, quote=c.quote,
                   quote_start=c.start, quote_end=c.end, anchor=c.anchor, link=c.link)


class PassageOut(CitationOut):
    rank: int
    section_title: str | None
    language: str
    text: str = Field(description="the whole passage (chunk text); "
                                  "quote == text[quote_start:quote_end]")

    @classmethod
    def of_passage(cls, p: Passage) -> PassageOut:
        return cls(rank=p.rank, section_title=p.section_title, language=p.language,
                   text=p.text,
                   **CitationOut.of(p.citation).model_dump())


class CitationCheckOut(BaseModel):
    checked: int
    valid: int
    failures: dict[str, int]


class AskResponse(BaseModel):
    question: str
    mode: Literal["extractive", "llm"]
    corpus: str
    retriever: str
    passages: list[PassageOut]
    answer: str | None = Field(None, description="LLM mode only")
    citations: list[CitationOut] = Field(default_factory=list,
                                         description="LLM mode only: citations that passed "
                                                     "the check")
    citation_check: CitationCheckOut

    @classmethod
    def of(cls, r: AskResult) -> AskResponse:
        return cls(question=r.question, mode=r.mode, corpus=r.corpus, retriever=r.retriever,
                   passages=[PassageOut.of_passage(p) for p in r.passages], answer=r.answer,
                   citations=[CitationOut.of(c) for c in r.citations],
                   citation_check=CitationCheckOut(**r.citation_check.as_dict()))


class DocumentOut(BaseModel):
    id: str
    title: str
    language: str
    corpus: Literal["real", "synthetic", "user"]
    is_synthetic: bool
    filename: str
    source: str | None
    edition: str | None
    kind: str | None = Field(None, description="type from the source manifest, e.g. 'law'")
    n_chunks: int


class OutlineSectionOut(BaseModel):
    idx: int = Field(description="index of the section's first passage in the document")
    chunk_id: str
    title: str | None = Field(description="heading path, parts joined with ' / '")
    chapter: int | None
    n_passages: int


class OutlineOut(BaseModel):
    document_id: str
    n_passages: int
    sections: list[OutlineSectionOut]


class DocumentPassageOut(BaseModel):
    idx: int
    chunk_id: str
    section_title: str | None
    char_start: int = Field(description="offset of the passage in the document text")
    char_end: int
    text: str


class DocumentPassagesOut(BaseModel):
    document_id: str
    total: int = Field(description="number of passages in the document")
    start: int = Field(description="index of the first passage returned")
    passages: list[DocumentPassageOut]


class HealthOut(BaseModel):
    status: Literal["ok"]
    mode: str
    retriever: str
    documents: int
    chunks: int
    user_documents: int
    public_demo: bool = Field(False, description="uploads disabled, corpus read-only")


class UploadOut(BaseModel):
    document_id: str
    status: Literal["ingested", "duplicate"]
    corpus: Literal["user"] = "user"
    filename: str
    n_pages: int
    n_ocr_pages: int
    n_chunks: int
    language: str
    warnings: list[str]
