# Work items

Tracked here until they are moved to GitHub issues. `[x]` = done and committed.

## Priority (next)

After fine-tuning attempt 1 gave no improvement on real questions
(`docs/experiments.md`), these come first:

- [ ] **Dev question set from train chapters** (hand-written, same style as real user
      questions), used for all tuning and model selection: analyzers (stem length,
      synonyms), embedding models, fine-tuning settings. Never the test set.
- [ ] **Eval set v2**: new real test questions, frozen like v1 (disjoint from v1:
      `scripts/freeze_eval_set.py` needs an option to exclude v1's ids), used once to
      confirm a candidate chosen on the dev set; reported separately from v1.
- [ ] **Screen off-the-shelf Uzbek embedding models on v1, report all**: every candidate
      tried is listed with its result, license and size, including the ones that do not
      help (see `docs/decisions.md`, "Next embedding experiments").
- [ ] Commit the Kaggle `training_log.json` of fine-tuning attempt 1 under `results/`, so
      the validation numbers in `docs/experiments.md` can be filled in from a file.
- [ ] Hash text files with normalized line endings (or add `.gitattributes` with
      `eol=lf`), so a CRLF checkout does not change `questions_sha256`.

## Stage 0: skeleton
- [x] Package layout, `pyproject.toml`, `.env.example`, `.gitignore`, Makefile
- [x] README draft with generated, empty metrics table
- [x] `docs/data.md`, `docs/decisions.md`, this list

## Stage 1: ingestion
- [x] PDF text-layer parsing with layout blocks
- [x] Scanned-page detection and OCR (tesseract `uzb+uzb_cyrl+rus`)
- [x] DOCX parsing (paragraphs and tables)
- [x] Text normalization (Uzbek apostrophes, whitespace) and script/language detection
- [x] Structure-aware chunking (articles / sections) with character offsets
- [x] Storage: documents, pages, chunks in PostgreSQL; original files on disk
- [x] Document-level train/test split
- [x] Synthetic document generator and OCR error-rate script

## Stage 2 prep: real documents
- [x] Source registry (`data/sources.json`) with a terms gate, fetch script, generated
      table in `docs/data.md`
- [x] Split stratified by kind (real / synthetic) and language
- [x] lex.uz robots.txt checked (none); terms checked by Sherzodbek (no statement on
      automated download or copying), recorded per source
- [x] Approval and license field for the four lex.uz sources (GitHub issue #3)
- [ ] Confirm the copyright-law article on official documents (ZRU-42)
- [x] Find and verify URLs: Civil Code part 2, Labor Code 2022 (uz-Latn and ru)
- [ ] Find and verify URLs: consumer protection law (uz and ru), official model contracts
- [x] Download approved sources, ingest, re-run `documind split` (chapter-group split)
- [ ] Held-out third act (consumer protection law) as an out-of-domain test set, never
      used for tuning or fine-tuning
- [ ] Label real evaluation questions (`data/eval/questions.jsonl`)

## Stage 2: retrieval baselines
- [x] BM25 baseline
- [x] multilingual-e5-small dense retrieval with Qdrant
- [x] Hybrid retrieval with reciprocal rank fusion
- [ ] Optional cross-encoder reranker (CPU latency must be measured)
- [ ] Real-set results (blocked on real documents and labeled questions)
- [ ] Re-check the BM25 analyzer choice on real train-split questions (GitHub issue #7)
- [ ] Dev question set from train chapters, used to tune analyzers (stem length,
      synonyms) without touching the test set (priority, see top)
- [x] Eval script: Recall@1/5/10, MRR on `data/eval/questions.jsonl`
- [x] Question-drafting tool for manual review

## Stage 3: API
- [x] FastAPI skeleton: `/health`, `/documents`, `/ask` (extractive quotes with lex.uz
      anchor links)
- [x] Pluggable LLM mode behind `DOCUMIND_ANSWER_MODE=llm` (off by default)
- [x] Citation-correctness metric (exact span), real and synthetic question sets
- [x] Upload endpoint (`POST /documents/upload`, separate "user" corpus)
- [ ] Authentication, rate limits and per-user quotas before the API is exposed beyond
      localhost
- [ ] Parse uploads in a sandboxed worker (separate process or container, no network,
      memory and CPU limits, wall-clock timeout); today they run in the API process
- [ ] Delete endpoint and a retention rule for uploaded documents
- [ ] A concrete LLM provider
- [ ] Per-request token limit and monthly LLM budget guard
- [ ] Quote selection is a heuristic (idf overlap); measure whether the quoted sentence
      is the one that answers the question (needs gold spans, not only gold chunks)
- [ ] Extractive quotes can be a heading line in PDFs (seen with an uploaded PDF:
      "1-modda. Shartnoma muddati" was quoted instead of the sentence after it). Quote
      selection skips only blocks stored with kind "heading", and PDF (and unstyled
      DOCX) blocks are stored as "text" even when the chunker treats them as headings
- [ ] Answer latency p50 on CPU (`results/latency.json`)

## Stage 4: UI
- [ ] Document viewer with highlighted source passage

## Stage 5: fine-tuning prep
- [x] Question–passage training pairs from train chunk groups only, with noise,
      cross-lingual and code-mixed queries and BM25 hard negatives
- [x] Validation set from held-out train chapter groups (for choosing the epoch)
- [x] Kaggle script (`kaggle/finetune_e5.py`)
- [x] ONNX export for the CPU service, verified against PyTorch
- [x] Before/after evaluation hook on the same test questions (`scripts/eval_finetune.py`)
- [x] Run the fine-tuning on Kaggle, export, run the before/after evaluation
      (attempt 1: no improvement on eval set v1, see `docs/experiments.md`)
- [ ] Hand-written dev questions from train chapters as a second validation signal
      (priority, see top)
- [ ] Optional: cross-lingual first-sentence pairs; dense-model hard negatives

## Stage 6: hardening
- [ ] pytest coverage, Docker Compose, CI (incl. `render_readme.py --check`)
- [ ] README results and Limitations with measured evidence

## Known open questions
- OCR on real scans: collect a small set of real (rights-cleared, no personal data) scans
  with hand-corrected text to measure CER; synthetic scans are too clean.
- OCR sometimes reads uz-Cyrl ў қ ғ ҳ as у к г х. For retrieval, consider folding these
  letters (and Latin ↔ Cyrillic transliteration) in the BM25 analyzer and query side.
- Pages with a broken text layer (mojibake) are not detected as needing OCR.
- Page rotation (OSD) and two-column layouts are not handled.
- DOCX has no pages: the whole document is page 1, so citations show no page number.
- PyMuPDF is AGPL-3.0: fine for a portfolio, check before offering it as a service.
- Chunk ids depend on the chunker configuration; changing it invalidates `gold_chunk`
  labels. Need a remapping tool (by character span overlap) before relabeling.
- Database migrations (Alembic) instead of `create_all`.
