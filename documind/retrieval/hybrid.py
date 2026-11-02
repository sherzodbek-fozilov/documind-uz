"""Reciprocal rank fusion (Cormack, Clarke & Büttcher, SIGIR 2009)."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence


def rrf(rankings: Sequence[Sequence[str]], k: int = 60, top_n: int | None = None) -> list[str]:
    """Fuse ranked lists of ids: score(d) = sum over lists of 1 / (k + rank), rank from 1.

    Ties are broken by the best rank the id reached in any list, then by id, so the
    result is deterministic.
    """
    score: dict[str, float] = defaultdict(float)
    best: dict[str, int] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            score[item] += 1.0 / (k + rank)
            best[item] = min(best.get(item, rank), rank)
    fused = sorted(score, key=lambda d: (-score[d], best[d], d))
    return fused[:top_n] if top_n else fused
