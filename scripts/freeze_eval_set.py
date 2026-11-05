"""Freeze the current labeled questions as a named eval set (e.g. "v1").

Writes data/eval/sets/<name>.json once (refuses to overwrite) with:
  * question_ids: stable ids of the frozen questions (documind.evaluation.question_id:
    hash of question text + gold chunks; tags and line order do not matter);
  * counts by language and tag, and the sha256 of questions.jsonl at freeze time;
  * the corpus fingerprint the gold chunk ids depend on: chunker version and sha256 of
    each document, and the sha256 of data/splits.json.

Later questions are appended to questions.jsonl as usual and belong to the next set (v2);
`eval_retrieval.py --eval-set v1` evaluates exactly the frozen questions and fails if any
of them was changed or removed, or if the corpus no longer has their gold chunks.

Usage: python scripts/freeze_eval_set.py --name v1 [--set real]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from documind.config import get_settings  # noqa: E402
from documind.evaluation import load_questions  # noqa: E402
from documind.storage import models  # noqa: E402
from documind.storage.db import make_session_factory  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SETS_DIR = ROOT / "data/eval/sets"
QUESTION_FILES = {"real": ROOT / "data/eval/questions.jsonl"}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_manifest(name: str, kind: str, questions: list, documents: list[dict],
                   questions_sha256: str, splits_sha256: str, frozen_on: str) -> dict:
    ids = [q.id for q in questions]
    if len(ids) != len(set(ids)):
        dupes = sorted(i for i, n in Counter(ids).items() if n > 1)
        raise ValueError(f"duplicate questions (same text and gold chunks): {dupes}")
    tags = Counter(t for q in questions for t in q.tags)
    return {
        "name": name,
        "set": kind,
        "frozen_on": frozen_on,
        "n": len(ids),
        "by_language": dict(sorted(Counter(q.language for q in questions).items())),
        "by_tag": dict(sorted(tags.items())),
        "questions_file": "data/eval/questions.jsonl",
        "questions_file_sha256": questions_sha256,
        "question_id": "sha256(question + U+001F + gold chunks joined by U+001E)[:12]",
        "corpus": {"documents": sorted(documents, key=lambda d: d["id"]),
                   "splits_file_sha256": splits_sha256},
        "question_ids": ids,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--name", required=True, help="eval set name, e.g. v1")
    ap.add_argument("--set", default="real", choices=sorted(QUESTION_FILES))
    args = ap.parse_args()
    out = SETS_DIR / f"{args.name}.json"
    if out.exists():
        raise SystemExit(f"{out} exists: a frozen eval set is never overwritten")
    path = QUESTION_FILES[args.set]
    questions, problems = load_questions(path)
    if problems:
        raise SystemExit("fix the question file first:\n  " + "\n  ".join(problems))
    questions = [q for q in questions if q.status == "reviewed"]
    settings = get_settings()
    with make_session_factory(settings.database_url)() as s:
        docs = s.execute(select(models.Document.id, models.Document.sha256,
                                models.Document.chunker_version)
                         .where(models.Document.is_synthetic.is_(args.set == "synthetic"))).all()
    documents = [{"id": d.id, "sha256": d.sha256, "chunker_version": d.chunker_version}
                 for d in docs]
    gold_docs = {g.split("#")[0] for q in questions for g in q.gold_chunks}
    missing = gold_docs - {d["id"] for d in documents}
    if missing:
        raise SystemExit(f"gold documents not ingested: {sorted(missing)}")
    manifest = build_manifest(args.name, args.set, questions, documents, sha256_file(path),
                              sha256_file(settings.splits_file),
                              datetime.now(UTC).date().isoformat())
    SETS_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"froze {manifest['n']} questions as {args.name}: {out}")
    print(json.dumps({k: manifest[k] for k in ("by_language", "questions_file_sha256")},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
