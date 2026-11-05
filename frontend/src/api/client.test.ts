// Handwritten sample responses; no server is started.
import { describe, expect, it } from "vitest";
import { ApiError, createClient } from "./client";
import type { AskResponse } from "./types";

const SAMPLE_ASK: AskResponse = {
  question: "Penya qachon hisoblanadi?",
  mode: "extractive",
  corpus: "real",
  retriever: "bm25",
  passages: [{
    rank: 1, document_id: "namuna-uz", chunk_id: "namuna-uz:0001",
    section_title: "1-modda. Ijara haqi", language: "uz-Latn",
    text: "Ijara haqi oyning oʻninchi kunigacha toʻlanadi. Kechikkan kun uchun penya hisoblanadi.",
    quote: "Kechikkan kun uchun penya hisoblanadi.", quote_start: 48, quote_end: 86,
    anchor: "-103", link: "https://lex.uz/ru/docs/-9999#-103",
  }],
  answer: null,
  citations: [],
  citation_check: { checked: 1, valid: 1, failures: {} },
};

type Call = { url: string; init?: RequestInit };

function fakeFetch(status: number, body: unknown, calls: Call[] = []): typeof fetch {
  return async (input, init) => {
    calls.push({ url: String(input), init });
    const text = typeof body === "string" ? body : JSON.stringify(body);
    return new Response(text, { status, headers: { "Content-Type": "application/json" } });
  };
}

async function failure(p: Promise<unknown>): Promise<ApiError> {
  try {
    await p;
  } catch (e) {
    if (e instanceof ApiError) return e;
    throw e;
  }
  throw new Error("expected the request to fail");
}

describe("createClient", () => {
  it("posts the question as JSON and returns the response", async () => {
    const calls: Call[] = [];
    const api = createClient("/api", fakeFetch(200, SAMPLE_ASK, calls));
    const r = await api.ask({ question: "Penya qachon hisoblanadi?", top_k: 5 });
    expect(r.passages[0].text.slice(48, 86)).toBe(r.passages[0].quote);
    expect(calls[0].url).toBe("/api/ask");
    expect(calls[0].init?.method).toBe("POST");
    expect(JSON.parse(String(calls[0].init?.body))).toEqual({
      question: "Penya qachon hisoblanadi?", top_k: 5,
    });
  });

  it("builds the documents URL with an optional corpus filter", async () => {
    const calls: Call[] = [];
    const api = createClient("/api", fakeFetch(200, [], calls));
    await api.documents();
    await api.documents("synthetic");
    expect(calls.map((c) => c.url)).toEqual(["/api/documents", "/api/documents?corpus=synthetic"]);
  });

  it("maps HTTP errors to kinds and keeps FastAPI's detail", async () => {
    const notFound = await failure(createClient("", fakeFetch(404, {
      detail: "document 'x' is not in the real corpus",
    })).ask({ question: "x", document_id: "x" }));
    expect([notFound.kind, notFound.status, notFound.message])
      .toEqual(["not_found", 404, "document 'x' is not in the real corpus"]);

    const empty = await failure(createClient("", fakeFetch(503, { detail: "no real documents ingested" }))
      .ask({ question: "x" }));
    expect(empty.kind).toBe("unavailable");

    const invalid = await failure(createClient("", fakeFetch(422, {
      detail: [{ msg: "String should have at least 1 character" }],
    })).ask({ question: "" }));
    expect([invalid.kind, invalid.message]).toEqual(["invalid", "String should have at least 1 character"]);

    const broken = await failure(createClient("", fakeFetch(500, "<html>oops</html>")).health());
    expect(broken.kind).toBe("server");
  });

  it("reports an unreachable API as a network error", async () => {
    const down: typeof fetch = async () => { throw new TypeError("Failed to fetch"); };
    const e = await failure(createClient("", down).health());
    expect([e.kind, e.status]).toEqual(["network", null]);
  });

  it("rejects a 200 answer whose body is not JSON", async () => {
    const e = await failure(createClient("", fakeFetch(200, "not json")).health());
    expect(e.kind).toBe("server");
  });

  it("lets an aborted request stay an AbortError", async () => {
    const aborted: typeof fetch = async () => { throw new DOMException("aborted", "AbortError"); };
    await expect(createClient("", aborted).ask({ question: "x" })).rejects.toMatchObject({
      name: "AbortError",
    });
  });
});
