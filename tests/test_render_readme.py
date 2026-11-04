import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("render_readme", ROOT / "scripts/render_readme.py")
render_readme = importlib.util.module_from_spec(spec)
spec.loader.exec_module(render_readme)


def _readme(tmp_path: Path) -> Path:
    path = tmp_path / "README.md"
    path.write_text(f"intro\n{render_readme.BEGIN}\nPLACEHOLDER_XYZ\n{render_readme.END}\noutro\n")
    return path


def test_missing_results_render_as_tbd(tmp_path):
    readme = _readme(tmp_path)
    render_readme.update_readme(readme, tmp_path / "empty")
    text = readme.read_text()
    assert text.count("| BM25 | TBD | TBD | TBD | TBD | TBD |") == 2  # real and synthetic
    assert "PLACEHOLDER_XYZ" not in text
    assert text.startswith("intro") and text.rstrip().endswith("outro")


def test_values_come_from_result_files(tmp_path):
    results = tmp_path / "results"
    results.mkdir()
    (results / "retrieval_bm25_real.json").write_text(json.dumps(
        {"metrics": {"recall@1": 0.25, "recall@5": 0.5, "mrr": 0.3333}, "n": 120,
         "ci95": {"recall@1": [0.1, 0.4]}}))
    readme = _readme(tmp_path)
    render_readme.update_readme(readme, results)
    text = readme.read_text()
    real, synthetic = text.split("SYNTHETIC sanity set")
    # recall@10 is absent from the file, so it must stay TBD; CI shown when present
    assert "| BM25 | 0.250 (0.10–0.40) | 0.500 | TBD | 0.333 | 120 |" in real
    # a real result never fills the synthetic table
    assert "| BM25 | TBD | TBD | TBD | TBD | TBD |" in synthetic


def test_repo_readme_has_markers():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert render_readme.BEGIN in text and render_readme.END in text


def test_per_metric_n(tmp_path):
    results = tmp_path / "results"
    results.mkdir()
    (results / "ocr_synthetic.json").write_text(json.dumps(
        {"metrics": {"cer_ru": 0.01}, "n": 24, "n_by_metric": {"cer_ru": 8}}))
    readme = _readme(tmp_path)
    render_readme.update_readme(readme, results)
    assert "| OCR CER, synthetic scans, ru | 1.0% | 8 |" in readme.read_text()


def test_small_real_samples_stay_tbd(tmp_path):
    results = tmp_path / "results"
    results.mkdir()
    (results / "retrieval_bm25_real.json").write_text(json.dumps(
        {"metrics": {"recall@1": 0.1, "recall@5": 0.5, "mrr": 0.27}, "n": 10}))
    (results / "retrieval_bm25_synthetic.json").write_text(json.dumps(
        {"metrics": {"recall@1": 0.8, "recall@5": 1.0, "mrr": 0.9}, "n": 10}))
    readme = _readme(tmp_path)
    render_readme.update_readme(readme, results)
    real, synthetic = readme.read_text().split("SYNTHETIC sanity set")
    assert "| BM25 | TBD | TBD | TBD | TBD | TBD |" in real
    assert "docs/experiments.md" in real
    assert "| BM25 | 0.800 | 1.000 | TBD | 0.900 | 10 |" in synthetic
