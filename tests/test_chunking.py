import pytest

from documind.ingestion.chunking import chunk_document, is_heading
from documind.ingestion.types import Block, ParsedDocument, ParsedPage


@pytest.mark.parametrize("text", ["5-modda. Ijara muddati", "12 - модда", "Статья 7. Цена",
                                  "II bob. Umumiy qoidalar", "Глава IV", "1. SHARTNOMA PREDMETI",
                                  "РЕКВИЗИТЫ СТОРОН"])
def test_headings(text):
    assert is_heading(text)


@pytest.mark.parametrize("text", ["1.1. Ijarachi joydan foydalanadi.",
                                  "Oylik ijara haqi 5 000 000 soʻm.",
                                  "1. Ijarachi joydan maqsadiga muvofiq foydalanishi shart.",
                                  "OOO"])
def test_not_headings(text):
    assert not is_heading(text)


def _doc(pages):
    return ParsedDocument("t.pdf", "application/pdf",
                          [ParsedPage(i + 1, [Block(t) for t in p]) for i, p in enumerate(pages)])


def test_offsets_sections_and_pages():
    long_clause = "1.2. " + " ".join(f"soʻz{i}." for i in range(70))
    doc = _doc([["IJARA SHARTNOMASI", "1-modda. Predmet", "1.1. Qisqa band.", long_clause],
                ["1.3. Davomi.", "2-modda. Narx", "2.1. Narx 100 soʻm."]])
    text, spans, chunks = chunk_document(doc, max_words=30)
    # every chunk is an exact span of the document text
    for c in chunks:
        assert text[c.char_start:c.char_end] == c.text
        assert c.n_words <= 30 + 5  # headings may push slightly over the limit
    # chunk ids are contiguous and ordered
    assert [c.idx for c in chunks] == list(range(len(chunks)))
    assert all(a.char_end <= b.char_start for a, b in zip(chunks, chunks[1:], strict=False))
    # no chunk mixes text from two sections
    art2 = [c for c in chunks if "2.1." in c.text]
    assert len(art2) == 1 and "1.3." not in art2[0].text
    assert art2[0].section_title == "2-modda. Narx" and art2[0].page_start == 2
    # the heading group is attached to the first body text, not emitted alone
    assert chunks[0].text.startswith("IJARA SHARTNOMASI") and "1.1." in chunks[0].text
    assert chunks[0].section_title == "IJARA SHARTNOMASI / 1-modda. Predmet"
    # page spans point at the right text
    assert text[spans[1].char_start:].startswith("1.3. Davomi.")
    blk = spans[1].blocks[0]
    page_text = text[spans[1].char_start:spans[1].char_end]
    assert page_text[blk["start"]:blk["end"]] == "1.3. Davomi."


def test_chunk_spanning_pages():
    doc = _doc([["1-modda. Predmet", "1.1. Birinchi sahifa."], ["1.2. Ikkinchi sahifa."]])
    _, _, chunks = chunk_document(doc, max_words=100)
    assert len(chunks) == 1
    assert (chunks[0].page_start, chunks[0].page_end) == (1, 2)


def test_empty_pages_and_document():
    _, spans, chunks = chunk_document(_doc([[], ["1.1. Matn."], []]), max_words=50)
    assert [s.page_no for s in spans] == [1, 2, 3] and len(chunks) == 1
    assert chunks[0].page_start == 2
    assert chunk_document(_doc([[]]), max_words=50)[2] == []


def test_short_preamble_joins_first_section():
    doc = _doc([["SINTETIK NAMUNA. Hammasi oʻylab topilgan.", "IJARA SHARTNOMASI",
                 "Toshkent shahri, shartnoma tuzildi.", "1-modda. Predmet", "1.1. Band."]])
    _, _, chunks = chunk_document(doc, max_words=8)
    assert chunks[0].text.startswith("SINTETIK NAMUNA") and "Toshkent" in chunks[0].text
    assert chunks[0].section_title == "IJARA SHARTNOMASI"
    assert not any(c.text.rstrip().endswith("SHARTNOMASI") for c in chunks)
