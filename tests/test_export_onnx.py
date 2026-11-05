"""Torch-free part of scripts/export_onnx.py: the pooling check."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _module(path: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod  # dataclasses look their module up while the class is built
    spec.loader.exec_module(mod)
    return mod


def test_export_pooling_check(tmp_path):
    ex = _module("scripts/export_onnx.py", "export_onnx")
    (tmp_path / "1_Pooling").mkdir()
    (tmp_path / "modules.json").write_text(json.dumps([
        {"path": "", "type": "sentence_transformers.models.Transformer"},
        {"path": "1_Pooling", "type": "sentence_transformers.models.Pooling"},
        {"path": "2_Normalize", "type": "sentence_transformers.models.Normalize"}]))
    for ok in ({"pooling_mode": "mean"},
               {"pooling_mode_mean_tokens": True, "pooling_mode_cls_token": False}):
        (tmp_path / "1_Pooling/config.json").write_text(json.dumps(ok))
        ex.check_pooling(tmp_path)
    for bad in ({"pooling_mode": "cls"},
                {"pooling_mode_mean_tokens": True, "pooling_mode_cls_token": True}):
        (tmp_path / "1_Pooling/config.json").write_text(json.dumps(bad))
        with pytest.raises(SystemExit):
            ex.check_pooling(tmp_path)
