"""Generate SYNTHETIC retrieval questions for the synthetic contracts (sanity set).

For every document in data/synthetic/manifest.jsonl, the contract text is rebuilt with
the same seed as ``make_synthetic_docs.py`` (generation is deterministic), a fixed
question bank is applied to known clauses, and each clause is located among the
document's chunks in the database (fuzzy match, so OCR'd scans work too).

The questions do not name the parties or the contract number, so they are evaluated
with ``"scope": "document"`` (search within the gold document). They are a sanity
check of the pipeline, not a measure of real-world quality: template text, template
questions, many near-identical documents.

Output: data/eval/questions_synthetic.jsonl (every line has "synthetic": true).
Usage: python scripts/make_synthetic_questions.py [--data data/synthetic] [--seed 13]
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

from rapidfuzz import fuzz
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common import ROOT  # noqa: E402
from make_synthetic_docs import build_blocks  # noqa: E402

from documind.config import get_settings  # noqa: E402
from documind.ingestion.text import normalize_block  # noqa: E402
from documind.storage import models  # noqa: E402
from documind.storage.db import make_session_factory  # noqa: E402
from documind.translit import latin_to_cyrillic  # noqa: E402

# (section number, clause number) -> (uz question, ru question). Sections 1-3 are
# template-specific; 4-8 are the common tail (liability, force majeure, disputes, term).
BANK = {
    "ijara": {
        (1, 1): ("Ijaraga beriladigan joyning maydoni qancha?",
                 "Какова площадь арендуемого помещения?"),
        (1, 2): ("Joydan qanday maqsadda foydalaniladi?",
                 "Для чего арендатор будет использовать помещение?"),
        (2, 1): ("Har oy qancha ijara toʻlanadi?", "Сколько составляет плата за аренду в месяц?"),
        (2, 3): ("Kafolat puli qancha va qachon toʻlanadi?",
                 "Какой залог нужно внести и в какой срок?"),
        (2, 4): ("Kommunal toʻlovlarni kim toʻlaydi?", "Кто оплачивает коммунальные услуги?"),
        (3, 2): ("Ijarachi joyni boshqa shaxsga ijaraga bera oladimi?",
                 "Можно ли сдать помещение в субаренду?"),
        (3, 3): ("Kapital taʼmirni kim qiladi?", "Кто отвечает за капитальный ремонт?"),
    },
    "xizmat": {
        (1, 1): ("Ijrochi qanday xizmat koʻrsatadi?", "Какие услуги оказывает исполнитель?"),
        (1, 2): ("Xizmatlar qaysi vaqtda koʻrsatiladi?", "В какое время оказываются услуги?"),
        (2, 1): ("Xizmatlar oyiga qancha turadi?", "Сколько стоят услуги в месяц?"),
        (2, 2): ("Buyurtmachi toʻlovni necha kunda amalga oshirishi kerak?",
                 "В какой срок заказчик должен оплатить услуги?"),
        (3, 3): ("Ijrochi boshqa tashkilotlarni jalb qilishi mumkinmi?",
                 "Может ли исполнитель привлекать субподрядчиков?"),
        (3, 4): ("Maxfiy maʼlumotlar boʻyicha qanday majburiyat bor?",
                 "Какие обязательства о конфиденциальности есть в договоре?"),
    },
    "oldi_sotdi": {
        (1, 1): ("Qancha mahsulot yetkazib beriladi?", "Сколько единиц товара поставляется?"),
        (2, 1): ("Shartnomaning umumiy qiymati qancha?", "Какова общая сумма договора?"),
        (2, 2): ("Oldindan qancha toʻlash kerak?", "Какой размер предоплаты?"),
        (2, 3): ("Yetkazib berish xarajatlarini kim qoplaydi?", "Кто платит за доставку товара?"),
        (3, 1): ("Mahsulot qancha vaqtda yetkazib beriladi?",
                 "Через сколько дней товар будет доставлен?"),
        (3, 3): ("Mahsulotga qancha muddat kafolat beriladi?", "Какой гарантийный срок на товар?"),
    },
}
COMMON = {
    (4, 1): ("Toʻlov kechiksa qancha penya hisoblanadi?", "Какая пеня за просрочку оплаты?"),
    (5, 2): ("Fors-major haqida ikkinchi tarafni qachon xabardor qilish kerak?",
             "В какой срок нужно сообщить о форс-мажоре?"),
    (6, 2): ("Nizo qaysi sudda koʻriladi?", "В каком суде рассматриваются споры?"),
    (7, 1): ("Shartnoma qancha muddatga tuzilgan?", "На какой срок заключён договор?"),
    (7, 2): ("Shartnomani muddatidan oldin qanday bekor qilish mumkin?",
             "Как досрочно расторгнуть договор?"),
}
MIN_MATCH = 85  # rapidfuzz partial_ratio needed to accept a chunk as containing the clause


def clause_texts(blocks: list[tuple[str, str]]) -> dict[tuple[int, int], str]:
    out = {}
    for kind, text in blocks:
        if kind != "text":
            continue
        head = text.split(" ", 1)[0].rstrip(".")
        parts = head.split(".")
        if len(parts) == 2 and all(p.isdigit() for p in parts):
            out[(int(parts[0]), int(parts[1]))] = normalize_block(text)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data", type=Path, default=ROOT / "data/synthetic")
    ap.add_argument("--seed", type=int, default=13, help="must match make_synthetic_docs.py")
    ap.add_argument("--out", type=Path, default=ROOT / "data/eval/questions_synthetic.jsonl")
    args = ap.parse_args()
    manifest = [json.loads(x) for x in (args.data / "manifest.jsonl").read_text(
        encoding="utf-8").splitlines() if x.strip()]
    Session = make_session_factory(get_settings().database_url)
    rows, unmatched = [], 0
    with Session() as session:
        for m in manifest:
            n = int(m["doc_id"].rsplit("-", 1)[1])
            rng = random.Random(f"{args.seed}-{m['language']}-{m['template']}-{n}")
            clauses = clause_texts(build_blocks(m["template"], m["language"], rng))
            chunks = session.scalars(select(models.Chunk).where(
                models.Chunk.document_id == m["doc_id"]).order_by(models.Chunk.idx)).all()
            if not chunks:
                print(f"skip {m['doc_id']}: not ingested", file=sys.stderr)
                continue
            for key, (q_uz, q_ru) in {**BANK[m["template"]], **COMMON}.items():
                clause = clauses.get(key)
                if clause is None:
                    continue
                scored = [(fuzz.partial_ratio(clause, c.text), c) for c in chunks]
                score, best = max(scored, key=lambda x: x[0])
                if score < MIN_MATCH:
                    unmatched += 1
                    print(f"no chunk for {m['doc_id']} clause {key} (best {score:.0f})",
                          file=sys.stderr)
                    continue
                question = {"uz-Latn": q_uz, "uz-Cyrl": latin_to_cyrillic(q_uz),
                            "ru": q_ru}[m["language"]]
                rows.append({"question": question, "language": m["language"],
                             "gold_doc": m["doc_id"], "gold_chunk": best.id,
                             "scope": "document", "status": "synthetic", "synthetic": True,
                             "template": m["template"], "clause": f"{key[0]}.{key[1]}",
                             "match_score": round(score, 1)})
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"wrote {len(rows)} SYNTHETIC questions to {args.out} ({unmatched} clauses unmatched)")


if __name__ == "__main__":
    main()
