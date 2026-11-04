import json

from documind.evaluation import bootstrap_ci, load_questions, metrics_from_ranks, rank_of


def test_metrics():
    ranks = [1, 3, None, 10, 12]
    m = metrics_from_ranks(ranks)
    assert m["recall@1"] == 0.2 and m["recall@5"] == 0.4 and m["recall@10"] == 0.6
    assert abs(m["mrr"] - (1 + 1 / 3 + 1 / 10) / 5) < 1e-9
    assert metrics_from_ranks([]) == {}
    assert rank_of("b", ["a", "b"]) == 2 and rank_of("z", ["a"]) is None


def test_bootstrap_ci_brackets_the_estimate():
    ranks = [1] * 30 + [None] * 10
    ci = bootstrap_ci(ranks, metrics_from_ranks, n_boot=500)
    lo, hi = ci["recall@1"]
    assert lo < 0.75 < hi and 0 <= lo and hi <= 1
    assert ci == bootstrap_ci(ranks, metrics_from_ranks, n_boot=500)  # fixed seed


def test_load_questions_reports_problems(tmp_path):
    p = tmp_path / "q.jsonl"
    p.write_text("\n".join([
        json.dumps({"question": "Q?", "language": "ru", "gold_doc": "d", "gold_chunk": "d#c0"}),
        json.dumps({"question": "Q?", "language": "en", "gold_doc": "d", "gold_chunk": "d#c0"}),
        json.dumps({"question": "Q?", "language": "ru"}),
        "{not json",
        json.dumps({"question": "Q?", "language": "uz-Latn", "gold_doc": "d",
                    "gold_chunk": "d#c1", "scope": "document", "status": "draft"}),
    ]), encoding="utf-8")
    qs, problems = load_questions(p)
    assert len(qs) == 2 and len(problems) == 3
    assert qs[1].scope == "document" and qs[1].status == "draft"
    assert load_questions(tmp_path / "missing.jsonl") == ([], [])


def test_multiple_gold_chunks(tmp_path):
    p = tmp_path / "q.jsonl"
    p.write_text("\n".join([
        json.dumps({"question": "Q?", "language": "ru", "gold_doc": "d", "gold_chunk": "d#c1",
                    "gold_chunks": ["d#c1", "d#c2"]}),
        json.dumps({"question": "Q?", "language": "ru", "gold_doc": "d", "gold_chunk": "d#c9",
                    "gold_chunks": ["d#c1", "d#c2"]}),
    ]), encoding="utf-8")
    qs, problems = load_questions(p)
    assert len(qs) == 1 and qs[0].gold_chunks == ("d#c1", "d#c2") and len(problems) == 1
    assert rank_of(qs[0].gold_chunks, ["x", "d#c2", "d#c1"]) == 2
    single, _ = load_questions(tmp_path / "missing.jsonl")
    assert single == []


def test_tags_are_loaded_and_validated(tmp_path):
    p = tmp_path / "q.jsonl"
    base = {"question": "Q?", "language": "ru", "gold_doc": "d", "gold_chunk": "d#c1"}
    p.write_text("\n".join([json.dumps(base | {"tags": ["colloquial", "typo"]}),
                            json.dumps(base),
                            json.dumps(base | {"tags": "typo"})]), encoding="utf-8")
    qs, problems = load_questions(p)
    assert [q.tags for q in qs] == [("colloquial", "typo"), ()]
    assert len(problems) == 1 and "tags" in problems[0]
