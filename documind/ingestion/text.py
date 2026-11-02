"""Text normalization and script / language detection for uz-Latn, uz-Cyrl and ru."""

from __future__ import annotations

import re
import unicodedata

# Uzbek Latin uses U+02BB (ʻ) in oʻ/gʻ and U+02BC (ʼ) for the tutuq belgisi.
# In practice documents and OCR output use ' ` ‘ ’ ʼ ʻ interchangeably.
OKINA = "ʻ"  # ʻ
TUTUQ = "ʼ"  # ʼ
_APOSTROPHES = "'`‘’ʻʼ´"
_LATIN = "A-Za-z"
_OG_RE = re.compile(rf"(?<=[oOgG])[{_APOSTROPHES}](?=[{_LATIN}])")
_TUTUQ_RE = re.compile(rf"(?<=[{_LATIN}])(?<![oOgG])[{_APOSTROPHES}](?=[{_LATIN}])")
_SPACES_RE = re.compile(r"[ \t  -   　]+")
_ZERO_WIDTH_RE = re.compile("[­​‌‍﻿]")

UZ_CYRL_LETTERS = set("ўқғҳЎҚҒҲ")
RU_ONLY_LETTERS = set("ыщЫЩ")
# frequent function words; they survive OCR even when ў қ ғ ҳ are misread as у к г х
UZ_CYRL_WORDS = {"ва", "учун", "билан", "ушбу", "бу", "эса", "ҳам", "хам", "бўйича", "буйича",
                 "ёки", "тарафлар", "сўм", "сум"}
RU_WORDS = {"и", "в", "на", "не", "что", "по", "с", "от", "для", "или", "при", "из", "к",
            "сторон", "стороны", "сумов"}
# a word not followed by "." (so initials like "С. Хаёлов" are not read as the word "с")
_CYR_WORD_RE = re.compile(r"\b[\u0400-\u04ff]+\b(?!\.)")


def normalize_apostrophes(text: str) -> str:
    """Map apostrophe variants inside Latin words to ʻ (after o/g) or ʼ. Length-preserving."""
    text = _OG_RE.sub(OKINA, text)
    return _TUTUQ_RE.sub(TUTUQ, text)


# Latin letters that look like Cyrillic ones (same glyph in common fonts), one to one.
_LATIN_LOOKALIKES = "aceopxykACEOPXYKBHMT"
_CYRILLIC_EQUIVALENTS = "асеорхукАСЕОРХУКВНМТ"
_LAT2CYR = str.maketrans(_LATIN_LOOKALIKES, _CYRILLIC_EQUIVALENTS)
_LOOKALIKE_SET = frozenset(_LATIN_LOOKALIKES)
_WORD_RE = re.compile(r"[^\W\d_]+")


def _is_cyrillic(ch: str) -> bool:
    return "\u0400" <= ch <= "\u04ff"


def _is_latin(ch: str) -> bool:
    return "a" <= ch.lower() <= "z"


def fix_cyrillic_homoglyphs(text: str) -> str:
    """Replace Latin look-alike letters with Cyrillic ones inside mixed-script words.

    Only words that contain at least one Cyrillic letter are touched, and only when every
    Latin letter in the word has a Cyrillic look-alike (e.g. "пеpвой" with a Latin "p"
    becomes "первой"). Purely Latin words ("Ijarachi", company names) and words with other
    Latin letters (e.g. "Тexno", which has an "n") are left as they are. One character is
    replaced by one character, so lengths and offsets do not change.
    """
    def fix(m: re.Match) -> str:
        w = m.group(0)
        latin = [c for c in w if _is_latin(c)]
        if not latin or not any(_is_cyrillic(c) for c in w):
            return w
        if not all(c in _LOOKALIKE_SET for c in latin):
            return w
        return w.translate(_LAT2CYR)

    return _WORD_RE.sub(fix, text)


def normalize_block(text: str) -> str:
    """Normalize one paragraph: NFC, no zero-width chars, single spaces, no line breaks,
    Latin look-alikes inside Cyrillic words fixed, Uzbek apostrophes unified."""
    text = unicodedata.normalize("NFC", text)
    text = _ZERO_WIDTH_RE.sub("", text)
    text = text.replace("\r", "\n")
    text = " ".join(line.strip() for line in text.split("\n") if line.strip())
    text = _SPACES_RE.sub(" ", text).strip()
    text = fix_cyrillic_homoglyphs(text)
    return normalize_apostrophes(text)


def script_counts(text: str) -> dict[str, int]:
    latin = cyrillic = uz_cyrl = ru_only = 0
    words = [w.lower() for w in _CYR_WORD_RE.findall(text)]
    uz_words = sum(w in UZ_CYRL_WORDS for w in words)
    ru_words = sum(w in RU_WORDS for w in words)
    for ch in text:
        if ch.isalpha():
            if "a" <= ch.lower() <= "z":
                latin += 1
            elif "Ѐ" <= ch <= "ӿ":
                cyrillic += 1
                if ch in UZ_CYRL_LETTERS:
                    uz_cyrl += 1
                elif ch in RU_ONLY_LETTERS:
                    ru_only += 1
    return {"latin": latin, "cyrillic": cyrillic, "uz_cyrl": uz_cyrl, "ru_only": ru_only,
            "uz_cyrl_words": uz_words, "ru_words": ru_words}


def detect_language(text: str) -> str:
    """Return "uz-Latn", "uz-Cyrl", "ru" or "unknown".

    Heuristic: the majority script decides Latin vs Cyrillic. For Cyrillic, the letters
    ў қ ғ ҳ only occur in Uzbek, while ы and щ are frequent in Russian and (almost) absent
    in Uzbek. Because OCR often misreads ў қ ғ ҳ as у к г х, frequent function words
    (ва, учун, билан ... vs и, в, на ...) are counted too, with a higher weight.
    Latin text is assumed to be Uzbek; English is not a target language.
    """
    c = script_counts(text)
    if c["latin"] + c["cyrillic"] < 3:
        return "unknown"
    if c["latin"] > c["cyrillic"]:
        return "uz-Latn"
    uz = 2 * c["uz_cyrl"] + 3 * c["uz_cyrl_words"]  # ў қ ғ ҳ never occur in Russian
    ru = c["ru_only"] + 3 * c["ru_words"]
    return "uz-Cyrl" if uz > ru else "ru"


def word_count(text: str) -> int:
    return len(text.split())
