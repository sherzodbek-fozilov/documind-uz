# Work items

Tracked here until they are moved to GitHub issues. `[x]` = done and committed.

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
