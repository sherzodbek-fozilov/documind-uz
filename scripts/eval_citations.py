"""Citation correctness of /ask answers on the real and the synthetic question sets.

For every reviewed question whose gold chunk is in ``--split`` (default: test), the
question is asked the same way as the API asks it (``QAService.ask``, configured mode and
retriever, document scope for "document"-scope questions). Every returned citation is
then checked against the database, independently of the in-memory index:

  exact span   the quote equals ``chunk.text[quote_start:quote_end]`` of the cited chunk,
               the chunk belongs to the cited document, and the chunk is itself the
               exact span ``document.text[chunk.char_start:chunk.char_end]``
               -> ``citation_correctness`` (primary)
  anchor       for citations with an anchor: the quote starts inside the source block
               with that anchor -> ``anchor_correctness``

``gold_cited`` (share of questions with a gold chunk among the cited chunks) is context,
not a citation metric: it is retrieval Recall@top_k of the configured retriever.

In extractive mode every quote is cut from the chunk, so ``citation_correctness`` is
expected to be 100 %; it guards against offset bugs. It becomes informative in LLM
mode, where the model writes the quotes.

Writes results/citations_<set>.json (test split) or results/tuning/... (other splits).

Usage:
  python scripts/eval_citations.py                    # both sets, test split
  python scripts/eval_citations.py --set real --top-k 5
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common import ROOT, write_result  # noqa: E402
from sqlalchemy import select  # noqa: E402

from documind.config import get_settings  # noqa: E402
from documind.evaluation import load_questions  # noqa: E402
from documind.qa.citations import check_citation, summarize  # noqa: E402
from documind.qa.passages import chunk_segments  # noqa: E402
from documind.qa.service import QAService  # noqa: E402
from documind.storage import models  # noqa: E402
from documind.storage.db import make_session_factory  # noqa: E402

QUESTION_FILES = {"real": ROOT / "data/eval/questions.jsonl",
                  "synthetic": ROOT / "data/eval/questions_synthetic.jsonl"}
DATASET = {"real": "real documents (laws), hand-labeled questions",
           "synthetic": "SYNTHETIC contracts (synthetic-contracts-v1), template questions"}


def check_against_db(session, citation) -> tuple[str | None, bool | None]:
    """(exact-span failure reason or None, anchor ok / None if the citation has none)."""
    chunk = session.get(models.Chunk, citation.chunk_id)
    if chunk is None:
        return "unknown chunk", None
    reason = check_citation(citation, chunk.text, chunk.document_id)
    doc = chunk.document
    if reason is None and doc.text[chunk.char_start:chunk.char_end] != chunk.text:
        reason = "chunk is not the document text at its offsets"
    if citation.anchor is None:
        return reason, None
    pos = citation.start
    segs = chunk_segments(chunk.char_start, chunk.char_end,
                          [(p.char_start, p.blocks or []) for p in doc.pages])
    return reason, any(s.anchor == citation.anchor and s.start <= pos < s.end for s in segs)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--set", choices=["real", "synthetic", "all"], default="all")
    ap.add_argument("--split", default="test")
    ap.add_argument("--top-k", type=int, default=None, help="default: DOCUMIND_API_TOP_K")
    args = ap.parse_args()
    settings = get_settings()
    Session = make_session_factory(settings.database_url)
    service = QAService(Session, settings)
    top_k = args.top_k or settings.api_top_k

    for kind in (["real", "synthetic"] if args.set == "all" else [args.set]):
        questions, problems = load_questions(QUESTION_FILES[kind])
        for p in problems:
            print(f"WARNING {p}", file=sys.stderr)
        with Session() as s:
            split_of = dict(s.execute(select(models.Chunk.id, models.Chunk.split)).all())
        counts: Counter = Counter()
        selected = []
        for q in questions:
            if q.status == "draft":
                counts["skipped_unreviewed_draft"] += 1
            elif q.gold_chunk not in split_of:
                counts["skipped_gold_not_found"] += 1
            elif split_of[q.gold_chunk] != args.split:
                counts["other_split"] += 1
            else:
                selected.append(q)
        if not selected:
            print(f"[{kind}] no usable questions for split {args.split!r}; nothing written",
                  file=sys.stderr)
            continue

        reasons, anchors, per_q, gold_cited = [], [], [], 0
        inline = Counter()  # the service's own check, for comparison
        with Session() as s:
            for q in selected:
                res = service.ask(q.question, kind,
                                  q.gold_doc if q.scope == "document" else None, top_k)
                cites = res.citations if res.mode == "llm" else [p.citation for p in
                                                                 res.passages]
                q_reasons = []
                for c in cites:
                    reason, anchor_ok = check_against_db(s, c)
                    q_reasons.append(reason)
                    if anchor_ok is not None:
                        anchors.append(anchor_ok)
                # LLM citations dropped by the service's check count as invalid too
                dropped = res.citation_check.checked - res.citation_check.valid
                q_reasons += ["dropped by the service check"] * (dropped if res.mode == "llm"
                                                                  else 0)
                inline.update(res.citation_check.failures)
                reasons += q_reasons
                hit = any(c.chunk_id in q.gold_chunks for c in cites)
                gold_cited += hit
                per_q.append({"line": q.line, "language": q.language,
                              "n_citations": len(q_reasons),
                              "invalid": sum(r is not None for r in q_reasons),
                              "gold_cited": hit})
        report = summarize(reasons)
        payload = {
            "metrics": {"citation_correctness": report.correctness,
                        "anchor_correctness": (sum(anchors) / len(anchors)) if anchors
                        else None,
                        "gold_cited": gold_cited / len(selected)},
            # n = citations checked; questions are counted separately
            "n": report.checked,
            "n_by_metric": {"citation_correctness": report.checked,
                            "anchor_correctness": len(anchors),
                            "gold_cited": len(selected)},
            "failures": report.as_dict()["failures"],
            "service_check_failures": dict(inline),
            "set": kind,
            "split": args.split,
            "dataset": DATASET[kind],
            "question_counts": {"used": len(selected), **counts},
            "config": {"mode": service.mode, "retriever": settings.api_retriever,
                       "bm25_analyzer": settings.bm25_analyzer, "top_k": top_k,
                       "quote_max_sentences": settings.quote_max_sentences},
            "per_question": per_q,
        }
        name = (f"citations_{kind}.json" if args.split == "test"
                else f"tuning/citations_{kind}_{args.split}.json")
        (ROOT / "results" / "tuning").mkdir(parents=True, exist_ok=True)
        write_result(name, payload, "scripts/eval_citations.py")
        m = payload["metrics"]
        anchor = "n/a" if m["anchor_correctness"] is None else f"{m['anchor_correctness']:.3f}"
        print(f"{kind:10} questions {len(selected):4d}  citations {report.checked:4d}  "
              f"exact-span {m['citation_correctness']:.3f}  anchor {anchor}  "
              f"gold cited {m['gold_cited']:.3f}  -> results/{name}")


if __name__ == "__main__":
    main()
