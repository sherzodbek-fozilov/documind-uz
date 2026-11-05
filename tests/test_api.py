"""API tests on HANDWRITTEN documents: a small act in the lex.uz page structure (invented
text, element ids made up) and a synthetic DOCX. No real lex.uz content is used."""

import importlib.util
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from documind.api.app import create_app
from documind.ingestion.pipeline import ingest_file
from documind.qa.citations import Citation
from documind.qa.llm import LLMConfigError
from documind.qa.service import QAService
from documind.storage import models
from documind.storage.db import make_session_factory

ROOT = Path(__file__).resolve().parent.parent
LEX_URL = "https://lex.uz/ru/docs/-9999"


def elem(kind: str, eid: str, inner: str) -> str:
    return (f'<div class="{kind} lx_elem"><div class="lx_elem2"><span>btn</span></div>'
            f'<div id="{eid}">{inner}</div></div>')


ACT = f"""<!DOCTYPE html><html><head><title>01.02.2003. Namuna kodeksi</title></head><body>
<div class="lx_date_selected">05.06.2026</div>
{elem("ACT_TITLE", "-100", "NAMUNA KODEKSI")}
{elem("TEXT_HEADER_DEFAULT", "-101", "1-bob. Ijara")}
{elem("CLAUSE_DEFAULT", "-102", "1-modda. Ijara haqi")}
{elem("ACT_TEXT", "-103", "Ijara haqi har oyning oʻninchi kunigacha toʻlanadi. "
      "Kechiktirilgan har bir kun uchun penya hisoblanadi.")}
{elem("ACT_TEXT", "-104", "Ijarachi binoni oʻz hisobidan saqlaydi.")}
{elem("CLAUSE_DEFAULT", "-105", "2-modda. Shartnomani bekor qilish")}
{elem("ACT_TEXT", "-106", "Taraflar shartnomani bir oy oldin yozma ogohlantirib bekor "
      "qilishi mumkin.")}
</body></html>"""


def make_docx(path: Path) -> Path:
    import docx

    d = docx.Document()
    d.add_paragraph("SINOV SHARTNOMASI (SYNTHETIC)")
    d.add_paragraph("1-modda. Muddat")
    d.add_paragraph("Shartnoma bir yil muddatga tuziladi.")
    d.save(path)
    return path


@pytest.fixture
def db(settings, tmp_path):
    act = tmp_path / "act.html"
    act.write_text(ACT, encoding="utf-8")
    Session = make_session_factory(settings.database_url)
    with Session() as s:
        ingest_file(act, s, settings, doc_id="namuna-uz", source=LEX_URL)
        ingest_file(make_docx(tmp_path / "syn.docx"), s, settings, doc_id="syn-1",
                    is_synthetic=True, source="synthetic-test")
    return Session


@pytest.fixture
def client(settings, db):
    return TestClient(create_app(settings, QAService(db, settings)))


def test_health_and_documents(client):
    h = client.get("/health").json()
    assert h["status"] == "ok" and h["mode"] == "extractive" and h["retriever"] == "bm25"
    assert h["documents"] == 2 and h["chunks"] >= 2
    docs = {d["id"]: d for d in client.get("/documents").json()}
    assert docs["namuna-uz"]["title"] == "01.02.2003. Namuna kodeksi"
    assert docs["namuna-uz"]["edition"] == "05.06.2026"
    assert docs["namuna-uz"]["corpus"] == "real" and docs["syn-1"]["is_synthetic"]
    assert [d["id"] for d in client.get("/documents?corpus=synthetic").json()] == ["syn-1"]
    assert client.get("/documents?corpus=other").status_code == 422


def test_ask_returns_exact_quotes_with_lexuz_anchor_links(client, db):
    r = client.post("/ask", json={"question": "Penya qachon hisoblanadi?", "top_k": 2})
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "extractive" and body["answer"] is None and body["citations"] == []
    top = body["passages"][0]
    assert top["rank"] == 1 and top["document_id"] == "namuna-uz"
    assert top["quote"] == "Kechiktirilgan har bir kun uchun penya hisoblanadi."
    assert top["anchor"] == "-103" and top["link"] == f"{LEX_URL}#-103"
    with db() as s:
        chunk = s.get(models.Chunk, top["chunk_id"])
        assert chunk.text[top["quote_start"]:top["quote_end"]] == top["quote"]
        assert top["text"] == chunk.text  # the UI highlights the quote inside this text
    check = body["citation_check"]
    assert check == {"checked": len(body["passages"]), "valid": len(body["passages"]),
                     "failures": {}}


def test_ask_document_scope_synthetic_corpus_and_errors(client):
    r = client.post("/ask", json={"question": "Shartnoma muddati qancha?",
                                  "corpus": "synthetic", "document_id": "syn-1"}).json()
    assert r["passages"][0]["quote"] == "Shartnoma bir yil muddatga tuziladi."
    assert r["passages"][0]["link"] is None  # not a web source
    assert client.post("/ask", json={"question": "x", "document_id": "syn-1"}).status_code \
        == 404  # synthetic document, real corpus
    assert client.post("/ask", json={"question": ""}).status_code == 422
    assert client.post("/ask", json={"question": "x", "top_k": 11}).status_code == 422


def test_ask_on_an_empty_corpus_is_503(settings):
    app = create_app(settings)  # empty database
    assert TestClient(app).post("/ask", json={"question": "x"}).status_code == 503


class FakeLLM:
    """Returns one exact quote (in «»), one paraphrase, one citation of an unknown chunk."""

    def __init__(self, reply=None):
        self.reply, self.prompts = reply, []

    def complete(self, prompt, max_tokens):
        self.prompts.append((prompt, max_tokens))
        if self.reply is not None:
            return self.reply
        cid = prompt.split("[", 2)[2].split("]", 1)[0]  # first passage id in the prompt
        return json.dumps({"answer": "Har oyning oʻninchi kunigacha.", "citations": [
            {"chunk_id": cid, "quote": "«Ijara haqi har oyning oʻninchi kunigacha toʻlanadi.»"},
            {"chunk_id": cid, "quote": "Ijara haqi oyiga bir marta toʻlanadi."},
            {"chunk_id": "other#c0001", "quote": "Ijara haqi"}]}, ensure_ascii=False)


def test_llm_mode_keeps_only_exact_citations(settings, db):
    settings = settings.model_copy(update={"answer_mode": "llm"})
    llm = FakeLLM()
    client = TestClient(create_app(settings, QAService(db, settings, llm=llm)))
    body = client.post("/ask", json={"question": "Ijara haqi qachon toʻlanadi?"}).json()
    assert body["mode"] == "llm" and body["answer"] == "Har oyning oʻninchi kunigacha."
    assert [c["quote"] for c in body["citations"]] == [
        "Ijara haqi har oyning oʻninchi kunigacha toʻlanadi."]
    assert body["citations"][0]["link"] == f"{LEX_URL}#-103"
    assert body["citation_check"] == {"checked": 3, "valid": 1, "failures": {
        "quote is not in the chunk": 1, "chunk was not given to the model": 1}}
    assert body["passages"]  # the retrieved passages are still returned
    assert llm.prompts[0][1] == settings.llm_max_tokens_per_request


def test_llm_mode_errors(settings, db):
    settings = settings.model_copy(update={"answer_mode": "llm"})
    client = TestClient(create_app(settings, QAService(db, settings, llm=FakeLLM("no json"))))
    assert client.post("/ask", json={"question": "Ijara haqi"}).status_code == 502
    with pytest.raises(LLMConfigError):  # flag on, no provider configured
        QAService(db, settings)


def test_eval_script_check_detects_tampered_citations(db):
    spec = importlib.util.spec_from_file_location("eval_citations",
                                                  ROOT / "scripts/eval_citations.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    with db() as s:
        chunk = next(c for c in s.query(models.Chunk).all() if "penya" in c.text)
        start = chunk.text.index("Kechiktirilgan")
        quote = "Kechiktirilgan har bir kun uchun penya hisoblanadi."
        good = Citation("namuna-uz", chunk.id, quote, start, start + len(quote), "-103")
        assert mod.check_against_db(s, good) == (None, True)
        wrong_anchor = Citation(**{**good.__dict__, "anchor": "-104"})
        assert mod.check_against_db(s, wrong_anchor) == (None, False)
        shifted = Citation(**{**good.__dict__, "start": start + 1, "end": start + 1 + len(quote)})
        assert mod.check_against_db(s, shifted)[0] is not None
        assert mod.check_against_db(s, Citation("x", "x#c0000", "q", 0, 1))[0] == "unknown chunk"
