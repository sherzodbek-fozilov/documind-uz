"""OCR with tesseract. Groups recognized words into paragraphs with bounding boxes."""

from __future__ import annotations

import shutil
from collections import defaultdict

from PIL import Image

from .text import normalize_block
from .types import Block


class OCRUnavailableError(RuntimeError):
    pass


def tesseract_available(langs: str = "uzb+uzb_cyrl+rus") -> bool:
    if shutil.which("tesseract") is None:
        return False
    import pytesseract

    try:
        installed = set(pytesseract.get_languages(config=""))
    except Exception:
        return False
    return all(lang in installed for lang in langs.split("+"))


def ocr_image(image: Image.Image, langs: str, scale: float = 1.0,
              psm: int = 3) -> tuple[list[Block], float | None]:
    """OCR one page image.

    ``scale`` converts pixel coordinates to output units (e.g. 72 / dpi for PDF points).
    Returns paragraph blocks and the mean word confidence (0..100), or None if no words.
    """
    if shutil.which("tesseract") is None:
        raise OCRUnavailableError("tesseract binary not found; install tesseract-ocr")
    import pytesseract

    data = pytesseract.image_to_data(
        image, lang=langs, config=f"--psm {psm}", output_type=pytesseract.Output.DICT
    )
    # (block, paragraph) -> line -> words, preserving tesseract's reading order
    paragraphs: dict[tuple[int, int], dict[int, list[int]]] = defaultdict(lambda: defaultdict(list))
    confidences: list[float] = []
    for i, word in enumerate(data["text"]):
        if not word or not word.strip():
            continue
        conf = float(data["conf"][i])
        if conf >= 0:
            confidences.append(conf)
        key = (data["block_num"][i], data["par_num"][i])
        paragraphs[key][data["line_num"][i]].append(i)

    blocks: list[Block] = []
    for lines in paragraphs.values():
        idxs = [i for line in lines.values() for i in line]
        text = normalize_block("\n".join(
            " ".join(data["text"][i] for i in line) for line in lines.values()))
        if not text:
            continue
        x0 = min(data["left"][i] for i in idxs)
        y0 = min(data["top"][i] for i in idxs)
        x1 = max(data["left"][i] + data["width"][i] for i in idxs)
        y1 = max(data["top"][i] + data["height"][i] for i in idxs)
        blocks.append(Block(text=text, bbox=(x0 * scale, y0 * scale, x1 * scale, y1 * scale)))
    mean_conf = sum(confidences) / len(confidences) if confidences else None
    return blocks, mean_conf
