// Mirrors documind/api/schemas.py. Keep in sync when the API changes.

export type Corpus = "real" | "synthetic";

export interface Health {
  status: "ok";
  mode: string;
  retriever: string;
  documents: number;
  chunks: number;
  /** public demo: uploads disabled, corpus read-only */
  public_demo: boolean;
}

export interface DocumentInfo {
  id: string;
  title: string;
  language: string;
  corpus: Corpus;
  is_synthetic: boolean;
  source: string | null;
  edition: string | null;
  /** type from the source manifest (e.g. "law"); absent on servers older than this field */
  kind?: string | null;
  n_chunks: number;
}

/** A heading of a document; consecutive passages under one heading form a section. */
export interface OutlineSection {
  /** index of the section's first passage in the document */
  idx: number;
  chunk_id: string;
  /** heading path, parts joined with " / " */
  title: string | null;
  chapter: number | null;
  n_passages: number;
}

export interface DocumentOutline {
  document_id: string;
  n_passages: number;
  sections: OutlineSection[];
}

export interface DocumentPassage {
  idx: number;
  chunk_id: string;
  section_title: string | null;
  /** offsets of the passage in the document text */
  char_start: number;
  char_end: number;
  text: string;
}

/** A window of consecutive passages of one document. */
export interface DocumentPassages {
  document_id: string;
  total: number;
  start: number;
  passages: DocumentPassage[];
}

export interface PassageWindow {
  /** chunk id to centre the window on */
  around?: string;
  start?: number;
  limit?: number;
}

export interface Citation {
  document_id: string;
  chunk_id: string;
  /** exact span of the passage: text[quote_start:quote_end] */
  quote: string;
  quote_start: number;
  quote_end: number;
  /** element id in the source (lex.uz) */
  anchor: string | null;
  /** source URL, with #anchor for lex.uz */
  link: string | null;
}

export interface Passage extends Citation {
  rank: number;
  section_title: string | null;
  language: string;
  /** the whole passage (chunk text) */
  text: string;
}

export interface CitationCheck {
  checked: number;
  valid: number;
  failures: Record<string, number>;
}

export interface AskRequest {
  question: string;
  corpus?: Corpus;
  document_id?: string | null;
  top_k?: number | null;
}

export interface AskResponse {
  question: string;
  mode: "extractive" | "llm";
  corpus: string;
  retriever: string;
  passages: Passage[];
  answer: string | null;
  citations: Citation[];
  citation_check: CitationCheck;
}
