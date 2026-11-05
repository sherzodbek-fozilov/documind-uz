# %% [markdown]
# # Fine-tune multilingual-e5-small for DocuMind UZ (Kaggle, GPU)
#
# Self-contained: run it as one notebook cell (``!python finetune_e5.py``) or paste the
# cells (``# %%`` markers) into a notebook. Step-by-step: docs/finetune-runbook.md.
#
# What it does, in order (``prepare`` then ``train``):
#   1. clones the public repository at ``--ref`` into ``--work-dir`` (default /tmp/documind)
#   2. installs it with the ``finetune`` extra
#   3. re-fetches the APPROVED sources with scripts/fetch_sources.py (polite: robots.txt,
#      one request at a time, 10 s pause, a User-Agent naming the project)
#   4. ingests them into a SQLite database in the work dir (frozen data/splits.json)
#   5. builds the pairs with scripts/make_training_pairs.py (train chunk groups only) and
#      checks that chunk counts and pair-file sha256 equal the committed
#      results/training_pairs_stats.json, so the data is exactly what was reviewed
#   6. fine-tunes, picks the epoch on the validation pairs, saves to ``--out``
#
# Data is never uploaded or published: the documents, the database and the pair files
# stay in the work dir under /tmp, which Kaggle does not keep as notebook output. Only the
# model and count-only statistics are written to /kaggle/working. No test chunk and no
# test question is used here; test evaluation happens afterwards on the CPU side
# (scripts/eval_finetune.py) on the same real test questions as the baseline.
#
# Method: full fine-tuning of the PyTorch model (all weights), sentence-transformers
# ``MultipleNegativesRankingLoss`` over (query, positive, hard negative) with in-batch
# negatives, E5 prefixes "query: " / "passage: ", small learning rate, a few epochs, fixed
# seeds. Batches never contain two rows of the same article (an article's other-language
# version or its other queries would otherwise be counted as negatives).
#
# Output (``--out``, default /kaggle/working/e5-small-ft, and a .zip of it):
#   best/                       sentence-transformers model of the best validation epoch
#   training_log.json           config, versions, repo commit, data check, loss, val metrics
#   training_pairs_stats.json   pair counts (no text)
#
# Usage (Kaggle notebook, GPU T4, internet on):
#   !python finetune_e5.py --ref main --smoke   # setup check: everything up to one loss
#                                               # forward and 50 validation queries
#   !python finetune_e5.py --ref main           # full run
#   !python finetune_e5.py --data-dir DIR       # local: use existing pair files

# %%
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import shutil
import subprocess
import sys
import time
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from pathlib import Path

BASE_MODEL = "intfloat/multilingual-e5-small"
# the same revision as scripts/download_model.py (the CPU service's baseline)
BASE_REVISION = "614241f622f53c4eeff9890bdc4f31cfecc418b3"
REPO_URL = "https://github.com/sherzodbek-fozilov/documind-uz.git"
PAIR_FILES = ("pairs_train.jsonl", "pairs_val.jsonl", "corpus.jsonl")


@dataclass
class Config:
    base_model: str = BASE_MODEL
    base_revision: str = BASE_REVISION
    epochs: int = 3  # maximum; the best validation epoch is kept
    batch_size: int = 32
    lr: float = 2e-5
    weight_decay: float = 0.01
    warmup_ratio: float = 0.1
    max_grad_norm: float = 1.0
    max_seq_length: int = 512  # the service truncates at 512 tokens too
    mnrl_scale: float = 20.0  # sentence-transformers default
    fp16: bool = True
    seed: int = 42
    eval_batch_size: int = 128
    selection_metric: str = "mrr"  # validation MRR@10, chunk level


# %% helpers without torch (unit-tested in tests/test_kaggle_finetune.py)

def read_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def group_batches(keys: list[frozenset], batch_size: int, seed: int, epoch: int) -> list[list[int]]:
    """Shuffle rows into batches in which no two rows share a key (article of the
    positive or of the negative). Deterministic for (seed, epoch); every row is used once.
    A row that conflicts with the current batch waits for the next one."""
    rng = random.Random(f"{seed}:{epoch}")
    order = list(range(len(keys)))
    rng.shuffle(order)
    pending = deque(order)
    batches = []
    while pending:
        batch, used, waiting = [], set(), []
        while pending and len(batch) < batch_size:
            i = pending.popleft()
            if used.isdisjoint(keys[i]):
                batch.append(i)
                used |= keys[i]
            else:
                waiting.append(i)
        pending.extendleft(reversed(waiting))
        batches.append(batch)
    return batches


def row_keys(rows: list[dict]) -> list[frozenset]:
    return [frozenset({r["article"], r.get("negative_article") or r["article"]})
            for r in rows]


def retrieval_metrics(ranked_ids: list[list[str]], rows: list[dict],
                      article_of: dict[str, str], ks=(1, 5, 10)) -> dict:
    """Recall@k and MRR@10, chunk level (the positive itself, the primary metric) and
    article level (any chunk of the positive's article in any language), overall and per
    query type, noise and language pair."""
    def rank(ids: list[str], hit) -> int | None:
        return next((i for i, cid in enumerate(ids, 1) if hit(cid)), None)

    def summarize(rs: list[int | None]) -> dict:
        n = len(rs)
        out = {f"recall@{k}": sum(r is not None and r <= k for r in rs) / n for k in ks}
        out["mrr"] = sum(1 / r for r in rs if r is not None and r <= 10) / n
        return {"n": n, **{k: round(v, 4) for k, v in out.items()}}

    chunk, article = [], []
    groups: dict[str, list[int]] = defaultdict(list)
    for i, (ids, r) in enumerate(zip(ranked_ids, rows, strict=True)):
        chunk.append(rank(ids, lambda c, r=r: c == r["positive_id"]))
        article.append(rank(ids, lambda c, r=r: article_of.get(c) == r["article"]))
        groups[f"type:{r['query_type']}"].append(i)
        groups[f"noise:{r['noise']}"].append(i)
        groups[f"lang:{r['query_lang']}->{r['passage_lang']}"].append(i)
    return {"chunk": summarize(chunk), "article": summarize(article),
            "groups": {g: summarize([chunk[i] for i in idx])
                       for g, idx in sorted(groups.items())}}


def data_check(reference: dict, new: dict) -> list[str]:
    """Differences between the committed pair statistics and the ones built here. The
    sources are re-fetched, so lex.uz may have changed the text since it was reviewed."""
    problems = []
    for key in ("total", "train", "test_excluded", "chunker_versions", "documents"):
        a, b = reference["source_chunks"].get(key), new["source_chunks"].get(key)
        if a != b:
            problems.append(f"source chunks {key}: committed {a}, here {b}")
    for name in PAIR_FILES:
        a, b = reference["files_sha256"].get(name), new["files_sha256"].get(name)
        if a != b:
            problems.append(f"{name}: sha256 differs from the committed statistics")
    return problems


# %% prepare: clone, install, fetch, ingest, build pairs (all under --work-dir)

def run(cmd: list[str], cwd: Path | None = None, env: dict | None = None) -> str:
    print("+", " ".join(cmd), flush=True)
    res = subprocess.run(cmd, cwd=cwd, env=env, check=True, text=True,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    print(res.stdout[-3000:], flush=True)
    return res.stdout


def prepare(args: argparse.Namespace) -> tuple[Path, dict]:
    work = Path(args.work_dir)
    if str(work.resolve()).startswith("/kaggle/working"):
        raise SystemExit("--work-dir must not be under /kaggle/working: it holds lex.uz text "
                         "and Kaggle keeps /kaggle/working as notebook output")
    repo = work / "repo"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    run(["git", "clone", "--quiet", args.repo_url, str(repo)])
    run(["git", "checkout", "--quiet", args.ref], cwd=repo)
    commit = run(["git", "rev-parse", "HEAD"], cwd=repo).strip()
    run([sys.executable, "-m", "pip", "install", "-q", "-e", ".[finetune]"], cwd=repo)
    # read before make_training_pairs.py overwrites it in the clone
    reference = json.loads((repo / "results/training_pairs_stats.json").read_text())
    env = {**os.environ, "PYTHONHASHSEED": "0",
           "DOCUMIND_DATABASE_URL": f"sqlite:///{work / 'documind.sqlite'}",
           "DOCUMIND_STORAGE_DIR": str(work / "store")}
    run([sys.executable, "scripts/fetch_sources.py"], cwd=repo, env=env)
    run([sys.executable, "-m", "documind.cli", "ingest", "data/raw"], cwd=repo, env=env)
    data_dir = work / "training"
    run([sys.executable, "scripts/make_training_pairs.py", "--out-dir", str(data_dir)],
        cwd=repo, env=env)
    stats = json.loads((repo / "results/training_pairs_stats.json").read_text())
    problems = data_check(reference, stats)
    for p in problems:
        print(f"DATA CHECK: {p}", flush=True)
    if problems and not args.allow_data_change:
        raise SystemExit("the rebuilt data differs from the committed statistics (see above); "
                         "rerun with --allow-data-change only after reviewing why")
    print("data check: identical to the committed statistics" if not problems
          else "data check: differences accepted with --allow-data-change", flush=True)
    return data_dir, {"repo_url": args.repo_url, "ref": args.ref, "repo_commit": commit,
                      "data_check": {"identical": not problems, "problems": problems},
                      "pairs_stats": stats}


# %% torch part

def set_seeds(seed: int) -> None:
    import numpy as np
    import torch

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    torch.use_deterministic_algorithms(True, warn_only=True)


def evaluate(model, rows: list[dict], corpus: list[dict], cfg: Config) -> dict:
    import torch

    model.eval()
    with torch.no_grad():
        p = model.encode([f"passage: {c['text']}" for c in corpus],
                         batch_size=cfg.eval_batch_size, convert_to_tensor=True,
                         normalize_embeddings=True, show_progress_bar=False)
        q = model.encode([f"query: {r['query']}" for r in rows],
                         batch_size=cfg.eval_batch_size, convert_to_tensor=True,
                         normalize_embeddings=True, show_progress_bar=False)
        top = torch.topk(q @ p.T, k=min(10, len(corpus)), dim=1).indices.cpu().tolist()
    ids = [c["id"] for c in corpus]
    article_of = {c["id"]: c["article"] for c in corpus}
    return retrieval_metrics([[ids[j] for j in row] for row in top], rows, article_of)


def train(args: argparse.Namespace, cfg: Config, data_dir: Path, info: dict) -> None:
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")  # deterministic cuBLAS
    import sentence_transformers
    import torch
    import transformers
    from sentence_transformers import SentenceTransformer, losses

    set_seeds(cfg.seed)
    files = {n: data_dir / n for n in PAIR_FILES}
    train_rows, val_rows, corpus = (read_jsonl(files[n]) for n in files)
    if args.smoke:
        val_rows = val_rows[:50]
    device = "cuda" if torch.cuda.is_available() else "cpu"
    fp16 = cfg.fp16 and device == "cuda"
    out = Path(args.out)
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    if info.get("pairs_stats"):
        (out / "training_pairs_stats.json").write_text(json.dumps(info["pairs_stats"],
                                                                  indent=2))
    log = {"config": asdict(cfg), "device": device,
           "source": {k: v for k, v in info.items() if k != "pairs_stats"},
           "gpu": torch.cuda.get_device_name(0) if device == "cuda" else None,
           "versions": {"python": sys.version.split()[0], "torch": torch.__version__,
                        "transformers": transformers.__version__,
                        "sentence_transformers": sentence_transformers.__version__},
           "data_sha256": {n: sha256_file(p) for n, p in files.items()},
           "data_counts": {"train_pairs": len(train_rows), "val_pairs": len(val_rows),
                           "corpus": len(corpus)},
           "epochs": []}
    print(json.dumps({k: log[k] for k in ("device", "gpu", "versions", "data_counts")}))

    model = SentenceTransformer(cfg.base_model, revision=cfg.base_revision, device=device)
    model.max_seq_length = cfg.max_seq_length
    val0 = evaluate(model, val_rows, corpus, cfg)
    log["epochs"].append({"epoch": 0, "val": val0})
    print(f"epoch 0 (base) val: chunk {val0['chunk']}  article {val0['article']}")
    if args.eval_only:
        (out / "training_log.json").write_text(json.dumps(log, indent=2))
        return

    loss_fn = losses.MultipleNegativesRankingLoss(model, scale=cfg.mnrl_scale)
    keys = row_keys(train_rows)
    plan = [group_batches(keys, cfg.batch_size, cfg.seed, e) for e in range(1, cfg.epochs + 1)]
    total_steps = sum(len(b) for b in plan)

    def features(texts: list[str]) -> dict:
        # newer sentence-transformers also return non-tensor entries; move tensors only
        return {k: v.to(device) if hasattr(v, "to") else v
                for k, v in model.tokenize(texts).items()}

    def batch_loss(idx: list[int]):
        rows = [train_rows[i] for i in idx]
        feats = [features([f"query: {r['query']}" for r in rows]),
                 features([f"passage: {r['positive']}" for r in rows]),
                 features([f"passage: {r['negative']}" for r in rows])]
        with torch.autocast(device_type=device, dtype=torch.float16, enabled=fp16):
            return loss_fn(feats, None)

    if args.smoke:
        model.train()
        with torch.no_grad():
            loss = batch_loss(plan[0][0])
        log["smoke"] = {"batch": len(plan[0][0]), "loss": round(loss.item(), 5),
                        "steps_planned": total_steps, "trained": False}
        (out / "training_log.json").write_text(json.dumps(log, indent=2))
        print(f"smoke OK: one batch of {len(plan[0][0])}, loss {loss.item():.4f}; "
              f"{total_steps} steps planned; no training done")
        return

    no_decay = ("bias", "LayerNorm.weight", "LayerNorm.bias")
    params = [{"params": [p for n, p in model.named_parameters()
                          if not any(x in n for x in no_decay)],
               "weight_decay": cfg.weight_decay},
              {"params": [p for n, p in model.named_parameters()
                          if any(x in n for x in no_decay)], "weight_decay": 0.0}]
    opt = torch.optim.AdamW(params, lr=cfg.lr)
    sched = transformers.get_linear_schedule_with_warmup(
        opt, int(cfg.warmup_ratio * total_steps), total_steps)
    scaler = torch.amp.GradScaler("cuda", enabled=fp16)
    best = (val0["chunk"][cfg.selection_metric], 0)
    step = 0
    for epoch, batches in enumerate(plan, start=1):
        model.train()
        start, losses_epoch = time.time(), []
        for idx in batches:
            loss = batch_loss(idx)
            scaler.scale(loss).backward()
            scaler.unscale_(opt)
            torch.nn.utils.clip_grad_norm_(model.parameters(), cfg.max_grad_norm)
            scaler.step(opt)
            scaler.update()
            opt.zero_grad(set_to_none=True)
            sched.step()
            step += 1
            losses_epoch.append(loss.item())
            if step % 50 == 0:
                print(f"epoch {epoch} step {step}/{total_steps} "
                      f"loss {sum(losses_epoch[-50:]) / len(losses_epoch[-50:]):.4f}")
        val = evaluate(model, val_rows, corpus, cfg)
        score = val["chunk"][cfg.selection_metric]
        log["epochs"].append({"epoch": epoch, "steps": len(batches),
                              "mean_loss": round(sum(losses_epoch) / len(losses_epoch), 5),
                              "loss_every_50": [round(sum(losses_epoch[i:i + 50]) /
                                                      len(losses_epoch[i:i + 50]), 5)
                                                for i in range(0, len(losses_epoch), 50)],
                              "seconds": round(time.time() - start, 1), "val": val})
        print(f"epoch {epoch} val: chunk {val['chunk']}  article {val['article']}")
        if score > best[0]:  # ties keep the earlier (shorter-trained) epoch
            best = (score, epoch)
            model.save(str(out / "best"))
        (out / "training_log.json").write_text(json.dumps(log, indent=2))
    log["best_epoch"] = best[1]
    log["best_val_" + cfg.selection_metric] = best[0]
    if best[1] == 0:
        print("no epoch beat the base model on validation; nothing saved as best/")
    (out / "training_log.json").write_text(json.dumps(log, indent=2))
    archive = shutil.make_archive(str(out), "zip", root_dir=out)
    print(f"best epoch {best[1]} (val {cfg.selection_metric} {best[0]:.4f}); "
          f"model in {out / 'best'}; download {archive}")


# %% entry point

def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Fine-tune multilingual-e5-small (Kaggle)")
    ap.add_argument("--ref", default="main", help="branch, tag or commit of the repository")
    ap.add_argument("--repo-url", default=REPO_URL)
    ap.add_argument("--work-dir", default="/tmp/documind",
                    help="clone, documents, database and pairs (never /kaggle/working)")
    ap.add_argument("--data-dir", default=None,
                    help="use existing pair files instead of preparing them (local use)")
    ap.add_argument("--allow-data-change", action="store_true",
                    help="continue when the rebuilt pairs differ from the committed stats")
    ap.add_argument("--out", default="/kaggle/working/e5-small-ft")
    ap.add_argument("--epochs", type=int)
    ap.add_argument("--lr", type=float)
    ap.add_argument("--batch-size", type=int)
    ap.add_argument("--seed", type=int)
    ap.add_argument("--eval-only", action="store_true", help="base model on validation only")
    ap.add_argument("--smoke", action="store_true",
                    help="setup check: prepare, then one loss forward and 50 validation "
                         "queries, no training")
    # in a notebook, sys.argv holds the kernel's arguments: ignore unknown ones
    args, _ = ap.parse_known_args(argv)
    cfg = Config()
    for name in ("epochs", "lr", "batch_size", "seed"):
        if getattr(args, name) is not None:
            setattr(cfg, name, getattr(args, name))
    if args.data_dir:
        data_dir, info = Path(args.data_dir), {"data_dir": args.data_dir}
    else:
        data_dir, info = prepare(args)
    train(args, cfg, data_dir, info)


if __name__ == "__main__":
    main()
