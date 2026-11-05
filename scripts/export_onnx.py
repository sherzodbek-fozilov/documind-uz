"""Export a fine-tuned sentence-transformers E5 model to ONNX for the CPU service.

The output has the same layout as ``scripts/download_model.py`` writes for the base
model, so ``documind.retrieval.embedder.E5Embedder`` loads it unchanged:
  <out>/onnx/model.onnx      inputs input_ids, attention_mask, token_type_ids;
                             output last_hidden_state (mean pooling + L2 norm are done
                             by E5Embedder, as for the base model)
  <out>/onnx/tokenizer.json  and the other tokenizer / config files
  <out>/SOURCE.json          "revision" = sha256 of model.onnx (E5Embedder uses it as the
                             model id, so embedding caches never mix base and fine-tuned
                             vectors), base model, training log summary

The export is verified before anything is written as final: the ONNX embeddings (mean
pooled, normalized) must match the PyTorch sentence-transformers embeddings on
handwritten uz-Latn / uz-Cyrl / ru texts (max |diff| < 1e-4), and the tokenizer.json ids
must match the model's tokenizer.

Needs torch, transformers, sentence-transformers, onnx, onnxruntime (Kaggle has them; or
``pip install -e ".[finetune]"``). Runs on CPU.

Usage:
  python scripts/export_onnx.py --model /kaggle/working/e5-small-ft/best \
      --out models/multilingual-e5-small-ft [--training-log .../training_log.json]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

import numpy as np

CHECK_TEXTS = [
    "query: Ijara haqi qachon toʻlanadi?",
    "query: Ижара ҳақи қачон тўланади?",
    "query: Когда вносится арендная плата?",
    "passage: Ijara haqi har oyda 10 kundan kechiktirmay toʻlanadi va shartnomada "
    "belgilanadi. " * 20,  # long: exercises truncation at max_length
    "passage: Арендная плата вносится ежемесячно не позднее 10 дней.",
]
TOKENIZER_FILES = ("tokenizer.json", "tokenizer_config.json", "special_tokens_map.json",
                   "sentencepiece.bpe.model", "config.json")


def check_pooling(model_dir: Path) -> None:
    """E5Embedder does mean pooling and L2 normalization; the model must do the same."""
    modules = json.loads((model_dir / "modules.json").read_text())
    kinds = [m["type"].rsplit(".", 1)[-1] for m in modules]
    if kinds[:2] != ["Transformer", "Pooling"] or kinds[2:] not in ([], ["Normalize"]):
        raise SystemExit(f"unexpected modules {kinds}; expected Transformer, Pooling, "
                         "Normalize")
    pool_dir = next(model_dir / m["path"] for m in modules if m["type"].endswith("Pooling"))
    pool = json.loads((pool_dir / "config.json").read_text())
    if "pooling_mode" in pool:  # sentence-transformers >= 6
        mean_only = pool["pooling_mode"] == "mean"
    else:  # older versions: one boolean per mode
        modes = {k: v for k, v in pool.items() if k.startswith("pooling_mode_")}
        mean_only = modes.pop("pooling_mode_mean_tokens", False) and not any(modes.values())
    if not mean_only:
        raise SystemExit(f"pooling must be mean only, got {pool}")


def export(model_dir: Path, onnx_path: Path, opset: int) -> None:
    import torch
    from transformers import AutoModel

    model = AutoModel.from_pretrained(str(model_dir)).eval()

    class Wrapper(torch.nn.Module):
        def __init__(self, m):
            super().__init__()
            self.m = m

        def forward(self, input_ids, attention_mask, token_type_ids):
            return self.m(input_ids=input_ids, attention_mask=attention_mask,
                          token_type_ids=token_type_ids).last_hidden_state

    ids = torch.ones((2, 16), dtype=torch.long)
    args = (ids, torch.ones_like(ids), torch.zeros_like(ids))
    names = ["input_ids", "attention_mask", "token_type_ids"]
    axes = {n: {0: "batch_size", 1: "sequence_length"} for n in names}
    axes["last_hidden_state"] = {0: "batch_size", 1: "sequence_length"}
    kwargs = dict(input_names=names, output_names=["last_hidden_state"], dynamic_axes=axes,
                  opset_version=opset, do_constant_folding=True)
    onnx_path.parent.mkdir(parents=True, exist_ok=True)
    with torch.no_grad():
        try:  # torch >= 2.5 has a dynamo exporter; use the TorchScript one for dynamic_axes
            torch.onnx.export(Wrapper(model), args, str(onnx_path), dynamo=False, **kwargs)
        except TypeError:
            torch.onnx.export(Wrapper(model), args, str(onnx_path), **kwargs)


def onnx_embed(onnx_dir: Path, texts: list[str], max_length: int) -> tuple[np.ndarray, list]:
    """The same computation as E5Embedder (kept here so the check does not need documind)."""
    import onnxruntime as ort
    from tokenizers import Tokenizer

    tok = Tokenizer.from_file(str(onnx_dir / "tokenizer.json"))
    tok.enable_truncation(max_length)
    tok.enable_padding(pad_id=tok.token_to_id("<pad>"), pad_token="<pad>")
    enc = tok.encode_batch(texts)
    ids = np.array([e.ids for e in enc], dtype=np.int64)
    mask = np.array([e.attention_mask for e in enc], dtype=np.int64)
    sess = ort.InferenceSession(str(onnx_dir / "model.onnx"), providers=["CPUExecutionProvider"])
    hidden = sess.run(None, {"input_ids": ids, "attention_mask": mask,
                             "token_type_ids": np.zeros_like(ids)})[0]
    m = mask[..., None].astype(np.float32)
    pooled = (hidden * m).sum(1) / np.clip(m.sum(1), 1e-9, None)
    unpadded = [[i for i, a in zip(e.ids, e.attention_mask, strict=True) if a] for e in enc]
    return pooled / np.linalg.norm(pooled, axis=1, keepdims=True), unpadded


def verify(model_dir: Path, onnx_dir: Path, max_length: int, tol: float = 1e-4) -> dict:
    from sentence_transformers import SentenceTransformer

    st = SentenceTransformer(str(model_dir), device="cpu")
    st.max_seq_length = max_length
    ref = st.encode(CHECK_TEXTS, normalize_embeddings=True, convert_to_numpy=True)
    got, onnx_ids = onnx_embed(onnx_dir, CHECK_TEXTS, max_length)
    hf_ids = [st.tokenizer(t, truncation=True, max_length=max_length)["input_ids"]
              for t in CHECK_TEXTS]
    if hf_ids != onnx_ids:
        raise SystemExit("tokenizer.json ids differ from the model's tokenizer")
    diff = float(np.abs(ref - got).max())
    cos = float((ref * got).sum(1).min())
    if diff > tol:
        raise SystemExit(f"ONNX embeddings differ from PyTorch: max |diff| {diff:.2e} > {tol}")
    return {"texts": len(CHECK_TEXTS), "max_abs_diff": diff, "min_cosine": cos,
            "max_length": max_length}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--model", type=Path, required=True,
                    help="sentence-transformers model folder (e.g. .../e5-small-ft/best)")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--training-log", type=Path, default=None)
    ap.add_argument("--max-length", type=int, default=512)
    ap.add_argument("--opset", type=int, default=17)
    args = ap.parse_args()
    check_pooling(args.model)
    tmp = args.out.with_name(args.out.name + ".tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    onnx_dir = tmp / "onnx"
    export(args.model, onnx_dir / "model.onnx", args.opset)
    for name in TOKENIZER_FILES:
        if (args.model / name).exists():
            shutil.copy2(args.model / name, onnx_dir / name)
    check = verify(args.model, onnx_dir, args.max_length)
    digest = hashlib.sha256((onnx_dir / "model.onnx").read_bytes()).hexdigest()
    source = {"repo": "fine-tuned (scripts/export_onnx.py)", "revision": digest,
              "exported_from": str(args.model), "verification": check}
    if args.training_log and args.training_log.exists():
        log = json.loads(args.training_log.read_text())
        source["base_model"] = log["config"]["base_model"]
        source["base_revision"] = log["config"]["base_revision"]
        source["training"] = {k: log.get(k) for k in ("best_epoch", "data_sha256",
                                                     "versions", "config")}
        source["training"]["val_by_epoch"] = [
            {"epoch": e["epoch"], **e["val"]["chunk"]} for e in log["epochs"]]
    (tmp / "SOURCE.json").write_text(json.dumps(source, indent=2) + "\n")
    shutil.rmtree(args.out, ignore_errors=True)
    tmp.rename(args.out)
    print(f"exported to {args.out} (model id {digest[:12]}); check {check}")


if __name__ == "__main__":
    main()
