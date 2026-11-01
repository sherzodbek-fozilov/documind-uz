import json

import pytest

from documind.split import (
    assign_split,
    check_no_leakage,
    hash_split,
    load_overrides,
    stratified_split,
)


def test_hash_split_is_deterministic_and_roughly_proportional():
    ids = [f"doc-{i}" for i in range(2000)]
    first = [hash_split(i, 0.3) for i in ids]
    assert first == [hash_split(i, 0.3) for i in ids]
    share = first.count("test") / len(ids)
    assert 0.26 < share < 0.34


def test_edge_fractions():
    assert hash_split("x", 0.0) == "train" and hash_split("x", 1.0) == "test"


def test_overrides(tmp_path):
    path = tmp_path / "splits.json"
    path.write_text(json.dumps({"law-1": "test"}))
    overrides = load_overrides(path)
    assert assign_split("law-1", 0.0, overrides) == "test"
    path.write_text(json.dumps({"law-1": "dev"}))
    with pytest.raises(ValueError):
        load_overrides(path)
    assert load_overrides(tmp_path / "missing.json") == {}


def test_leakage_check():
    rows = [("a-uz", "a", "train"), ("a-ru", "a", "test"), ("b", "b", "train")]
    assert check_no_leakage(rows) == ["a"]


def test_stratified_split_balances_languages_and_respects_frozen():
    groups = {f"{lang}-{i}": lang for lang in ("uz-Latn", "uz-Cyrl", "ru") for i in range(10)}
    splits = stratified_split(groups, 0.3)
    for lang in ("uz-Latn", "uz-Cyrl", "ru"):
        assert sum(splits[g] == "test" for g, s in groups.items() if s == lang) == 3
    assert splits == stratified_split(groups, 0.3)  # deterministic
    # frozen assignments never move; new groups top up the test share
    frozen = {"ru-0": "test", "ru-1": "test", "ru-2": "test", "ru-3": "test"}
    again = stratified_split(groups, 0.3, frozen)
    assert all(again[g] == s for g, s in frozen.items())
    assert sum(again[g] == "test" for g in groups if g.startswith("ru-")) == 4
