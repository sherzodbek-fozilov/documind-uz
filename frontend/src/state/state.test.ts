import { describe, expect, it, vi } from "vitest";
import { sectionLeaf, sectionParents, sectionParts } from "../lib/section";
import { PASSAGE_UZ, askResponse } from "../test/samples";
import { MAX_SESSIONS, loadHistory, saveHistory, upsertSession } from "./history";
import type { Session } from "./history";
import { resolveTheme, storedTheme } from "./theme";

function session(id: string): Session {
  return {
    id, title: `Savol ${id}`, updatedAt: 1,
    turns: [{ id: `${id}-1`, question: `Savol ${id}`, corpus: "real", documentId: null,
              response: askResponse(`Savol ${id}`, [PASSAGE_UZ]) }],
  };
}

describe("history", () => {
  it("round-trips sessions through localStorage", () => {
    expect(loadHistory()).toEqual([]);
    saveHistory([session("a"), session("b")]);
    expect(loadHistory()).toEqual([session("a"), session("b")]);
    saveHistory([]);
    expect(window.localStorage.getItem("documind.history.v1")).toBeNull();
  });

  it("drops stored entries that are not valid sessions", () => {
    window.localStorage.setItem("documind.history.v1", JSON.stringify([
      session("a"), { id: "x" }, null, { ...session("c"), turns: [] },
      { ...session("d"), turns: [{ question: "no response" }] },
    ]));
    expect(loadHistory().map((s) => s.id)).toEqual(["a"]);
    window.localStorage.setItem("documind.history.v1", "{not json");
    expect(loadHistory()).toEqual([]);
    window.localStorage.setItem("documind.history.v1", JSON.stringify({ a: 1 }));
    expect(loadHistory()).toEqual([]);
  });

  it("puts an updated session first and caps the list", () => {
    const list = [session("a"), session("b")];
    expect(upsertSession(list, { ...session("b"), updatedAt: 2 }).map((s) => s.id)).toEqual(["b", "a"]);
    const many = Array.from({ length: MAX_SESSIONS }, (_, i) => session(String(i)));
    const next = upsertSession(many, session("new"));
    expect(next).toHaveLength(MAX_SESSIONS);
    expect(next[0].id).toBe("new");
  });

  it("drops the oldest sessions when the storage is full, and never throws", () => {
    const real = Storage.prototype.setItem;
    const setItem = vi.spyOn(Storage.prototype, "setItem").mockImplementation(function (this: Storage, k, v) {
      if (JSON.parse(v).length > 2) throw new DOMException("full", "QuotaExceededError");
      real.call(this, k, v);
    });
    saveHistory(Array.from({ length: 8 }, (_, i) => session(String(i))));
    expect(loadHistory().map((s) => s.id)).toEqual(["0", "1"]);
    setItem.mockImplementation(() => { throw new DOMException("blocked", "SecurityError"); });
    expect(() => saveHistory([session("a")])).not.toThrow();
    setItem.mockRestore();
  });
});

describe("theme", () => {
  it("is dark unless a valid choice is stored", () => {
    expect(storedTheme()).toBe("dark");
    window.localStorage.setItem("documind.theme", "light");
    expect(storedTheme()).toBe("light");
    window.localStorage.setItem("documind.theme", "pink");
    expect(storedTheme()).toBe("dark");
  });

  it("resolves the system choice from the OS setting", () => {
    expect(resolveTheme("light")).toBe("light");
    const matchMedia = vi.fn((q: string) => ({ matches: false, media: q }));
    vi.stubGlobal("matchMedia", matchMedia);
    expect(resolveTheme("system")).toBe("light");
    matchMedia.mockReturnValue({ matches: true, media: "" });
    expect(resolveTheme("system")).toBe("dark");
    vi.unstubAllGlobals();
  });
});

describe("section", () => {
  it("splits a heading path and finds the closest heading", () => {
    const path = "ГРАЖДАНСКИЙ КОДЕКС / Глава 29. Купля-продажа / Статья 386. Договор купли-продажи";
    expect(sectionParts(path)).toHaveLength(3);
    expect(sectionLeaf(path)).toBe("Статья 386. Договор купли-продажи");
    expect(sectionParents(path)).toEqual(["ГРАЖДАНСКИЙ КОДЕКС", "Глава 29. Купля-продажа"]);
    expect(sectionLeaf("1-modda. Ijara haqi")).toBe("1-modda. Ijara haqi");
    expect(sectionParents("1-modda. Ijara haqi")).toEqual([]);
    expect(sectionLeaf(null)).toBeNull();
    expect(sectionParts("")).toEqual([]);
  });
});
