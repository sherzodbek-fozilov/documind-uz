// Handwritten samples: invented text in the style of an act / contract. Element ids and
// URLs are made up; no real lex.uz content is used.
import type {
  AskResponse, DocumentInfo, DocumentOutline, DocumentPassage, DocumentPassages, Passage,
  PassageWindow,
} from "../api/types";

function passage(p: Omit<Passage, "quote_start" | "quote_end" | "document_id"> & {
  document_id?: string;
}): Passage {
  const start = p.text.indexOf(p.quote);
  if (start < 0) throw new Error(`sample quote not in its text: ${p.quote}`);
  return { document_id: "namuna-uz", ...p, quote_start: start, quote_end: start + p.quote.length };
}

export const PASSAGE_UZ = passage({
  rank: 1,
  chunk_id: "namuna-uz:0001",
  section_title: "1-modda. Ijara haqi",
  language: "uz-Latn",
  text: "1-modda. Ijara haqi\nIjara haqi har oyning oʻninchi kunigacha toʻlanadi. "
    + "Kechiktirilgan har bir kun uchun penya hisoblanadi.",
  quote: "Kechiktirilgan har bir kun uchun penya hisoblanadi.",
  anchor: "-103",
  link: "https://lex.uz/ru/docs/-9999#-103",
});

export const PASSAGE_RU = passage({
  rank: 2,
  document_id: "obrazets-ru",
  chunk_id: "obrazets-ru:0004",
  section_title: "Статья 4. Расторжение договора",
  language: "ru",
  text: "Статья 4. Расторжение договора\nСтороны вправе расторгнуть договор, письменно "
    + "предупредив другую сторону за один месяц.",
  quote: "Стороны вправе расторгнуть договор, письменно предупредив другую сторону за один месяц.",
  anchor: null,
  link: null,
});

export const PASSAGE_SYNTHETIC = passage({
  rank: 1,
  document_id: "syn-1",
  chunk_id: "syn-1:0000",
  section_title: null,
  language: "uz-Cyrl",
  text: "Шартнома бир йил муддатга тузилади.",
  quote: "Шартнома бир йил муддатга тузилади.",
  anchor: null,
  link: null,
});

export function askResponse(question: string, passages: Passage[]): AskResponse {
  return {
    question,
    mode: "extractive",
    corpus: "real",
    retriever: "bm25",
    passages,
    answer: null,
    citations: [],
    citation_check: { checked: passages.length, valid: passages.length, failures: {} },
  };
}

export const DOCUMENTS: DocumentInfo[] = [
  {
    id: "namuna-uz", title: "01.02.2003. Namuna kodeksi", language: "uz-Latn", corpus: "real",
    is_synthetic: false, source: "https://lex.uz/ru/docs/-9999", edition: "05.06.2026",
    kind: "law", n_chunks: 3,
  },
  {
    id: "obrazets-ru", title: "Образец договора аренды", language: "ru", corpus: "real",
    is_synthetic: false, source: null, edition: null, n_chunks: 5,
  },
  {
    id: "syn-1", title: "SINOV SHARTNOMASI (SYNTHETIC)", language: "uz-Cyrl",
    corpus: "synthetic", is_synthetic: true, source: "synthetic-test", edition: null, n_chunks: 1,
  },
];

// The three passages of "namuna-uz" in reading order; the middle one is PASSAGE_UZ.
function consecutive(parts: { chunk_id: string; section_title: string | null; text: string }[]): DocumentPassage[] {
  let offset = 0;
  return parts.map((p, idx) => {
    const char_start = offset;
    offset += p.text.length + 2; // passages are separated by a blank line in the document
    return { idx, ...p, char_start, char_end: char_start + p.text.length };
  });
}

export const DOC_PASSAGES: DocumentPassage[] = consecutive([
  { chunk_id: "namuna-uz:0000", section_title: null, text: "NAMUNA KODEKSI\n\n1-bob. Ijara" },
  { chunk_id: PASSAGE_UZ.chunk_id, section_title: PASSAGE_UZ.section_title, text: PASSAGE_UZ.text },
  {
    chunk_id: "namuna-uz:0002", section_title: "1-bob. Ijara / 2-modda. Shartnomani bekor qilish",
    text: "2-modda. Shartnomani bekor qilish\nTaraflar shartnomani bir oy oldin yozma ogohlantirib "
      + "bekor qilishi mumkin.",
  },
]);

export const OUTLINE: DocumentOutline = {
  document_id: "namuna-uz",
  n_passages: DOC_PASSAGES.length,
  sections: DOC_PASSAGES.map((p) => ({
    idx: p.idx, chunk_id: p.chunk_id, title: p.section_title, chapter: 1, n_passages: 1,
  })),
};

/** What GET /documents/{id}/passages returns for a window of DOC_PASSAGES. */
export function passagesWindow(win: PassageWindow = {}): DocumentPassages {
  const limit = win.limit ?? 7;
  let start = win.start ?? 0;
  if (win.around !== undefined) {
    const centre = DOC_PASSAGES.findIndex((p) => p.chunk_id === win.around);
    if (centre < 0) throw new Error(`no sample passage ${win.around}`);
    start = Math.max(centre - Math.floor(limit / 2), 0);
  }
  return {
    document_id: "namuna-uz", total: DOC_PASSAGES.length, start,
    passages: DOC_PASSAGES.slice(start, start + limit),
  };
}
