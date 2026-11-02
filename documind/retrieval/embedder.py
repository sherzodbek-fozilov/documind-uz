"""Sentence embeddings with an ONNX export of an E5 model (CPU, no PyTorch).

E5 models expect the prefixes "query: " and "passage: ", mean pooling over tokens and
L2 normalization (see the model card of intfloat/multilingual-e5-small). Inputs longer
than ``max_length`` tokens are truncated; the chunker keeps chunks below that limit.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path

import numpy as np


class E5Embedder:
    def __init__(self, model_dir: Path, max_length: int = 512, batch_size: int = 16,
                 threads: int | None = None):
        import onnxruntime as ort
        from tokenizers import Tokenizer

        model_dir = Path(model_dir)
        onnx_dir = model_dir / "onnx" if (model_dir / "onnx").exists() else model_dir
        if not (onnx_dir / "model.onnx").exists():
            raise FileNotFoundError(f"{onnx_dir / 'model.onnx'} not found; run "
                                    "scripts/download_model.py")
        self.tokenizer = Tokenizer.from_file(str(onnx_dir / "tokenizer.json"))
        self.tokenizer.enable_truncation(max_length)
        self.tokenizer.enable_padding(pad_id=self.tokenizer.token_to_id("<pad>"),
                                      pad_token="<pad>")
        opts = ort.SessionOptions()
        if threads:
            opts.intra_op_num_threads = threads
        self.session = ort.InferenceSession(str(onnx_dir / "model.onnx"), opts,
                                            providers=["CPUExecutionProvider"])
        self.input_names = {i.name for i in self.session.get_inputs()}
        self.batch_size = batch_size
        source = model_dir / "SOURCE.json"
        self.model_id = (json.loads(source.read_text())["revision"][:12]
                         if source.exists() else model_dir.name)

    def _encode(self, texts: Sequence[str]) -> np.ndarray:
        out = []
        # sort by length so padding inside a batch is small; restore order afterwards
        order = sorted(range(len(texts)), key=lambda i: len(texts[i]))
        for start in range(0, len(order), self.batch_size):
            idx = order[start:start + self.batch_size]
            enc = self.tokenizer.encode_batch([texts[i] for i in idx])
            ids = np.array([e.ids for e in enc], dtype=np.int64)
            mask = np.array([e.attention_mask for e in enc], dtype=np.int64)
            feeds = {"input_ids": ids, "attention_mask": mask}
            if "token_type_ids" in self.input_names:
                feeds["token_type_ids"] = np.zeros_like(ids)
            hidden = self.session.run(None, feeds)[0]
            m = mask[..., None].astype(np.float32)
            pooled = (hidden * m).sum(axis=1) / np.clip(m.sum(axis=1), 1e-9, None)
            pooled /= np.linalg.norm(pooled, axis=1, keepdims=True)
            out.append((idx, pooled))
        result = np.zeros((len(texts), out[0][1].shape[1] if out else 0), dtype=np.float32)
        for idx, vecs in out:
            result[idx] = vecs
        return result

    def embed_queries(self, texts: Sequence[str]) -> np.ndarray:
        return self._encode([f"query: {t}" for t in texts])

    def embed_passages(self, texts: Sequence[str], cache_dir: Path | None = None) -> np.ndarray:
        """Embed passages, optionally caching by (model, text) hash in ``cache_dir``."""
        if cache_dir is None:
            return self._encode([f"passage: {t}" for t in texts])
        key = hashlib.sha256(json.dumps([self.model_id, list(texts)]).encode()).hexdigest()[:24]
        path = Path(cache_dir) / f"passages-{key}.npy"
        if path.exists():
            return np.load(path)
        vecs = self._encode([f"passage: {t}" for t in texts])
        path.parent.mkdir(parents=True, exist_ok=True)
        np.save(path, vecs)
        return vecs
