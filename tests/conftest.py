from pathlib import Path

import pytest

from documind.config import Settings
from documind.ingestion.ocr import tesseract_available

FONT = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
HAS_OCR = tesseract_available("uzb+uzb_cyrl+rus")

requires_ocr = pytest.mark.skipif(not HAS_OCR, reason="tesseract with uzb/uzb_cyrl/rus missing")
requires_font = pytest.mark.skipif(not FONT.exists(), reason="DejaVuSans font missing")


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(_env_file=None, database_url=f"sqlite:///{tmp_path / 'test.sqlite'}",
                    storage_dir=tmp_path / "store", splits_file=tmp_path / "splits.json",
                    chunk_max_words=60)


UZ_LATN = ["IJARA SHARTNOMASI",
           "1-modda. Shartnoma predmeti",
           "1.1. Ijaraga beruvchi Ijarachiga umumiy maydoni 60 kvadrat metr boʻlgan noturar "
           "joyni vaqtincha foydalanish uchun beradi.",
           "2-modda. Ijara haqi",
           "2.1. Oylik ijara haqi 5 000 000 soʻmni tashkil etadi."]
RU = ["ДОГОВОР АРЕНДЫ",
      "Статья 1. Предмет договора",
      "1.1. Арендодатель передаёт Арендатору нежилое помещение площадью 60 квадратных метров.",
      "Статья 2. Арендная плата",
      "2.1. Ежемесячная арендная плата составляет 5 000 000 сумов."]


def make_text_pdf(path: Path, pages: list[list[str]], fontsize: float = 12) -> Path:
    import pymupdf

    doc = pymupdf.open()
    for paragraphs in pages:
        page = doc.new_page()
        y = 72
        for par in paragraphs:
            rect = pymupdf.Rect(72, y, page.rect.width - 72, y + 80)
            page.insert_textbox(rect, par, fontsize=fontsize, fontname="dejavu",
                                fontfile=str(FONT))
            y += 80
    doc.save(path)
    return path


def make_scanned_pdf(path: Path, text_pdf: Path, dpi: int = 200) -> Path:
    """Rasterize a text PDF into an image-only PDF (no text layer)."""
    import pymupdf

    out = pymupdf.open()
    with pymupdf.open(text_pdf) as src:
        for page in src:
            pix = page.get_pixmap(dpi=dpi)
            new = out.new_page(width=page.rect.width, height=page.rect.height)
            new.insert_image(new.rect, pixmap=pix)
    out.save(path)
    return path
