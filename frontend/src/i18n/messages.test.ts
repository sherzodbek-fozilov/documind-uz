import { describe, expect, it } from "vitest";
import { LANGS, MESSAGES, detectLang, translate } from "./messages";

describe("messages", () => {
  it("has every key, non-empty, in every language", () => {
    const keys = Object.keys(MESSAGES.en).sort();
    for (const lang of LANGS) {
      expect(Object.keys(MESSAGES[lang]).sort()).toEqual(keys);
      for (const k of keys) expect(MESSAGES[lang][k as keyof typeof MESSAGES.en].trim()).not.toBe("");
    }
  });

  it("uses the same placeholders in every language", () => {
    const names = (s: string) => [...s.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();
    for (const [key, en] of Object.entries(MESSAGES.en)) {
      for (const lang of LANGS) {
        expect(names(MESSAGES[lang][key as keyof typeof MESSAGES.en]), `${lang}:${key}`)
          .toEqual(names(en));
      }
    }
  });

  it("fills placeholders and keeps unknown ones", () => {
    expect(translate("ru", "docs.chunks", { n: 12 })).toBe("Фрагментов: 12");
    expect(translate("uz", "results.check", { valid: 3, checked: 3 }))
      .toBe("Iqtiboslar manba matni bilan tekshirildi: 3 tadan 3 tasi");
    expect(translate("en", "docs.edition")).toBe("Edition: {edition}");
  });

  it("detects the browser language and defaults to Uzbek", () => {
    expect(detectLang(["ru-RU", "en"])).toBe("ru");
    expect(detectLang(["de-DE", "en-GB"])).toBe("en");
    expect(detectLang(["uz-Cyrl-UZ"])).toBe("uz");
    expect(detectLang(["fr"])).toBe("uz");
    expect(detectLang([])).toBe("uz");
  });
});
