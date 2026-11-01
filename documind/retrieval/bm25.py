"""Okapi BM25 over pre-tokenized documents (small in-memory index)."""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from collections.abc import Callable, Sequence


class BM25:
    def __init__(self, k1: float = 1.2, b: float = 0.75):
        self.k1, self.b = k1, b

    def fit(self, docs: Sequence[list[str]]) -> BM25:
        self.n = len(docs)
        self.doc_len = [len(d) for d in docs]
        self.avgdl = sum(self.doc_len) / self.n if self.n else 0.0
        self.postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
        for i, doc in enumerate(docs):
            for term, tf in Counter(doc).items():
                self.postings[term].append((i, tf))
        self.idf = {t: math.log(1 + (self.n - len(p) + 0.5) / (len(p) + 0.5))
                    for t, p in self.postings.items()}
        return self

    def scores(self, query: list[str], candidates: set[int] | None = None) -> dict[int, float]:
        out: dict[int, float] = defaultdict(float)
        for term in set(query):
            idf = self.idf.get(term)
            if idf is None:
                continue
            for i, tf in self.postings[term]:
                if candidates is not None and i not in candidates:
                    continue
                norm = self.k1 * (1 - self.b + self.b * self.doc_len[i] / self.avgdl)
                out[i] += idf * tf * (self.k1 + 1) / (tf + norm)
        return out

    def search(self, query: list[str], k: int = 10,
               candidates: set[int] | None = None) -> list[tuple[int, float]]:
        s = self.scores(query, candidates)
        return sorted(s.items(), key=lambda x: (-x[1], x[0]))[:k]


def build(texts: Sequence[str], analyzer: Callable[[str], list[str]], **params) -> BM25:
    return BM25(**params).fit([analyzer(t) for t in texts])
