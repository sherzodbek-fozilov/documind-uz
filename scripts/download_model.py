"""Download the ONNX export of an embedding model from Hugging Face, pinned to a revision.

Default: intfloat/multilingual-e5-small (MIT license), ONNX files only, into
``models/multilingual-e5-small/``. ``models/`` is git-ignored.

Usage: python scripts/download_model.py [--repo ID] [--revision SHA] [--out DIR]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from huggingface_hub import snapshot_download

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REPO = "intfloat/multilingual-e5-small"
# pinned so that results are reproducible; update deliberately
DEFAULT_REVISION = "614241f622f53c4eeff9890bdc4f31cfecc418b3"
FILES = ["onnx/model.onnx", "onnx/tokenizer.json", "onnx/config.json",
         "onnx/tokenizer_config.json", "onnx/special_tokens_map.json"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", default=DEFAULT_REPO)
    ap.add_argument("--revision", default=DEFAULT_REVISION)
    ap.add_argument("--out", type=Path, default=ROOT / "models/multilingual-e5-small")
    args = ap.parse_args()
    path = snapshot_download(args.repo, revision=args.revision, allow_patterns=FILES,
                             local_dir=args.out)
    (args.out / "SOURCE.json").write_text(json.dumps(
        {"repo": args.repo, "revision": args.revision, "files": FILES}, indent=2) + "\n")
    print(f"model files in {path}")


if __name__ == "__main__":
    main()
