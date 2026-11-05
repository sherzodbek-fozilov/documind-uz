// Mirrors documind/api/schemas.py. Keep in sync when the API changes.

export type Corpus = "real" | "synthetic";

export interface Health {
  status: "ok";
  mode: string;
  retriever: string;
  documents: number;
  chunks: number;
}

export interface DocumentInfo {
  id: string;
  title: string;
  language: string;
  corpus: Corpus;
  is_synthetic: boolean;
  source: string | null;
  edition: string | null;
  n_chunks: number;
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
