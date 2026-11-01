# Evaluation questions

`questions.jsonl` is written and corrected by hand. One JSON object per line:

```json
{"question": "Shartnoma qachon kuchga kiradi?", "language": "uz-Latn", "gold_doc": "syn-uz-latn-ijara-000", "gold_chunk": "syn-uz-latn-ijara-000#c0007"}
```

- `language`: one of `uz-Latn`, `uz-Cyrl`, `ru`
- `gold_doc`: the document id as stored by ingestion (`documind stats` lists them)
- `gold_chunk`: the chunk id `<doc_id>#c<NNNN>`. Chunk ids depend on the chunker
  settings recorded in `chunks.chunker_version`.

Only questions about **test-split** documents are used for the reported metrics.
