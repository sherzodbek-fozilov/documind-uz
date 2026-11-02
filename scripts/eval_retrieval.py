"""Evaluate retrieval methods on labeled questions; real and synthetic sets separately.

Question files:
  data/eval/questions.jsonl            real documents, written and reviewed by hand
  data/eval/questions_synthetic.jsonl  SYNTHETIC documents, generated from templates

Each set is searched only within its own corpus (real or synthetic chunks, all splits),
and only questions whose gold chunk is in ``--split`` (default: test) are scored. The
split is per chunk: the document's split, or its chapter group's split for acts split by
chapter.
Questions with ``"status": "draft"`` (unreviewed drafts) are skipped and counted.

Writes results/retrieval_<method>_<set>.json for the test split (rendered in the README),
or results/tuning/... for any other split (used for choosing settings, not reported).

Usage:
  python scripts/eval_retrieval.py                         # all methods, both sets, test
  python scripts/eval_retrieval.py --set synthetic --methods bm25
  python scripts/eval_retrieval.py --split train --methods bm25 \
      --bm25-analyzers plain,fold,plain+stem6,fold+stem6   # tuning on train questions
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common import ROOT, write_result  # noqa: E402

from documind.config import get_settings  # noqa: E402
from documind.evaluation import (  # noqa: E402
    bootstrap_ci,
    load_questions,
    metrics_from_ranks,
    rank_of,
)
from documind.retrieval.corpus import load_corpus  # noqa: E402
from documind.retrieval.retrievers import (  # noqa: E402
    BM25Retriever,
    DenseRetriever,
    HybridRetriever,
)
from documind.storage.db import make_session_factory  # noqa: E402

QUESTION_FILES = {"real": ROOT / "data/eval/questions.jsonl",
                  "synthetic": ROOT / "data/eval/questions_synthetic.jsonl"}
DATASET = {"real": "real documents (laws, model contracts), hand-labeled questions",
           "synthetic": "SYNTHETIC contracts (synthetic-contracts-v1), template questions"}
MAX_K = 10


def evaluate(retriever, questions, chunk_ids: set[str]) -> tuple[list, list]:
    ranks, per_q = [], []
    for q in questions:
        start = time.perf_counter()
        results = retriever.search(q.question, k=MAX_K,
                                   doc_id=q.gold_doc if q.scope == "document" else None)
        latency = time.perf_counter() - start
        r = rank_of(q.gold_chunk, results)
        ranks.append(r)
        per_q.append({"line": q.line, "language": q.language, "rank": r,
                      "top1": results[0] if results else None, "latency_s": round(latency, 4)})
    return ranks, per_q


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--set", choices=["real", "synthetic", "all"], default="all")
    ap.add_argument("--split", default="test")
    ap.add_argument("--methods", default="bm25,e5_small,hybrid_rrf")
    ap.add_argument("--bm25-analyzers", default=None,
                    help="comma-separated analyzers to compare (default: the configured one)")
    args = ap.parse_args()
    settings = get_settings()
    Session = make_session_factory(settings.database_url)
    methods = args.methods.split(",")
    analyzers = (args.bm25_analyzers.split(",") if args.bm25_analyzers
                 else [settings.bm25_analyzer])
    sets = ["real", "synthetic"] if args.set == "all" else [args.set]
    embedder = None
    summary_rows = []

    for kind in sets:
        questions, problems = load_questions(QUESTION_FILES[kind])
        for p in problems:
            print(f"WARNING {p}", file=sys.stderr)
        with Session() as session:
            chunks = load_corpus(session, kind)
        if not chunks:
            print(f"[{kind}] no {kind} documents ingested; skipping", file=sys.stderr)
            continue
        by_id = {c.id: c for c in chunks}
        split_of_doc = {c.doc_id: c.split for c in chunks}
        counts: Counter = Counter()
        selected = []
        for q in questions:
            if q.status == "draft":
                counts["skipped_unreviewed_draft"] += 1
            elif q.gold_chunk not in by_id or by_id[q.gold_chunk].doc_id != q.gold_doc:
                counts["skipped_gold_not_found"] += 1
                print(f"WARNING [{kind}] line {q.line}: gold {q.gold_chunk} not in corpus "
                      f"or not in {q.gold_doc}", file=sys.stderr)
            elif by_id[q.gold_chunk].split != args.split:
                counts["other_split"] += 1
            else:
                selected.append(q)
        if not selected:
            print(f"[{kind}] no usable questions for split {args.split!r} "
                  f"({dict(counts)}); nothing written", file=sys.stderr)
            continue
        chunker_versions = sorted({c.chunker_version for c in chunks})

        retrievers = {}
        for analyzer in analyzers:
            if "bm25" in methods or "hybrid_rrf" in methods:
                retrievers[f"bm25[{analyzer}]"] = BM25Retriever(chunks, analyzer)
        if "e5_small" in methods or "hybrid_rrf" in methods:
            if embedder is None:
                from documind.retrieval.embedder import E5Embedder
                embedder = E5Embedder(settings.embed_model_dir)
            retrievers["e5_small"] = DenseRetriever(chunks, embedder, f"chunks_{kind}",
                                                    qdrant_url=settings.qdrant_url,
                                                    cache_dir=settings.embed_cache_dir)
        runs = []
        for analyzer in analyzers:
            if "bm25" in methods:
                runs.append(("bm25", analyzer, retrievers[f"bm25[{analyzer}]"]))
            if "hybrid_rrf" in methods:
                runs.append(("hybrid_rrf", analyzer, HybridRetriever(
                    [retrievers[f"bm25[{analyzer}]"], retrievers["e5_small"]],
                    rrf_k=settings.rrf_k, depth=settings.retrieval_depth)))
        if "e5_small" in methods:
            runs.append(("e5_small", None, retrievers["e5_small"]))

        for method, analyzer, retriever in runs:
            ranks, per_q = evaluate(retriever, selected, set(by_id))
            by_lang = defaultdict(list)
            for q, r in zip(selected, ranks, strict=True):
                by_lang[q.language].append(r)
            latencies = sorted(p["latency_s"] for p in per_q)
            payload = {
                "metrics": metrics_from_ranks(ranks),
                "n": len(selected),
                "ci95": bootstrap_ci(ranks, metrics_from_ranks),
                "by_language": {lang: {"n": len(r), **metrics_from_ranks(r)}
                                for lang, r in sorted(by_lang.items())},
                "set": kind,
                "split": args.split,
                "dataset": DATASET[kind],
                "scope": dict(Counter(q.scope for q in selected)),
                "corpus": {"chunks": len(chunks), "documents": len(split_of_doc),
                           "chunker_versions": chunker_versions},
                "question_counts": {"used": len(selected), **counts},
                "config": {"method": method, "bm25_analyzer": analyzer,
                           "embed_model": getattr(embedder, "model_id", None)
                           if method != "bm25" else None,
                           "rrf_k": settings.rrf_k if method == "hybrid_rrf" else None,
                           "depth": settings.retrieval_depth if method == "hybrid_rrf"
                           else None},
                "latency_s": {"p50": latencies[len(latencies) // 2],
                              "max": latencies[-1]},
                "per_question": per_q,
            }
            if args.split == "test" and (analyzer in (None, settings.bm25_analyzer)):
                name = f"retrieval_{method}_{kind}.json"
            else:
                tag = f"_{analyzer.replace('+', '-')}" if analyzer else ""
                name = f"tuning/retrieval_{method}{tag}_{kind}_{args.split}.json"
            (ROOT / "results" / "tuning").mkdir(parents=True, exist_ok=True)
            write_result(name, payload, "scripts/eval_retrieval.py")
            m = payload["metrics"]
            summary_rows.append((kind, method, analyzer or "-", len(selected), m["recall@1"],
                                 m["recall@5"], m["recall@10"], m["mrr"], name))

    print(f"\n{'set':10} {'method':11} {'analyzer':12} {'n':>4} {'R@1':>6} {'R@5':>6} "
          f"{'R@10':>6} {'MRR':>6}  file")
    for row in summary_rows:
        print(f"{row[0]:10} {row[1]:11} {row[2]:12} {row[3]:4d} {row[4]:6.3f} {row[5]:6.3f} "
              f"{row[6]:6.3f} {row[7]:6.3f}  results/{row[8]}")


if __name__ == "__main__":
    main()
