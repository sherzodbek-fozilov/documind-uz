"""Unit tests for the citation check, extractive quote selection and the LLM hooks.
All texts are handwritten for these tests."""

from documind.qa.citations import Citation, check_citation, locate_quote, summarize

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
