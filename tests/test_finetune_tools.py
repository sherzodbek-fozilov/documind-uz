"""Before/after comparison of the fine-tuned model: paired bootstrap and the checks that
both runs used the same questions."""

import importlib.util
import sys
from pathlib import Path

import pytest

from documind.evaluation import metrics_from_ranks, paired_bootstrap_delta

ROOT = Path(__file__).resolve().parent.parent


def _module(path: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod  # dataclasses look their module up while the class is built
    spec.loader.exec_module(mod)
    return mod


def test_paired_bootstrap_delta():
    a = [1, None, 3, 2, None, 1]
    assert paired_bootstrap_delta(a, a)["mrr"] == {"delta": 0.0, "ci95": [0.0, 0.0]}
    b = [1, 1, 1, 1, 1, 1]
    d = paired_bootstrap_delta(a, b)
    expected = metrics_from_ranks(b)["recall@1"] - metrics_from_ranks(a)["recall@1"]
    assert d["recall@1"]["delta"] == pytest.approx(expected)
    lo, hi = d["mrr"]["ci95"]
    assert 0 <= lo <= d["mrr"]["delta"] <= hi
    with pytest.raises(ValueError):
        paired_bootstrap_delta([1], [1, 2])


def _result(model: str, lines=(3, 5), ranks=(1, None)) -> dict:
    return {"set": "real", "split": "test", "n": len(lines), "questions_sha256": "abc",
            "corpus": {"chunks": 10}, "config": {"embed_model": model},
            "metrics": metrics_from_ranks(list(ranks)),
            "per_question": [{"line": n, "language": "ru", "tags": [], "rank": r,
                              "rank_article": r} for n, r in zip(lines, ranks, strict=True)]}


def test_eval_finetune_refuses_different_questions_and_compares():
    ev = _module("scripts/eval_finetune.py", "eval_finetune")
    base, ftr = _result("base"), _result("ft", ranks=(1, 2))
    assert ev.same_questions(base, ftr) == []
    assert "different questions" in ev.same_questions(base, _result("ft", lines=(3, 6)))
    assert "both runs used the same embedding model" in ev.same_questions(base,
                                                                          _result("base"))
    other = _result("ft") | {"questions_sha256": "zzz"}
    assert "question files differ (sha256)" in ev.same_questions(base, other)
    cmp = ev.compare(base, ftr)
    assert cmp["chunk_questions"] == {"better": 1, "worse": 0, "same": 1}
    assert cmp["chunk"]["recall@5"]["delta"] == pytest.approx(0.5)


