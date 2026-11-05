// Handwritten samples only (invented text in the style of a contract/act).
import { describe, expect, it } from "vitest";
import { splitAroundQuote, trimContext } from "./highlight";

const UZ = "1-modda. Ijara haqi. Ijara haqi har oyning oʻninchi kunigacha toʻlanadi. "
  + "Kechiktirilgan har bir kun uchun penya hisoblanadi.";
const UZ_QUOTE = "Kechiktirilgan har bir kun uchun penya hisoblanadi.";

describe("splitAroundQuote", () => {
  it("uses the offsets when they point at the exact quote", () => {
    const start = UZ.indexOf(UZ_QUOTE);
    const h = splitAroundQuote(UZ, UZ_QUOTE, start, start + UZ_QUOTE.length);
    expect(h.exact).toBe(true);
    expect(h.quote).toBe(UZ_QUOTE);
    expect(h.before + h.quote + h.after).toBe(UZ);
    expect(h.after).toBe("");
  });

  it("works for Cyrillic Uzbek and Russian text", () => {
    const ru = "Статья 2. Арендатор содержит помещение за свой счёт. Иное не допускается.";
    const q = "Арендатор содержит помещение за свой счёт.";
    const s = ru.indexOf(q);
    expect(splitAroundQuote(ru, q, s, s + q.length)).toEqual({
      before: "Статья 2. ", quote: q, after: " Иное не допускается.", exact: true,
    });
    const cyr = "Шартнома бир йил муддатга тузилади.";
    expect(splitAroundQuote(cyr, cyr, 0, cyr.length).quote).toBe(cyr);
  });

  it("falls back to the verbatim quote when offsets disagree", () => {
    // Python offsets count code points, JS strings count UTF-16 units: a character
    // outside the BMP before the quote shifts them by one.
    const text = "𝟙 Ijarachi binoni oʻz hisobidan saqlaydi.";
    const q = "Ijarachi binoni";
    const h = splitAroundQuote(text, q, 2, 2 + q.length); // code-point offsets
    expect(h).toEqual({ before: "𝟙 ", quote: q, after: " oʻz hisobidan saqlaydi.", exact: true });
  });

  it("does not highlight a quote that is not in the passage", () => {
    const h = splitAroundQuote(UZ, "penya hisoblanmaydi", 10, 29);
    expect(h).toEqual({ before: UZ, quote: "", after: "", exact: false });
  });

  it("rejects empty quotes and broken offsets", () => {
    expect(splitAroundQuote(UZ, "", 0, 0).exact).toBe(false);
    expect(splitAroundQuote("abc", "abc", -1, 99).exact).toBe(true); // found verbatim
    expect(splitAroundQuote("abc", "x", 5, 2).exact).toBe(false);
  });
});

describe("trimContext", () => {
  it("cuts long context at word boundaries and never cuts the quote", () => {
    const before = "birinchi ikkinchi uchinchi toʻrtinchi ";
    const after = " beshinchi oltinchi yettinchi sakkizinchi";
    const q = "penya hisoblanadi";
    const h = trimContext({ before, quote: q, after, exact: true }, 15);
    expect(h.quote).toBe(q);
    expect(h.before.startsWith("…")).toBe(true);
    expect(h.after.endsWith("…")).toBe(true);
    expect(h.before).toBe("…toʻrtinchi ");
    expect(h.after).toBe(" beshinchi…");
  });

  it("keeps short context unchanged", () => {
    const h = { before: "a ", quote: "b", after: " c", exact: true };
    expect(trimContext(h, 300)).toEqual(h);
  });
});
