"""Draft candidate evaluation questions from chunks, for manual review and correction.

Drafts are deliberately simple (no LLM): one question from the section heading and,
when the chunk states a number (amount, days, percent), one question asking for it.
They copy the passage's wording, which would favor BM25, so every draft must be
rewritten in natural language before it is used. The eval script ignores lines with
"status": "draft".

Workflow:
  1. python scripts/draft_questions.py                    # real test docs -> data/eval/drafts/
  2. edit data/eval/drafts/drafts-real-test.jsonl: rewrite "question", fix "gold_chunk"
     if a better chunk answers it, set "status": "reviewed" (or delete the line)
  3. python scripts/draft_questions.py --accept data/eval/drafts/drafts-real-test.jsonl
     moves reviewed lines into data/eval/questions.jsonl (refuses unedited drafts)
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common import ROOT  # noqa: E402

from documind.config import get_settings  # noqa: E402
from documind.retrieval.corpus import CorpusChunk, load_corpus  # noqa: E402
from documind.storage.db import make_session_factory  # noqa: E402
from documind.translit import latin_to_cyrillic  # noqa: E402

QUESTIONS = ROOT / "data/eval/questions.jsonl"
DRAFTS_DIR = ROOT / "data/eval/drafts"
_NUMBERING = re.compile(r"^\s*(\d+(\.\d+)*\s*-?\s*(modda|модда|bob|боб)?\.?|"
                        r"(статья|глава|раздел)\s+\d+\.?|[IVXLC]+\s*[.\-]?)\s*",
                        re.IGNORECASE)
_NUMBER = re.compile(r"\d[\d\s]*(?:[.,]\d+)?")
_SENTENCE = re.compile(r"(?<=[^\W\d_][.!?])\s+")
MIN_WORDS = 15

TEMPLATES = {
    "title": {"uz-Latn": "{t} qanday tartibga solinadi?",
              "uz-Cyrl": "{t} " + latin_to_cyrillic("qanday tartibga solinadi?"),
              "ru": "Что установлено в части «{t}»?"},
    "number": {"uz-Latn": "qancha", "uz-Cyrl": "қанча", "ru": "сколько"},
}


def clean_title(title: str | None) -> str | None:
    if not title:
        return None
    last = title.split(" / ")[-1]
    t = _NUMBERING.sub("", last).strip(" .:")
    if len(t) < 4:
        return None
    return t[0].upper() + t[1:].lower() if t.isupper() else t


def number_question(text: str, language: str) -> str | None:
    """Turn the first sentence that contains a number into a question about that number."""
    body = re.sub(r"^\s*\d+(\.\d+)*\.\s*", "", text.split("\n\n")[-1])
    for sentence in _SENTENCE.split(body):
        if _NUMBER.search(sentence) and len(sentence.split()) >= 5:
            q = _NUMBER.sub(TEMPLATES["number"][language] + " ", sentence, count=1)
            return re.sub(r"\s+", " ", q).strip().rstrip(".;:") + "?"
    return None


def drafts_for(chunk: CorpusChunk) -> list[tuple[str, str]]:
    out = []
    lang = chunk.language if chunk.language in TEMPLATES["title"] else "uz-Latn"
    title = clean_title(chunk.section_title)
    if title:
        out.append(("title", TEMPLATES["title"][lang].format(t=title)))
    nq = number_question(chunk.text, lang)
    if nq:
        out.append(("number", nq))
    return out


def make_drafts(chunks: list[CorpusChunk], split: str, per_doc: int,
                seed: int) -> list[dict]:
    rng = random.Random(seed)
    by_doc: dict[str, list[CorpusChunk]] = {}
    for c in chunks:
        if c.split == split and len(c.text.split()) >= MIN_WORDS:
            by_doc.setdefault(c.doc_id, []).append(c)
    rows = []
    for doc_id in sorted(by_doc):
        picked = rng.sample(by_doc[doc_id], min(per_doc, len(by_doc[doc_id])))
        for c in sorted(picked, key=lambda x: x.id):
            for method, q in drafts_for(c):
                rows.append({"question": q, "draft_question": q, "status": "draft",
                             "language": c.language, "gold_doc": c.doc_id, "gold_chunk": c.id,
                             "scope": "corpus", "draft_method": method,
                             "context": c.text[:400]})
    return rows


def accept(path: Path, allow_unedited: bool) -> tuple[int, int, list[str]]:
    """Move reviewed rows from a drafts file into questions.jsonl; keep the rest."""
    keep, moved, problems = [], [], []
    existing = set()
    if QUESTIONS.exists():
        existing = {(r["question"], r["gold_chunk"]) for r in
                    (json.loads(x) for x in QUESTIONS.read_text(encoding="utf-8").splitlines()
                     if x.strip())}
    for n, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        row = json.loads(raw)
        if row.get("status") != "reviewed":
            keep.append(row)
            continue
        if row["question"].strip() == (row.get("draft_question") or "").strip() \
                and not allow_unedited:
            problems.append(f"line {n}: marked reviewed but the question is the unedited draft")
            keep.append(row)
            continue
        if (row["question"], row["gold_chunk"]) in existing:
            problems.append(f"line {n}: already in {QUESTIONS.name}")
            continue
        moved.append({k: row[k] for k in ("question", "language", "gold_doc", "gold_chunk",
                                          "scope", "draft_question") if k in row}
                     | {"status": "reviewed"})
    if moved:
        with QUESTIONS.open("a", encoding="utf-8") as f:
            for row in moved:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in keep),
                    encoding="utf-8")
    return len(moved), len(keep), problems


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--kind", choices=["real", "synthetic"], default="real")
    ap.add_argument("--split", default="test")
    ap.add_argument("--per-doc", type=int, default=10, help="chunks sampled per document")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--accept", type=Path, help="move reviewed drafts into questions.jsonl")
    ap.add_argument("--allow-unedited", action="store_true")
    args = ap.parse_args()

    if args.accept:
        moved, kept, problems = accept(args.accept, args.allow_unedited)
        for p in problems:
            print(f"WARNING {p}", file=sys.stderr)
        print(f"moved {moved} reviewed questions to {QUESTIONS}; {kept} lines left in "
              f"{args.accept}")
        return

    Session = make_session_factory(get_settings().database_url)
    with Session() as session:
        chunks = load_corpus(session, args.kind)
    rows = make_drafts(chunks, args.split, args.per_doc, args.seed)
    if not rows:
        raise SystemExit(f"no {args.kind} chunks in split {args.split!r}; ingest documents first")
    DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    out = DRAFTS_DIR / f"drafts-{args.kind}-{args.split}.jsonl"
    if out.exists():
        raise SystemExit(f"{out} exists; review or delete it first (it may hold your edits)")
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                   encoding="utf-8")
    print(f"wrote {len(rows)} drafts to {out}")


if __name__ == "__main__":
    main()
