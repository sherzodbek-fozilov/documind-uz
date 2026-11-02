"""Train/test split by document group, never by chunk.

Default: the split of a group is a pure function of its id (a hash), so it does not
depend on ingestion order and never changes when new documents are added. Explicit
assignments in ``data/splits.json`` (``{"group_id": "train" | "test"}``) take precedence;
``stratified_split`` produces such a file balanced per language (``documind split``).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from pathlib import Path

SPLITS = ("train", "test")
SPLIT_UNITS = ("document", "chapter")


def split_group_of(group_id: str, split_unit: str, chapter: int | None) -> str:
    """Split group of a chunk. With unit "chapter", the same chapter number in every
    language version of an act (same group_id) forms one group; text before the first
    chapter goes to chapter 0."""
    if split_unit == "document":
        return group_id
    if split_unit == "chapter":
        return f"{group_id}/ch{chapter or 0}"
    raise ValueError(f"split_unit must be one of {SPLIT_UNITS}")


def document_split(chunk_splits: Iterable[str], fallback: str) -> str:
    values = set(chunk_splits)
    return values.pop() if len(values) == 1 else ("mixed" if values else fallback)


def hash_split(group_id: str, test_fraction: float) -> str:
    h = int.from_bytes(hashlib.sha256(group_id.encode("utf-8")).digest()[:8], "big")
    return "test" if h / 2**64 < test_fraction else "train"


def load_overrides(path: Path | None) -> dict[str, str]:
    if path is None or not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    bad = {k: v for k, v in data.items() if v not in SPLITS}
    if bad:
        raise ValueError(f"invalid split values in {path}: {bad}")
    return data


def assign_split(group_id: str, test_fraction: float, overrides: dict[str, str]) -> str:
    return overrides.get(group_id) or hash_split(group_id, test_fraction)


def check_no_leakage(rows: Iterable[tuple[str, str, str]]) -> list[str]:
    """rows: (doc_id, group_id, split). Returns groups that appear in both splits."""
    seen: dict[str, set[str]] = {}
    for _doc, group, split in rows:
        seen.setdefault(group, set()).add(split)
    return sorted(g for g, s in seen.items() if len(s) > 1)


def stratified_split(groups: dict[str, str], test_fraction: float,
                     existing: dict[str, str] | None = None) -> dict[str, str]:
    """Assign groups to splits so each stratum (e.g. language) gets ~test_fraction test groups.

    groups: {group_id: stratum}. Groups already in ``existing`` keep their split (a frozen
    split must not move documents between train and test). Within a stratum, new groups
    are ordered by hash and the test share is topped up to round(test_fraction * n).
    """
    existing = dict(existing or {})
    by_stratum: dict[str, list[str]] = {}
    for gid, stratum in groups.items():
        by_stratum.setdefault(stratum, []).append(gid)
    out = {g: s for g, s in existing.items()}
    for members in by_stratum.values():
        target = round(test_fraction * len(members))
        have = sum(existing.get(g) == "test" for g in members)
        new = sorted((g for g in members if g not in existing),
                     key=lambda g: hashlib.sha256(g.encode("utf-8")).hexdigest())
        n_test = max(0, min(len(new), target - have))
        for i, g in enumerate(new):
            out[g] = "test" if i < n_test else "train"
    return dict(sorted(out.items()))
