"""Frozen eval sets: stable question ids, selection, the freeze manifest, and the
before/after check that both runs used the same eval set."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from documind.evaluation import Question, load_eval_set, question_id, select_eval_set

ROOT = Path(__file__).resolve().parent.parent


def _module(path: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _q(text: str, gold: str = "a#c1", line: int = 1, tags=()) -> Question:
    return Question(text, "ru", "a", gold, line=line, tags=tuple(tags))


def test_question_id_depends_only_on_text_and_gold():
    a = _q("Можно ли?", line=1, tags=("neutral",))
    b = _q("Можно ли?", line=40, tags=("neutral", "ambiguous-gold"))  # moved and re-tagged
    assert a.id == b.id == question_id("Можно ли?", ["a#c1"])
    assert _q("Можно ли? ").id != a.id                          # text changed
    assert _q("Можно ли?", gold="a#c2").id != a.id              # gold changed
    assert len(a.id) == 12


def test_select_eval_set_keeps_file_order_and_reports_missing(tmp_path):
    qs = [_q("q1", line=1), _q("q2", line=2), _q("q3", line=3)]
    es = {"name": "v1", "set": "real", "question_ids": [qs[2].id, qs[0].id, "deadbeef0000"]}
    selected, missing = select_eval_set(qs, es)
    assert [q.question for q in selected] == ["q1", "q3"]
    assert missing == ["deadbeef0000"]
    path = tmp_path / "v1.json"
    path.write_text(json.dumps(es | {"question_ids": [qs[0].id, qs[0].id]}))
    with pytest.raises(ValueError):
        load_eval_set(path)  # duplicate ids


def test_freeze_manifest_records_ids_counts_and_corpus():
    fz = _module("scripts/freeze_eval_set.py", "freeze_eval_set")
    qs = [_q("q1", tags=("neutral",)), _q("q2", gold="a#c2", tags=("typo", "neutral"))]
    docs = [{"id": "b", "sha256": "2", "chunker_version": "v"},
            {"id": "a", "sha256": "1", "chunker_version": "v"}]
    m = fz.build_manifest("v1", "real", qs, docs, "qsha", "ssha", "2026-11-05")
    assert m["question_ids"] == [q.id for q in qs] and m["n"] == 2
    assert m["by_language"] == {"ru": 2} and m["by_tag"] == {"neutral": 2, "typo": 1}
    assert [d["id"] for d in m["corpus"]["documents"]] == ["a", "b"]
    assert m["questions_file_sha256"] == "qsha" and m["corpus"]["splits_file_sha256"] == "ssha"
    with pytest.raises(ValueError, match="duplicate"):
        fz.build_manifest("v1", "real", [qs[0], _q("q1")], docs, "q", "s", "d")


def test_eval_finetune_refuses_different_eval_sets():
    ev = _module("scripts/eval_finetune.py", "eval_finetune_es")
    per_q = [{"id": "x1", "line": 1, "language": "ru", "tags": [], "rank": 1,
              "rank_article": 1}]
    base = {"questions_sha256": "s", "split": "test", "set": "real", "corpus": {},
            "config": {"embed_model": "base"}, "eval_set": {"name": "v1"}, "per_question": per_q}
    ft = base | {"config": {"embed_model": "ft"}}
    assert ev.same_questions(base, ft) == []
    assert "different eval sets" in ev.same_questions(base, ft | {"eval_set": None})
    other_ids = ft | {"per_question": [per_q[0] | {"id": "x2"}]}
    assert "different question ids" in ev.same_questions(base, other_ids)
