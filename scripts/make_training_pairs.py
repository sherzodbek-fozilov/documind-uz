"""Generate fine-tuning pairs for the embedding model from the TRAIN split of the real corpus.

Reads the ingested real documents from the database (run ``scripts/fetch_sources.py`` and
``documind ingest data/raw`` first). Test chunks are dropped before anything else; the
test questions in data/eval/ are not read. See documind/training/pairs.py for the rules.

Writes (git-ignored, they contain lex.uz text, which this project does not redistribute):
  data/training/pairs_train.jsonl  query, positive, hard negative + labels
  data/training/pairs_val.jsonl    query, positive (validation chapter groups)
  data/training/corpus.jsonl       all train + val passages (validation retrieval corpus)
Writes (committed, counts only, no text):
  results/training_pairs_stats.json

Usage: python scripts/make_training_pairs.py [--seed 13] [--val-fraction 0.15]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common import ROOT, write_result  # noqa: E402

from documind.config import get_settings  # noqa: E402
from documind.retrieval.corpus import load_corpus  # noqa: E402
from documind.storage.db import make_session_factory  # noqa: E402
from documind.training.pairs import build_pairs, check_pairs, pair_stats  # noqa: E402

OUT_DIR = ROOT / "data/training"


def write_jsonl(path: Path, rows: list[dict]) -> str:
    data = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows).encode("utf-8")
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seed", type=int, default=13)
    ap.add_argument("--val-fraction", type=float, default=0.15,
                    help="share of each act's train chapter groups held out for validation")
    ap.add_argument("--mixed-fraction", type=float, default=0.1,
                    help="share of articles that also get code-mixed uz/ru queries")
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = ap.parse_args()
    settings = get_settings()
    Session = make_session_factory(settings.database_url)
    with Session() as session:
        chunks = load_corpus(session, "real")
    if not chunks:
        raise SystemExit("no real documents ingested; run scripts/fetch_sources.py and "
                         "documind ingest data/raw first")

    pairs = build_pairs(chunks, seed=args.seed, val_fraction=args.val_fraction,
                        mixed_fraction=args.mixed_fraction, analyzer=settings.bm25_analyzer)
    problems = check_pairs(pairs, chunks)
    if problems:
        for p in problems[:20]:
            print(f"ERROR {p}", file=sys.stderr)
        raise SystemExit(f"{len(problems)} problems; nothing written")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    hashes = {name: write_jsonl(args.out_dir / name, rows) for name, rows in
              (("pairs_train.jsonl", pairs.train), ("pairs_val.jsonl", pairs.val),
               ("corpus.jsonl", pairs.corpus))}
    stats = pair_stats(pairs)
    source_chunks = {
        "total": len(chunks),
        "train": sum(c.split == "train" for c in chunks),
        "test_excluded": sum(c.split != "train" for c in chunks),
        "chunker_versions": sorted({c.chunker_version for c in chunks}),
        "documents": sorted({c.doc_id for c in chunks}),
    }
    payload = {
        "description": "Fine-tuning pairs for the embedding model, from TRAIN chunk groups "
                       "only. Counts only; the pair files contain lex.uz text and are not "
                       "committed.",
        "config": {"seed": args.seed, "val_fraction": args.val_fraction,
                   "mixed_fraction": args.mixed_fraction,
                   "bm25_analyzer": settings.bm25_analyzer, "val_salt": "val-v1"},
        "source_chunks": source_chunks,
        **stats,
        "checks": {"problems": 0, "test_chunks_in_outputs": 0},
        "files_sha256": hashes,
    }
    path = write_result("training_pairs_stats.json", payload, "scripts/make_training_pairs.py")
    t, v = stats["train"], stats["val"]
    print(f"train: {t['pairs']} pairs, {t['articles']} articles, {t['split_groups']} groups")
    print(f"val:   {v['pairs']} pairs, {v['articles']} articles, {v['split_groups']} groups")
    print(f"files in {args.out_dir}; stats in {path}")


if __name__ == "__main__":
    main()
