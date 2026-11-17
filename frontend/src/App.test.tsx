// The whole page against a fake API client with handwritten responses.
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { App } from "./App";
import { ApiError } from "./api/client";
import type { ApiClient } from "./api/client";
import type { AskResponse } from "./api/types";
import { renderIn } from "./test/render";
import { DOCUMENTS, OUTLINE, PASSAGE_UZ, askResponse, passagesWindow } from "./test/samples";
import { choose, selected } from "./test/select";

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
  it("shows the real documents without an API status, then answers with a highlighted quote", async () => {
    const api = fakeApi();
    renderIn(<App api={api} />);
    await waitFor(() => expect(api.health).toHaveBeenCalled());
    // normal connectivity is not displayed anywhere
    expect(screen.queryByText(/API/)).toBeNull();
    expect(screen.queryByText(/3 documents, 9 chunks/)).toBeNull();
    expect(screen.queryByRole("alert")).toBeNull();
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
    expect(selected("Search in")).toBe("01.02.2003. Namuna kodeksi");
    expect(document.activeElement).toBe(screen.getByLabelText("Your question"));
    await askQuestion("Ijara haqi?");
    expect(api.ask).toHaveBeenLastCalledWith(expect.objectContaining({ document_id: "namuna-uz" }),
                                             expect.any(AbortSignal));
    expect(await screen.findByText("In: 01.02.2003. Namuna kodeksi")).toBeTruthy();
  });

  it("always searches the real corpus and never offers the synthetic test documents", async () => {
    const api = fakeApi();
    renderIn(<App api={api} />);
    // no collection switch, in the composer or in the library
    expect(screen.queryByRole("combobox", { name: "Collection" })).toBeNull();
    await waitFor(() => expect(api.documents).toHaveBeenCalled());
    await userEvent.click(screen.getByRole("combobox", { name: "Search in" }));
    expect((await screen.findAllByRole("option")).map((o) => o.textContent))
      .toEqual(["All documents", "01.02.2003. Namuna kodeksi", "Образец договора аренды"]);
    await userEvent.keyboard("{Escape}");

    const docs = await openLibrary();
    await waitFor(() => expect(within(docs).getAllByRole("listitem")).toHaveLength(2));
    expect(docs.textContent).not.toMatch(/synthetic|SINOV/i);
    expect(within(docs).queryByRole("combobox", { name: "Collection" })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Workspace" }));

    await askQuestion("Шартнома муддати?");
    await screen.findByRole("article");
    expect(api.ask).toHaveBeenLastCalledWith(
      { question: "Шартнома муддати?", corpus: "real", document_id: null },
      expect.any(AbortSignal));
  });

  it("asks the real corpus when retrying a turn saved with another corpus", async () => {
    window.localStorage.setItem("documind.history.v1", JSON.stringify([{
      id: "old", title: "Eski savol", updatedAt: 1,
      turns: [{ id: "t1", question: "Eski savol", corpus: "synthetic", documentId: null,
                response: askResponse("Eski savol", []) }],
    }]));
    const ask = vi.fn()
      .mockRejectedValueOnce(new ApiError("server", 500, "boom"))
      .mockImplementation(async (req) => askResponse(req.question, [PASSAGE_UZ]));
    renderIn(<App api={fakeApi({ ask })} />);
    const history = screen.getByRole("region", { name: "History" });
    await userEvent.click(within(history).getByRole("button", { name: /^Eski savol/ }));
    await askQuestion("Yangi savol");
    const alert = await screen.findByRole("alert");
    await userEvent.click(within(alert).getByRole("button", { name: "Try again" }));
    await screen.findByRole("article");
    for (const call of ask.mock.calls) expect(call[0].corpus).toBe("real");
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
    await choose("Search in", "Образец договора аренды");
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

  it("reports an unreachable service with a notice that goes away once it is back", async () => {
    const down = async () => { throw new ApiError("network", null, "Failed to fetch"); };
    const api = fakeApi({ health: vi.fn(down), documents: vi.fn(down) });
    renderIn(<App api={api} />, "ru");
    const text = await screen.findByText("Сервис временно недоступен. Попробуйте ещё раз чуть позже.");
    const notice = text.closest("[role=alert]") as HTMLElement;
    expect(notice).toBeTruthy();

    (api.documents as ReturnType<typeof vi.fn>).mockResolvedValue(DOCUMENTS);
    (api.health as ReturnType<typeof vi.fn>).mockResolvedValue(HEALTH);
    await userEvent.click(within(notice).getByRole("button", { name: "Повторить" }));
    // back to normal: nothing about the connection is shown
    await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
  });

  it("explains an unreachable API in the document library and retries", async () => {
    const down = async () => { throw new ApiError("network", null, "Failed to fetch"); };
    const api = fakeApi({ health: vi.fn(down), documents: vi.fn(down) });
    renderIn(<App api={api} />);
    const docs = await openLibrary();
    expect(within(docs).getByRole("alert").textContent).toContain("The API cannot be reached");

    (api.documents as ReturnType<typeof vi.fn>).mockResolvedValue(DOCUMENTS);
    (api.health as ReturnType<typeof vi.fn>).mockResolvedValue(HEALTH);
    await userEvent.click(within(docs).getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(within(docs).getAllByRole("listitem")).toHaveLength(2));
    await waitFor(() => expect(screen.queryByText(/temporarily unavailable/)).toBeNull());
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

  it.each([
    ["en", "Technical details"],
    ["ru", "Техническая информация"],
    ["uz", "Texnik maʼlumot"],
  ] as const)("shows no technical panel or internal details in the results (%s)", async (lang, title) => {
    renderIn(<App api={fakeApi()} />, lang);
    await askQuestion("Penya?");
    await screen.findByRole("article");
    const results = document.querySelector(".chat__thread")!;
    expect(screen.queryByText(title)).toBeNull();
    expect(results.querySelector("details")).toBeNull();
    for (const internal of [PASSAGE_UZ.chunk_id, "bm25", "extractive", "real"]) {
      expect(results.textContent).not.toContain(internal);
    }
    // what users need is still there
    expect(within(results as HTMLElement).getByRole("link").getAttribute("href")).toBe(PASSAGE_UZ.link);
    expect(results.querySelector("mark")?.textContent).toBe(PASSAGE_UZ.quote);
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
    // empty: exactly one sentence
    expect(history.querySelectorAll("p")).toHaveLength(1);
    expect(within(history).getByText("Your history will appear after your first query")).toBeTruthy();

    await askQuestion("Penya qachon hisoblanadi?");
    await screen.findByRole("article");
    await askQuestion("Ijara haqi?");
    await waitFor(() => expect(screen.getAllByRole("article")).toHaveLength(2));
    // one session, titled with its first question; the empty-state message is gone
    expect(within(history).getAllByRole("listitem")).toHaveLength(1);
    expect(within(history).queryByText("Your history will appear after your first query")).toBeNull();
    expect(within(history).queryByText(/browser/)).toBeNull();

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
    expect(window.localStorage.getItem("documind.sidebar.collapsed")).toBe("1");
    await userEvent.click(screen.getByRole("button", { name: "Open sidebar" }));
    expect(screen.getByRole("region", { name: "History" })).toBeTruthy();
  });

  it("keeps the results, history and scope while the sidebar collapses and expands", async () => {
    const api = fakeApi();
    renderIn(<App api={api} />);
    await choose("Search in", "Образец договора аренды");
    await askQuestion("Penya?");
    await screen.findByRole("article");

    await userEvent.click(screen.getByRole("button", { name: "Collapse sidebar" }));
    // the rail navigates with the same handlers
    const rail = screen.getByRole("complementary", { name: "DocuMind UZ" });
    await userEvent.click(within(rail).getByRole("button", { name: "Document library" }));
    expect(await screen.findByRole("region", { name: "Documents" })).toBeTruthy();
    const workspace = within(rail).getByRole("button", { name: "Workspace" });
    workspace.focus();
    await userEvent.keyboard("{Enter}");
    expect(workspace.getAttribute("aria-current")).toBe("page");
    expect(screen.getByRole("article")).toBeTruthy(); // the results are still there

    await userEvent.click(within(rail).getByRole("button", { name: "Open sidebar" }));
    const history = screen.getByRole("region", { name: "History" });
    expect(within(history).getAllByRole("listitem")).toHaveLength(1);
    expect(selected("Search in")).toBe("Образец договора аренды");
    expect(api.ask).toHaveBeenCalledTimes(1);
    expect(api.ask).toHaveBeenCalledWith(
      { question: "Penya?", corpus: "real", document_id: "obrazets-ru" }, expect.any(AbortSignal));
  });
});
