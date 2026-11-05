import { describe, expect, it } from "vitest";
import { safeHttpUrl } from "./url";

describe("safeHttpUrl", () => {
  it("keeps http(s) links with their anchor", () => {
    expect(safeHttpUrl("https://lex.uz/ru/docs/-9999#-103")).toBe("https://lex.uz/ru/docs/-9999#-103");
    expect(safeHttpUrl("http://example.org/a")).toBe("http://example.org/a");
  });

  it("drops other schemes, relative paths and empty values", () => {
    expect(safeHttpUrl("javascript:alert(1)")).toBeNull();
    expect(safeHttpUrl("data:text/html,x")).toBeNull();
    expect(safeHttpUrl("synthetic-test")).toBeNull();
    expect(safeHttpUrl("/home/user/act.pdf")).toBeNull();
    expect(safeHttpUrl("")).toBeNull();
    expect(safeHttpUrl(null)).toBeNull();
  });
});
