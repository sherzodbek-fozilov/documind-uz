"""Generate SYNTHETIC contracts in uz-Latn, uz-Cyrl and ru as PDF, DOCX and simulated scans.

Everything produced here is synthetic: invented parties, names, addresses and amounts.
Every document starts with a "SINTETIK NAMUNA" / "СИНТЕТИЧЕСКИЙ ОБРАЗЕЦ" line, its file
name starts with ``syn-``, and the manifest marks it ``"synthetic": true``.

Each generated contract appears in the corpus exactly once, in one format (PDF with a
text layer, DOCX, or an image-only "scanned" PDF), so the corpus has no duplicates.
For scans, the clean page text is saved in ``_truth/<doc_id>.json`` for OCR evaluation.

Output (default ``data/synthetic/``):
    manifest.jsonl            one line per document (read by ``documind ingest``)
    syn-<lang>-<type>-NNN.pdf|.docx
    _truth/<doc_id>.json      ground-truth page text for scanned documents

Usage: python scripts/make_synthetic_docs.py [--out DIR] [--per-combo 4] [--seed 13]
"""

from __future__ import annotations

import argparse
import io
import json
import random
import sys
from pathlib import Path
from xml.sax.saxutils import escape

import docx
import pymupdf
from PIL import Image, ImageFilter
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import synthetic_templates as T  # noqa: E402

from documind.ingestion.pdf import _text_blocks  # noqa: E402
from documind.translit import latin_to_cyrillic  # noqa: E402

DATASET_ID = "synthetic-contracts-v1"
LANGS = ["uz-Latn", "uz-Cyrl", "ru"]
FORMATS = ["pdf", "docx", "scan"]
FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")
MONTHS_UZ = ["yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul", "avgust", "sentabr",
             "oktabr", "noyabr", "dekabr"]
MONTHS_RU = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа",
             "сентября", "октября", "ноября", "декабря"]


def _amount(rng: random.Random, lo: int, hi: int) -> str:
    return f"{rng.randrange(lo, hi, 50_000):,}".replace(",", " ")


def sample_params(rng: random.Random, lang: str) -> dict[str, str]:
    a, b = rng.sample(T.COMPANIES, 2)
    city = rng.choice(T.CITIES)
    year, month, day = rng.choice([2024, 2025, 2026]), rng.randrange(12), rng.randint(1, 28)
    goods = rng.choice(T.GOODS)
    service = rng.choice(T.SERVICES)
    ru = lang == "ru"
    penalty = rng.choice(["0,1", "0,2", "0,3", "0,5"])
    return {
        "city": T.CITIES_RU[city] if ru else city,
        "date": (f"{day} {MONTHS_RU[month]} {year} г." if ru
                 else f"{year}-yil {day}-{MONTHS_UZ[month]}"),
        "num": f"{rng.randint(1, 99)}/{year % 100}-{rng.randint(100, 999)}",
        "party_a": f"«{a}» MChJ" if not ru else f"ООО «{a}»",
        "party_b": f"«{b}» MChJ" if not ru else f"ООО «{b}»",
        "person_a": f"{rng.choice(T.INITIALS)} {rng.choice(T.SURNAMES)}",
        "person_b": f"{rng.choice(T.INITIALS)} {rng.choice(T.SURNAMES)}",
        "amount": _amount(rng, 2_000_000, 90_000_000),
        "deposit": _amount(rng, 1_000_000, 10_000_000),
        "term": str(rng.choice([6, 11, 12, 24, 36])),
        "penalty": penalty,
        "max_penalty": str(rng.choice([10, 20, 50])),
        "pay_days": str(rng.choice([5, 10, 15, 20])),
        "notice_days": str(rng.choice([10, 15, 30])),
        "address": (f"{T.CITIES_RU[city] if ru else city}, {rng.choice(T.STREETS)}, "
                    + (f"д. {rng.randint(1, 120)}" if ru else f"{rng.randint(1, 120)}-uy")),
        "area": str(rng.choice([24, 36, 48, 60, 85, 120, 150])),
        "goods": goods[1] if ru else goods[0],
        "quantity": str(rng.choice([20, 50, 100, 250, 400])),
        "delivery_days": str(rng.choice([7, 10, 14, 21, 30])),
        "warranty": str(rng.choice([6, 12, 18, 24])),
        "service": service[1] if ru else service[0],
        "report_day": str(rng.choice([3, 5, 10])),
        "hours": "9:00–18:00",
    }


def build_blocks(template: str, lang: str, rng: random.Random) -> list[tuple[str, str]]:
    """Return [(kind, text)] with kind in {"mark", "title", "heading", "text"}."""
    tpl = T.TEMPLATES[template]
    ru = lang == "ru"
    i = 1 if ru else 0
    params = sample_params(rng, lang)
    heading_style = rng.choice(["upper", "article"])
    blocks = [("mark", T.MARK["ru" if ru else "uz"]),
              ("title", tpl["title"][i]),
              ("text", tpl["intro"][i].format(**params))]
    sections = tpl["sections"] + T.COMMON_TAIL
    for n, sec in enumerate(sections, start=1):
        head, clauses = sec[i], sec[2 + i]
        if heading_style == "upper":
            heading = f"{n}. {head.upper()}"
        else:
            heading = f"Статья {n}. {head}" if ru else f"{n}-modda. {head}"
        blocks.append(("heading", heading))
        for k, clause in enumerate(clauses, start=1):
            blocks.append(("text", f"{n}.{k}. {clause.format(**params)}"))
    if lang == "uz-Cyrl":
        blocks = [(kind, latin_to_cyrillic(text)) for kind, text in blocks]
    return blocks


def write_pdf(blocks: list[tuple[str, str]], path: Path, title: str) -> None:
    pdfmetrics.registerFont(TTFont("DejaVu", str(FONT_DIR / "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVu-Bold", str(FONT_DIR / "DejaVuSans-Bold.ttf")))
    styles = {
        "mark": ParagraphStyle("mark", fontName="DejaVu", fontSize=8, leading=10),
        "title": ParagraphStyle("title", fontName="DejaVu-Bold", fontSize=13, leading=17,
                                alignment=1, spaceBefore=6, spaceAfter=8),
        "heading": ParagraphStyle("heading", fontName="DejaVu-Bold", fontSize=11, leading=14,
                                  spaceBefore=8, spaceAfter=4),
        "text": ParagraphStyle("text", fontName="DejaVu", fontSize=11, leading=15,
                               spaceAfter=4, alignment=4),
    }
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=22 * mm, rightMargin=18 * mm,
                            topMargin=20 * mm, bottomMargin=20 * mm, title=title,
                            subject="SYNTHETIC document generated by make_synthetic_docs.py",
                            invariant=1)
    story = []
    for kind, text in blocks:
        story.append(Paragraph(escape(text), styles[kind]))
    story.append(Spacer(1, 4 * mm))
    doc.build(story)


def write_docx(blocks: list[tuple[str, str]], path: Path) -> None:
    d = docx.Document()
    d.core_properties.title = blocks[1][1]
    d.core_properties.subject = "SYNTHETIC document generated by make_synthetic_docs.py"
    for kind, text in blocks:
        if kind == "title":
            d.add_heading(text, level=1)
        elif kind == "heading":
            d.add_heading(text, level=2)
        else:
            d.add_paragraph(text)
    d.save(str(path))


def degrade(img: Image.Image, rng: random.Random) -> Image.Image:
    """Simulate a mediocre office scan: slight skew, blur, sensor noise, JPEG artifacts."""
    img = img.rotate(rng.uniform(-0.8, 0.8), resample=Image.BICUBIC, fillcolor=255,
                     expand=False)
    img = img.filter(ImageFilter.GaussianBlur(radius=rng.uniform(0.3, 0.8)))
    noise = Image.effect_noise(img.size, rng.uniform(15, 30))
    img = Image.blend(img, noise, alpha=0.08)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=rng.randint(45, 70))
    return Image.open(io.BytesIO(buf.getvalue())).convert("L")


def write_scan(clean_pdf: Path, path: Path, rng: random.Random, dpi: int = 200) -> list[str]:
    """Rasterize ``clean_pdf`` into an image-only PDF. Returns clean text per page."""
    truth = []
    out = pymupdf.open()
    with pymupdf.open(clean_pdf) as src:
        for page in src:
            truth.append("\n\n".join(b.text for b in _text_blocks(page)))
            pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)
            img = degrade(Image.frombytes("L", (pix.width, pix.height), pix.samples), rng)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
            new = out.new_page(width=page.rect.width, height=page.rect.height)
            new.insert_image(new.rect, stream=buf.getvalue())
    out.set_metadata({"subject": "SYNTHETIC simulated scan generated by make_synthetic_docs.py"})
    out.save(path, garbage=3, deflate=True, no_new_id=True)
    return truth


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=Path("data/synthetic"))
    ap.add_argument("--per-combo", type=int, default=4,
                    help="documents per (language, contract type)")
    ap.add_argument("--seed", type=int, default=13)
    args = ap.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "_truth").mkdir(exist_ok=True)
    tmp_dir = args.out / "_tmp"
    tmp_dir.mkdir(exist_ok=True)
    manifest = []
    counter = 0
    for lang in LANGS:
        for template in T.TEMPLATES:
            for n in range(args.per_combo):
                rng = random.Random(f"{args.seed}-{lang}-{template}-{n}")
                fmt = FORMATS[counter % len(FORMATS)]
                counter += 1
                doc_id = f"syn-{lang.lower()}-{template.replace('_', '-')}-{n:03d}"
                blocks = build_blocks(template, lang, rng)
                if fmt == "docx":
                    fname = f"{doc_id}.docx"
                    write_docx(blocks, args.out / fname)
                else:
                    fname = f"{doc_id}.pdf"
                    clean = (tmp_dir if fmt == "scan" else args.out) / fname
                    write_pdf(blocks, clean, title=blocks[1][1])
                    if fmt == "scan":
                        truth = write_scan(clean, args.out / fname, rng)
                        (args.out / "_truth" / f"{doc_id}.json").write_text(
                            json.dumps({"doc_id": doc_id, "language": lang, "pages": truth},
                                       ensure_ascii=False, indent=1), encoding="utf-8")
                        clean.unlink()
                manifest.append({
                    "file": fname, "doc_id": doc_id, "group_id": doc_id, "synthetic": True,
                    "source": DATASET_ID, "language": lang, "format": fmt,
                    "template": template,
                    "transliterated": lang == "uz-Cyrl",
                })
    tmp_dir.rmdir()
    with (args.out / "manifest.jsonl").open("w", encoding="utf-8") as f:
        for row in manifest:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"wrote {len(manifest)} SYNTHETIC documents to {args.out}")


if __name__ == "__main__":
    main()
