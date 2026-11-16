"""Protections for a publicly reachable service, on HANDWRITTEN documents: small request
bodies, validation errors that do not echo the input, and a read-only mode that does not
depend on the operator remembering DOCUMIND_PUBLIC_DEMO."""

import io
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from documind import cli
from documind.api.app import UPLOAD_PATH, create_app
from documind.config import Settings, get_settings, is_loopback
from documind.ingestion.pipeline import ingest_file
from documind.storage.db import make_engine, make_session_factory

DOC = ["NAMUNA SHARTNOMASI", "1-modda. Ijara haqi",
       "Ijara haqi har oyning oʻninchi kunigacha toʻlanadi."]
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def docx_bytes(paragraphs: list[str]) -> bytes:
    import docx

    d = docx.Document()
    for p in paragraphs:
        d.add_paragraph(p)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


@pytest.fixture
def corpus(settings, tmp_path) -> Settings:
    """Settings of a database that holds one real document."""
    path = tmp_path / "doc.docx"
    path.write_bytes(docx_bytes(DOC))
    with make_session_factory(settings.database_url)() as s:
        ingest_file(path, s, settings, doc_id="real-1", source="handwritten")
    return settings


def upload(client: TestClient):
    return client.post(UPLOAD_PATH, files={"file": ("a.docx", docx_bytes(DOC), DOCX_MIME)})


# --- request body size ------------------------------------------------------------------------

def test_ask_refuses_a_large_body_before_parsing_it(corpus):
    client = TestClient(create_app(corpus))
    limit = corpus.api_max_body_bytes
    big = json.dumps({"question": "Ijara haqi", "padding": "a" * (limit + 1)})
    r = client.post("/ask", content=big, headers={"content-type": "application/json"})
    assert r.status_code == 413
    assert r.json()["detail"] == f"request body is larger than the limit of {limit} bytes"

    def chunks():  # no Content-Length: counted as it arrives
        for _ in range(limit // 1000 + 2):
            yield b"a" * 1000

    r = client.post("/ask", content=chunks(), headers={"content-type": "application/json"})
    assert r.request.headers.get("transfer-encoding") == "chunked"
    assert r.status_code == 413

    # the longest valid question, in the script that takes the most bytes per character
    r = client.post("/ask", json={"question": "ў" * 1000})
    assert r.status_code == 200


def test_the_small_limit_covers_every_path_except_upload(corpus):
    client = TestClient(create_app(corpus))
    body = b"a" * (corpus.api_max_body_bytes + 1)
    for method, path in (("POST", "/documents"), ("POST", "/nope"), ("PUT", "/ask"),
                         ("POST", "/documents/real-1/outline")):
        assert client.request(method, path, content=body).status_code == 413, (method, path)
    # private mode: an upload larger than the small limit is still accepted
    assert len(docx_bytes(DOC)) > corpus.api_max_body_bytes
    assert upload(client).status_code == 201


def test_body_limit_is_configurable(corpus):
    small = corpus.model_copy(update={"api_max_body_bytes": 1024})
    client = TestClient(create_app(small))
    # a Cyrillic letter takes two bytes in UTF-8: about 2000 bytes, over this limit
    r = client.post("/ask", json={"question": "ў" * 1000})
    assert r.status_code == 413
    assert client.post("/ask", json={"question": "Ijara haqi"}).status_code == 200
    with pytest.raises(ValueError):
        Settings(_env_file=None, api_max_body_bytes=10)


# --- validation errors ------------------------------------------------------------------------

def test_validation_errors_do_not_echo_the_input(corpus):
    client = TestClient(create_app(corpus))
    marker = "MAXFIY" * 200  # 1200 characters: too long for a question
    r = client.post("/ask", json={"question": marker})
    assert r.status_code == 422
    assert "MAXFIY" not in r.text and len(r.content) < 400
    (err,) = r.json()["detail"]
    assert set(err) == {"type", "loc", "msg"}
    assert err["loc"] == ["body", "question"] and "at most 1000 characters" in err["msg"]

    as_json = {"content-type": "application/json"}
    for kwargs in ({"content": b"{not json MAXFIY", "headers": as_json},
                   {"json": {"question": "x", "top_k": "MAXFIY"}},
                   {"json": {"question": "x", "corpus": "MAXFIY"}},
                   {"content": b'"MAXFIY"', "headers": {"content-type": "text/plain"}}):
        r = client.post("/ask", **kwargs)
        assert r.status_code == 422 and "MAXFIY" not in r.text, kwargs
        assert all(set(e) == {"type", "loc", "msg"} for e in r.json()["detail"])

    r = client.get("/documents/real-1/passages", params={"limit": "MAXFIY"})
    assert r.status_code == 422 and "MAXFIY" not in r.text


# --- exposure: what counts as published beyond this machine -----------------------------------

@pytest.mark.parametrize("host", ["127.0.0.1", "127.8.9.1", "::1", "[::1]", "localhost",
                                  "LOCALHOST", "app.localhost", " 127.0.0.1 "])
def test_loopback_hosts(host):
    assert is_loopback(host)


@pytest.mark.parametrize("host", ["0.0.0.0", "::", "", " ", "10.0.0.5", "192.168.1.10",
                                  "203.0.113.7", "demo.example.org", "localhost.example.org",
                                  "127.0.0.1.example.org", "not an address", "*"])
def test_everything_else_counts_as_exposed(host):
    assert not is_loopback(host)


PRIVATE = [("127.0.0.1", ":80"), ("127.0.0.1", ":8080"), ("::1", ":80"), ("localhost", ":80"),
           ("127.0.0.1", "localhost"), ("127.0.0.1", "http://localhost:8080"),
           ("127.0.0.1", "localhost:80, [::1]:80"), ("127.0.0.1", "")]
EXPOSED = [("0.0.0.0", ":80"),                     # public bind, the flag forgotten
           ("0.0.0.0", "demo.example.org"),        # the documented public setup
           ("127.0.0.1", "demo.example.org"),      # a domain, even behind a loopback bind
           ("127.0.0.1", "https://demo.example.org"),
           ("127.0.0.1", "localhost, demo.example.org"),
           ("127.0.0.1", "203.0.113.7:80"),
           ("::", ":80"), ("", ":80"), ("10.8.0.1", ":80"), ("WEB_BIND", ":80")]


@pytest.mark.parametrize(("bind", "site"), PRIVATE)
def test_private_combinations(bind, site):
    s = Settings(_env_file=None, web_bind=bind, site_address=site)
    assert s.exposure() is None and s.read_only_demo is False
    assert s.model_copy(update={"public_demo": True}).read_only_demo is True


@pytest.mark.parametrize(("bind", "site"), EXPOSED)
def test_exposed_combinations_are_read_only_without_the_flag(bind, site):
    s = Settings(_env_file=None, public_demo=False, web_bind=bind, site_address=site)
    assert s.exposure() is not None and s.read_only_demo is True


def test_defaults_are_private(monkeypatch):
    for name in ("DOCUMIND_WEB_BIND", "DOCUMIND_SITE_ADDRESS", "DOCUMIND_PUBLIC_DEMO"):
        monkeypatch.delenv(name, raising=False)
    s = Settings(_env_file=None)
    assert (s.web_bind, s.site_address, s.read_only_demo) == ("127.0.0.1", ":80", False)


@pytest.mark.parametrize("env", [
    {"DOCUMIND_WEB_BIND": "0.0.0.0"},
    {"DOCUMIND_WEB_BIND": "0.0.0.0", "DOCUMIND_PUBLIC_DEMO": "false"},
    {"DOCUMIND_SITE_ADDRESS": "demo.example.org", "DOCUMIND_PUBLIC_DEMO": "false"},
    {"DOCUMIND_WEB_BIND": "", "DOCUMIND_PUBLIC_DEMO": "false"},
    {"DOCUMIND_PUBLIC_DEMO": "true"},
])
def test_dangerous_environments_are_read_only(monkeypatch, env):
    for name in ("DOCUMIND_WEB_BIND", "DOCUMIND_SITE_ADDRESS", "DOCUMIND_PUBLIC_DEMO"):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    assert Settings(_env_file=None).read_only_demo is True


# --- the API in an exposed configuration ------------------------------------------------------

@pytest.mark.parametrize(("bind", "site"), [("0.0.0.0", ":80"), ("127.0.0.1", "demo.example.org")])
def test_exposed_api_refuses_uploads_even_without_the_demo_flag(corpus, bind, site, caplog):
    exposed = corpus.model_copy(update={"public_demo": False, "web_bind": bind,
                                        "site_address": site})
    with caplog.at_level("WARNING", logger="documind.api"):
        client = TestClient(create_app(exposed))
    assert "DOCUMIND_PUBLIC_DEMO is not set" in caplog.text  # the operator is told why

    assert client.get("/health").json()["public_demo"] is True
    r = upload(client)
    assert r.status_code == 403 and "disabled" in r.json()["detail"]
    assert not exposed.user_storage_dir.exists()  # nothing was written
    # no user corpus, and the main database is opened read-only
    assert client.post("/ask", json={"question": "Ijara", "corpus": "user"}).status_code == 503
    assert client.post("/ask", json={"question": "Ijara haqi"}).status_code == 200
    with make_session_factory(exposed.database_url, read_only=True)() as s:
        with pytest.raises(OperationalError, match="readonly"):
            s.execute(text("DELETE FROM chunks"))
            s.commit()


def test_private_api_keeps_uploads_and_docs(corpus):
    client = TestClient(create_app(corpus))  # defaults: loopback, no domain, no demo flag
    assert client.get("/health").json()["public_demo"] is False
    assert upload(client).status_code == 201
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 200, path


@pytest.mark.parametrize("update", [{"public_demo": True}, {"web_bind": "0.0.0.0"}])
def test_api_docs_are_off_in_the_public_demo(corpus, update):
    client = TestClient(create_app(corpus.model_copy(update=update)))
    for path in ("/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"):
        assert client.get(path).status_code == 404, path
    assert client.get("/health").status_code == 200


# --- "documind serve" -------------------------------------------------------------------------

def test_serve_on_a_public_host_announces_it(monkeypatch):
    # set through monkeypatch, so that what announce_bind writes to the environment is
    # removed again after the test
    monkeypatch.setenv("DOCUMIND_WEB_BIND", "127.0.0.1")
    monkeypatch.setenv("DOCUMIND_SITE_ADDRESS", ":80")
    monkeypatch.setenv("DOCUMIND_PUBLIC_DEMO", "false")
    get_settings.cache_clear()
    try:
        cli.announce_bind("127.0.0.1")
        assert get_settings().read_only_demo is False
        cli.announce_bind("0.0.0.0")
        assert get_settings().read_only_demo is True
        # a loopback host does not hide an exposure that was already declared
        cli.announce_bind("127.0.0.1")
        assert get_settings().read_only_demo is True
    finally:
        get_settings.cache_clear()


# --- database connections ---------------------------------------------------------------------

def test_postgres_connections_are_checked_before_use(tmp_path):
    pg = make_engine("postgresql+psycopg://documind_api:x@localhost:5432/documind")
    assert pg.pool._pre_ping is True  # no connection is opened by creating the engine
    ro = make_engine("postgresql+psycopg://documind_api:x@localhost:5432/documind", read_only=True)
    assert ro.pool._pre_ping is True
    assert make_engine(f"sqlite:///{tmp_path / 'x.sqlite'}").pool._pre_ping is False
