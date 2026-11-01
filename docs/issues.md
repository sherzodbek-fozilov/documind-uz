# Work items

Tracked here until they are moved to GitHub issues. `[x]` = done and committed.

## Stage 0: skeleton
- [x] Package layout, `pyproject.toml`, `.env.example`, `.gitignore`, Makefile
- [x] README draft with generated, empty metrics table
- [x] `docs/data.md`, `docs/decisions.md`, this list

## Stage 1: ingestion
- [ ] PDF text-layer parsing with layout blocks
- [ ] Scanned-page detection and OCR (tesseract `uzb+uzb_cyrl+rus`)
- [ ] DOCX parsing (paragraphs and tables)
- [ ] Text normalization (Uzbek apostrophes, whitespace) and script/language detection
- [ ] Structure-aware chunking (articles / sections) with character offsets
- [ ] Storage: documents, pages, chunks in PostgreSQL; original files on disk
- [ ] Document-level train/test split
- [ ] Synthetic document generator and OCR error-rate script

## Stage 2: retrieval baselines
- [ ] BM25 baseline
- [ ] multilingual-e5-small dense retrieval with Qdrant
- [ ] Hybrid retrieval with reciprocal rank fusion
- [ ] Optional cross-encoder reranker (CPU latency must be measured)
- [ ] Eval script: Recall@1/5/10, MRR on `data/eval/questions.jsonl`
- [ ] Question-drafting tool for manual review

## Stage 3: API
- [ ] FastAPI: upload, ask, answer with citations
- [ ] Per-request token limit and monthly LLM budget guard
- [ ] Citation-correctness metric

## Stage 4: UI
- [ ] Document viewer with highlighted source passage

## Stage 5: fine-tuning prep
- [ ] Question–passage training pairs from train documents only
- [ ] Kaggle notebook
- [ ] Before/after evaluation on the same test set

## Stage 6: hardening
- [ ] pytest coverage, Docker Compose, CI (incl. `render_readme.py --check`)
- [ ] README results and Limitations with measured evidence

## Known open questions
- Chunk ids depend on the chunker configuration; changing it invalidates `gold_chunk`
  labels. Need a remapping tool (by character span overlap) before relabeling.
- Database migrations (Alembic) instead of `create_all`.
