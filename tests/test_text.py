import pytest

from documind.ingestion.text import OKINA, TUTUQ, detect_language, normalize_block
from documind.translit import latin_to_cyrillic


@pytest.mark.parametrize("variant", ["'", "`", "‘", "’", "ʼ", "ʻ"])
def test_okina_variants_are_unified(variant):
    assert normalize_block(f"o{variant}zbek g{variant}alaba") == f"o{OKINA}zbek g{OKINA}alaba"


def test_tutuq_and_length_preserving_apostrophes():
    assert normalize_block("ma'lumot san’at") == f"ma{TUTUQ}lumot san{TUTUQ}at"
    # quotes around words are not touched
    assert normalize_block("'shartnoma'") == "'shartnoma'"


def test_whitespace_and_line_breaks():
    assert normalize_block("  Ijara\nshartnomasi \t 1­2 ") == "Ijara shartnomasi 12"


@pytest.mark.parametrize("text,lang", [
    ("Ushbu shartnoma taraflar oʻrtasida tuzildi", "uz-Latn"),
    ("Ушбу шартнома тарафлар ўртасида тузилди ва қуйидагилар", "uz-Cyrl"),
    ("Настоящий договор заключён между сторонами, которые обязуются", "ru"),
    ("12.05.2024", "unknown"),
    # OCR lost ў/қ (у/к): function words still identify Uzbek
    ("Етказиб берувчи Харидорга офис стулларини 50 дона микдорида етказиб беради, "
     "Харидор эса уни кабул килади ва хакини тулайди", "uz-Cyrl"),
    # initials are not the Russian preposition "с"
    ("«Оқ Тош Савдо» МЧЖ: манзил Фарғона, Намуна кўчаси, 5-уй. Директор С. Хаёлов. "
     "Директор С. Хаёлов. К. Намунов", "uz-Cyrl"),
    ("Директор С. Иванов подписал договор с поставщиком и передал его в отдел", "ru"),
])
def test_detect_language(text, lang):
    assert detect_language(text) == lang


def test_transliteration():
    assert latin_to_cyrillic("Oʻzbekiston Respublikasi") == "Ўзбекистон Республикаси"
    assert latin_to_cyrillic("SHARTNOMA, gʻalaba, maʼlumot, yer, ega") == \
        "ШАРТНОМА, ғалаба, маълумот, ер, эга"
    assert detect_language(latin_to_cyrillic("Toʻlov qoʻshimcha haq")) == "uz-Cyrl"
