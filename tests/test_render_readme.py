import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("render_readme", ROOT / "scripts/render_readme.py")
render_readme = importlib.util.module_from_spec(spec)
spec.loader.exec_module(render_readme)


def _readme(tmp_path: Path) -> Path:
    path = tmp_path / "README.md"
    path.write_text(f"intro\n{render_readme.BEGIN}\nold\n{render_readme.END}\noutro\n")
    return path


def test_missing_results_render_as_tbd(tmp_path):
    readme = _readme(tmp_path)
    render_readme.update_readme(readme, tmp_path / "empty")
    text = readme.read_text()
    assert "| BM25 | TBD | TBD | TBD | TBD | TBD |" in text
    assert "old" not in text and text.startswith("intro") and text.rstrip().endswith("outro")


def test_values_come_from_result_files(tmp_path):
    results = tmp_path / "results"
    results.mkdir()
    (results / "retrieval_bm25.json").write_text(json.dumps(
        {"metrics": {"recall@1": 0.25, "recall@5": 0.5, "mrr": 0.3333}, "n": 12}))
    readme = _readme(tmp_path)
    render_readme.update_readme(readme, results)
    # recall@10 is absent from the file, so it must stay TBD
    assert "| BM25 | 0.250 | 0.500 | TBD | 0.333 | 12 |" in readme.read_text()


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
