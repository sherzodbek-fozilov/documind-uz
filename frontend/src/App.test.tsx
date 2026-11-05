// The whole page against a fake API client with handwritten responses.
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { App } from "./App";
import { ApiError } from "./api/client";
import type { ApiClient } from "./api/client";
import type { AskResponse } from "./api/types";
import { renderIn } from "./test/render";
import { DOCUMENTS, PASSAGE_SYNTHETIC, PASSAGE_UZ, askResponse } from "./test/samples";

const HEALTH = {
  status: "ok" as const, mode: "extractive", retriever: "bm25", documents: 3, chunks: 9, public_demo: false,
};

function fakeApi(over: Partial<ApiClient> = {}): ApiClient {
  return {
    health: vi.fn(async () => HEALTH),
    documents: vi.fn(async () => DOCUMENTS),
    ask: vi.fn(async (req) => askResponse(req.question, [PASSAGE_UZ])),
    ...over,
  };
}

async function askQuestion(text: string) {
  await userEvent.type(screen.getByRole("textbox"), `${text}{Enter}`);
}

describe("App", () => {
  it("shows the API status and the real documents, then answers with a highlighted quote", async () => {
    const api = fakeApi();
    renderIn(<App api={api} />);
    expect(await screen.findByText("3 documents, 9 chunks · extractive · bm25")).toBeTruthy();
    const docs = screen.getByRole("region", { name: "Documents" });
    await waitFor(() => expect(within(docs).getAllByRole("listitem")).toHaveLength(2));
    expect(screen.getByText("Ask a question to see passages with the exact quote highlighted."))
      .toBeTruthy();

    await askQuestion("Penya qachon hisoblanadi?");
    const card = await screen.findByRole("article", { name: "01.02.2003. Namuna kodeksi" });
    expect(within(card).getByText(PASSAGE_UZ.quote, { selector: "mark" })).toBeTruthy();
    expect(within(card).getByRole("link").getAttribute("href")).toBe(PASSAGE_UZ.link);
    expect(api.ask).toHaveBeenCalledWith(
      { question: "Penya qachon hisoblanadi?", corpus: "real", document_id: null },
      expect.any(AbortSignal));
  });

  it("restricts the question to a document picked in the list", async () => {
    const api = fakeApi();
    renderIn(<App api={api} />);
    const docs = await screen.findByRole("region", { name: "Documents" });
    const buttons = await within(docs).findAllByRole("button", { name: "Search only here" });
    await userEvent.click(buttons[0]);
    expect((screen.getByLabelText("Search in") as HTMLSelectElement).value).toBe("namuna-uz");
    await askQuestion("Ijara haqi?");
    expect(api.ask).toHaveBeenLastCalledWith(expect.objectContaining({ document_id: "namuna-uz" }),
                                             expect.any(AbortSignal));
  });

  it("switches to the synthetic collection and drops a scope from the other one", async () => {
    const api = fakeApi({
      ask: vi.fn(async (req) => ({ ...askResponse(req.question, [PASSAGE_SYNTHETIC]), corpus: "synthetic" })),
    });
    renderIn(<App api={api} />);
    await userEvent.selectOptions(await screen.findByLabelText("Search in"), "namuna-uz");
    await userEvent.selectOptions(screen.getByLabelText("Collection"), "synthetic");
    expect((screen.getByLabelText("Search in") as HTMLSelectElement).value).toBe("");
    const docs = screen.getByRole("region", { name: "Documents" });
    expect(within(docs).getAllByRole("listitem")).toHaveLength(1);

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
  });

  it("reports an unreachable API in the status line and the document list", async () => {
    const down = async () => { throw new ApiError("network", null, "Failed to fetch"); };
    const api = fakeApi({ health: vi.fn(down), documents: vi.fn(down) });
    renderIn(<App api={api} />);
    expect(await screen.findByText("API offline")).toBeTruthy();
    const docs = screen.getByRole("region", { name: "Documents" });
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
    expect(signal?.aborted).toBe(false);
    unmount();
    expect(signal?.aborted).toBe(true);
  });
});
