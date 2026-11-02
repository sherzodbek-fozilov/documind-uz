"""Tests for the lex.uz HTML parser on a HANDWRITTEN sample.

The sample only imitates the page structure (class names, nesting, element ids); all
text is invented for this test. No lex.uz content is copied here.
"""

from documind.ingestion.chunking import chunk_document
from documind.ingestion.lexuz_html import is_lexuz_html, parse_lexuz_html

WIDGETS = ('<div class="lx_elem2"><div class="lx_elem3"><span>Button A</span>'
           '<span>Button B</span></div></div>')


def elem(kind: str, eid: str, inner: str) -> str:
    return (f'<div class="{kind} lx_elem" onmousemove="lx_mo(event,{eid})">{WIDGETS}'
            f'<div name="{eid}" id="{eid}">{inner}</div></div>')


def note(text: str) -> str:
    return f'<div class="COMMENT lx_no_select"><div>{text}</div></div>'


SAMPLE = f"""<!DOCTYPE html><html lang="ru-UZ"><head><title>01.02.2003. Namuna kodeksi</title>
<script>var x = "<div class='ACT_TEXT lx_elem'>not text</div>";</script>
<style>.ACT_TEXT {{ color: red; }}</style></head><body>
<div class="dropdown-menu lx_date_ddm">
  <div class="dropdown-menu__item lx_date_selected">05.06.2026</div>
  <div class="dropdown-menu__item lx_date_link">01.01.2025</div>
</div>
{elem("ACT_TITLE", "-10", "NAMUNA KODEKSI")}
{elem("BY_DEFAULT", "-11", "")}
{elem("TEXT_HEADER_DEFAULT", "-12", "BIRINCHI QISM")}
{elem("TEXT_HEADER_DEFAULT", "-13", "1-bob. Umumiy qoidalar")}
{elem("CLAUSE_DEFAULT", "-14", "1-modda. Kodeksning maqsadi")}
{elem("ACT_TEXT", "-15", "Ushbu kodeks <b>namuna</b> uchun <a href='/x'>yozilgan</a>.")}
{note("(1-modda 2020-yil tahririda — eski tahrirga qarang)")}
{elem("ACT_TEXT", "-16", "Birinchi qator<br/>ikkinchi qator.")}
<div class="INDEXES_ON_REF lx_no_select" style="display:none"><div>[indeks matni]</div></div>
{elem("TEXT_HEADER_DEFAULT", "-17", "2-bob. Maxsus qoidalar")}
{elem("CLAUSE_DEFAULT", "-18", "2-modda. Taraflar")}
{elem("ACT_TEXT", "-19", "Taraflar shartnomani yozma shaklda tuzadi.")}
<div class="CHANGES_ORIGINS lx_no_select"><div>Oʻzgartirish manbalari</div></div>
</body></html>"""


def test_parse_structure_kinds_anchors_and_skipped_notes(tmp_path):
    path = tmp_path / "act.html"
    path.write_text(SAMPLE, encoding="utf-8")
    assert is_lexuz_html(path)
    doc = parse_lexuz_html(path)
    blocks = doc.pages[0].blocks
    assert [(b.kind, b.anchor, b.text) for b in blocks] == [
        ("heading", "-10", "NAMUNA KODEKSI"),
        ("heading", "-12", "BIRINCHI QISM"),
        ("heading", "-13", "1-bob. Umumiy qoidalar"),
        ("heading", "-14", "1-modda. Kodeksning maqsadi"),
        ("text", "-15", "Ushbu kodeks namuna uchun yozilgan."),
        ("text", "-16", "Birinchi qator ikkinchi qator."),
        ("heading", "-17", "2-bob. Maxsus qoidalar"),
        ("heading", "-18", "2-modda. Taraflar"),
        ("text", "-19", "Taraflar shartnomani yozma shaklda tuzadi."),
    ]
    joined = " ".join(b.text for b in blocks)
    for skipped in ("Button", "tahrir", "indeks", "manbalari", "not text", "color"):
        assert skipped not in joined
    assert doc.meta["title"] == "01.02.2003. Namuna kodeksi"
    assert doc.meta["edition"] == "05.06.2026"
    assert doc.mime == "text/html" and len(doc.pages) == 1


def test_chunks_follow_articles_and_chapters(tmp_path):
    path = tmp_path / "act.html"
    path.write_text(SAMPLE, encoding="utf-8")
    text, spans, chunks = chunk_document(parse_lexuz_html(path), max_words=180)
    assert len(chunks) == 2
    assert chunks[0].section_title.endswith("1-modda. Kodeksning maqsadi")
    assert chunks[0].chapter == 1 and chunks[1].chapter == 2
    assert chunks[1].text.startswith("2-bob. Maxsus qoidalar")
    # block anchors are kept for citation links
    assert [b["anchor"] for b in spans[0].blocks][:3] == ["-10", "-12", "-13"]


def test_not_a_lexuz_page(tmp_path):
    path = tmp_path / "other.html"
    path.write_text("<html><body><p>Hello</p></body></html>", encoding="utf-8")
    assert not is_lexuz_html(path)
