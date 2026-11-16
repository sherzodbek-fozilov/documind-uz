import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../api/client";
import type { ApiClient } from "../api/client";
import { renderIn } from "../test/render";
import { DOCUMENTS, DOC_PASSAGES, OUTLINE, PASSAGE_RU, PASSAGE_UZ, passagesWindow } from "../test/samples";
import { SourceViewer } from "./SourceViewer";

function fakeApi(passages: ApiClient["passages"]): ApiClient {
  const unused = async () => { throw new Error("not used by the viewer"); };
  return { health: unused, documents: unused, ask: unused, outline: async () => OUTLINE, passages };
}

const CITED = { documentId: "namuna-uz", passage: PASSAGE_UZ, startIdx: 0 };

describe("SourceViewer", () => {
  it("shows the cited passage in its context, with the exact quote highlighted", async () => {
    const passages = vi.fn(async (_id, win) => passagesWindow(win));
    const { container } = renderIn(
      <SourceViewer target={CITED} document={DOCUMENTS[0]} api={fakeApi(passages)} onClose={() => {}} />);
    expect(screen.getByRole("status").textContent).toContain("Loading the text…");

    const mark = await screen.findByText(PASSAGE_UZ.quote, { selector: "mark" });
    expect(container.querySelectorAll("mark")).toHaveLength(1);
    const cited = mark.closest("section")!;
    expect(cited.textContent).toBe(PASSAGE_UZ.text); // the passage text is not altered
    expect(cited.getAttribute("aria-label")).toBe("Quoted passage");
    expect(container.querySelectorAll(".viewer__passage")).toHaveLength(3);

    expect(screen.getByText("Edition: 05.06.2026")).toBeTruthy();
    expect(screen.getByText("Uzbek (Latin)")).toBeTruthy();
    expect(screen.getByText("Beginning of the document")).toBeTruthy();
    expect(screen.getByText("End of the document")).toBeTruthy();
    const link = screen.getByRole("link");
    expect(link.getAttribute("href")).toBe("https://lex.uz/ru/docs/-9999#-103");
    expect(link.getAttribute("rel")).toBe("noopener noreferrer");
  });

  it("loads earlier and later text on request", async () => {
    // a window of one passage, as for a long document
    const passages = vi.fn(async (_id, win) => passagesWindow({ ...win, limit: win?.around ? 1 : win?.limit }));
    const { container } = renderIn(
      <SourceViewer target={CITED} document={DOCUMENTS[0]} api={fakeApi(passages)} onClose={() => {}} />);
    await screen.findByText(PASSAGE_UZ.quote, { selector: "mark" });
    expect(screen.getByText("Passages 2–2 of 3")).toBeTruthy();
    const texts = () => [...container.querySelectorAll(".viewer__passage")].map((s) => s.textContent);

    await userEvent.click(screen.getByRole("button", { name: "Show earlier text" }));
    await waitFor(() => expect(texts()).toEqual([DOC_PASSAGES[0].text, PASSAGE_UZ.text]));
    expect(passages).toHaveBeenLastCalledWith("namuna-uz", { start: 0, limit: 1 });
    expect(screen.queryByRole("button", { name: "Show earlier text" })).toBeNull();

    await userEvent.click(screen.getByRole("button", { name: "Show later text" }));
    await waitFor(() => expect(texts()).toEqual(DOC_PASSAGES.map((p) => p.text)));
    expect(passages).toHaveBeenLastCalledWith("namuna-uz", { start: 2, limit: 6 });
    expect(screen.getByText("Passages 1–3 of 3")).toBeTruthy();
    expect(container.querySelectorAll("mark")).toHaveLength(1);
  });

  it("shows only the cited passage, and says so, when the server has no document text", async () => {
    const passages = vi.fn(async () => { throw new ApiError("not_found", 404, "Not Found"); });
    const { container } = renderIn(
      <SourceViewer target={{ documentId: "obrazets-ru", passage: PASSAGE_RU, startIdx: 0 }}
                    document={DOCUMENTS[1]} api={fakeApi(passages)} onClose={() => {}} />, "ru");
    expect((await screen.findByRole("note")).textContent).toContain("Можно показать только этот фрагмент");
    expect(container.querySelector("mark")!.textContent).toBe(PASSAGE_RU.quote);
    expect(container.querySelectorAll(".viewer__passage")).toHaveLength(1);
    expect(screen.queryByRole("button", { name: "Показать текст выше" })).toBeNull();
    expect(screen.queryByRole("link")).toBeNull(); // this document has no online source
  });

  it("opens a section without a highlight, and reports a failure with a retry", async () => {
    const passages = vi.fn()
      .mockRejectedValueOnce(new ApiError("network", null, "Failed to fetch"))
      .mockImplementation(async (_id, win) => passagesWindow(win));
    const { container } = renderIn(
      <SourceViewer target={{ documentId: "namuna-uz", passage: null, startIdx: 2 }}
                    document={DOCUMENTS[0]} api={fakeApi(passages)} onClose={() => {}} />);
    const alert = await screen.findByRole("alert");
    await userEvent.click(within(alert).getByRole("button", { name: "Try again" }));
    expect(await screen.findByText(/Taraflar shartnomani/)).toBeTruthy();
    expect(container.querySelector("mark")).toBeNull();
    expect(passages).toHaveBeenLastCalledWith("namuna-uz", { start: 2, limit: 7 }, expect.any(AbortSignal));
    // the heading path of the section, closest heading last
    expect(screen.getAllByRole("listitem").map((li) => li.textContent))
      .toEqual(["1-bob. Ijara", "2-modda. Shartnomani bekor qilish"]);
    expect(screen.getByRole("link").getAttribute("href")).toBe("https://lex.uz/ru/docs/-9999");
  });

  it("closes, and limits the search to the document", async () => {
    const onClose = vi.fn();
    const onSearchHere = vi.fn();
    renderIn(<SourceViewer target={CITED} document={DOCUMENTS[0]} onClose={onClose} onSearchHere={onSearchHere}
                           api={fakeApi(async (_id, win) => passagesWindow(win))} />);
    const close = screen.getByRole("button", { name: "Close source viewer" });
    expect(document.activeElement).toBe(close);
    await userEvent.click(screen.getByRole("button", { name: "Search only here" }));
    expect(onSearchHere).toHaveBeenCalledWith("namuna-uz");
    await userEvent.click(close);
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("never links to a non-http source", async () => {
    renderIn(<SourceViewer target={{ ...CITED, passage: { ...PASSAGE_UZ, link: "javascript:alert(1)" } }}
                           document={{ ...DOCUMENTS[0], source: "file:///etc/passwd" }} onClose={() => {}}
                           api={fakeApi(async (_id, win) => passagesWindow(win))} />);
    await screen.findByText(PASSAGE_UZ.quote, { selector: "mark" });
    expect(screen.queryByRole("link")).toBeNull();
  });
});
