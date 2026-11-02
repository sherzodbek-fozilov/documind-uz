"""Tokenizers ("analyzers") for BM25.

plain:  NFC, lowercase, apostrophes removed (oʻ / o' / o` all become "o"), split on
        anything that is not a letter or digit.
fold:   plain, then Cyrillic is mapped to Latin with Uzbek-aware rules and letters that
        OCR confuses are merged (қ/к → k, ҳ/х → h, ғ/г → g, ў → o). A uz-Latn query can then
        match a uz-Cyrl passage, and "микдор" (OCR) matches "миқдор". Russian goes through
        the same map, which is harmless because queries and passages are mapped alike.
+stem:  any analyzer can add "prefix stemming": tokens are cut to their first N
        characters. A crude but common baseline for agglutinative Uzbek
        (shartnoma / shartnomaning / shartnomasi) and inflected Russian.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable

_TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)
_APOSTROPHES = re.compile("['`‘’ʻʼ´]")

_CYR2LAT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "ғ": "g", "д": "d", "е": "e", "ё": "yo",
    "ж": "j", "з": "z", "и": "i", "й": "y", "к": "k", "қ": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "ў": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ҳ": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sh", "ъ": "",
    "ы": "i", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}
# Latin side of the same merges, so both scripts land on one form
_LAT_FOLD = str.maketrans({"q": "k", "x": "h"})


def _plain_tokens(text: str) -> list[str]:
    text = unicodedata.normalize("NFC", text).lower()
    text = _APOSTROPHES.sub("", text)
    return _TOKEN_RE.findall(text)


def _fold_token(tok: str) -> str:
    if any("Ѐ" <= c <= "ӿ" for c in tok):
        tok = "".join(_CYR2LAT.get(c, c) for c in tok)
    return tok.translate(_LAT_FOLD)


def get_analyzer(name: str) -> Callable[[str], list[str]]:
    """name: "plain" | "fold", optionally with "+stemN" (e.g. "fold+stem6")."""
    base, _, stem = name.partition("+")
    if base not in ("plain", "fold"):
        raise ValueError(f"unknown analyzer {name!r}")
    n = int(stem.removeprefix("stem")) if stem else 0
    if stem and not stem.startswith("stem"):
        raise ValueError(f"unknown analyzer option {stem!r}")

    def analyze(text: str) -> list[str]:
        toks = _plain_tokens(text)
        if base == "fold":
            toks = [_fold_token(t) for t in toks]
        if n:
            toks = [t[:n] for t in toks]
        return [t for t in toks if t]

    return analyze
