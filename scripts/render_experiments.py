"""Render result tables for one experiment into docs/experiments.md (between markers).

The tables are generated from results/retrieval_<method>_<set>.json, so every number in
docs/experiments.md comes from a result file written by scripts/eval_retrieval.py. The
block records the source files' git commit and generation time; text around the block is
written by hand.

With ``--finetune`` the block compares the base and the fine-tuned embedding model from
results/finetune_compare_<set>[_<eval set>].json and the matching retrieval files
(retrieval_<method>[_ft]_<set>[_<eval set>].json): base and fine-tuned metrics, paired
deltas with bootstrap intervals, question counts, and per-language and per-tag deltas.
The per-tag deltas are computed here from the per-question ranks in the comparison file
(same paired bootstrap as scripts/eval_finetune.py).

Usage: python scripts/render_experiments.py --name pilot-2026-11-04 [--set real]
       python scripts/render_experiments.py --name pilot-3 --eval-set v1
       python scripts/render_experiments.py --name finetune-1 --eval-set v1 --finetune
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from documind.evaluation import paired_bootstrap_delta  # noqa: E402

DOC = ROOT / "docs/experiments.md"
METHODS = [("BM25", "bm25"), ("e5-small (dense)", "e5_small"), ("Hybrid RRF", "hybrid_rrf")]
KEYS = [("Recall@1", "recall@1"), ("Recall@5", "recall@5"), ("Recall@10", "recall@10"),
        ("MRR@10", "mrr")]
FT_METHODS = [("e5-small (dense)", "e5_small"), ("Hybrid RRF", "hybrid_rrf")]


def _cell(metrics: dict, ci: dict, key: str) -> str:
    if key not in metrics:
        return "—"
    lo, hi = ci.get(key, [None, None])
    return f"{metrics[key]:.2f} [{lo:.2f}–{hi:.2f}]" if lo is not None else f"{metrics[key]:.2f}"


def render(results: dict[str, dict]) -> str:
    first = next(iter(results.values()))
    es = first.get("eval_set") or {}
    suffix = f"_{es['name']}" if es else ""
    out = [f"Source: `results/retrieval_*_{first['set']}{suffix}.json`, split "
           f"`{first['split']}`, n = {first['n']} questions, commit "
           f"`{first.get('git_commit')}`, generated {first.get('generated_at')}. "
           "Brackets: 95% bootstrap confidence interval."]
    if first.get("questions_sha256"):
        out.append(f"Questions file sha256: `{first['questions_sha256']}`.")
    if es:
        out.append(f"Eval set: `{es['name']}` ({es['n']} frozen questions, "
                   f"`data/eval/sets/{es['name']}.json` sha256 `{es['file_sha256']}`).")
    out = [" ".join(out), ""]
    for title, mkey, ckey in [("Chunk level (primary)", "metrics", "ci95"),
                              ("Article level (secondary)", "metrics_article", "ci95_article")]:
        out += [f"**{title}**", "", "| Method | " + " | ".join(k for k, _ in KEYS) + " |",
                "|---" * (len(KEYS) + 1) + "|"]
        for label, m in METHODS:
            d = results[m]
            out.append(f"| {label} | " + " | ".join(_cell(d.get(mkey, {}), d.get(ckey, {}), k)
                                                    for _, k in KEYS) + " |")
        out.append("")
    for title, field in [("By language", "by_language"), ("By tag", "by_tag")]:
        groups = sorted(next(iter(results.values()))[field])
        out += [f"**{title}** (Recall@5 / MRR@10, chunk level; article-level Recall@5 in "
                "parentheses)", "",
                "| Group | n | " + " | ".join(label for label, _ in METHODS) + " |",
                "|---|---|" + "---|" * len(METHODS)]
        for g in groups:
            n = results[METHODS[0][1]][field][g]["n"]
            cells = []
            for _, m in METHODS:
                v = results[m][field][g]
                cells.append(f"{v['recall@5']:.2f} / {v['mrr']:.2f} "
                             f"({v['article']['recall@5']:.2f})")
            out.append(f"| {g} | {n} | " + " | ".join(cells) + " |")
        out.append("")
    return "\n".join(out).rstrip()


def _delta(d: dict) -> str:
    lo, hi = d["ci95"]
    return f"{d['delta']:+.3f} [{lo:+.3f}, {hi:+.3f}]"


def render_finetune(cmp: dict, base: dict[str, dict], ft: dict[str, dict]) -> str:
    """Base vs fine-tuned on the same questions; every number comes from the files."""
    b0, f0 = base[FT_METHODS[0][1]], ft[FT_METHODS[0][1]]
    es = cmp.get("eval_set")
    same_ids = all([q["id"] for q in base[m]["per_question"]]
                   == [q["id"] for q in ft[m]["per_question"]] for _, m in FT_METHODS)
    m0 = cmp["methods"][FT_METHODS[0][1]]
    head = [f"Source: `results/finetune_compare_{cmp['set']}{'_' + es if es else ''}.json` "
            f"(commit `{cmp.get('git_commit')}`, generated {cmp.get('generated_at')}), base runs "
            f"commit `{b0.get('git_commit')}`, fine-tuned runs commit `{f0.get('git_commit')}`. "
            f"Eval set `{es}`, split `{cmp['split']}`, n = {m0['n']} questions; question ids "
            f"identical in base and fine-tuned runs: {'yes' if same_ids else 'NO'}. "
            f"Base model revision `{m0['base_model']}`, fine-tuned model `{m0['ft_model']}`."]
    if b0.get("questions_sha256") != f0.get("questions_sha256"):
        head.append(f"Questions file sha256 differs between the runs (base "
                    f"`{b0.get('questions_sha256')}`, fine-tuned `{f0.get('questions_sha256')}`).")
    else:
        head.append(f"Questions file sha256 `{b0.get('questions_sha256')}`.")
    head.append("Deltas are fine-tuned minus base; brackets: 95% paired bootstrap interval.")
    out = [" ".join(head), ""]
    for title, level, mkey in [("Chunk level (primary)", "chunk", "metrics"),
                               ("Article level (secondary)", "article", "metrics_article")]:
        out += [f"**{title}**", "", "| Method | Metric | Base | Fine-tuned | Delta [95% CI] |",
                "|---|---|---|---|---|"]
        for label, m in FT_METHODS:
            for name, key in KEYS:
                out.append(f"| {label} | {name} | {base[m][mkey][key]:.3f} | "
                           f"{ft[m][mkey][key]:.3f} | {_delta(cmp['methods'][m][level][key])} |")
        out.append("")
    out += ["**Questions whose rank changed** (better = gold found higher)", "",
            "| Method | Level | Better | Worse | Same |", "|---|---|---|---|---|"]
    for label, m in FT_METHODS:
        for level in ("chunk", "article"):
            c = cmp["methods"][m][f"{level}_questions"]
            out.append(f"| {label} | {level} | {c['better']} | {c['worse']} | {c['same']} |")
    out.append("")
    for title, groups_of in [("By language", "language"), ("By tag", "tag")]:
        out += [f"**{title}** (chunk level, delta Recall@5 / delta MRR@10 with 95% CI)", "",
                "| Group | n | " + " | ".join(label for label, _ in FT_METHODS) + " |",
                "|---|---|" + "---|" * len(FT_METHODS)]
        pq0 = cmp["methods"][FT_METHODS[0][1]]["per_question"]
        if groups_of == "language":
            groups = sorted({q["language"] for q in pq0})
        else:
            groups = sorted({t for q in pq0 for t in q["tags"]})
        for g in groups:
            cells, n = [], 0
            for _, m in FT_METHODS:
                pq = cmp["methods"][m]["per_question"]
                sel = [q for q in pq if (q["language"] == g if groups_of == "language"
                                         else g in q["tags"])]
                n = len(sel)
                d = paired_bootstrap_delta([q["rank_base"] for q in sel],
                                           [q["rank_ft"] for q in sel])
                cells.append(f"{_delta(d['recall@5'])} / {_delta(d['mrr'])}")
            out.append(f"| {g} | {n} | " + " | ".join(cells) + " |")
        out.append("")
    return "\n".join(out).rstrip()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--name", required=True, help="marker name of the experiment block")
    ap.add_argument("--set", default="real")
    ap.add_argument("--eval-set", default=None, help="read results of a frozen set, e.g. v1")
    ap.add_argument("--finetune", action="store_true",
                    help="render the base vs fine-tuned comparison instead")
    args = ap.parse_args()
    suffix = f"_{args.eval_set}" if args.eval_set else ""

    def load(name: str) -> dict:
        return json.loads((ROOT / "results" / name).read_text(encoding="utf-8"))

    if args.finetune:
        cmp = load(f"finetune_compare_{args.set}{suffix}.json")
        base = {m: load(f"retrieval_{m}_{args.set}{suffix}.json") for _, m in FT_METHODS}
        ft = {m: load(f"retrieval_{m}_ft_{args.set}{suffix}.json") for _, m in FT_METHODS}
        block = render_finetune(cmp, base, ft)
    else:
        block = render({m: load(f"retrieval_{m}_{args.set}{suffix}.json") for _, m in METHODS})
    begin = (f"<!-- BEGIN EXPERIMENT {args.name} (generated by scripts/render_experiments.py, "
             "do not edit) -->")
    end = f"<!-- END EXPERIMENT {args.name} -->"
    text = DOC.read_text(encoding="utf-8")
    pattern = re.compile(re.escape(begin) + r".*?" + re.escape(end), re.S)
    if not pattern.search(text):
        raise SystemExit(f"markers for {args.name} not found in {DOC}")
    DOC.write_text(pattern.sub(lambda _: f"{begin}\n{block}\n{end}", text),
                   encoding="utf-8")
    print(f"updated {DOC}")


if __name__ == "__main__":
    main()
