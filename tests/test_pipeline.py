import os

import docx
import pytest
from conftest import RU, UZ_LATN, make_scanned_pdf, make_text_pdf, requires_font, requires_ocr
from sqlalchemy import select

from documind.cli import main as cli_main
from documind.ingestion.pipeline import ingest_file
from documind.storage import models
from documind.storage.db import make_session_factory


def _check_consistency(session, doc_id):
    doc = session.get(models.Document, doc_id)
    for c in doc.chunks:
        assert doc.text[c.char_start:c.char_end] == c.text
    for p in doc.pages:
        page_text = doc.text[p.char_start:p.char_end]
        for b in p.blocks:
            assert page_text[b["start"]:b["end"]]
    return doc


@requires_font
def test_ingest_pdf_and_dedupe(tmp_path, settings):
    pdf = make_text_pdf(tmp_path / "Ijara Shartnoma №1.pdf", [UZ_LATN, RU])
    Session = make_session_factory(settings.database_url)
    with Session() as s:
        res = ingest_file(pdf, s, settings, is_synthetic=True, source="test")
        assert res.status == "ingested" and res.doc_id == "ijara-shartnoma-1"
        assert res.n_pages == 2 and res.n_chunks >= 2 and res.split in ("train", "test")
        doc = _check_consistency(s, res.doc_id)
        assert doc.is_synthetic and doc.chunker_version == "struct-v1-w60"
        assert (settings.storage_dir / f"{doc.sha256}.pdf").exists()
        langs = {c.language for c in doc.chunks}
        assert {"uz-Latn", "ru"} <= langs
        assert doc.chunks[0].id == "ijara-shartnoma-1#c0000"
        # same bytes again: deduplicated
        again = ingest_file(pdf, s, settings)
        assert again.status == "duplicate" and again.doc_id == res.doc_id
        # same name, different content: gets a suffixed id instead of overwriting
        other = make_text_pdf(tmp_path / "Ijara-Shartnoma-1.pdf", [RU])
        res2 = ingest_file(other, s, settings)
        assert res2.doc_id.startswith("ijara-shartnoma-1-") and res2.doc_id != res.doc_id
        assert s.scalar(select(models.Document).where(models.Document.id == res.doc_id))


def test_group_shares_split(tmp_path, settings):
    Session = make_session_factory(settings.database_url)
    with Session() as s:
        splits = set()
        for i, text in enumerate(["Ushbu qonun kuchga kiradi.", "Настоящий закон вступает."]):
            d = docx.Document()
            d.add_paragraph(text)
            path = tmp_path / f"law-{i}.docx"
            d.save(path)
            splits.add(ingest_file(path, s, settings, group_id="law-x").split)
        assert len(splits) == 1


@requires_font
@requires_ocr
def test_ingest_scanned_pdf(tmp_path, settings):
    scan = make_scanned_pdf(tmp_path / "scan.pdf",
                            make_text_pdf(tmp_path / "a.pdf", [UZ_LATN], fontsize=13))
    Session = make_session_factory(settings.database_url)
    with Session() as s:
        res = ingest_file(scan, s, settings)
        assert res.n_ocr_pages == 1 and res.language == "uz-Latn"
        doc = _check_consistency(s, res.doc_id)
        assert doc.pages[0].is_ocr and doc.pages[0].ocr_confidence > 60
        assert any("2.1." in c.text for c in doc.chunks)


def test_cli_ingest_with_manifest_and_stats(tmp_path, settings, monkeypatch, capsys):
    data = tmp_path / "data"
    data.mkdir()
    d = docx.Document()
    d.add_paragraph("SINTETIK NAMUNA. Ushbu shartnoma tuzildi.")
    d.save(data / "a.docx")
    (data / "manifest.jsonl").write_text(
        '{"file": "a.docx", "doc_id": "syn-a", "group_id": "g1", "synthetic": true, '
        '"source": "synthetic-test"}\n', encoding="utf-8")
    for key, value in [("DATABASE_URL", settings.database_url),
                       ("STORAGE_DIR", str(settings.storage_dir)),
                       ("SPLITS_FILE", str(settings.splits_file))]:
        monkeypatch.setenv(f"DOCUMIND_{key}", value)
    from documind.config import get_settings
    get_settings.cache_clear()
    assert cli_main(["ingest", str(data)]) == 0
    assert '"doc_id": "syn-a"' in capsys.readouterr().out
    assert cli_main(["stats"]) == 0
    out = capsys.readouterr().out
    assert '"synthetic": 1' in out and '"leaking_groups": []' in out
    get_settings.cache_clear()


@pytest.mark.postgres
@pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not set")
def test_postgres_roundtrip(tmp_path, settings):
    from sqlalchemy import text

    url = os.environ["TEST_DATABASE_URL"]
    Session = make_session_factory(url)
    with Session() as s:
        s.execute(text("TRUNCATE documents CASCADE"))
        s.commit()
        d = docx.Document()
        d.add_heading("ДОГОВОР", level=1)
        d.add_paragraph("1.1. Ушбу шартнома тарафлар ўртасида тузилди.")
        d.save(tmp_path / "pg.docx")
        res = ingest_file(tmp_path / "pg.docx", s, settings)
        doc = _check_consistency(s, res.doc_id)
        assert doc.chunks[0].language == "uz-Cyrl"
        assert isinstance(doc.script_stats, dict) and doc.pages[0].blocks[0]["kind"] == "heading"


def test_cli_split_stratifies_real_and_synthetic(tmp_path, settings, monkeypatch, capsys):
    import json

    from documind.config import get_settings

    for key, value in [("DATABASE_URL", settings.database_url),
                       ("STORAGE_DIR", str(settings.storage_dir)),
                       ("SPLITS_FILE", str(settings.splits_file)),
                       ("TEST_FRACTION", "0.5")]:
        monkeypatch.setenv(f"DOCUMIND_{key}", value)
    get_settings.cache_clear()
    Session = make_session_factory(settings.database_url)
    with Session() as s:
        for i in range(4):
            for synthetic in (True, False):
                d = docx.Document()
                d.add_paragraph(f"Ushbu hujjat {i} {synthetic} boʻyicha tuzildi.")
                path = tmp_path / f"{'syn' if synthetic else 'real'}-{i}.docx"
                d.save(path)
                ingest_file(path, s, get_settings(), is_synthetic=synthetic)
    assert cli_main(["split"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["groups"] == {"real/uz-Latn/test": 2, "real/uz-Latn/train": 2,
                             "synthetic/uz-Latn/test": 2, "synthetic/uz-Latn/train": 2}
    assert cli_main(["stats"]) == 0
    stats = json.loads(capsys.readouterr().out)
    assert stats["by_kind_and_split"] == {"real/test": 2, "real/train": 2,
                                          "synthetic/test": 2, "synthetic/train": 2}
    get_settings.cache_clear()
