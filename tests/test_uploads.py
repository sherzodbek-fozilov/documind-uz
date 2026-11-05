"""Unit tests for the upload checks (documind/ingestion/uploads.py). All files are made
in the tests from handwritten text; nothing comes from a real document."""

import io
import zipfile

import pytest
from PIL import Image

from documind.ingestion.docx_parser import DOCX_MIME
from documind.ingestion.uploads import (
    UploadRejected,
    check_limits,
    check_name_and_type,
    safe_display_name,
    save_limited,
    sniff,
)


def rejected(fn, *args) -> UploadRejected:
    with pytest.raises(UploadRejected) as info:
        fn(*args)
    return info.value


@pytest.mark.parametrize("raw, expected", [
    ("shartnoma.pdf", "shartnoma.pdf"),
    ("../../etc/passwd.pdf", "passwd.pdf"),
    ("..\\..\\Windows\\win.ini.docx", "win.ini.docx"),
    ("/abs/path/ijara.docx", "ijara.docx"),
    ("ij\x00ara\x1b[31m.pdf", "ijara[31m.pdf"),
    ("..", "upload"),
    ("", "upload"),
    (None, "upload"),
    ("Договор аренды.pdf", "Договор аренды.pdf"),
])
def test_safe_display_name(raw, expected):
    assert safe_display_name(raw) == expected


def test_safe_display_name_keeps_the_extension_of_long_names():
    name = safe_display_name("a" * 500 + ".docx")
    assert len(name) == 200 and name.endswith(".docx")


def test_name_and_type_whitelist():
    assert check_name_and_type("A.PDF", "application/pdf") == ".pdf"
    assert check_name_and_type("x.docx", DOCX_MIME) == ".docx"
    assert check_name_and_type("scan.tif", "image/tiff; charset=binary") == ".tif"
    for name, ctype in [("x.exe", "application/pdf"), ("page.html", "text/html"),
                        ("noext", "application/pdf"), ("x.pdf.exe", "application/pdf"),
                        ("x.doc", "application/msword")]:
        assert rejected(check_name_and_type, name, ctype).status == 415
    # extension and declared type must agree; octet-stream is not accepted
    for name, ctype in [("x.pdf", "image/png"), ("x.pdf", "application/octet-stream"),
                        ("x.png", None), ("x.jpg", "image/png")]:
        err = rejected(check_name_and_type, name, ctype)
        assert err.status == 415 and "does not match" in err.message


def test_save_limited(tmp_path):
    data = b"%PDF-" + b"x" * 100
    sha, size = save_limited(io.BytesIO(data).read, tmp_path / "a.pdf", 1000)
    assert size == len(data) and len(sha) == 64 and (tmp_path / "a.pdf").read_bytes() == data
    # over the limit: rejected, and the partial file is removed
    err = rejected(save_limited, io.BytesIO(b"y" * 70_000).read, tmp_path / "b.pdf", 1000)
    assert err.status == 413 and not (tmp_path / "b.pdf").exists()
    assert rejected(save_limited, io.BytesIO(b"").read, tmp_path / "c.pdf", 10).status == 422
    assert not (tmp_path / "c.pdf").exists()
    # never overwrites an existing file
    with pytest.raises(FileExistsError):
        save_limited(io.BytesIO(b"z").read, tmp_path / "a.pdf", 10)


def png_bytes(size=(20, 20)) -> bytes:
    buf = io.BytesIO()
    Image.new("L", size, 255).save(buf, "PNG")
    return buf.getvalue()


def test_sniff_rejects_renamed_files(tmp_path):
    png = tmp_path / "x.png"
    png.write_bytes(png_bytes())
    sniff(png, ".png")
    for suffix in (".pdf", ".jpg", ".docx", ".tif"):
        assert rejected(sniff, png, suffix).status == 415


def test_pdf_limits(tmp_path, settings):
    import pymupdf

    def pdf(name, pages=1, size=(595, 842), **save):
        doc = pymupdf.open()
        for _ in range(pages):
            doc.new_page(width=size[0], height=size[1]).insert_text((72, 72), "Ijara haqi")
        doc.save(tmp_path / name, **save)
        return tmp_path / name

    check_limits(pdf("ok.pdf", pages=2), ".pdf", settings)
    s = settings.model_copy(update={"upload_max_pages": 2})
    assert "3 pages" in rejected(check_limits, pdf("long.pdf", 3), ".pdf", s).message
    # a page whose OCR rendering would be a huge image
    huge = pdf("huge.pdf", size=(14000, 14000))
    assert "too large" in rejected(check_limits, huge, ".pdf", settings).message
    enc = pdf("enc.pdf", encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="u", owner_pw="o")
    assert "encrypted" in rejected(check_limits, enc, ".pdf", settings).message
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"%PDF-1.7\nnot really a pdf")
    assert rejected(check_limits, bad, ".pdf", settings).status == 422


def test_image_limits(tmp_path, settings):
    ok = tmp_path / "ok.png"
    ok.write_bytes(png_bytes())
    check_limits(ok, ".png", settings)
    big = tmp_path / "big.png"
    big.write_bytes(png_bytes((2000, 1000)))
    s = settings.model_copy(update={"upload_max_pixels": 1_000_000})
    assert "too large" in rejected(check_limits, big, ".png", s).message
    tif = tmp_path / "pages.tif"
    frames = [Image.new("L", (10, 10), 255) for _ in range(3)]
    frames[0].save(tif, save_all=True, append_images=frames[1:])
    check_limits(tif, ".tif", settings)
    s = settings.model_copy(update={"upload_max_pages": 2})
    assert "3 pages" in rejected(check_limits, tif, ".tif", s).message
    # a JPEG signature but PNG content is caught by the format check too
    assert rejected(check_limits, ok, ".jpg", settings).status == 415
    # damaged header: rejected here (a damaged body only fails when the parser decodes
    # it; that case is tested through the API)
    broken = tmp_path / "broken.png"
    broken.write_bytes(png_bytes()[:30])
    assert rejected(check_limits, broken, ".png", settings).status == 422


def make_zip(path, members: dict[str, bytes]):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in members.items():
            z.writestr(name, data)
    return path


DOCX_PARTS = {"[Content_Types].xml": b"<Types/>", "word/document.xml": b"<w:document/>"}


def test_docx_limits(tmp_path, settings):
    check_limits(make_zip(tmp_path / "ok.docx", DOCX_PARTS), ".docx", settings)
    # a highly compressible member: small file, large when unpacked
    bomb = make_zip(tmp_path / "bomb.docx", {**DOCX_PARTS, "word/media/x": b"\0" * 3_000_000})
    assert bomb.stat().st_size < 50_000
    s = settings.model_copy(update={"upload_max_unzipped_bytes": 1_000_000})
    assert "unpacked" in rejected(check_limits, bomb, ".docx", s).message
    many = make_zip(tmp_path / "many.docx", {**DOCX_PARTS, **{f"p{i}": b"" for i in range(20)}})
    s = settings.model_copy(update={"upload_max_zip_entries": 10})
    assert "parts" in rejected(check_limits, many, ".docx", s).message
    plain_zip = make_zip(tmp_path / "plain.docx", {"readme.txt": b"hi"})
    assert "not a Word document" in rejected(check_limits, plain_zip, ".docx",
                                             settings).message
    not_zip = tmp_path / "nz.docx"
    not_zip.write_bytes(b"PK\x03\x04garbage")
    assert rejected(check_limits, not_zip, ".docx", settings).status == 422
