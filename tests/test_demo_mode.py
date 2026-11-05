"""Public demo mode (DOCUMIND_PUBLIC_DEMO=true) on a HANDWRITTEN DOCX: uploads are
refused before the body is read, there is no user corpus, and the main database is
opened read-only."""

import io
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from documind.api.app import create_app
from documind.ingestion.pipeline import ingest_file
from documind.storage import models
from documind.storage.db import make_engine, make_session_factory

DOC = ["NAMUNA SHARTNOMASI", "1-modda. Ijara haqi",
       "Ijara haqi har oyning oʻninchi kunigacha toʻlanadi."]


def docx_bytes(paragraphs: list[str]) -> bytes:
    import docx

    d = docx.Document()
    for p in paragraphs:
        d.add_paragraph(p)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


@pytest.fixture
def demo(settings, tmp_path):
    path = tmp_path / "doc.docx"
    path.write_bytes(docx_bytes(DOC))
    with make_session_factory(settings.database_url)() as s:
        ingest_file(path, s, settings, doc_id="real-1", source="handwritten")
    demo_settings = settings.model_copy(update={"public_demo": True})
    return TestClient(create_app(demo_settings)), demo_settings


def test_health_reports_demo(demo):
    client, _ = demo
    body = client.get("/health").json()
    assert body["public_demo"] is True
    assert body["documents"] == 1 and body["user_documents"] == 0


def test_ask_works_on_read_only_corpus(demo):
    client, _ = demo
    r = client.post("/ask", json={"question": "Ijara haqi qachon toʻlanadi?"})
    assert r.status_code == 200
    assert r.json()["passages"][0]["document_id"] == "real-1"


def test_upload_is_refused_and_nothing_is_stored(demo):
    client, settings = demo
    r = client.post("/documents/upload",
                    files={"file": ("a.docx", docx_bytes(DOC), "application/octet-stream")})
    assert r.status_code == 403
    assert "disabled" in r.json()["detail"]
    assert not settings.user_storage_dir.exists()
    assert not os.path.exists(settings.user_database_url.removeprefix("sqlite:///"))


def test_user_corpus_does_not_exist(demo):
    client, _ = demo
    r = client.post("/ask", json={"question": "Ijara haqi", "corpus": "user"})
    assert r.status_code == 503


def test_read_only_sqlite_refuses_writes(demo):
    _, settings = demo
    with make_session_factory(settings.database_url, read_only=True)() as s:
        assert s.query(models.Document).count() == 1
        with pytest.raises(OperationalError, match="readonly"):
            s.execute(text("DELETE FROM chunks"))
            s.commit()


def test_read_only_sqlite_needs_a_file():
    with pytest.raises(ValueError):
        make_engine("sqlite://", read_only=True)


def test_demo_does_not_create_tables(tmp_path, settings):
    """A read-only start never creates the schema: it must exist already."""
    empty = tmp_path / "empty.sqlite"
    engine = make_engine(f"sqlite:///{empty}")
    with engine.connect():  # creates the file, no tables
        pass
    engine.dispose()
    s = settings.model_copy(update={"public_demo": True,
                                    "database_url": f"sqlite:///{empty}"})
    client = TestClient(create_app(s))
    with pytest.raises(OperationalError):
        client.get("/health")


@pytest.mark.postgres
@pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not set")
def test_read_only_postgres_refuses_writes():
    url = os.environ["TEST_DATABASE_URL"]
    make_session_factory(url)  # tables exist
    with make_session_factory(url, read_only=True)() as s:
        assert s.execute(text("SHOW default_transaction_read_only")).scalar() == "on"
        with pytest.raises(Exception, match="read-only transaction"):
            s.execute(text("DELETE FROM chunks"))
