"""Ask a question: retrieve chunks, quote the best passage of each, check citations.

Used by the API and by ``scripts/eval_citations.py``. Indexes are built lazily, once
per corpus, from the chunks in the database; restart the process after ingesting new
documents with the CLI.

Corpora: "real" and "synthetic" (evaluation corpora, main database) and "user" (uploaded
documents, a separate database; its index is rebuilt after every upload). Without a
user database (e.g. in the eval scripts) the "user" corpus does not exist.
"""

from __future__ import annotations

import threading
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from ..config import Settings
from ..ingestion.ocr import OCRUnavailableError
from ..ingestion.pipeline import ingest_file
from ..ingestion.uploads import UploadRejected
from ..retrieval.corpus import CorpusChunk, load_corpus
from ..retrieval.retrievers import BM25Retriever, DenseRetriever, HybridRetriever
from ..storage import models
from .citations import CheckReport, Citation, check_citation, locate_quote, summarize
from .llm import LLMClient, build_prompt, load_llm, parse_response
from .passages import Segment, chunk_segments, select_quote, source_link

CORPORA = ("real", "synthetic", "user")


class UnknownDocument(LookupError):
    pass


class EmptyCorpus(LookupError):
    pass


class LLMOutputError(RuntimeError):
    pass


@dataclass(frozen=True)
class Passage:
    rank: int
    document_id: str
    chunk_id: str
    section_title: str | None
    language: str
    citation: Citation  # the extractive quote of this chunk
    text: str  # the whole chunk text; citation.quote == text[citation.start:citation.end]


@dataclass
class AskResult:
    question: str
    mode: str
    corpus: str
    retriever: str
    passages: list[Passage]
    answer: str | None = None  # LLM mode only
    citations: list[Citation] = field(default_factory=list)  # LLM mode: valid ones only
    # extractive: the passages' quotes; LLM: every citation the model made
    citation_check: CheckReport = field(default_factory=CheckReport)


@dataclass
class _Index:
    chunks: dict[str, CorpusChunk]
    offsets: dict[str, tuple[int, int]]  # chunk -> (char_start, char_end) in its document
    pages: dict[str, list[tuple[int, list[dict]]]]  # document -> [(page start, blocks)]
    sources: dict[str, str | None]
    bm25: BM25Retriever
    retriever: object

    def segments(self, chunk_id: str) -> list[Segment]:
        chunk = self.chunks[chunk_id]
        start, end = self.offsets[chunk_id]
        return chunk_segments(start, end, self.pages.get(chunk.doc_id, []))


class QAService:
    def __init__(self, session_factory: sessionmaker[Session], settings: Settings, *,
                 llm: LLMClient | None = None, embedder=None,
                 user_session_factory: sessionmaker[Session] | None = None):
        self.session_factory = session_factory
        self.user_session_factory = user_session_factory
        self.settings = settings
        self.mode = settings.answer_mode
        self.llm = llm if llm is not None or self.mode != "llm" else load_llm(settings)
        self._embedder = embedder
        self._indexes: dict[str, _Index] = {}
        self._lock = threading.Lock()
        self._ingest_lock = threading.Lock()  # one upload is ingested at a time

    # --- corpus -------------------------------------------------------------------------
    def _factory(self, corpus: str) -> sessionmaker[Session]:
        if corpus not in CORPORA:
            raise ValueError(f"corpus must be one of {CORPORA}")
        if corpus != "user":
            return self.session_factory
        if self.user_session_factory is None:
            raise EmptyCorpus("uploads are not configured (no user database)")
        return self.user_session_factory

    def documents(self) -> list[dict]:
        out = []
        for corpus_db in ("main", "user"):
            if corpus_db == "user" and self.user_session_factory is None:
                continue
            factory = self.session_factory if corpus_db == "main" else self.user_session_factory
            with factory() as s:
                n_chunks = dict(s.execute(select(models.Chunk.document_id, func.count())
                                          .group_by(models.Chunk.document_id)).all())
                docs = s.scalars(select(models.Document).order_by(models.Document.id)).all()
                out += [{"id": d.id, "title": (d.meta or {}).get("title") or d.filename,
                         "language": d.language, "is_synthetic": d.is_synthetic,
                         "corpus": ("user" if corpus_db == "user" else
                                    "synthetic" if d.is_synthetic else "real"),
                         "filename": d.filename, "source": d.source,
                         "edition": (d.meta or {}).get("edition"),
                         "n_chunks": n_chunks.get(d.id, 0)} for d in docs]
        return out

    def counts(self) -> dict[str, int]:
        def count(factory, model) -> int:
            with factory() as s:
                return s.scalar(select(func.count()).select_from(model))

        out = {"documents": count(self.session_factory, models.Document),
               "chunks": count(self.session_factory, models.Chunk), "user_documents": 0}
        if self.user_session_factory is not None:
            out["user_documents"] = count(self.user_session_factory, models.Document)
        return out

    def index(self, corpus: str) -> _Index:
        self._factory(corpus)  # validates the corpus name
        with self._lock:
            if corpus not in self._indexes:
                self._indexes[corpus] = self._build(corpus)
            return self._indexes[corpus]

    def _build(self, corpus: str) -> _Index:
        synthetic = corpus == "synthetic"
        # the user database holds only uploads, all stored with is_synthetic = False
        with self._factory(corpus)() as s:
            chunks = load_corpus(s, "synthetic" if synthetic else "real")
            offsets = {cid: (a, b) for cid, a, b in s.execute(
                select(models.Chunk.id, models.Chunk.char_start, models.Chunk.char_end)
                .join(models.Document).where(models.Document.is_synthetic.is_(synthetic)))}
            pages: dict[str, list] = defaultdict(list)
            for doc_id, start, blocks in s.execute(
                    select(models.Page.document_id, models.Page.char_start, models.Page.blocks)
                    .join(models.Document).where(models.Document.is_synthetic.is_(synthetic))
                    .order_by(models.Page.document_id, models.Page.page_no)):
                pages[doc_id].append((start, blocks or []))
            sources = dict(s.execute(select(models.Document.id, models.Document.source)
                                     .where(models.Document.is_synthetic.is_(synthetic))).all())
        if not chunks:
            raise EmptyCorpus(f"no {corpus} documents ingested" if corpus != "user"
                              else "no documents uploaded yet")
        bm25 = BM25Retriever(chunks, self.settings.bm25_analyzer)
        retriever = bm25
        if self.settings.api_retriever == "hybrid":
            if self._embedder is None:
                from ..retrieval.embedder import E5Embedder
                self._embedder = E5Embedder(self.settings.embed_model_dir)
            dense = DenseRetriever(chunks, self._embedder, f"api_chunks_{corpus}",
                                   qdrant_url=self.settings.qdrant_url,
                                   cache_dir=self.settings.embed_cache_dir)
            retriever = HybridRetriever([bm25, dense], rrf_k=self.settings.rrf_k,
                                        depth=self.settings.retrieval_depth)
        return _Index({c.id: c for c in chunks}, offsets, dict(pages), sources, bm25,
                      retriever)

    # --- uploads ------------------------------------------------------------------------
    def add_user_document(self, path: Path, filename: str, sha256: str) -> dict:
        """Parse (with OCR if needed) and store an upload in the user corpus.

        Returns the stored document: id, status ("ingested", or "duplicate" for a file
        uploaded before, then with the earlier upload's details), filename, page, OCR
        page and chunk counts, language and parser warnings.

        ``path`` must already have passed the checks in ``ingestion.uploads``. Raises
        UploadRejected for files that cannot be parsed, need OCR on a server without
        tesseract, or contain no text (such documents are not kept)."""
        factory = self._factory("user")
        settings = self.settings.model_copy(update={"storage_dir":
                                                    self.settings.user_storage_dir})
        with self._ingest_lock, factory() as s:
            try:
                res = ingest_file(path, s, settings, doc_id=f"user-{sha256[:16]}",
                                  source=None, filename=filename,
                                  meta={"kind": "upload"})
            except OCRUnavailableError as exc:
                s.rollback()
                raise UploadRejected(503, "this file needs OCR, but OCR (tesseract) is not "
                                          "available on this server") from exc
            except Exception as exc:  # parser errors on untrusted input
                s.rollback()
                raise UploadRejected(422, f"the file could not be read "
                                          f"({type(exc).__name__})") from exc
            if res.status == "ingested" and res.n_chunks == 0:
                doc = s.get(models.Document, res.doc_id)
                stored = Path(doc.storage_path)
                s.delete(doc)
                s.commit()
                stored.unlink(missing_ok=True)
                raise UploadRejected(422, "no text was found in the file"
                                     + (" (OCR found none)" if res.n_ocr_pages else ""))
            doc = s.get(models.Document, res.doc_id)
            info = {"document_id": doc.id, "status": res.status, "filename": doc.filename,
                    "n_pages": doc.n_pages, "n_ocr_pages": doc.n_ocr_pages,
                    "n_chunks": len(doc.chunks), "language": doc.language,
                    "warnings": list(doc.warnings or [])}
        if res.status == "ingested":
            with self._lock:
                self._indexes.pop("user", None)  # rebuilt on the next question
        return info

    # --- asking -------------------------------------------------------------------------
    def _citation(self, idx: _Index, chunk: CorpusChunk, start: int, end: int,
                  anchor: str | None = None, *, find_anchor: bool = False) -> Citation:
        if find_anchor:
            anchor = next((s.anchor for s in idx.segments(chunk.id)
                           if s.start <= start < s.end), None)
        return Citation(chunk.doc_id, chunk.id, chunk.text[start:end], start, end, anchor,
                        source_link(idx.sources.get(chunk.doc_id), anchor))

    def ask(self, question: str, corpus: str = "real", document_id: str | None = None,
            top_k: int | None = None) -> AskResult:
        idx = self.index(corpus)
        if document_id is not None and document_id not in idx.sources:
            raise UnknownDocument(f"document {document_id!r} is not in the {corpus} corpus")
        k = top_k or self.settings.api_top_k
        ids = idx.retriever.search(question, k=k, doc_id=document_id)
        passages = []
        for rank, cid in enumerate(ids, start=1):
            chunk = idx.chunks[cid]
            start, end, anchor = select_quote(chunk.text, idx.segments(cid), question,
                                              idx.bm25.analyze, idx.bm25.index.idf,
                                              self.settings.quote_max_sentences)
            passages.append(Passage(rank, chunk.doc_id, cid, chunk.section_title,
                                    chunk.language, self._citation(idx, chunk, start, end,
                                                                   anchor), chunk.text))
        result = AskResult(question, self.mode, corpus, idx.retriever.name, passages)
        if self.mode != "llm" or not passages:
            result.citation_check = summarize(
                check_citation(p.citation, idx.chunks[p.chunk_id].text, p.document_id)
                for p in passages)
            return result

        prompt = build_prompt(question, [(p.chunk_id, idx.chunks[p.chunk_id].text)
                                         for p in passages])
        raw = self.llm.complete(prompt, self.settings.llm_max_tokens_per_request)
        try:
            result.answer, cited = parse_response(raw)
        except ValueError as exc:  # includes json.JSONDecodeError
            raise LLMOutputError(f"LLM reply is not the expected JSON: {exc}") from exc
        given = {p.chunk_id for p in passages}
        reasons = []
        for cid, quote in cited:
            if cid not in given:
                reasons.append("chunk was not given to the model")
                continue
            chunk = idx.chunks[cid]
            loc = locate_quote(quote, chunk.text)
            if loc is None:
                reasons.append("quote is not in the chunk")
                continue
            citation = self._citation(idx, chunk, *loc, find_anchor=True)
            reason = check_citation(citation, chunk.text, chunk.doc_id)
            reasons.append(reason)
            if reason is None:
                result.citations.append(citation)
        result.citation_check = summarize(reasons)
        return result
