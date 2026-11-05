"""Torch-free parts of kaggle/finetune_e5.py: batching, validation metrics, data check."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _module(path: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod  # dataclasses look their module up while the class is built
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def ft():
    return _module("kaggle/finetune_e5.py", "finetune_e5")


def test_kaggle_script_imports_without_torch(ft):
    assert ft.Config().base_revision == _module(
        "scripts/download_model.py", "download_model").DEFAULT_REVISION


def test_group_batches_no_shared_article_and_every_row_once(ft):
    rows = []
    for art in range(30):
        for _q in range(4):  # 4 queries per article, negatives from the next article
            rows.append({"article": f"a/{art}", "negative_article": f"a/{(art + 1) % 30}"})
    keys = ft.row_keys(rows)
    batches = ft.group_batches(keys, batch_size=8, seed=1, epoch=1)
    flat = [i for b in batches for i in b]
    assert sorted(flat) == list(range(len(rows)))
    for b in batches:
        used = [k for i in b for k in keys[i]]
        assert len(used) == len(set(used))
        arts = [rows[i]["article"] for i in b]
        negs = {rows[i]["negative_article"] for i in b}
        assert len(arts) == len(set(arts)) and not negs & set(arts)
    assert batches == ft.group_batches(keys, 8, seed=1, epoch=1)
    assert batches != ft.group_batches(keys, 8, seed=1, epoch=2)


def test_retrieval_metrics_chunk_and_article_level(ft):
    rows = [{"positive_id": "uz#1", "article": "x/1", "query_type": "title", "noise": "none",
             "query_lang": "uz-Latn", "passage_lang": "uz-Latn"},
            {"positive_id": "uz#2", "article": "x/2", "query_type": "title",
             "noise": "typos", "query_lang": "uz-Latn", "passage_lang": "uz-Latn"}]
    article_of = {"uz#1": "x/1", "ru#1": "x/1", "uz#2": "x/2", "ru#2": "x/2", "uz#3": "x/3"}
    ranked = [["uz#1", "ru#1"], ["ru#2", "uz#3", "uz#2"]]
    m = ft.retrieval_metrics(ranked, rows, article_of)
    assert m["chunk"]["recall@1"] == 0.5 and m["chunk"]["mrr"] == round((1 + 1 / 3) / 2, 4)
    assert m["article"]["recall@1"] == 1.0  # the ru version of article 2 counts here
    assert m["groups"]["noise:typos"]["mrr"] == round(1 / 3, 4)




def test_data_check_compares_with_committed_stats(ft):
    ref = {"source_chunks": {"total": 10, "train": 7, "test_excluded": 3,
                             "chunker_versions": ["v1"], "documents": ["a", "b"]},
           "files_sha256": {n: "x" for n in ft.PAIR_FILES}}
    assert ft.data_check(ref, json.loads(json.dumps(ref))) == []
    changed = json.loads(json.dumps(ref))
    changed["source_chunks"]["train"] = 8
    changed["files_sha256"]["pairs_train.jsonl"] = "y"
    problems = ft.data_check(ref, changed)
    assert len(problems) == 2 and "train" in problems[0] and "pairs_train" in problems[1]


def test_prepare_refuses_work_dir_in_kaggle_output(ft):
    import argparse

    with pytest.raises(SystemExit, match="must not be under /kaggle/working"):
        ft.prepare(argparse.Namespace(work_dir="/kaggle/working/tmp"))
