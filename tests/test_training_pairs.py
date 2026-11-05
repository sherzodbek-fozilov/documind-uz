"""Training-pair generation on a small handwritten corpus (no lex.uz text)."""

import json
import random

from documind.retrieval.corpus import CorpusChunk
from documind.training.pairs import (
    add_typos,
    article_title,
    build_pairs,
    check_pairs,
    drop_diacritics,
    first_sentence,
    holdout_groups,
    noisy_variants,
    pair_stats,
    strip_apostrophes,
    versions_correspond,
)

# (article number, chapter, uz title, uz body, ru title, ru body); handwritten
ARTICLES = [
    (1, 1, "Ijara shartnomasi",
     "Ijara shartnomasi boʻyicha ijaraga beruvchi mol-mulkni haq evaziga vaqtincha "
     "foydalanishga beradi. Shartnoma yozma shaklda tuziladi.",
     "Договор аренды",
     "По договору аренды арендодатель предоставляет имущество за плату во временное "
     "пользование. Договор заключается в письменной форме."),
    (2, 1, "Ijara haqi",
     "Ijara haqi har oyda 10 kundan kechiktirmay toʻlanadi va shartnomada belgilanadi.",
     "Арендная плата",
     "Арендная плата вносится ежемесячно не позднее 10 дней и определяется договором."),
    (3, 2, "Ijara muddati",
     "Ijara muddati shartnomada koʻrsatilmagan boʻlsa, shartnoma nomuayyan muddatga "
     "tuzilgan hisoblanadi.",
     "Срок аренды",
     "Если срок аренды в договоре не определен, договор считается заключенным на "
     "неопределенный срок."),
    (4, 2, "Ijarachining majburiyatlari",
     "Ijarachi mol-mulkni soz holatda saqlashi va joriy taʼmirlashni oʻz hisobidan "
     "amalga oshirishi shart.",
     "Обязанности арендатора",
     "Арендатор обязан поддерживать имущество в исправном состоянии и производить за свой "
     "счет текущий ремонт."),
    (5, 3, "Pudrat shartnomasi",
     "Pudrat shartnomasi boʻyicha pudratchi buyurtmachining topshirigʻiga binoan muayyan "
     "ishni bajarish majburiyatini oladi.",
     "Договор подряда",
     "По договору подряда подрядчик обязуется выполнить по заданию заказчика определенную "
     "работу."),
    (6, 3, "Ishning sifati",
     "Pudratchi bajargan ishning sifati shartnoma shartlariga muvofiq boʻlishi kerak va "
     "kafolat muddati 2 yil.",
     "Качество работы",
     "Качество выполненной подрядчиком работы должно соответствовать условиям договора, "
     "гарантийный срок 3 года."),  # numbers differ on purpose: versions do not correspond
    (7, 4, "Shartnomani bekor qilish",
     "Taraflar shartnomani oʻzaro kelishuv asosida istalgan vaqtda bekor qilishlari "
     "mumkin.",
     "Расторжение договора",
     "Стороны вправе в любое время расторгнуть договор по взаимному соглашению."),
    (8, 4, "Nizolarni hal qilish",
     "Taraflar oʻrtasidagi nizolar muzokaralar yoʻli bilan, kelishuvga erishilmasa sud "
     "tartibida hal qilinadi.",
     "Разрешение споров",
     "Споры между сторонами разрешаются путем переговоров, а при недостижении согласия в "
     "судебном порядке."),
]
SPLITS = {"act/ch1": "train", "act/ch2": "train", "act/ch3": "train", "act/ch4": "test"}


def make_corpus() -> list[CorpusChunk]:
    chunks = []
    for lang, doc in (("uz-Latn", "act-uz"), ("ru", "act-ru")):
        for i, (n, ch, uz_t, uz_b, ru_t, ru_b) in enumerate(ARTICLES):
            head = f"{n}-modda. {uz_t}" if lang == "uz-Latn" else f"Статья {n}. {ru_t}"
            body = uz_b if lang == "uz-Latn" else ru_b
            group = f"act/ch{ch}"
            chunks.append(CorpusChunk(f"{doc}#c{i:04d}", doc, SPLITS[group], lang,
                                      f"{head}\n\n{body}", head, "test-v1", "act", group))
    return chunks


def test_article_title_and_first_sentence():
    assert article_title("2-§. Umumiy qoidalar / 85-modda. Jamoa kelishuvlari") == \
        "Jamoa kelishuvlari"
    assert article_title("Глава 3 / Статья 12. Цена договора") == "Цена договора"
    assert article_title("Глава 3. Общие положения") is None
    text = ("Статья 1. Договор аренды\n\n1) По договору аренды арендодатель предоставляет "
            "имущество за плату. Договор заключается в письменной форме.")
    assert first_sentence(text) == ("По договору аренды арендодатель предоставляет имущество "
                                    "за плату.")
    assert first_sentence("Статья 9. Исключена\n\nИсключена.") is None


def test_noise_is_on_queries_and_deterministic():
    q = "Ijarachining majburiyatlari qanday boʻladi"
    assert strip_apostrophes("oʻz gʻaznaga taʼtil") == "oz gaznaga tatil"
    assert drop_diacritics("Ҳудудий қоидалар ўзгарди ғалаба", "uz-Cyrl") == \
        "Худудий коидалар узгарди галаба"
    assert drop_diacritics("Объём удержаний", "ru") == "Объем удержании"
    a = add_typos(q, random.Random("x"))
    assert a == add_typos(q, random.Random("x")) and a != q
    assert abs(len(a) - len(q)) <= 2
    kinds = {n: (lang, t) for n, lang, t in noisy_variants(q, "uz-Latn", random.Random(1))}
    assert set(kinds) == {"typos", "no_apostrophes", "cyrillic", "cyrillic_no_diacritics"}
    assert kinds["cyrillic"] == ("uz-Cyrl", "Ижарачининг мажбуриятлари қандай бўлади")
    assert kinds["cyrillic_no_diacritics"][1] == "Ижарачининг мажбуриятлари кандай булади"
    ru = {n for n, _, _ in noisy_variants("Срок аренды", "ru", random.Random(1))}
    assert ru == {"typos"}  # nothing to drop in "Срок аренды", so no identical variant


def test_versions_correspond_by_paragraphs_and_numbers():
    assert versions_correspond("A\n\nсрок 10 дней", "B\n\nmuddat 10 kun")
    assert not versions_correspond("A\n\nсрок 10 дней", "B\n\nmuddat 15 kun")
    assert not versions_correspond("A\n\nB\n\nC", "A\n\nB")


def test_holdout_groups_is_per_act_and_deterministic():
    groups = [f"a/ch{i}" for i in range(20)] + [f"b/ch{i}" for i in range(10)]
    val = holdout_groups(groups, 0.2)
    assert val == holdout_groups(reversed(groups), 0.2)
    assert sum(g.startswith("a/") for g in val) == 4
    assert sum(g.startswith("b/") for g in val) == 2
    assert holdout_groups(["c/ch1"], 0.5) == set()  # a single group is never held out


def test_build_pairs_never_touches_test_and_keeps_twins_together():
    chunks = make_corpus()
    test_ids = {c.id for c in chunks if c.split == "test"}
    pairs = build_pairs(chunks, seed=3, val_fraction=0.34, mixed_fraction=1.0)
    assert check_pairs(pairs, chunks) == []
    rows = pairs.train + pairs.val
    used = {r[k] for r in rows for k in ("positive_id", "negative_id") if k in r}
    used |= {r["id"] for r in pairs.corpus}
    assert not used & test_ids
    test_texts = {c.text for c in chunks if c.split == "test"}
    assert not any(t in r["positive"] or t in r.get("negative", "")
                   for r in rows for t in test_texts)
    # one train group is held out: both language versions of its articles are in val only
    assert len(pairs.val_groups) == 1
    val_articles = {r["article"] for r in pairs.val}
    assert val_articles and not val_articles & {r["article"] for r in pairs.train}
    for art in val_articles:
        assert {r["passage_lang"] for r in pairs.val if r["article"] == art} == {"uz-Latn", "ru"}
    # validation pairs have no negatives; training pairs always have one
    assert all("negative" not in r for r in pairs.val)
    assert all(r["negative"] and r["negative_id"] != r["positive_id"] for r in pairs.train)


def test_build_pairs_query_types_negatives_and_mixed():
    chunks = make_corpus()
    by_id = {c.id: c for c in chunks}
    pairs = build_pairs(chunks, seed=3, val_fraction=0.0, mixed_fraction=1.0)
    rows = pairs.train
    types = {r["query_type"] for r in rows}
    assert types == {"title", "first_sentence", "xling_title", "mixed"}
    # article 6: versions differ (2 vs 3 years) -> no cross-lingual or mixed pairs
    assert pairs.skipped["versions_differ"] == 1
    assert not [r for r in rows if r["article"] == "act/6"
                and r["query_type"] in ("xling_title", "mixed")]
    for r in rows:
        pos, neg = by_id[r["positive_id"]], by_id[r["negative_id"]]
        assert neg.article_key != pos.article_key
        assert r["negative_article"] == f"act/{neg.article_key[1]}" != r["article"]
        assert neg.language == pos.language == r["passage_lang"]
        assert neg.split == "train"
        if r["query_type"] == "xling_title" and r["noise"] == "none":
            assert r["query_lang"] != r["passage_lang"]
    # the clean uz title of article 1 points to the uz passage; the ru one to the ru passage
    clean = {(r["query_type"], r["query_lang"], r["passage_lang"], r["article"]): r
             for r in rows if r["noise"] == "none"}
    assert clean[("title", "uz-Latn", "uz-Latn", "act/1")]["query"] == "Ijara shartnomasi"
    assert clean[("xling_title", "uz-Latn", "ru", "act/1")]["positive"].startswith("Статья 1.")
    assert clean[("xling_title", "ru", "uz-Latn", "act/1")]["positive"].startswith("1-modda.")
    mixed = [r for r in rows if r["query_type"] == "mixed" and r["article"] == "act/1"]
    allowed = {"uz-Latn": {"Договор аренды haqida qonunda nima deyilgan?",
                           "Договор аренды boʻyicha qoida qanday?"},
               "ru": {"что говорится про ijara shartnomasi?",
                      "какие правила по ijara shartnomasi?"}}
    assert len(mixed) == 2 and {r["passage_lang"] for r in mixed} == {"uz-Latn", "ru"}
    assert all(r["query"] in allowed[r["passage_lang"]] for r in mixed)
    assert all(r["noise"] == "none" and r["query_lang"] == "mixed" for r in mixed)
    # noisy rows copy the passage of their clean parent unchanged
    for r in rows:
        if r["noise"] != "none":
            assert r["positive"] == by_id[r["positive_id"]].index_text


def test_build_pairs_is_reproducible_and_stats_have_no_text():
    chunks = make_corpus()
    a = build_pairs(chunks, seed=5, val_fraction=0.34)
    b = build_pairs(list(reversed(chunks)), seed=5, val_fraction=0.34)
    assert sorted(map(json.dumps, a.train)) == sorted(map(json.dumps, b.train))
    stats = json.dumps(pair_stats(a), ensure_ascii=False)
    for c in chunks:
        for word in c.text.split():
            if len(word) > 6 and word.isalpha():
                assert word not in stats
