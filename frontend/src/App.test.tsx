// The whole page against a fake API client with handwritten responses.
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { App } from "./App";
import { ApiError } from "./api/client";
import type { ApiClient } from "./api/client";
import type { AskResponse } from "./api/types";
import { renderIn } from "./test/render";
import {
  DOCUMENTS, OUTLINE, PASSAGE_SYNTHETIC, PASSAGE_UZ, askResponse, passagesWindow,
} from "./test/samples";

const HEALTH = {
  status: "ok" as const, mode: "extractive", retriever: "bm25", documents: 3, chunks: 9, public_demo: false,
};

function fakeApi(over: Partial<ApiClient> = {}): ApiClient {
  return {
    health: vi.fn(async () => HEALTH),
    documents: vi.fn(async () => DOCUMENTS),
    ask: vi.fn(async (req) => askResponse(req.question, [PASSAGE_UZ])),
    outline: vi.fn(async () => OUTLINE),
    passages: vi.fn(async (_id, win) => passagesWindow(win)),
    ...over,
  };
}

async function askQuestion(text: string) {
  await userEvent.type(screen.getByRole("textbox", { name: /question|вопрос|savol/i }), `${text}{Enter}`);
}

async function openLibrary() {
  await userEvent.click(screen.getByRole("button", { name: "Document library" }));
  return screen.findByRole("region", { name: "Documents" });
}

describe("App", () => {
  it("shows the API status and the real documents, then answers with a highlighted quote", async () => {
    const api = fakeApi();
    renderIn(<App api={api} />);
    expect(await screen.findByText("API online")).toBeTruthy();
    // counts, mode and retriever are technical details, behind the status disclosure
    const technical = screen.getByText("3 documents, 9 chunks · extractive · bm25");
    expect(technical.closest("details")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "What do you want to find in the legislation?" }))
      .toBeTruthy();

    const docs = await openLibrary();
    await waitFor(() => expect(within(docs).getAllByRole("listitem")).toHaveLength(2));

    await userEvent.click(screen.getByRole("button", { name: "Workspace" }));
    await askQuestion("Penya qachon hisoblanadi?");
    const card = await screen.findByRole("article", { name: "01.02.2003. Namuna kodeksi" });
    expect(within(card).getByText(PASSAGE_UZ.quote, { selector: "mark" })).toBeTruthy();
    expect(within(card).getByRole("link").getAttribute("href")).toBe(PASSAGE_UZ.link);
    expect(api.ask).toHaveBeenCalledWith(
      { question: "Penya qachon hisoblanadi?", corpus: "real", document_id: null },
      expect.any(AbortSignal));
    // the question is shown as the user's message
    expect(screen.getByRole("heading", { level: 2, name: /Penya qachon hisoblanadi\?/ })).toBeTruthy();
  });

  it("restricts the question to a document picked in the library", async () => {
    const api = fakeApi();
    renderIn(<App api={api} />);
    const docs = await openLibrary();
    const buttons = await within(docs).findAllByRole("button", { name: "Search only here" });
    await userEvent.click(buttons[0]);
    // back in the workspace, with the scope set and the question box focused
    const scope = screen.getByLabelText("Search in") as HTMLSelectElement;
    expect(scope.value).toBe("namuna-uz");
    expect(document.activeElement).toBe(screen.getByLabelText("Your question"));
    await askQuestion("Ijara haqi?");
    expect(api.ask).toHaveBeenLastCalledWith(expect.objectContaining({ document_id: "namuna-uz" }),
                                             expect.any(AbortSignal));
    expect(await screen.findByText("In: 01.02.2003. Namuna kodeksi")).toBeTruthy();
  });

  it("switches to the synthetic collection and drops a scope from the other one", async () => {
    const api = fakeApi({
      ask: vi.fn(async (req) => ({ ...askResponse(req.question, [PASSAGE_SYNTHETIC]), corpus: "synthetic" })),
    });
    renderIn(<App api={api} />);
    await screen.findByRole("option", { name: "01.02.2003. Namuna kodeksi" });
    await userEvent.selectOptions(screen.getByLabelText("Search in"), "namuna-uz");
    await userEvent.selectOptions(screen.getByLabelText("Collection"), "synthetic");
    expect((screen.getByLabelText("Search in") as HTMLSelectElement).value).toBe("");

    const docs = await openLibrary();
    expect(within(docs).getAllByRole("listitem")).toHaveLength(1);
    await userEvent.click(screen.getByRole("button", { name: "Workspace" }));

    await askQuestion("Шартнома муддати?");
    const card = await screen.findByRole("article", { name: "SINOV SHARTNOMASI (SYNTHETIC)" });
    expect(within(card).getByText("No online source")).toBeTruthy();
    expect(api.ask).toHaveBeenLastCalledWith(
      { question: "Шартнома муддати?", corpus: "synthetic", document_id: null },
      expect.any(AbortSignal));
  });

  it("shows the empty state when no passage is found", async () => {
    renderIn(<App api={fakeApi({ ask: vi.fn(async (req) => askResponse(req.question, [])) })} />, "uz");
    await askQuestion("Mavjud boʻlmagan narsa");
    expect((await screen.findByText(/Hech narsa topilmadi/)).getAttribute("role")).toBe("status");
    expect(screen.queryByRole("article")).toBeNull();
  });

  it("offers to repeat a scoped question over all documents when nothing is found", async () => {
    const ask = vi.fn(async (req: { question: string; document_id?: string | null }) =>
      askResponse(req.question, req.document_id ? [] : [PASSAGE_UZ]));
    renderIn(<App api={fakeApi({ ask })} />);
    await screen.findByRole("option", { name: "Образец договора аренды" });
    await userEvent.selectOptions(screen.getByLabelText("Search in"), "obrazets-ru");
    await askQuestion("Penya?");
    await userEvent.click(await screen.findByRole("button", { name: "Search all documents" }));
    expect(await screen.findByRole("article")).toBeTruthy();
    expect(ask).toHaveBeenLastCalledWith(
      { question: "Penya?", corpus: "real", document_id: null }, expect.any(AbortSignal));
  });

  it("explains a failed question and retries it", async () => {
    const ask = vi.fn()
      .mockRejectedValueOnce(new ApiError("unavailable", 503, "no real documents ingested"))
      .mockImplementation(async (req) => askResponse(req.question, [PASSAGE_UZ]));
    renderIn(<App api={fakeApi({ ask })} />, "ru");
    await askQuestion("Когда платить?");
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("В этой коллекции ещё нет загруженных документов.");
    expect(alert.textContent).toContain("no real documents ingested");

    await userEvent.click(within(alert).getByRole("button", { name: "Повторить" }));
    expect(await screen.findByRole("article")).toBeTruthy();
    expect(ask).toHaveBeenCalledTimes(2);
    expect(ask.mock.calls[1][0].question).toBe("Когда платить?");
    // the retry replaced the failed turn: the question is shown once
    expect(screen.getAllByRole("heading", { level: 2, name: /Когда платить\?/ })).toHaveLength(1);
  });

  it("reports an unreachable API in the status line and the document library", async () => {
    const down = async () => { throw new ApiError("network", null, "Failed to fetch"); };
    const api = fakeApi({ health: vi.fn(down), documents: vi.fn(down) });
    renderIn(<App api={api} />);
    expect(await screen.findByText("API offline")).toBeTruthy();
    const docs = await openLibrary();
    expect(within(docs).getByRole("alert").textContent).toContain("The API cannot be reached");

    (api.documents as ReturnType<typeof vi.fn>).mockResolvedValue(DOCUMENTS);
    (api.health as ReturnType<typeof vi.fn>).mockResolvedValue(HEALTH);
    await userEvent.click(within(docs).getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(within(docs).getAllByRole("listitem")).toHaveLength(2));
    expect(await screen.findByText(/3 documents/)).toBeTruthy();
  });

  it("cancels the request in flight when the page goes away", async () => {
    let signal: AbortSignal | undefined;
    const ask = vi.fn((_req, s?: AbortSignal) => {
      signal = s;
      return new Promise<AskResponse>(() => {}); // never answers
    });
    const { unmount } = renderIn(<App api={fakeApi({ ask })} />);
    await askQuestion("Ijara haqi?");
    expect(screen.getByRole("button", { name: "Searching…" })).toBeTruthy();
    expect(screen.getByText("Searching…").closest("[role=status]")).toBeTruthy();
    expect(signal?.aborted).toBe(false);
    unmount();
    expect(signal?.aborted).toBe(true);
  });

  it("asks an example question from the start screen", async () => {
    const api = fakeApi();
    renderIn(<App api={api} />, "ru");
    await userEvent.click(screen.getByRole("button", { name: "Когда вносится арендная плата?" }));
    expect(api.ask).toHaveBeenCalledWith(
      { question: "Когда вносится арендная плата?", corpus: "real", document_id: null },
      expect.any(AbortSignal));
    expect(await screen.findByRole("article")).toBeTruthy();
  });

  it("shows the answer text only when the API returns one", async () => {
    const llm = vi.fn(async (req: { question: string }) => ({
      ...askResponse(req.question, [PASSAGE_UZ]), mode: "llm" as const,
      answer: "Kechiktirilgan har bir kun uchun penya hisoblanadi.",
      citations: [PASSAGE_UZ],
    }));
    const { unmount } = renderIn(<App api={fakeApi({ ask: llm })} />);
    await askQuestion("Penya?");
    const card = await screen.findByRole("article");
    expect(screen.getByText("Answer")).toBeTruthy();
    expect(screen.getByText("Kechiktirilgan har bir kun uchun penya hisoblanadi.", { selector: "p.answer__text" }))
      .toBeTruthy();
    expect(within(card).getByText("Cited in the answer")).toBeTruthy();
    unmount();

    // extractive mode: passages as search results, no answer text of any kind
    renderIn(<App api={fakeApi()} />);
    await askQuestion("Penya?");
    await screen.findByRole("article");
    expect(screen.queryByText("Answer")).toBeNull();
    expect(document.querySelector(".answer__text")).toBeNull();
    expect(screen.getByText(/This is a search result, not a generated answer or legal advice/)).toBeTruthy();
  });

  it("keeps internal identifiers out of the result and inside the technical details", async () => {
    renderIn(<App api={fakeApi()} />);
    await askQuestion("Penya?");
    const card = await screen.findByRole("article");
    expect(card.textContent).not.toContain(PASSAGE_UZ.chunk_id);
    expect(card.textContent).not.toContain("bm25");
    const tech = screen.getByText("Technical details").closest("details")!;
    expect(tech.open).toBe(false);
    expect(within(tech).getByText(PASSAGE_UZ.chunk_id)).toBeTruthy();
    expect(within(tech).getByText("bm25")).toBeTruthy();
  });

  it("opens a quote in the source viewer with its context and the link to the original", async () => {
    const api = fakeApi();
    renderIn(<App api={api} />);
    await askQuestion("Penya?");
    const card = await screen.findByRole("article");
    await userEvent.click(within(card).getByRole("button", { name: "View in context" }));

    const viewer = screen.getByRole("complementary", { name: "Source" });
    expect(within(viewer).getByRole("heading", { name: "01.02.2003. Namuna kodeksi" })).toBeTruthy();
    expect(within(viewer).getByText("1-modda. Ijara haqi", { selector: "li" })).toBeTruthy();
    expect(await within(viewer).findByText(PASSAGE_UZ.quote, { selector: "mark" })).toBeTruthy();
    // the passages before and after the quoted one are shown too
    expect(within(viewer).getByText(/NAMUNA KODEKSI/)).toBeTruthy();
    expect(within(viewer).getByText(/Taraflar shartnomani bir oy oldin/)).toBeTruthy();
    expect(within(viewer).getByText("Passages 1–3 of 3")).toBeTruthy();
    expect(api.passages).toHaveBeenCalledWith("namuna-uz", { around: PASSAGE_UZ.chunk_id, limit: 7 },
                                              expect.any(AbortSignal));
    const link = within(viewer).getByRole("link", { name: /Open original · lex\.uz/ });
    expect(link.getAttribute("href")).toBe(PASSAGE_UZ.link);
    expect(within(card).getByRole("button", { name: "View in context" }).getAttribute("aria-pressed"))
      .toBe("true");

    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("complementary", { name: "Source" })).toBeNull();
  });

  it("browses the structure of a document and opens a section in the viewer", async () => {
    const api = fakeApi();
    renderIn(<App api={api} />);
    const docs = await openLibrary();
    const structure = await within(docs).findAllByRole("button", { name: "Structure" });
    await userEvent.click(structure[0]);

    const details = screen.getByRole("region", { name: "01.02.2003. Namuna kodeksi" });
    expect(api.outline).toHaveBeenCalledWith("namuna-uz", expect.any(AbortSignal));
    await userEvent.click(await within(details).findByRole("button", { name: "2-modda. Shartnomani bekor qilish" }));
    expect(api.passages).toHaveBeenLastCalledWith("namuna-uz", { start: 2, limit: 7 }, expect.any(AbortSignal));
    const viewer = screen.getByRole("complementary", { name: "Source" });
    expect(await within(viewer).findByText(/Taraflar shartnomani bir oy oldin/)).toBeTruthy();
    expect(viewer.querySelector("mark")).toBeNull(); // nothing is quoted here

    await userEvent.click(within(details).getByRole("button", { name: "Back to the library" }));
    expect(screen.getByRole("region", { name: "Documents" })).toBeTruthy();
  });

  it("keeps the query history in the browser and reopens a session without asking again", async () => {
    const api = fakeApi();
    const { unmount } = renderIn(<App api={api} />);
    const history = screen.getByRole("region", { name: "History" });
    expect(within(history).getByText("Your queries will appear here.")).toBeTruthy();
    expect(within(history).getByText("Saved only in this browser.")).toBeTruthy();

    await askQuestion("Penya qachon hisoblanadi?");
    await screen.findByRole("article");
    await askQuestion("Ijara haqi?");
    await waitFor(() => expect(screen.getAllByRole("article")).toHaveLength(2));
    // one session, titled with its first question
    expect(within(history).getAllByRole("listitem")).toHaveLength(1);

    // (the sidebar and the phone top bar both have this button)
    await userEvent.click(screen.getAllByRole("button", { name: "New query" })[0]);
    expect(screen.queryByRole("article")).toBeNull();
    expect(screen.getByRole("heading", { name: "What do you want to find in the legislation?" })).toBeTruthy();
    unmount();

    // a new page load: the session comes back from localStorage
    renderIn(<App api={api} />);
    const again = screen.getByRole("region", { name: "History" });
    await userEvent.click(within(again).getByRole("button", { name: /^Penya qachon hisoblanadi\?/ }));
    expect(screen.getAllByRole("article")).toHaveLength(2);
    expect(api.ask).toHaveBeenCalledTimes(2);

    await userEvent.click(within(again).getByRole("button", { name: "Delete “Penya qachon hisoblanadi?”" }));
    expect(within(again).queryAllByRole("listitem")).toHaveLength(0);
    expect(screen.queryByRole("article")).toBeNull();
    expect(window.localStorage.getItem("documind.history.v1")).toBeNull();
  });

  it("switches the theme, remembers it, and collapses the sidebar", async () => {
    renderIn(<App api={fakeApi()} />);
    expect(document.documentElement.dataset.theme).toBe("dark"); // the primary theme
    await userEvent.click(screen.getByRole("button", { name: "Light" }));
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(window.localStorage.getItem("documind.theme")).toBe("light");
    expect(screen.getByRole("button", { name: "Light" }).getAttribute("aria-pressed")).toBe("true");

    await userEvent.click(screen.getByRole("button", { name: "Collapse sidebar" }));
    expect(screen.queryByRole("region", { name: "History" })).toBeNull();
    expect(screen.getAllByRole("button", { name: "New query" }).length).toBeGreaterThan(0);
    await userEvent.click(screen.getByRole("button", { name: "Expand sidebar" }));
    expect(screen.getByRole("region", { name: "History" })).toBeTruthy();
  });
});
