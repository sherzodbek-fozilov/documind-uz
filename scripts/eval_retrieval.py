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
  python scripts/eval_retrieval.py --set real --methods e5_small,hybrid_rrf \
      --embed-model-dir models/multilingual-e5-small-ft --variant ft
      # fine-tuned model: writes retrieval_e5_small_ft_real.json, retrieval_hybrid_rrf_ft_...
      # (scripts/eval_finetune.py runs base and fine-tuned on the same questions)
  python scripts/eval_retrieval.py --set real --eval-set v1
      # only the questions frozen in data/eval/sets/v1.json; writes
      # results/retrieval_<method>_real_v1.json and fails if a frozen question is missing
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common import ROOT, write_result  # noqa: E402

from documind.config import get_settings  # noqa: E402
from documind.evaluation import (  # noqa: E402
    article_rank,
    bootstrap_ci,
    load_eval_set,
    load_questions,
    metrics_from_ranks,
    rank_of,
    select_eval_set,
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


def evaluate(retriever, questions, key_of: dict) -> tuple[list, list, list]:
    """Chunk-level ranks (primary), article-level ranks (secondary), per-question records."""
    ranks, art_ranks, per_q = [], [], []
    for q in questions:
        start = time.perf_counter()
        results = retriever.search(q.question, k=MAX_K,
                                   doc_id=q.gold_doc if q.scope == "document" else None)
        latency = time.perf_counter() - start
        r = rank_of(q.gold_chunks, results)
        ra = article_rank(q.gold_chunks, results, key_of)
        ranks.append(r)
        art_ranks.append(ra)
        per_q.append({"id": q.id, "line": q.line, "language": q.language, "tags": list(q.tags),
                      "rank": r,
                      "rank_article": ra, "top1": results[0] if results else None,
                      "latency_s": round(latency, 4)})
    return ranks, art_ranks, per_q


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--set", choices=["real", "synthetic", "all"], default="all")
    ap.add_argument("--split", default="test")
    ap.add_argument("--methods", default="bm25,e5_small,hybrid_rrf")
    ap.add_argument("--bm25-analyzers", default=None,
                    help="comma-separated analyzers to compare (default: the configured one)")
    ap.add_argument("--embed-model-dir", type=Path, default=None,
                    help="ONNX embedding model (default: DOCUMIND_EMBED_MODEL_DIR)")
    ap.add_argument("--eval-set", default=None,
                    help="evaluate only a frozen question set, e.g. v1 (data/eval/sets/v1.json)")
    ap.add_argument("--variant", default="",
                    help="suffix for the dense and hybrid method names, e.g. 'ft' for the "
                         "fine-tuned model (results/retrieval_e5_small_ft_<set>.json)")
    args = ap.parse_args()
    settings = get_settings()
    embed_dir = args.embed_model_dir or settings.embed_model_dir
    suffix = f"_{args.variant}" if args.variant else ""
    if suffix and "bm25" in args.methods.split(","):
        ap.error("--variant changes the embedding model only; leave bm25 out of --methods")
    eval_set = None
    if args.eval_set:
        es_path = ROOT / "data/eval/sets" / f"{args.eval_set}.json"
        eval_set = load_eval_set(es_path)
        if args.set != eval_set["set"]:
            ap.error(f"eval set {args.eval_set} is for --set {eval_set['set']}")
        eval_set["file_sha256"] = hashlib.sha256(es_path.read_bytes()).hexdigest()
    es_suffix = f"_{args.eval_set}" if args.eval_set else ""
    Session = make_session_factory(settings.database_url)
    methods = args.methods.split(",")
    analyzers = (args.bm25_analyzers.split(",") if args.bm25_analyzers
                 else [settings.bm25_analyzer])
    sets = ["real", "synthetic"] if args.set == "all" else [args.set]
    embedder = None
    summary_rows = []

    for kind in sets:
        questions, problems = load_questions(QUESTION_FILES[kind])
        questions_sha256 = hashlib.sha256(QUESTION_FILES[kind].read_bytes()).hexdigest()
        for p in problems:
            print(f"WARNING {p}", file=sys.stderr)
        if eval_set is not None:
            questions, missing = select_eval_set(questions, eval_set)
            if missing:
                raise SystemExit(f"eval set {eval_set['name']}: {len(missing)} frozen questions "
                                 f"not found (edited or removed?): {missing}")
        with Session() as session:
            chunks = load_corpus(session, kind)
        if not chunks:
            print(f"[{kind}] no {kind} documents ingested; skipping", file=sys.stderr)
            continue
        by_id = {c.id: c for c in chunks}
        key_of = {c.id: c.article_key for c in chunks}
        split_of_doc = {c.doc_id: c.split for c in chunks}
        counts: Counter = Counter()
        selected = []
        for q in questions:
            if q.status == "draft":
                counts["skipped_unreviewed_draft"] += 1
            elif (any(g not in by_id for g in q.gold_chunks)
                  or by_id[q.gold_chunk].doc_id != q.gold_doc):
                counts["skipped_gold_not_found"] += 1
                print(f"WARNING [{kind}] line {q.line}: a gold chunk of {q.gold_chunks} is not "
                      f"in the corpus, or {q.gold_chunk} is not in {q.gold_doc}", file=sys.stderr)
            elif by_id[q.gold_chunk].split != args.split:
                counts["other_split"] += 1
            else:
                selected.append(q)
        if eval_set is not None and len(selected) != eval_set["n"]:
            raise SystemExit(f"eval set {eval_set['name']}: only {len(selected)} of "
                             f"{eval_set['n']} frozen questions are usable ({dict(counts)}); "
                             "the corpus or split changed")
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
                embedder = E5Embedder(embed_dir)
            retrievers["e5_small"] = DenseRetriever(chunks, embedder, f"chunks_{kind}{suffix}",
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
            method = f"{method}{suffix}"
            ranks, art_ranks, per_q = evaluate(retriever, selected, key_of)
            by_lang, by_tag = defaultdict(list), defaultdict(list)
            for q, r, ra in zip(selected, ranks, art_ranks, strict=True):
                by_lang[q.language].append((r, ra))
                for tag in q.tags:
                    by_tag[tag].append((r, ra))

            def group(pairs: list) -> dict:
                return {"n": len(pairs), **metrics_from_ranks([p[0] for p in pairs]),
                        "article": metrics_from_ranks([p[1] for p in pairs])}

            latencies = sorted(p["latency_s"] for p in per_q)
            payload = {
                # primary: the gold chunk itself
                "metrics": metrics_from_ranks(ranks),
                "n": len(selected),
                "ci95": bootstrap_ci(ranks, metrics_from_ranks),
                # secondary: any chunk of the gold article, in any language version
                "metrics_article": metrics_from_ranks(art_ranks),
                "ci95_article": bootstrap_ci(art_ranks, metrics_from_ranks),
                "by_language": {lang: group(v) for lang, v in sorted(by_lang.items())},
                # a question with several tags counts in each of them; untagged questions
                # appear in no tag group
                "by_tag": {tag: group(v) for tag, v in sorted(by_tag.items())},
                "set": kind,
                "split": args.split,
                "dataset": DATASET[kind],
                "scope": dict(Counter(q.scope for q in selected)),
                "corpus": {"chunks": len(chunks), "documents": len(split_of_doc),
                           "chunker_versions": chunker_versions},
                "question_counts": {"used": len(selected), **counts},
                "questions_sha256": questions_sha256,
                "eval_set": ({"name": eval_set["name"], "n": eval_set["n"],
                              "file_sha256": eval_set["file_sha256"]} if eval_set else None),
                "config": {"method": method, "bm25_analyzer": analyzer,
                           "embed_model": getattr(embedder, "model_id", None)
                           if method != "bm25" else None,
                           "embed_model_dir": str(embed_dir) if method != "bm25" else None,
                           "rrf_k": settings.rrf_k if method.startswith("hybrid") else None,
                           "depth": settings.retrieval_depth if method.startswith("hybrid")
                           else None},
                "latency_s": {"p50": latencies[len(latencies) // 2],
                              "max": latencies[-1]},
                "per_question": per_q,
            }
            if args.split == "test" and (analyzer in (None, settings.bm25_analyzer)):
                name = f"retrieval_{method}_{kind}{es_suffix}.json"
            else:
                tag = f"_{analyzer.replace('+', '-')}" if analyzer else ""
                name = f"tuning/retrieval_{method}{tag}_{kind}{es_suffix}_{args.split}.json"
            (ROOT / "results" / "tuning").mkdir(parents=True, exist_ok=True)
            write_result(name, payload, "scripts/eval_retrieval.py")
            m, ma = payload["metrics"], payload["metrics_article"]
            summary_rows.append((kind, method, analyzer or "-", len(selected), m["recall@1"],
                                 m["recall@5"], m["recall@10"], m["mrr"], ma["recall@5"],
                                 ma["mrr"], name))

    print(f"\n{'set':10} {'method':11} {'analyzer':12} {'n':>4} {'R@1':>6} {'R@5':>6} "
          f"{'R@10':>6} {'MRR':>6} | {'art R@5':>7} {'art MRR':>7}  file")
    for row in summary_rows:
        print(f"{row[0]:10} {row[1]:11} {row[2]:12} {row[3]:4d} {row[4]:6.3f} {row[5]:6.3f} "
              f"{row[6]:6.3f} {row[7]:6.3f} | {row[8]:7.3f} {row[9]:7.3f}  results/{row[10]}")

if __name__ == "__main__":
    main()
