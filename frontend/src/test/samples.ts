// Handwritten samples: invented text in the style of an act / contract. Element ids and
// URLs are made up; no real lex.uz content is used.
import type { AskResponse, Passage } from "../api/types";

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
