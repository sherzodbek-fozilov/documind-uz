"""Retrieval evaluation: question loading/validation, ranks, Recall@k, MRR, bootstrap CIs.

Definitions (per question; usually one gold chunk, optionally several in "gold_chunks"):
  rank       position of the first gold chunk found in the result list (1 = first), None
             if no gold chunk is in the top ``max_k`` results
  Recall@k   share of questions with rank <= k
  MRR@10     mean of 1/rank over questions, 0 when rank is None or > 10
Confidence intervals: percentile bootstrap over questions (2000 resamples, fixed seed).
"""

from __future__ import annotations

import json
import random
from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

LANGUAGES = ("uz-Latn", "uz-Cyrl", "ru")
SCOPES = ("corpus", "document")
REQUIRED = ("question", "language", "gold_doc", "gold_chunk")


@dataclass
class Question:
    question: str
    language: str
    gold_doc: str
    gold_chunk: str
    scope: str = "corpus"
    status: str = "reviewed"
    draft_question: str | None = None
    line: int = 0
    gold_chunks: tuple[str, ...] = ()  # all acceptable chunks; defaults to (gold_chunk,)

    def __post_init__(self):
        if not self.gold_chunks:
            self.gold_chunks = (self.gold_chunk,)


def load_questions(path: Path) -> tuple[list[Question], list[str]]:
    """Return (questions, problems). Malformed lines are reported, not raised."""
    questions, problems = [], []
    if not path.exists():
        return questions, problems
    for n, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError as exc:
            problems.append(f"{path.name}:{n}: invalid JSON ({exc.msg})")
            continue
        missing = [k for k in REQUIRED if not row.get(k)]
        if missing:
            problems.append(f"{path.name}:{n}: missing {', '.join(missing)}")
            continue
        if row["language"] not in LANGUAGES:
            problems.append(f"{path.name}:{n}: language must be one of {LANGUAGES}")
            continue
        scope = row.get("scope", "corpus")
        if scope not in SCOPES:
            problems.append(f"{path.name}:{n}: scope must be one of {SCOPES}")
            continue
        golds = tuple(row.get("gold_chunks") or [row["gold_chunk"]])
        if row["gold_chunk"] not in golds:
            problems.append(f"{path.name}:{n}: gold_chunk must be one of gold_chunks")
            continue
        questions.append(Question(row["question"], row["language"], row["gold_doc"],
                                  row["gold_chunk"], scope, row.get("status", "reviewed"),
                                  row.get("draft_question"), n, golds))
    return questions, problems


def rank_of(gold: str | Iterable[str], results: list[str]) -> int | None:
    """Rank of the best-placed gold chunk (one id or several), None if none is found."""
    golds = {gold} if isinstance(gold, str) else set(gold)
    for i, cid in enumerate(results, start=1):
        if cid in golds:
            return i
    return None


def metrics_from_ranks(ranks: list[int | None], ks: Iterable[int] = (1, 5, 10),
                       mrr_k: int = 10) -> dict[str, float]:
    n = len(ranks)
    if n == 0:
        return {}
    out = {f"recall@{k}": sum(r is not None and r <= k for r in ranks) / n for k in ks}
    out["mrr"] = sum(1.0 / r for r in ranks if r is not None and r <= mrr_k) / n
    return out


def bootstrap_ci(ranks: list[int | None], fn: Callable[[list], dict[str, float]],
                 n_boot: int = 2000, seed: int = 0) -> dict[str, list[float]]:
    if not ranks:
        return {}
    rng = random.Random(seed)
    samples: dict[str, list[float]] = defaultdict(list)
    for _ in range(n_boot):
        resample = [ranks[rng.randrange(len(ranks))] for _ in ranks]
        for key, value in fn(resample).items():
            samples[key].append(value)
    ci = {}
    for key, vals in samples.items():
        vals.sort()
        ci[key] = [vals[int(0.025 * n_boot)], vals[min(int(0.975 * n_boot), n_boot - 1)]]
    return ci
