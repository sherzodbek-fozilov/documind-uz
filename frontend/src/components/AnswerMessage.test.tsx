import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { renderIn } from "../test/render";
import { PASSAGE_RU, PASSAGE_UZ, askResponse } from "../test/samples";
import { AnswerMessage } from "./AnswerMessage";

const TITLES = { "namuna-uz": "Namuna kodeksi", "obrazets-ru": "Образец договора" };

describe("AnswerMessage", () => {
  it("lists the passages in rank order with document titles", () => {
    renderIn(<AnswerMessage response={askResponse("Penya?", [PASSAGE_UZ, PASSAGE_RU])} titles={TITLES} />);
    expect(screen.getByRole("region", { name: "Passages for: “Penya?”" })).toBeTruthy();
    const titles = screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent);
    expect(titles).toEqual(["Namuna kodeksi", "Образец договора"]);
    expect(screen.getByText("2 passages")).toBeTruthy();
    expect(screen.getByText("Quotes verified against the source text: 2 of 2")).toBeTruthy();
  });

  it("shows an empty state when nothing is found", () => {
    renderIn(<AnswerMessage response={askResponse("Nima?", [])} titles={{}} />, "ru");
    expect(screen.getByRole("status").textContent).toContain("Ничего не найдено");
    expect(screen.queryByRole("article")).toBeNull();
    expect(screen.queryByRole("button")).toBeNull(); // nothing to widen: the search was not scoped
  });

  it("offers a search over all documents when a scoped search finds nothing", async () => {
    const onSearchAll = vi.fn();
    renderIn(<AnswerMessage response={askResponse("Nima?", [])} titles={{}} onSearchAll={onSearchAll} />);
    await userEvent.click(screen.getByRole("button", { name: "Search all documents" }));
    expect(onSearchAll).toHaveBeenCalledOnce();
  });

  it("presents extractive results as search results, without any answer text", () => {
    const { container } = renderIn(<AnswerMessage response={askResponse("Penya?", [PASSAGE_UZ])} titles={TITLES} />);
    expect(container.querySelector(".answer__text")).toBeNull();
    expect(screen.queryByText("Answer")).toBeNull();
    expect(screen.getByText(/not a generated answer or legal advice/)).toBeTruthy();
    expect(screen.queryByText("Cited in the answer")).toBeNull();
  });

  it("shows the API's answer and marks the passages it cites", () => {
    const response = {
      ...askResponse("Penya?", [PASSAGE_UZ, PASSAGE_RU]), mode: "llm" as const,
      answer: "Kechiktirilgan har bir kun uchun penya hisoblanadi.",
      citations: [PASSAGE_UZ],
      citation_check: { checked: 2, valid: 1, failures: { "quote is not in the chunk": 1 } },
    };
    renderIn(<AnswerMessage response={response} titles={TITLES} />);
    expect(screen.getByText(response.answer, { selector: ".answer__text" })).toBeTruthy();
    expect(screen.getByText(/Check the quotes before relying on it/)).toBeTruthy();
    const cards = screen.getAllByRole("article");
    expect(within(cards[0]).getByText("Cited in the answer")).toBeTruthy();
    expect(within(cards[1]).queryByText("Cited in the answer")).toBeNull();
    expect(screen.getByText("Quotes verified against the source text: 1 of 2")).toBeTruthy();
  });

  it("keeps the mode, retriever and chunk ids in a closed technical panel", () => {
    renderIn(<AnswerMessage response={askResponse("Penya?", [PASSAGE_UZ])} titles={TITLES} />);
    const tech = screen.getByText("Technical details").closest("details")!;
    expect(tech.open).toBe(false);
    expect(within(tech).getByText("extractive")).toBeTruthy();
    expect(within(tech).getByText("bm25")).toBeTruthy();
    expect(within(tech).getByText("namuna-uz:0001")).toBeTruthy();
    expect(within(tech).getByText("1 of 1 valid")).toBeTruthy();
    expect(screen.getByRole("article").textContent).not.toContain("namuna-uz:0001");
  });

  it("copies the quotes with their documents, articles and links", async () => {
    const writeText = vi.fn(async (_text: string) => {});
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    renderIn(<AnswerMessage response={askResponse("Penya?", [PASSAGE_UZ, PASSAGE_RU])} titles={TITLES} />);
    await userEvent.click(screen.getByRole("button", { name: "Copy" }));
    const text = writeText.mock.calls[0][0];
    expect(text).toContain(`1. «${PASSAGE_UZ.quote}»\n— Namuna kodeksi, 1-modda. Ijara haqi\n${PASSAGE_UZ.link}`);
    expect(text).toContain(`2. «${PASSAGE_RU.quote}»\n— Образец договора, Статья 4. Расторжение договора`);
    expect(await screen.findByText("Copied")).toBeTruthy();
  });

  it("says so when the browser refuses to copy", async () => {
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText: async () => { throw new Error("denied"); } }, configurable: true,
    });
    renderIn(<AnswerMessage response={askResponse("Penya?", [PASSAGE_UZ])} titles={TITLES} />);
    await userEvent.click(screen.getByRole("button", { name: "Copy" }));
    expect(await screen.findByText("Could not copy")).toBeTruthy();
  });
});
