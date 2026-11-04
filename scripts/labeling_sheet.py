"""Labeling sheet for real evaluation questions, done in batches (e.g. in a chat).

  plan    pick the chunks to label from the REAL TEST split and save their ids in
          data/eval/labeling_plan.json (ids only, no text; seeded, reproducible)
  show    print one batch (chunk id, language, chapter / article title, text)
  record  read lines "chunk_id | language | question [| tags]" from stdin and append them to
          data/eval/questions.jsonl with "status": "reviewed" (same format as
          draft_questions.py --accept). Several gold chunks: "id1, id2 | language | q".
          Optional 4th column: comma-separated tags (e.g. "colloquial, typo"), stored as
          "tags": [...] exactly as written (only surrounding spaces are removed).
          The question text is stored exactly as given.

Selection: half Civil Code, half Labor Code per language; within an act, chunks are
spread over its test chapters roughly in proportion to their size (at least one per
chapter); chunks under MIN_WORDS words and excluded articles are skipped; uz and ru
chunks are taken from different articles, so no batch shows a translation pair.

Usage:
  python scripts/labeling_sheet.py plan
  python scripts/labeling_sheet.py show --batch 1
  python scripts/labeling_sheet.py record < answers.txt
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from documind.config import get_settings  # noqa: E402
from documind.evaluation import LANGUAGES  # noqa: E402
from documind.storage import models  # noqa: E402
from documind.storage.db import make_session_factory  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PLAN = ROOT / "data/eval/labeling_plan.json"
QUESTIONS = ROOT / "data/eval/questions.jsonl"
MIN_WORDS = 25
BATCH = 20
# articles to avoid: (act group_id, article number); see docs/data.md (version check)
EXCLUDED_ARTICLES = {("civil-code-part2", 888)}
PER_ACT = {"civil-code-part2": 25, "labor-code-2022": 25}  # per language
_ARTICLE_RE = re.compile(r"(?:^|/ )\s*(?:(\d{1,4})\s*-\s*modda\b|Статья\s+(\d{1,4})\b)",
                         re.IGNORECASE)


def article_of(section_title: str | None) -> int | None:
    found = _ARTICLE_RE.findall(section_title or "")
    return int(found[-1][0] or found[-1][1]) if found else None


def allocate(sizes: dict[int, int], total: int) -> dict[int, int]:
    """At least one per chapter, the rest in proportion to size (largest remainder)."""
    alloc = {ch: 1 for ch in sizes}
    rest = total - len(sizes)
    whole = sum(sizes.values())
    shares = {ch: rest * n / whole for ch, n in sizes.items()}
    for ch, share in shares.items():
        alloc[ch] += int(share)
    left = total - sum(alloc.values())
    for ch in sorted(shares, key=lambda c: -(shares[c] - int(shares[c])))[:left]:
        alloc[ch] += 1
    return alloc


def load_test_chunks(session) -> list[dict]:
    rows = session.execute(
        select(models.Chunk, models.Document.group_id).join(models.Document)
        .where(models.Document.is_synthetic.is_(False), models.Chunk.split == "test")
        .order_by(models.Chunk.id)).all()
    return [{"id": c.id, "doc": c.document_id, "act": g, "language": c.language,
             "chapter": c.chapter, "article": article_of(c.section_title),
             "title": c.section_title, "words": c.n_words, "text": c.text}
            for c, g in rows]


def make_plan(chunks: list[dict], seed: int) -> list[str]:
    rng = random.Random(seed)
    usable = [c for c in chunks if c["words"] >= MIN_WORDS
              and (c["act"], c["article"]) not in EXCLUDED_ARTICLES]
    picked: dict[str, list[dict]] = {}
    used_articles: set[tuple[str, int | None, int | None]] = set()
    for lang in ("uz-Latn", "ru"):
        picked[lang] = []
        for act, quota in PER_ACT.items():
            pool = [c for c in usable if c["act"] == act and c["language"] == lang]
            by_ch: dict[int, list[dict]] = defaultdict(list)
            for c in pool:
                by_ch[c["chapter"]].append(c)
            alloc = allocate({ch: len(v) for ch, v in by_ch.items()}, quota)
            for ch in sorted(by_ch):
                cands = [c for c in by_ch[ch]
                         if (act, ch, c["article"]) not in used_articles or c["article"] is None]
                rng.shuffle(cands)
                chosen, chosen_articles = [], set()
                for c in cands:
                    if len(chosen) == alloc[ch]:
                        break
                    if c["article"] is not None and c["article"] in chosen_articles:
                        continue  # one chunk per article
                    chosen.append(c)
                    chosen_articles.add(c["article"])
                for c in chosen:
                    used_articles.add((act, ch, c["article"]))
                picked[lang] += chosen
    for lang in picked:
        rng.shuffle(picked[lang])
    # interleave: each batch holds BATCH/2 chunks of each language
    order = []
    for i in range(max(len(v) for v in picked.values())):
        for lang in ("uz-Latn", "ru"):
            if i < len(picked[lang]):
                order.append(picked[lang][i]["id"])
    return order


def show(chunks_by_id: dict[str, dict], ids: list[str], batch: int) -> str:
    part = ids[(batch - 1) * BATCH: batch * BATCH]
    n_batches = (len(ids) + BATCH - 1) // BATCH
    out = [f"Batch {batch} of {n_batches} ({len(part)} chunks)", ""]
    for cid in part:
        c = chunks_by_id[cid]
        act = "Civil Code pt 2" if c["act"].startswith("civil") else "Labor Code"
        title = (c["title"] or "").split(" / ")[-1]
        out += [f"### `{cid}` | {c['language']} | {act}, chapter {c['chapter']} | {title}",
                "", c["text"], ""]
    return "\n".join(out)


def parse_answers(lines: list[str], chunks_by_id: dict[str, dict],
                  existing: set[tuple[str, tuple[str, ...]]]) -> tuple[list[dict], list[str]]:
    rows, problems = [], []
    for n, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        parts = line.split("|", 3)
        if len(parts) not in (3, 4):
            problems.append(f"line {n}: expected 'chunk_id | language | question [| tags]'")
            continue
        ids = [x.strip().strip("`") for x in parts[0].split(",") if x.strip()]
        language, question = parts[1].strip(), parts[2].strip()
        tags = [t.strip() for t in parts[3].split(",") if t.strip()] if len(parts) == 4 else []
        bad = [i for i in ids if i not in chunks_by_id]
        if not ids or bad:
            problems.append(f"line {n}: not a real test chunk: {', '.join(bad) or '(none)'}")
            continue
        if language not in LANGUAGES:
            problems.append(f"line {n}: language must be one of {LANGUAGES}")
            continue
        if not question:
            problems.append(f"line {n}: empty question")
            continue
        if (question, tuple(ids)) in existing:
            problems.append(f"line {n}: already recorded")
            continue
        row = {"question": question, "language": language, "gold_doc": chunks_by_id[ids[0]]["doc"],
               "gold_chunk": ids[0], "scope": "corpus"}
        if len(ids) > 1:
            row["gold_chunks"] = ids
        if tags:
            row["tags"] = tags
        row["status"] = "reviewed"
        rows.append(row)
        existing.add((question, tuple(ids)))
    return rows, problems


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--force", action="store_true", help="overwrite an existing plan")
    s = sub.add_parser("show")
    s.add_argument("--batch", type=int, required=True)
    sub.add_parser("record")
    args = ap.parse_args()

    Session = make_session_factory(get_settings().database_url)
    with Session() as session:
        chunks = load_test_chunks(session)
    by_id = {c["id"]: c for c in chunks}

    if args.cmd == "plan":
        if PLAN.exists() and not args.force:
            raise SystemExit(f"{PLAN} exists (labeling may have started); use --force")
        ids = make_plan(chunks, args.seed)
        PLAN.write_text(json.dumps({"seed": args.seed, "min_words": MIN_WORDS,
                                    "excluded_articles": sorted(EXCLUDED_ARTICLES),
                                    "chunk_ids": ids}, ensure_ascii=False, indent=1) + "\n",
                        encoding="utf-8")
        counts = defaultdict(int)
        for cid in ids:
            c = by_id[cid]
            counts[f"{c['language']} {c['act']} ch{c['chapter']}"] += 1
        print(f"planned {len(ids)} chunks in {(len(ids) + BATCH - 1) // BATCH} batches")
        print(json.dumps(dict(sorted(counts.items())), ensure_ascii=False, indent=1))
    elif args.cmd == "show":
        ids = json.loads(PLAN.read_text(encoding="utf-8"))["chunk_ids"]
        print(show(by_id, ids, args.batch))
    else:
        existing = set()
        if QUESTIONS.exists():
            for line in QUESTIONS.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    r = json.loads(line)
                    existing.add((r["question"], tuple(r.get("gold_chunks") or [r["gold_chunk"]])))
        rows, problems = parse_answers(sys.stdin.read().splitlines(), by_id, existing)
        for pr in problems:
            print(f"NOT RECORDED {pr}", file=sys.stderr)
        with QUESTIONS.open("a", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"recorded {len(rows)} questions in {QUESTIONS}")


if __name__ == "__main__":
    main()
