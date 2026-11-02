"""compare_versions on HANDWRITTEN lex.uz-like samples (invented text, no lex.uz content)."""

import importlib.util
from pathlib import Path

from test_lexuz_html import elem

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("compare_versions",
                                              ROOT / "scripts/compare_versions.py")
cv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cv)


def _page(parts: list[tuple[str, str]]) -> str:
    body = "".join(elem(kind, str(i), text) for i, (kind, text) in enumerate(parts, start=1))
    return f"<html><head><title>t</title></head><body>{body}</body></html>"


def test_compare_finds_paragraph_number_and_missing_differences(tmp_path):
    uz = [("TEXT_HEADER_DEFAULT", "1-bob. Bob"),
          ("CLAUSE_DEFAULT", "1-modda. Birinchi"), ("ACT_TEXT", "Muddat 10 kun."),
          ("CLAUSE_DEFAULT", "2-modda. Ikkinchi"), ("ACT_TEXT", "Bir."), ("ACT_TEXT", "Ikki."),
          ("CLAUSE_DEFAULT", "3-modda. Uchinchi"), ("ACT_TEXT", "Foiz 0,5 va 3-modda."),
          ("CLAUSE_DEFAULT", "4-modda. Faqat oʻzbekcha"), ("ACT_TEXT", "Matn.")]
    ru = [("TEXT_HEADER_DEFAULT", "Глава 1. Глава"),
          ("CLAUSE_DEFAULT", "Статья 1. Первая"), ("ACT_TEXT", "Срок 10 дней."),
          ("CLAUSE_DEFAULT", "Статья 2. Вторая"), ("ACT_TEXT", "Один и два."),
          ("CLAUSE_DEFAULT", "Статья 3. Третья"), ("ACT_TEXT", "Процент 0.5 и статья 4.")]
    (tmp_path / "uz.html").write_text(_page(uz), encoding="utf-8")
    (tmp_path / "ru.html").write_text(_page(ru), encoding="utf-8")
    a, _ = cv.article_signatures(tmp_path / "uz.html")
    b, _ = cv.article_signatures(tmp_path / "ru.html")
    assert a[1] == (1, ("10",)) and b[1] == (1, ("10",))  # same: not reported
    diffs = cv.compare(a, b)
    assert diffs == [(2, "paragraphs", "2 vs 1"), (3, "numbers", "3 vs 4"),
                     (4, "missing", "only in first")]
    table = cv.render({"edition": "x"}, {"edition": "y"}, "uz-Latn", "ru", diffs, 4, 3)
    assert "**3 articles differ**" in table and "| 3 | numbers | 3 vs 4 |" in table
