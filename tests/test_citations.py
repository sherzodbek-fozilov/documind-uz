"""Unit tests for the citation check, extractive quote selection and the LLM hooks.
All texts are handwritten for these tests."""

from documind.qa.citations import Citation, check_citation, locate_quote, summarize
from documind.qa.passages import (
    Segment,
    chunk_segments,
    select_quote,
    sentence_spans,
    source_link,
)
from documind.retrieval.analyzers import get_analyzer

CHUNK = ("3-modda. Ijara haqi\n\nIjara haqi har oyning 10-kunigacha toʻlanadi. "
         "Kechiktirilgan har bir kun uchun 0,1 foiz penya hisoblanadi.\n\n"
         "1.1. Ijarachi binoni saqlaydi.")


def cite(quote: str, start: int | None = None, doc: str = "d1") -> Citation:
    start = CHUNK.find(quote) if start is None else start
    return Citation(doc, "d1#c0000", quote, start, start + len(quote))


def test_check_citation_accepts_only_exact_spans():
    ok = cite("Ijara haqi har oyning 10-kunigacha toʻlanadi.")
    assert check_citation(ok, CHUNK, "d1") is None
    # the same quote with right text but wrong offsets
    assert check_citation(cite(ok.quote, start=ok.start + 1), CHUNK, "d1") == \
        "quote is not the chunk text at its offsets"
    # one changed letter (apostrophe variant) is not the same text
    changed = Citation("d1", "d1#c0000", ok.quote.replace("ʻ", "'"), ok.start, ok.end)
    assert check_citation(changed, CHUNK, "d1") is not None
    assert check_citation(ok, CHUNK, "d2") == "chunk is not in the cited document"
    assert check_citation(ok, None, None) == "unknown chunk"
    assert check_citation(cite("", start=0), CHUNK, "d1") == "empty quote"
    assert check_citation(cite("x", start=len(CHUNK)), CHUNK, "d1") == "offsets outside the chunk"


def test_locate_quote_is_exact_after_stripping_quote_marks():
    assert locate_quote("«Ijarachi binoni saqlaydi.»", CHUNK) == (
        CHUNK.find("Ijarachi"), len(CHUNK))
    assert locate_quote("  Ijara haqi  ", CHUNK) == (0 + CHUNK.find("Ijara haqi"),
                                                     CHUNK.find("Ijara haqi") + 10)
    # paraphrase, and a quote stitched from two sentences, are not found
    assert locate_quote("Ijara haqi har oy toʻlanadi.", CHUNK) is None
    assert locate_quote("toʻlanadi. Ijarachi binoni", CHUNK) is None
    assert locate_quote("«»", CHUNK) is None


def test_summarize():
    r = summarize([None, "empty quote", None, "empty quote"])
    assert (r.checked, r.valid, r.correctness) == (4, 2, 0.5)
    assert r.as_dict()["failures"] == {"empty quote": 2}
    assert summarize([]).correctness is None


def test_sentence_spans_keep_clause_numbers_and_trim():
    start = CHUNK.find("Ijara haqi har")
    end = CHUNK.find("\n\n1.1.")
    spans = sentence_spans(CHUNK, start, end)
    assert [CHUNK[s:e] for s, e in spans] == [
        "Ijara haqi har oyning 10-kunigacha toʻlanadi.",
        "Kechiktirilgan har bir kun uchun 0,1 foiz penya hisoblanadi."]
    s = CHUNK.find("1.1.")
    assert [CHUNK[a:b] for a, b in sentence_spans(CHUNK, s, len(CHUNK))] == [
        "1.1. Ijarachi binoni saqlaydi."]


SEGMENTS = [Segment(0, 19, "heading", "-1"),
            Segment(21, CHUNK.find("\n\n1.1."), "text", "-2"),
            Segment(CHUNK.find("1.1."), len(CHUNK), "text", "-3")]
ANALYZE = get_analyzer("fold+stem6")
IDF = {t: 1.0 for t in ANALYZE(CHUNK)} | {"penya": 3.0, "binoni": 2.0}


def test_select_quote_picks_the_matching_sentence_and_its_anchor():
    s, e, anchor = select_quote(CHUNK, SEGMENTS, "penya qancha?", ANALYZE, IDF)
    assert CHUNK[s:e] == "Kechiktirilgan har bir kun uchun 0,1 foiz penya hisoblanadi."
    assert anchor == "-2"
    s, e, anchor = select_quote(CHUNK, SEGMENTS, "binoni kim saqlaydi", ANALYZE, IDF)
    assert (CHUNK[s:e], anchor) == ("1.1. Ijarachi binoni saqlaydi.", "-3")


def test_select_quote_joins_sentences_only_when_that_adds_terms():
    s, e, _ = select_quote(CHUNK, SEGMENTS, "toʻlanadi penya", ANALYZE, IDF)
    assert CHUNK[s:e].startswith("Ijara haqi har") and CHUNK[s:e].endswith("hisoblanadi.")
    s, e, _ = select_quote(CHUNK, SEGMENTS, "toʻlanadi penya", ANALYZE, IDF, max_sentences=1)
    assert CHUNK[s:e].startswith("Kechiktirilgan")
    # a window never crosses a block: "penya" + "binoni" are in different blocks
    s, e, _ = select_quote(CHUNK, SEGMENTS, "penya binoni", ANALYZE, IDF)
    assert "\n\n" not in CHUNK[s:e]


def test_select_quote_skips_headings_and_falls_back_to_first_sentence():
    s, e, anchor = select_quote(CHUNK, SEGMENTS, "Ijara haqi", ANALYZE, IDF)
    assert anchor == "-2"  # the heading also matches, but headings are not quoted
    s, e, anchor = select_quote(CHUNK, SEGMENTS, "арендная плата", ANALYZE, IDF)
    assert (CHUNK[s:e], anchor) == ("Ijara haqi har oyning 10-kunigacha toʻlanadi.", "-2")


def test_chunk_segments_clip_blocks_to_the_chunk():
    pages = [(100, [{"start": 0, "end": 10, "kind": "heading", "anchor": "a"},
                    {"start": 12, "end": 40, "kind": "text", "anchor": "b"},
                    {"start": 42, "end": 60, "kind": "text"}])]
    assert chunk_segments(112, 130, pages) == [Segment(0, 18, "text", "b")]
    assert chunk_segments(105, 150, pages)[0] == Segment(0, 5, "heading", "a")
    assert chunk_segments(0, 50, []) == [Segment(0, 50)]


def test_source_link():
    assert source_link("https://lex.uz/ru/docs/6257291", "6264702") == \
        "https://lex.uz/ru/docs/6257291#6264702"
    assert source_link("https://lex.uz/ru/docs/-180552", "-1813") == \
        "https://lex.uz/ru/docs/-180552#-1813"
    assert source_link("https://lex.uz/ru/docs/1", None) == "https://lex.uz/ru/docs/1"
    assert source_link("https://example.org/a.pdf", "x") == "https://example.org/a.pdf"
    assert source_link("synthetic-contracts-v1", "x") is None
    assert source_link(None, None) is None
