import docx
import pytest
from conftest import RU, UZ_LATN, make_scanned_pdf, make_text_pdf, requires_font, requires_ocr

from documind.ingestion.docx_parser import parse_docx
from documind.ingestion.pdf import parse_pdf


@requires_font
def test_text_pdf_blocks(tmp_path):
    pdf = make_text_pdf(tmp_path / "a.pdf", [UZ_LATN[:3], RU[:3]])
    doc = parse_pdf(pdf, ocr_langs="uzb", ocr_enabled=False)
    assert len(doc.pages) == 2 and not any(p.is_ocr for p in doc.pages)
    assert [b.text for b in doc.pages[0].blocks] == UZ_LATN[:3]
    assert doc.pages[1].blocks[1].text == "Статья 1. Предмет договора"
    assert all(b.bbox is not None for b in doc.pages[0].blocks)


@requires_font
def test_scanned_page_flagged_when_ocr_disabled(tmp_path):
    scan = make_scanned_pdf(tmp_path / "s.pdf", make_text_pdf(tmp_path / "a.pdf", [UZ_LATN]))
    doc = parse_pdf(scan, ocr_langs="uzb", ocr_enabled=False)
    assert doc.pages[0].blocks == [] and "looks scanned" in doc.warnings[0]


@requires_font
@requires_ocr
def test_scanned_pdf_is_ocrd(tmp_path):
    scan = make_scanned_pdf(tmp_path / "s.pdf",
                            make_text_pdf(tmp_path / "a.pdf", [UZ_LATN, RU], fontsize=13),
                            dpi=200)
    doc = parse_pdf(scan, ocr_langs="uzb+uzb_cyrl+rus", ocr_dpi=300)
    assert all(p.is_ocr and p.ocr_confidence > 60 for p in doc.pages)
    page1 = " ".join(b.text for b in doc.pages[0].blocks)
    page2 = " ".join(b.text for b in doc.pages[1].blocks)
    assert "1-modda. Shartnoma predmeti" in page1
    assert "boʻlgan" in page1  # apostrophe variant from OCR normalized to U+02BB
    assert "Статья 2. Арендная плата" in page2
    # bboxes are converted back to PDF points (inside an A4-ish page)
    x0, y0, x1, y1 = doc.pages[0].blocks[0].bbox
    assert 0 <= x0 < x1 <= doc.pages[0].width and 0 <= y0 < y1 <= doc.pages[0].height


def test_docx_paragraphs_headings_tables(tmp_path):
    d = docx.Document()
    d.add_heading("IJARA SHARTNOMASI", level=1)
    d.add_paragraph("1.1. Ijaraga beruvchi joyni beradi.")
    d.add_paragraph("   ")
    table = d.add_table(rows=2, cols=2)
    table.cell(0, 0).text, table.cell(0, 1).text = "Taraf", "Manzil"
    table.cell(1, 0).text, table.cell(1, 1).text = "«Namuna» MChJ", "Toshkent"
    d.add_paragraph("Imzolar")
    path = tmp_path / "c.docx"
    d.save(path)
    doc = parse_docx(path)
    blocks = doc.pages[0].blocks
    assert [(b.kind, b.text) for b in blocks] == [
        ("heading", "IJARA SHARTNOMASI"),
        ("text", "1.1. Ijaraga beruvchi joyni beradi."),
        ("table", "Taraf | Manzil"),
        ("table", "«Namuna» MChJ | Toshkent"),
        ("text", "Imzolar"),
    ]


def test_unsupported_type(tmp_path, settings):
    from documind.ingestion.pipeline import parse_file

    (tmp_path / "x.txt").write_text("hi")
    with pytest.raises(ValueError, match="unsupported"):
        parse_file(tmp_path / "x.txt", settings)
