"""Helpers shared by evaluation scripts: provenance for results/*.json."""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def git_commit() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                                       text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return None


def write_result(name: str, payload: dict, script: str) -> Path:
    payload = {**payload, "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
               "git_commit": git_commit(), "script": script}
    path = ROOT / "results" / name
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
