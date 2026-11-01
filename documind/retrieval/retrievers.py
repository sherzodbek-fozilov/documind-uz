"""Retrievers over one corpus. Each returns chunk ids, best first.

``doc_id`` restricts the search to one document (the "document" scope, used when a user
asks about a specific uploaded file); otherwise the whole corpus is searched.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import numpy as np

from .analyzers import get_analyzer
from .bm25 import build
from .corpus import CorpusChunk
from .hybrid import rrf


class BM25Retriever:
    def __init__(self, chunks: Sequence[CorpusChunk], analyzer: str = "fold+stem6",
                 k1: float = 1.2, b: float = 0.75):
        self.name = f"bm25[{analyzer}]"
        self.chunks = list(chunks)
        self.analyze = get_analyzer(analyzer)
        self.index = build([c.index_text for c in self.chunks], self.analyze, k1=k1, b=b)
        self._by_doc: dict[str, set[int]] = {}
        for i, c in enumerate(self.chunks):
            self._by_doc.setdefault(c.doc_id, set()).add(i)

    def search(self, query: str, k: int = 10, doc_id: str | None = None) -> list[str]:
        cand = self._by_doc.get(doc_id, set()) if doc_id else None
        return [self.chunks[i].id for i, _ in self.index.search(self.analyze(query), k, cand)]


class DenseRetriever:
    def __init__(self, chunks: Sequence[CorpusChunk], embedder, collection: str,
                 qdrant_url: str | None = None, cache_dir: Path | None = None):
        from .dense import QdrantIndex

        self.name = "e5_small"
        self.embedder = embedder
        self.chunks = list(chunks)
        vecs = embedder.embed_passages([c.index_text for c in self.chunks], cache_dir=cache_dir)
        self.index = QdrantIndex(collection, vecs.shape[1], url=qdrant_url)
        self.index.add([c.id for c in self.chunks], vecs,
                       [{"doc_id": c.doc_id, "language": c.language} for c in self.chunks])

    def search(self, query: str, k: int = 10, doc_id: str | None = None) -> list[str]:
        vec: np.ndarray = self.embedder.embed_queries([query])[0]
        return [cid for cid, _ in self.index.search(vec, k, doc_id=doc_id)]


class HybridRetriever:
    def __init__(self, retrievers: Sequence, rrf_k: int = 60, depth: int = 100):
        self.name = "hybrid_rrf"
        self.retrievers, self.rrf_k, self.depth = list(retrievers), rrf_k, depth

    def search(self, query: str, k: int = 10, doc_id: str | None = None) -> list[str]:
        lists = [r.search(query, self.depth, doc_id) for r in self.retrievers]
        return rrf(lists, k=self.rrf_k, top_n=k)
