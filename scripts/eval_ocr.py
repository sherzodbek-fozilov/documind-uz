"""Measure OCR character error rate (CER) on the SYNTHETIC simulated scans.

For every scanned document in data/synthetic/manifest.jsonl, each page is OCR'd and
compared with the clean text of the page it was rendered from (data/synthetic/_truth/).
Both sides go through the same normalization (NFC, apostrophes) and whitespace is
collapsed, so paragraph segmentation does not count as an error.

CER = total edit distance / total ground-truth characters (micro-average over pages).

Two configurations are measured:
  * "multi":  one combined model for every page (``DOCUMIND_OCR_LANGS``, default
              uzb+uzb_cyrl+rus); this is what ingestion uses, since the language of an
              uploaded scan is not known in advance.
  * "oracle": the single model of the page's true language (uzb / uzb_cyrl / rus); an
              upper bound for "detect the language first, then OCR".

Caveat: the scans are synthetic renders with mild degradation, so these numbers are an
optimistic lower bound on real-world CER. Writes results/ocr_synthetic.json.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import pymupdf
from rapidfuzz.distance import Levenshtein

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common import ROOT, write_result  # noqa: E402

from documind.config import get_settings  # noqa: E402
from documind.ingestion.ocr import ocr_image  # noqa: E402
from documind.ingestion.pdf import render_page  # noqa: E402
from documind.ingestion.text import normalize_block  # noqa: E402

ORACLE = {"uz-Latn": "uzb", "uz-Cyrl": "uzb_cyrl", "ru": "rus"}
KEY = {"uz-Latn": "uz_latn", "uz-Cyrl": "uz_cyrl", "ru": "ru"}


def flat(text: str) -> str:
    return re.sub(r"\s+", " ", normalize_block(text)).strip()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data", type=Path, default=ROOT / "data/synthetic")
    ap.add_argument("--configs", default="multi,oracle")
    args = ap.parse_args()
    settings = get_settings()
    import pytesseract

    manifest = [json.loads(line) for line in (args.data / "manifest.jsonl").read_text(
        encoding="utf-8").splitlines() if line.strip()]
    scans = [m for m in manifest if m["format"] == "scan"]
    if not scans:
        raise SystemExit("no scanned documents in manifest; run make_synthetic_docs.py")

    configs = args.configs.split(",")
    # config -> language -> [edits, truth_chars, pages, conf_sum, conf_n]
    agg: dict[str, dict[str, list[float]]] = {c: defaultdict(lambda: [0, 0, 0, 0.0, 0])
                                              for c in configs}
    for m in scans:
        truth = json.loads((args.data / "_truth" / f"{m['doc_id']}.json").read_text("utf-8"))
        with pymupdf.open(args.data / m["file"]) as doc:
            for page, gt in zip(doc, truth["pages"], strict=True):
                image = render_page(page, settings.ocr_dpi)
                gt_flat = flat(gt)
                for config in configs:
                    langs = settings.ocr_langs if config == "multi" else ORACLE[m["language"]]
                    blocks, conf = ocr_image(image, langs)
                    hyp = flat(" ".join(b.text for b in blocks))
                    a = agg[config][m["language"]]
                    a[0] += Levenshtein.distance(hyp, gt_flat)
                    a[1] += len(gt_flat)
                    a[2] += 1
                    if conf is not None:
                        a[3] += conf
                        a[4] += 1
        print(f"done {m['doc_id']}", file=sys.stderr)

    def summary(per_lang: dict[str, list[float]]) -> dict:
        out = {}
        for lang, (edits, chars, pages, conf_sum, conf_n) in sorted(per_lang.items()):
            out[lang] = {"cer": edits / chars if chars else None, "pages": pages,
                         "chars": chars, "mean_word_confidence": conf_sum / conf_n
                         if conf_n else None}
        tot_e = sum(v[0] for v in per_lang.values())
        tot_c = sum(v[1] for v in per_lang.values())
        out["all"] = {"cer": tot_e / tot_c if tot_c else None,
                      "pages": sum(v[2] for v in per_lang.values()), "chars": tot_c}
        return out

    by_config = {c: summary(agg[c]) for c in configs}
    main_cfg = by_config.get("multi") or by_config[configs[0]]
    metrics = {f"cer_{KEY[lang]}": main_cfg[lang]["cer"] for lang in ORACLE if lang in main_cfg}
    metrics["cer_all"] = main_cfg["all"]["cer"]
    payload = {
        "metrics": metrics,
        "n": main_cfg["all"]["pages"],
        "dataset": "synthetic-contracts-v1 simulated scans (SYNTHETIC, mild degradation)",
        "unit": "pages",
        "config": {"multi_langs": settings.ocr_langs, "dpi": settings.ocr_dpi,
                   "tesseract": str(pytesseract.get_tesseract_version()),
                   "metric": "micro CER over whitespace-collapsed page text"},
        "by_config": by_config,
    }
    path = write_result("ocr_synthetic.json", payload, "scripts/eval_ocr.py")
    print(json.dumps(payload["metrics"], indent=2))
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
