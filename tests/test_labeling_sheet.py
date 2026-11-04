import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("labeling_sheet", ROOT / "scripts/labeling_sheet.py")
ls = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ls)


def _chunk(cid, act, lang, ch, art, words=40):
    title = f"{art}-modda. X" if lang == "uz-Latn" else f"Статья {art}. X"
    return {"id": cid, "doc": cid.split("#")[0], "act": act, "language": lang, "chapter": ch,
            "article": art, "title": title, "words": words, "text": "t"}


def test_article_of():
    assert ls.article_of("29-bob. Oldi-sotdi / 386-modda. Oldi-sotdi shartnomasi") == 386
    assert ls.article_of("Глава 29 / Статья 386. Договор") == 386
    assert ls.article_of("29-bob. Oldi-sotdi") is None


def test_allocate_sums_and_covers_every_chapter():
    alloc = ls.allocate({1: 100, 2: 10, 3: 1}, 10)
    assert sum(alloc.values()) == 10 and min(alloc.values()) >= 1 and alloc[1] > alloc[2]


def test_plan_excludes_short_and_listed_articles_and_avoids_translation_pairs(monkeypatch):
    monkeypatch.setattr(ls, "PER_ACT", {"civil-code-part2": 4})
    chunks = []
    for art in range(880, 892):
        for lang, doc in (("uz-Latn", "civil-code-part2-uz"), ("ru", "civil-code-part2-ru")):
            chunks.append(_chunk(f"{doc}#c{art}", "civil-code-part2", lang, 51, art))
    chunks.append(_chunk("civil-code-part2-uz#short", "civil-code-part2", "uz-Latn", 51, 999, 5))
    ids = ls.make_plan(chunks, seed=1)
    by_id = {c["id"]: c for c in chunks}
    assert len(ids) == 8
    assert all(by_id[i]["article"] != 888 and by_id[i]["words"] >= ls.MIN_WORDS for i in ids)
    uz_articles = {by_id[i]["article"] for i in ids if by_id[i]["language"] == "uz-Latn"}
    ru_articles = {by_id[i]["article"] for i in ids if by_id[i]["language"] == "ru"}
    assert not uz_articles & ru_articles
    assert [by_id[i]["language"] for i in ids[:2]] == ["uz-Latn", "ru"]  # interleaved


def test_parse_answers_keeps_wording_and_validates():
    by_id = {"a#c1": _chunk("a#c1", "x", "ru", 1, 1), "a#c2": _chunk("a#c2", "x", "ru", 1, 2)}
    lines = ["a#c1 | ru |  Какой срок?  ", "`a#c1`, a#c2 | ru | Кто платит?",
             "zz#c9 | ru | Нет такого?", "a#c1 | en | Q?", "a#c1 | ru | Какой срок?", "broken"]
    rows, problems = ls.parse_answers(lines, by_id, set())
    assert rows[0] == {"question": "Какой срок?", "language": "ru", "gold_doc": "a",
                       "gold_chunk": "a#c1", "scope": "corpus", "status": "reviewed"}
    assert rows[1]["gold_chunks"] == ["a#c1", "a#c2"] and rows[1]["gold_chunk"] == "a#c1"
    assert len(rows) == 2 and len(problems) == 4


def test_parse_answers_optional_tags_column():
    by_id = {"a#c1": _chunk("a#c1", "x", "ru", 1, 1)}
    lines = ["a#c1 | uz-Latn | Ijtimoiy tatildan bosh tortsam boʻladimi? "
             "| colloquial, no-apostrophe",
             "a#c1 | ru | Без тегов?",
             "a#c1 | ru | Пустые теги? |  , "]
    rows, problems = ls.parse_answers(lines, by_id, set())
    assert problems == []
    # wording and apostrophes are stored exactly; tags keep their spelling
    assert rows[0]["question"] == "Ijtimoiy tatildan bosh tortsam boʻladimi?"
    assert rows[0]["tags"] == ["colloquial", "no-apostrophe"]
    assert "tags" not in rows[1] and "tags" not in rows[2]
