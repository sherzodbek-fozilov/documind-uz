"""POST /documents/upload on HANDWRITTEN samples (DOCX, text PDF, PNG made in the tests).

The main database holds one handwritten "real" document, so the tests can check that
uploads stay in the separate user corpus.
"""

import io
import re
import zipfile

import pytest
from conftest import FONT, UZ_LATN, make_text_pdf, requires_font, requires_ocr
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont

from documind.api.app import create_app
from documind.ingestion.docx_parser import DOCX_MIME
from documind.ingestion.pipeline import ingest_file
from documind.qa.service import QAService
from documind.retrieval.corpus import load_corpus
from documind.storage import models
from documind.storage.db import make_session_factory

UPLOAD = "/documents/upload"


def docx_bytes(paragraphs: list[str]) -> bytes:
    import docx

    d = docx.Document()
    for p in paragraphs:
        d.add_paragraph(p)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


SALE = ["OLDI-SOTDI SHARTNOMASI", "1-modda. Predmet",
        "Sotuvchi xaridorga ikki tonna paxta tolasini topshiradi.",
        "2-modda. Toʻlov", "Xaridor narxni yetkazib berilgandan keyin besh kun ichida toʻlaydi."]
REAL = ["NAMUNA QONUNI", "1-modda. Maqsad", "Ushbu qonun sinov uchun yozilgan."]


@pytest.fixture
def client(settings, tmp_path):
    main = tmp_path / "real.docx"
    main.write_bytes(docx_bytes(REAL))
    with make_session_factory(settings.database_url)() as s:
        ingest_file(main, s, settings, doc_id="real-1", source="handwritten")
    return TestClient(create_app(settings))


def upload(client, name, data, ctype):
    return client.post(UPLOAD, files={"file": (name, data, ctype)})


def main_state(settings):
    with make_session_factory(settings.database_url)() as s:
        return (s.query(models.Document).count(), s.query(models.Chunk).count(),
                sorted(c.doc_id for c in load_corpus(s, "real")))


def test_upload_docx_goes_to_the_user_corpus_only(client, settings):
    before = main_state(settings)
    assert client.post("/ask", json={"question": "paxta", "corpus": "user"}).status_code == 503
    r = upload(client, "Oldi-sotdi shartnomasi.docx", docx_bytes(SALE), DOCX_MIME)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "ingested" and body["corpus"] == "user"
    assert body["document_id"].startswith("user-") and body["n_chunks"] >= 1
    assert body["filename"] == "Oldi-sotdi shartnomasi.docx" and body["n_ocr_pages"] == 0

    docs = client.get("/documents?corpus=user").json()
    assert [(d["id"], d["filename"]) for d in docs] == [
        (body["document_id"], "Oldi-sotdi shartnomasi.docx")]
    assert client.get("/health").json()["user_documents"] == 1

    ans = client.post("/ask", json={"question": "Xaridor narxni qachon toʻlaydi?",
                                    "corpus": "user"}).json()
    top = ans["passages"][0]
    assert top["document_id"] == body["document_id"] and top["link"] is None
    assert top["quote"] == ("Xaridor narxni yetkazib berilgandan keyin besh kun ichida "
                            "toʻlaydi.")
    # isolation: the main database and the real corpus are unchanged
    assert main_state(settings) == before
    real = client.post("/ask", json={"question": "paxta tolasi toʻlov", "top_k": 5}).json()
    assert {p["document_id"] for p in real["passages"]} <= {"real-1"}
    assert client.post("/ask", json={"question": "paxta", "document_id": body["document_id"]}
                       ).status_code == 404  # not in the real corpus
    scoped = client.post("/ask", json={"question": "paxta", "corpus": "user",
                                       "document_id": body["document_id"]})
    assert scoped.status_code == 200
    # the stored copy is named by its hash, inside the user store only
    stored = list(settings.user_storage_dir.iterdir())
    assert len(stored) == 1 and re.fullmatch(r"[0-9a-f]{64}\.docx", stored[0].name)
    assert len(list(settings.storage_dir.iterdir())) == 1  # only the main document


def test_duplicate_upload_and_index_refresh(client):
    first = upload(client, "a.docx", docx_bytes(SALE), DOCX_MIME).json()
    again = upload(client, "renamed.docx", docx_bytes(SALE), DOCX_MIME)
    assert again.status_code == 200
    assert again.json() | {"status": "ingested"} == first
    # a second, different upload is searchable right away (the user index is rebuilt)
    other = ["IJARA SHARTNOMASI", "1-modda. Ijara haqi", "Ijarachi har oy oʻn million soʻm "
             "ijara haqi toʻlaydi."]
    new = upload(client, "ijara.docx", docx_bytes(other), DOCX_MIME).json()
    ans = client.post("/ask", json={"question": "ijara haqi", "corpus": "user"}).json()
    assert ans["passages"][0]["document_id"] == new["document_id"]


def test_path_traversal_in_the_file_name_is_harmless(client, settings, tmp_path):
    for i, name in enumerate(["../../evil.docx", "..\\..\\evil.docx", "/etc/evil.docx"]):
        r = upload(client, name, docx_bytes(SALE + [f"Ilova {i}."]), DOCX_MIME)
        assert r.status_code == 201 and r.json()["filename"] == "evil.docx"
    assert not (tmp_path.parent / "evil.docx").exists()
    assert not (tmp_path / "evil.docx").exists()
    assert all(re.fullmatch(r"[0-9a-f]{64}\.docx", p.name)
               for p in settings.user_storage_dir.iterdir())


def test_rejections_have_clear_messages(client, settings):
    cases = [
        (("tool.exe", b"MZ\x90\x00", "application/octet-stream"), 415, "not accepted"),
        (("page.html", b"<html></html>", "text/html"), 415, "not accepted"),
        (("x.pdf", b"%PDF-1.7", "application/octet-stream"), 415, "does not match"),
        (("x.pdf", docx_bytes(SALE), "application/pdf"), 415, "signature"),
        (("x.docx", b"", DOCX_MIME), 422, "empty"),
        (("x.pdf", b"%PDF-1.7\ngarbage", "application/pdf"), 422, "cannot be opened"),
    ]
    for (name, data, ctype), status, text in cases:
        r = upload(client, name, data, ctype)
        assert r.status_code == status and text in r.json()["detail"], (name, r.text)
    assert client.post(UPLOAD).status_code == 422  # no file field
    # a DOCX with the right parts but broken XML fails in the parser -> 422, not 500
    broken = io.BytesIO()
    with zipfile.ZipFile(broken, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", "<not xml")
    r = upload(client, "broken.docx", broken.getvalue(), DOCX_MIME)
    assert r.status_code == 422 and "could not be read" in r.json()["detail"]
    # no text at all: rejected and not kept
    r = upload(client, "empty.docx", docx_bytes(["", "   "]), DOCX_MIME)
    assert r.status_code == 422 and "no text" in r.json()["detail"]
    assert client.get("/health").json()["user_documents"] == 0
    assert not settings.user_storage_dir.exists() or not any(settings.user_storage_dir.iterdir())


def test_size_limit(settings, tmp_path):
    small = settings.model_copy(update={"upload_max_bytes": 2000})
    client = TestClient(create_app(small))
    # ~36 kB: over the 2000-byte file limit, but under limit + multipart overhead,
    # so the endpoint (not the middleware) rejects it
    r = upload(client, "a.docx", docx_bytes(SALE), DOCX_MIME)
    assert r.status_code == 413 and "larger than the limit" in r.json()["detail"]
    # body far over the limit: stopped by the middleware while it is received
    r = upload(client, "a.docx", b"PK\x03\x04" + b"\0" * 200_000, DOCX_MIME)
    assert r.status_code == 413 and r.json()["detail"].startswith("request body is larger")

    def chunks():  # no Content-Length: counted as it arrives
        for _ in range(100):
            yield b"\0" * 1000

    r = client.post(UPLOAD, content=chunks(),
                    headers={"content-type": "multipart/form-data; boundary=x"})
    assert r.request.headers.get("transfer-encoding") == "chunked"
    assert r.status_code == 413 and r.json()["detail"].startswith("request body is larger")


def png(text: str, font=None) -> bytes:
    img = Image.new("L", (1400, 300), 255)
    ImageDraw.Draw(img).text((40, 100), text, fill=0, font=font)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def test_truncated_image_is_a_clear_error(client):
    data = png("x")
    r = upload(client, "scan.png", data[:-40], "image/png")
    assert r.status_code == 422, r.text


def test_ocr_unavailable_is_503_and_nothing_is_stored(client, settings, monkeypatch):
    import documind.ingestion.ocr as ocr

    monkeypatch.setattr(ocr.shutil, "which", lambda _: None)
    r = upload(client, "scan.png", png("IJARA SHARTNOMASI"), "image/png")
    assert r.status_code == 503 and "OCR" in r.json()["detail"]
    assert client.get("/health").json()["user_documents"] == 0


def test_uploads_not_configured(settings, tmp_path):
    service = QAService(make_session_factory(settings.database_url), settings)
    client = TestClient(create_app(settings, service))
    assert upload(client, "a.docx", docx_bytes(SALE), DOCX_MIME).status_code == 503


@requires_font
def test_upload_text_pdf(client, tmp_path):
    pdf = make_text_pdf(tmp_path / "ijara.pdf", [UZ_LATN])
    r = upload(client, "ijara.pdf", pdf.read_bytes(), "application/pdf")
    assert r.status_code == 201, r.text
    assert r.json()["n_pages"] == 1 and r.json()["n_ocr_pages"] == 0
    ans = client.post("/ask", json={"question": "Oylik ijara haqi qancha?",
                                    "corpus": "user"}).json()
    assert "5 000 000" in ans["passages"][0]["quote"]


@requires_ocr
@requires_font
def test_upload_scanned_png_is_ocrd(client):
    font = ImageFont.truetype(str(FONT), 64)
    r = upload(client, "scan.png", png("IJARA SHARTNOMASI", font), "image/png")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["n_ocr_pages"] == 1 and body["n_chunks"] >= 1
    ans = client.post("/ask", json={"question": "ijara shartnomasi", "corpus": "user"}).json()
    assert "SHARTNOMA" in ans["passages"][0]["quote"].upper()


def test_docx_external_entities_are_not_resolved(client, tmp_path):
    """XXE: an entity pointing at a local file must not pull that file into the text."""
    secret = tmp_path / "secret.txt"
    secret.write_text("MAXFIY-MATN-12345", encoding="utf-8")
    src = zipfile.ZipFile(io.BytesIO(docx_bytes(["PLACEHOLDER"])))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        for info in src.infolist():
            data = src.read(info)
            if info.filename == "word/document.xml":
                xml = data.decode()
                decl, body = xml.split("?>", 1)
                xml = (decl + f'?><!DOCTYPE d [<!ENTITY xxe SYSTEM "file://{secret}">]>'
                       + body.replace("PLACEHOLDER", "Ilova &xxe; matni"))
                data = xml.encode()
            z.writestr(info, data)
    r = upload(client, "xxe.docx", out.getvalue(), DOCX_MIME)
    assert r.status_code == 201, r.text  # stored, with the entity left unresolved
    ans = client.post("/ask", json={"question": "Ilova matni", "corpus": "user"}).json()
    assert ans["passages"] and all("MAXFIY" not in p["quote"] for p in ans["passages"])
