"""Retrieval evaluation: question loading/validation, ranks, Recall@k, MRR, bootstrap CIs.

Definitions (per question; usually one gold chunk, optionally several in "gold_chunks"):
  rank       position of the first gold chunk found in the result list (1 = first), None
             if no gold chunk is in the top ``max_k`` results
  Recall@k   share of questions with rank <= k
  MRR@10     mean of 1/rank over questions, 0 when rank is None or > 10
Confidence intervals: percentile bootstrap over questions (2000 resamples, fixed seed).

Primary metric: chunk level (above). Secondary metric, reported next to it: article level,
where a result counts if it is ANY chunk of the gold article in ANY language version of
the act (``article_rank``); a gold chunk outside a numbered article falls back to
chunk-level matching.
"""

from __future__ import annotations

import hashlib
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
    tags: tuple[str, ...] = ()  # free labels from the annotator, e.g. ("colloquial", "typo")

    def __post_init__(self):
        if not self.gold_chunks:
            self.gold_chunks = (self.gold_chunk,)

    @property
    def id(self) -> str:
        return question_id(self.question, self.gold_chunks)


def question_id(question: str, gold_chunks: Iterable[str]) -> str:
    """Stable id of a labeled question: derived from its text and gold chunks only, so it
    does not change when lines are appended, reordered or re-tagged, and it is not stored
    in questions.jsonl (the annotator's lines stay untouched)."""
    payload = question + "\x1f" + "\x1e".join(gold_chunks)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def load_eval_set(path: Path) -> dict:
    """A frozen eval set: {"name", "set", "question_ids": [...], ...}."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    ids = data.get("question_ids") or []
    if not data.get("name") or not ids or len(ids) != len(set(ids)):
        raise ValueError(f"{path}: needs a name and a non-empty list of unique question_ids")
    return data


def select_eval_set(questions: list[Question],
                    eval_set: dict) -> tuple[list[Question], list[str]]:
    """Questions of a frozen set (in file order), and the set's ids that were not found,
    e.g. because a frozen question was edited or removed."""
    wanted = set(eval_set["question_ids"])
    selected = [q for q in questions if q.id in wanted]
    found = {q.id for q in selected}
    return selected, [i for i in eval_set["question_ids"] if i not in found]


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
        tags = row.get("tags") or []
        if not isinstance(tags, list) or not all(isinstance(t, str) and t for t in tags):
            problems.append(f"{path.name}:{n}: tags must be a list of non-empty strings")
            continue
        questions.append(Question(row["question"], row["language"], row["gold_doc"],
                                  row["gold_chunk"], scope, row.get("status", "reviewed"),
                                  row.get("draft_question"), n, golds, tuple(tags)))
    return questions, problems


def rank_of(gold: str | Iterable[str], results: list[str]) -> int | None:
    """Rank of the best-placed gold chunk (one id or several), None if none is found."""
    golds = {gold} if isinstance(gold, str) else set(gold)
    for i, cid in enumerate(results, start=1):
        if cid in golds:
            return i
    return None


def article_rank(golds: Iterable[str], results: list[str],
                 key_of: dict[str, tuple | None]) -> int | None:
    """Rank of the first result that is in the same article as a gold chunk (any chunk,
    any language). ``key_of`` maps chunk id -> article key, or None when the chunk is not
    inside a numbered article (then only the chunk itself matches)."""
    def key(cid: str) -> tuple:
        return key_of.get(cid) or ("chunk", cid)

    gold_keys = {key(g) for g in golds}
    for i, cid in enumerate(results, start=1):
        if key(cid) in gold_keys:
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


def paired_bootstrap_delta(ranks_a: list[int | None], ranks_b: list[int | None],
                           fn: Callable[[list], dict[str, float]] = metrics_from_ranks,
                           n_boot: int = 2000, seed: int = 0) -> dict[str, dict]:
    """Difference b - a of each metric on the SAME questions (ranks_a[i] and ranks_b[i] are
    one question), with a paired percentile bootstrap: questions are resampled once and
    both systems are scored on the resample. Returns {metric: {"delta", "ci95"}}."""
    if len(ranks_a) != len(ranks_b):
        raise ValueError("paired comparison needs the same questions in the same order")
    if not ranks_a:
        return {}
    base, new = fn(ranks_a), fn(ranks_b)
    rng = random.Random(seed)
    n = len(ranks_a)
    samples: dict[str, list[float]] = defaultdict(list)
    for _ in range(n_boot):
        idx = [rng.randrange(n) for _ in range(n)]
        a, b = fn([ranks_a[i] for i in idx]), fn([ranks_b[i] for i in idx])
        for key in base:
            samples[key].append(b[key] - a[key])
    out = {}
    for key, vals in samples.items():
        vals.sort()
        out[key] = {"delta": new[key] - base[key],
                    "ci95": [vals[int(0.025 * n_boot)], vals[min(int(0.975 * n_boot),
                                                                 n_boot - 1)]]}
    return out
