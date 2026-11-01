"""Uzbek Latin → Cyrillic transliteration (rule-based, approximate).

Known limits: loanwords are not handled from a dictionary (only the frequent "-tsiya" →
"-ция" pattern), and "ye" / "e" are mapped by position only. Good enough for synthetic
text and for script-insensitive matching; not a substitute for a real Cyrillic source.
"""

from __future__ import annotations

import re

_PAIRS = [
    ("tsiya", "ция"), ("oʻ", "ў"), ("gʻ", "ғ"), ("sh", "ш"), ("ch", "ч"), ("yo", "ё"),
    ("yu", "ю"), ("ya", "я"), ("ye", "е"), ("ʼ", "ъ"),
]
_SINGLE = dict(zip("abdfghijklmnopqrstuvxyz",
                   "абдфгҳижклмнопқрстувхйз", strict=True))
_VOWELS = set("aeiouаеиоуўэёюя")
_TOKEN_RE = re.compile("|".join(re.escape(a) for a, _ in _PAIRS) + r"|[a-z]", re.IGNORECASE)
_MAP = dict(_PAIRS)


def _case(src: str, dst: str) -> str:
    if src.isupper() and (len(src) > 1 or len(dst) == 1):
        return dst.upper()
    if src[0].isupper():
        return dst[0].upper() + dst[1:]
    return dst


def latin_to_cyrillic(text: str) -> str:
    out: list[str] = []
    pos = 0
    for m in _TOKEN_RE.finditer(text):
        out.append(text[pos:m.start()])
        src = m.group(0)
        low = src.lower()
        if low in _MAP:
            dst = _MAP[low]
        elif low == "e":
            prev = text[m.start() - 1].lower() if m.start() > 0 else " "
            dst = "э" if (not prev.isalpha() or prev in _VOWELS) else "е"
        else:
            dst = _SINGLE[low]
        out.append(_case(src, dst))
        pos = m.end()
    out.append(text[pos:])
    return "".join(out)
