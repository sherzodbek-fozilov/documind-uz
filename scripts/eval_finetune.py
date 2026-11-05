"""Before/after evaluation of the fine-tuned embedding model on the SAME real test questions.

Runs ``scripts/eval_retrieval.py`` twice with identical arguments, once with the base
ONNX model and once with the fine-tuned one (``--variant ft``), for the dense and hybrid
methods, then compares the two runs question by question:

  results/retrieval_e5_small_<set>.json       results/retrieval_e5_small_ft_<set>.json
  results/retrieval_hybrid_rrf_<set>.json     results/retrieval_hybrid_rrf_ft_<set>.json
  results/finetune_compare_<set>.json         deltas with paired bootstrap 95 % CIs

The comparison refuses to run unless both files were made from the same question file
(sha256), the same questions (line numbers, languages) and the same corpus. This hook
only reports: the training epoch and all settings must already be fixed on the
validation pairs before it is run (see kaggle/finetune_e5.py).

Usage:
  python scripts/eval_finetune.py --ft-model-dir models/multilingual-e5-small-ft
  python scripts/eval_finetune.py --compare-only          # reuse existing result files
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common import ROOT, write_result  # noqa: E402

from documind.evaluation import paired_bootstrap_delta  # noqa: E402

PAIRS = (("e5_small", "e5_small_ft"), ("hybrid_rrf", "hybrid_rrf_ft"))


def load(method: str, kind: str) -> dict:
    path = ROOT / "results" / f"retrieval_{method}_{kind}.json"
    if not path.exists():
        raise SystemExit(f"{path} not found; run without --compare-only")
    return json.loads(path.read_text(encoding="utf-8"))


def same_questions(a: dict, b: dict) -> list[str]:
    problems = []
    if a.get("questions_sha256") != b.get("questions_sha256"):
        problems.append("question files differ (sha256)")
    if a["split"] != b["split"] or a["set"] != b["set"]:
        problems.append("different set or split")
    if a["corpus"] != b["corpus"]:
        problems.append("different corpus")
    qa = [(q["line"], q["language"]) for q in a["per_question"]]
    qb = [(q["line"], q["language"]) for q in b["per_question"]]
    if qa != qb:
        problems.append("different questions")
    if a["config"].get("embed_model") == b["config"].get("embed_model"):
        problems.append("both runs used the same embedding model")
    return problems


def compare(base: dict, ft: dict) -> dict:
    out = {"base_model": base["config"]["embed_model"], "ft_model": ft["config"]["embed_model"],
           "n": base["n"]}
    for level, key in (("chunk", "rank"), ("article", "rank_article")):
        ra = [q[key] for q in base["per_question"]]
        rb = [q[key] for q in ft["per_question"]]
        out[level] = paired_bootstrap_delta(ra, rb)
        worse = sum((b or 99) > (a or 99) for a, b in zip(ra, rb, strict=True))
        better = sum((b or 99) < (a or 99) for a, b in zip(ra, rb, strict=True))
        out[f"{level}_questions"] = {"better": better, "worse": worse,
                                     "same": len(ra) - better - worse}
    by_lang = {}
    for lang in sorted({q["language"] for q in base["per_question"]}):
        idx = [i for i, q in enumerate(base["per_question"]) if q["language"] == lang]
        by_lang[lang] = paired_bootstrap_delta([base["per_question"][i]["rank"] for i in idx],
                                               [ft["per_question"][i]["rank"] for i in idx])
    out["by_language_chunk"] = by_lang
    out["per_question"] = [{"line": a["line"], "language": a["language"], "tags": a["tags"],
                            "rank_base": a["rank"], "rank_ft": b["rank"],
                            "rank_article_base": a["rank_article"],
                            "rank_article_ft": b["rank_article"]}
                           for a, b in zip(base["per_question"], ft["per_question"],
                                           strict=True)]
    return out


def run_eval(kind: str, split: str, extra: list[str]) -> None:
    cmd = [sys.executable, str(ROOT / "scripts/eval_retrieval.py"), "--set", kind,
           "--split", split, "--methods", "e5_small,hybrid_rrf", *extra]
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, cwd=ROOT)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ft-model-dir", type=Path, default=ROOT / "models/multilingual-e5-small-ft")
    ap.add_argument("--base-model-dir", type=Path, default=None,
                    help="default: DOCUMIND_EMBED_MODEL_DIR (the base model)")
    ap.add_argument("--set", default="real", choices=["real", "synthetic"])
    ap.add_argument("--compare-only", action="store_true")
    args = ap.parse_args()
    split = "test"  # before/after is reported on the test split only
    if not args.compare_only:
        if not (args.ft_model_dir / "onnx" / "model.onnx").exists():
            raise SystemExit(f"{args.ft_model_dir}/onnx/model.onnx not found; export it with "
                             "scripts/export_onnx.py")
        base_extra = (["--embed-model-dir", str(args.base_model_dir)]
                      if args.base_model_dir else [])
        run_eval(args.set, split, base_extra)
        run_eval(args.set, split, ["--embed-model-dir", str(args.ft_model_dir),
                                   "--variant", "ft"])
    payload = {"set": args.set, "split": split, "methods": {}}
    print(f"\n{'method':12} {'n':>4} {'metric':10} {'base':>6} {'ft':>6} {'delta':>7}  95% CI")
    for base_m, ft_m in PAIRS:
        base, ft = load(base_m, args.set), load(ft_m, args.set)
        problems = same_questions(base, ft)
        if problems:
            raise SystemExit(f"{base_m} vs {ft_m}: not comparable: {'; '.join(problems)}")
        cmp = compare(base, ft)
        payload["methods"][base_m] = cmp
        payload["questions_sha256"] = base["questions_sha256"]
        for metric in ("recall@1", "recall@5", "recall@10", "mrr"):
            d = cmp["chunk"][metric]
            print(f"{base_m:12} {cmp['n']:4d} {metric:10} {base['metrics'][metric]:6.3f} "
                  f"{ft['metrics'][metric]:6.3f} {d['delta']:+7.3f}  "
                  f"[{d['ci95'][0]:+.3f}, {d['ci95'][1]:+.3f}]")
    path = write_result(f"finetune_compare_{args.set}.json", payload,
                        "scripts/eval_finetune.py")
    print(f"written {path}")


if __name__ == "__main__":
    main()
