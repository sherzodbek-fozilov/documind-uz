import copy
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("fetch_sources", ROOT / "scripts/fetch_sources.py")
fetch_sources = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch_sources)

ENTRY = {"id": "law-ru", "title": "Закон", "language": "ru", "kind": "law", "group_id": "law",
         "download_url": None, "accessed_on": None, "sha256": None,
         "terms": {"status": "needs review", "url": "https://example.org/terms", "license": None,
                   "checked_by": None, "checked_on": None}}


def _registry(**terms):
    entry = copy.deepcopy(ENTRY)
    entry["terms"].update(terms)
    return {"sources": [entry]}


def test_repo_registry_is_valid_and_nothing_unreviewed_is_approved():
    registry = fetch_sources.load_registry()
    assert fetch_sources.validate(registry) == []
    for s in registry["sources"]:
        if s["terms"]["status"] == "approved":
            assert s["terms"]["license"] and s["terms"]["checked_on"]


def test_approved_requires_license_and_checker():
    problems = fetch_sources.validate(_registry(status="approved"))
    assert any("terms.license" in p for p in problems)
    assert any("terms.checked_by" in p for p in problems)


def test_needs_review_is_never_included(tmp_path):
    (tmp_path / "law-ru.pdf").write_bytes(b"%PDF-1.4 fake")
    rows, log = fetch_sources.collect(_registry(), tmp_path, allow_download=False,
                                      today="2026-11-01")
    assert rows == [] and "terms needs review" in log[0]


def test_hand_placed_file_needs_access_date(tmp_path):
    (tmp_path / "law-ru.pdf").write_bytes(b"%PDF-1.4 fake")
    reg = _registry(status="approved", license="public domain (official act)",
                    checked_by="me", checked_on="2026-11-02")
    rows, log = fetch_sources.collect(reg, tmp_path, allow_download=False, today="2026-11-03")
    assert rows == [] and "accessed_on is empty" in log[0]
    reg["sources"][0]["accessed_on"] = "2026-11-02"
    rows, _ = fetch_sources.collect(reg, tmp_path, allow_download=False, today="2026-11-03")
    assert rows[0]["synthetic"] is False and rows[0]["group_id"] == "law"
    assert reg["sources"][0]["sha256"] and rows[0]["accessed_on"] == "2026-11-02"
    table = fetch_sources.render_table(reg, {"law-ru"})
    assert "**approved**" in table and "| yes |" in table
    json.dumps(rows)


def test_data_md_table_is_up_to_date():
    registry = fetch_sources.load_registry()
    manifest = ROOT / "data/raw/manifest.jsonl"
    included = ({json.loads(x)["doc_id"] for x in manifest.read_text().splitlines() if x}
                if manifest.exists() else set())
    text = (ROOT / "docs/data.md").read_text(encoding="utf-8")
    table = fetch_sources.render_table(registry, included)
    assert fetch_sources.update_data_md(text, table) == text
