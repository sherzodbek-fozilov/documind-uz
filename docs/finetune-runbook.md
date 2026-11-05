# Fine-tuning runbook (stage 5)

How to fine-tune multilingual-e5-small on Kaggle, bring the model back, export it to ONNX
and compare it with the base model on the real test questions.

Rules that hold throughout:

- **No data is uploaded or published.** The notebook rebuilds the training pairs on
  Kaggle from the approved sources. Do not add a dataset, do not upload `data/training/`,
  do not make the notebook public, and do not publish its output as a dataset.
- **No test question decides anything.** The epoch is chosen on the validation pairs
  (held-out train chapters) inside the notebook. `eval_finetune.py` only reports.
  If you change a setting after seeing test results, record that in `docs/decisions.md`.

Kaggle's interface changes from time to time; if a button has moved, look for the same
setting in the notebook's right-hand panel ("Session options" / "Settings").

## 1. Kaggle notebook setup (once)

1. Sign in at kaggle.com. **Phone verification** is needed for internet access in
   notebooks: your profile → Settings → Phone verification.
2. **Create → New Notebook.**
3. In the right-hand panel (Session options):
   - **Accelerator: GPU T4** (T4 x2 is fine; one GPU is used). Avoid P100: recent PyTorch
     builds no longer support it.
   - **Internet: On** (needed for git clone, pip, lex.uz and the base model download).
   - **Persistence: none.**
4. Keep **Sharing: Private** (the default). Do not attach any dataset ("Add data").

## 2. Smoke run (check the setup first)

Replace `REF` with the branch, tag or commit to use: `feat/finetune-prep` until it is
merged, `main` after that. For a reproducible run, use a commit sha.

Cell 1 — fetch the script:

```
!wget -q -O finetune_e5.py https://raw.githubusercontent.com/sherzodbek-fozilov/documind-uz/REF/kaggle/finetune_e5.py
```

Cell 2 — smoke run (a few minutes; four polite requests to lex.uz with 10 s pauses):

```
!python finetune_e5.py --ref REF --smoke
```

It clones the repository into `/tmp/documind`, installs it with the `finetune` extra,
re-fetches the approved sources, ingests them, builds the pairs, loads the base model,
scores 50 validation queries and runs one loss forward. It does **not** train.

Expected lines near the end:

```
data check: identical to the committed statistics
epoch 0 (base) val: chunk {...}  article {...}
smoke OK: one batch of 32, loss ...; 970 steps planned; no training done
```

If it stops with `DATA CHECK: ...`, lex.uz has changed the text since the committed
statistics were made (chunk counts or pair files differ). Do not just pass
`--allow-data-change`: re-ingest locally first, check that the test questions' gold
chunks still match (`scripts/eval_retrieval.py`), and update the committed statistics in
a reviewed commit.

If lex.uz cannot be reached from Kaggle (network or region), stop: there is no other
approved way to get the documents onto Kaggle.

## 3. Full run

Cell 3:

```
!python finetune_e5.py --ref REF
```

Defaults (fixed in advance, see `docs/decisions.md`): full fine-tuning, lr 2e-5,
batch 32, at most 3 epochs, warmup 10 %, fp16, seed 42. It prints validation metrics for
the base model (epoch 0) and after each epoch, keeps the best epoch by validation MRR@10,
and writes to `/kaggle/working`:

| File | Contents |
|---|---|
| `e5-small-ft/best/` | the sentence-transformers model of the best epoch |
| `e5-small-ft/training_log.json` | config, library versions, repo commit, data check, loss curve, validation metrics per epoch, `best_epoch` |
| `e5-small-ft/training_pairs_stats.json` | pair counts (no text) |
| `e5-small-ft.zip` | all of the above, for download |

If it prints `no epoch beat the base model on validation`, there is no `best/` folder:
record the result, do not export.

To keep the result without leaving the browser open, use **Save Version → Save & Run
All (Commit)** instead of running cells interactively; the output is kept with the
(private) notebook version. Only the model and statistics are in it: the documents and
pairs stay in `/tmp`, which is not saved.

## 4. Download the result

- Interactive session: right-hand panel → **Output** (`/kaggle/working`) →
  `e5-small-ft.zip` → ⋮ → **Download**. Files disappear when the session stops.
- Saved version: the notebook's page → **Output** tab → download `e5-small-ft.zip`.

Locally (in the repository; `runs/` is git-ignored):

```bash
mkdir -p runs/e5-small-ft
```

```bash
unzip -o ~/Downloads/e5-small-ft.zip -d runs/e5-small-ft
```

Check `runs/e5-small-ft/training_log.json`: `source.data_check.identical` should be
`true`, and note `best_epoch` and the validation metrics per epoch.

## 5. Export to ONNX (CPU)

Install the fine-tuning extra. On a machine without a GPU, install the CPU build of
PyTorch first so that pip does not pull the large CUDA build:

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

```bash
pip install -e ".[dev,finetune]"
```

```bash
python scripts/export_onnx.py --model runs/e5-small-ft/best --out models/multilingual-e5-small-ft --training-log runs/e5-small-ft/training_log.json
```

The script refuses to finish unless the ONNX embeddings match the PyTorch ones
(max |diff| < 1e-4) and the tokenizer ids are identical. The folder has the same layout
as the base model, so the service can use it with
`DOCUMIND_EMBED_MODEL_DIR=models/multilingual-e5-small-ft`.

## 6. Before/after evaluation on the real test questions

The real documents must be ingested locally, and the base model downloaded:

```bash
python scripts/fetch_sources.py
```

```bash
documind ingest data/raw
```

```bash
python scripts/download_model.py
```

Then:

```bash
python scripts/eval_finetune.py --ft-model-dir models/multilingual-e5-small-ft
```

It runs `eval_retrieval.py` for the base and the fine-tuned model with identical
arguments on the test split, refuses to compare unless both used the same question file
(sha256), the same questions and the same corpus, and writes:

- `results/retrieval_e5_small_ft_real.json`, `results/retrieval_hybrid_rrf_ft_real.json`
  (README rows "Fine-tuned e5-small" and "Hybrid with fine-tuned e5")
- `results/finetune_compare_real.json`: deltas with paired bootstrap 95 % CIs,
  per language, and per-question rank changes

Then `python scripts/render_readme.py` and record the outcome (including a null or
negative result) in `docs/experiments.md` / `docs/decisions.md`.

## Local runs without Kaggle

`kaggle/finetune_e5.py --data-dir data/training --out runs/e5-small-ft` uses the pair files
from `scripts/make_training_pairs.py` instead of preparing them; `--smoke` and
`--eval-only` work the same way.
