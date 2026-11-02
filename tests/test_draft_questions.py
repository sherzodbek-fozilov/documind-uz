import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _draft_module():
    spec = importlib.util.spec_from_file_location("draft_questions",
                                                  ROOT / "scripts/draft_questions.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_draft_helpers():
    d = _draft_module()
    assert d.clean_title("ШАРТНОМА / 5-modda. Ijara muddati") == "Ijara muddati"
    assert d.clean_title("Статья 7. Цена") == "Цена"
    assert d.clean_title("2. ЦЕНА И УСЛОВИЯ ОПЛАТЫ") == "Цена и условия оплаты"
    q = d.number_question("2. ЦЕНА\n\n2.1. Общая сумма договора составляет 5 000 000 сумов.",
                          "ru")
    assert q == "Общая сумма договора составляет сколько сумов?"


def test_accept_refuses_unedited_drafts(tmp_path, monkeypatch):
    d = _draft_module()
    monkeypatch.setattr(d, "QUESTIONS", tmp_path / "questions.jsonl")
    drafts = tmp_path / "drafts.jsonl"
    base = {"language": "ru", "gold_doc": "d", "gold_chunk": "d#c0", "scope": "corpus",
            "draft_question": "Draft?"}
    rows = [base | {"question": "Draft?", "status": "reviewed"},        # unedited
            base | {"question": "Сколько стоит?", "status": "reviewed"},  # edited
            base | {"question": "Draft?", "status": "draft"}]            # not reviewed
    drafts.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    moved, kept, problems = d.accept(drafts, allow_unedited=False)
    assert (moved, kept) == (1, 2) and "unedited" in problems[0]
    accepted = [json.loads(x) for x in (tmp_path / "questions.jsonl").read_text().splitlines()]
    assert accepted[0]["question"] == "Сколько стоит?" and accepted[0]["status"] == "reviewed"
    assert "context" not in accepted[0]
