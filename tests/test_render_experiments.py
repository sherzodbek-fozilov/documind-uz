import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("render_experiments",
                                              ROOT / "scripts/render_experiments.py")
rx = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rx)


def _result(r1: float) -> dict:
    m = {"recall@1": r1, "recall@5": 0.5, "recall@10": 0.6, "mrr": 0.3}
    group = {"n": 2, **m, "article": {**m, "recall@5": 1.0}}
    return {"set": "real", "split": "test", "n": 10, "git_commit": "abc1234",
            "generated_at": "2026-11-04T00:00:00+00:00", "metrics": m,
            "ci95": {k: [0.0, 1.0] for k in m}, "metrics_article": m,
            "ci95_article": {k: [0.1, 0.9] for k in m},
            "by_language": {"ru": group}, "by_tag": {"typo": group}}


def test_render_uses_only_values_from_the_result_files():
    out = rx.render({"bm25": _result(0.1), "e5_small": _result(0.2), "hybrid_rrf": _result(0.3)})
    assert "n = 10 questions, commit `abc1234`" in out
    assert "| BM25 | 0.10 [0.00–1.00] | 0.50 [0.00–1.00] |" in out
    assert "| Hybrid RRF | 0.30 [0.10–0.90] |" in out  # article-level table uses ci95_article
    assert "| typo | 2 | 0.50 / 0.30 (1.00) |" in out


def test_render_header_shows_questions_sha_and_eval_set():
    r = _result(0.1) | {"questions_sha256": "abc123",
                        "eval_set": {"name": "v1", "n": 10, "file_sha256": "def456"}}
    out = rx.render({"bm25": r, "e5_small": r, "hybrid_rrf": r})
    assert "`results/retrieval_*_real_v1.json`" in out
    assert "Questions file sha256: `abc123`" in out
    assert "Eval set: `v1` (10 frozen questions, `data/eval/sets/v1.json` sha256 `def456`)" in out
