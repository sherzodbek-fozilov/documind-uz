import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { renderIn } from "../test/render";
import { PASSAGE_RU, PASSAGE_UZ } from "../test/samples";
import { SourceCard } from "./SourceCard";

describe("SourceCard", () => {
  it("highlights exactly the quote inside the whole passage", () => {
    const { container } = renderIn(<SourceCard passage={PASSAGE_UZ} title="Namuna kodeksi" />);
    const marks = container.querySelectorAll("mark");
    expect(marks).toHaveLength(1);
    expect(marks[0].textContent).toBe(PASSAGE_UZ.quote);
    const p = container.querySelector(".source__text")!;
    expect(p.textContent).toBe(PASSAGE_UZ.text);
    expect(p.getAttribute("lang")).toBe("uz-Latn");
  });

  it("shows the title, the article and a link to the source anchor, but no internal ids", () => {
    renderIn(<SourceCard passage={PASSAGE_UZ} title="Namuna kodeksi" />);
    const card = screen.getByRole("article", { name: "Namuna kodeksi" });
    expect(within(card).getByText("1", { selector: ".source__rank" })).toBeTruthy();
    expect(within(card).getByText("1-modda. Ijara haqi", { selector: ".source__article" })).toBeTruthy();
    expect(card.textContent).not.toContain("namuna-uz:0001");
    const link = within(card).getByRole("link");
    expect(link.getAttribute("href")).toBe("https://lex.uz/ru/docs/-9999#-103");
    expect(link.getAttribute("rel")).toBe("noopener noreferrer");
    expect(link.textContent).toBe("Open original");
  });

  it("says when there is no online source, and falls back to the document id", () => {
    renderIn(<SourceCard passage={PASSAGE_RU} />, "ru");
    const card = screen.getByRole("article", { name: "obrazets-ru" });
    expect(within(card).queryByRole("link")).toBeNull();
    expect(within(card).getByText("Нет онлайн-источника")).toBeTruthy();
    expect(within(card).getByText("Статья:")).toBeTruthy();
  });

  it("never links to a non-http source", () => {
    renderIn(<SourceCard passage={{ ...PASSAGE_UZ, link: "javascript:alert(1)" }} />);
    expect(screen.queryByRole("link")).toBeNull();
  });

  it("shows the quote separately, without a highlight, when it is not in the passage", () => {
    const broken = { ...PASSAGE_UZ, quote: "Bu matn parchada yoʻq.", quote_start: 0, quote_end: 21 };
    const { container } = renderIn(<SourceCard passage={broken} />, "uz");
    expect(container.querySelector("mark")).toBeNull();
    expect(screen.getByRole("note").textContent).toContain("Iqtibos parcha ichida topilmadi");
    expect(container.querySelector("blockquote")!.textContent).toBe("Bu matn parchada yoʻq.");
    expect(container.querySelector(".source__text")!.textContent).toBe(PASSAGE_UZ.text);
  });

  it("collapses blank lines around the quote but never inside it", () => {
    const text = "1-bob. Ijara\n\n1-modda. Muddat\n\nBirinchi qism.\n\nIkkinchi qism.\n\nOxiri.";
    const quote = "Birinchi qism.\n\nIkkinchi qism.";
    const start = text.indexOf(quote);
    const { container } = renderIn(<SourceCard passage={{ ...PASSAGE_UZ, text, quote,
      quote_start: start, quote_end: start + quote.length }} />);
    expect(container.querySelector("mark")!.textContent).toBe(quote);
    expect(container.querySelector(".source__text")!.textContent)
      .toBe("1-bob. Ijara\n1-modda. Muddat\nBirinchi qism.\n\nIkkinchi qism.\nOxiri.");
  });

  it("shows only the closest heading of a heading path", () => {
    renderIn(<SourceCard passage={{ ...PASSAGE_UZ, section_title: "NAMUNA KODEKSI / 1-bob. Ijara / 1-modda. Ijara haqi" }} />);
    expect(screen.getByText("1-modda. Ijara haqi", { selector: ".source__article" })).toBeTruthy();
    expect(screen.queryByText(/1-bob/)).toBeNull();
  });

  it("shortens a long passage around the quote and expands it on request", async () => {
    const before = "Avvalgi gap. ".repeat(60);
    const after = " Keyingi gap.".repeat(60);
    const quote = "Kechiktirilgan har bir kun uchun penya hisoblanadi.";
    const text = `${before}${quote}${after}`;
    const { container } = renderIn(<SourceCard passage={{ ...PASSAGE_UZ, text, quote,
      quote_start: before.length, quote_end: before.length + quote.length }} />);
    const shown = () => container.querySelector(".source__text")!.textContent!;
    expect(shown().length).toBeLessThan(text.length);
    expect(shown()).toContain(quote);

    const toggle = screen.getByRole("button", { name: "Show full passage" });
    expect(toggle.getAttribute("aria-expanded")).toBe("false");
    await userEvent.click(toggle);
    expect(shown()).toBe(text);
    expect(container.querySelector("mark")!.textContent).toBe(quote);
    await userEvent.click(screen.getByRole("button", { name: "Show less" }));
    expect(shown().length).toBeLessThan(text.length);
  });

  it("has no expand button for a passage that is shown in full", () => {
    renderIn(<SourceCard passage={PASSAGE_UZ} />);
    expect(screen.queryByRole("button", { name: "Show full passage" })).toBeNull();
  });

  it("opens the passage in the viewer and copies the exact quote", async () => {
    const onView = vi.fn();
    const writeText = vi.fn(async () => {});
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    renderIn(<SourceCard passage={PASSAGE_UZ} onView={onView} />);
    await userEvent.click(screen.getByRole("button", { name: "View in context" }));
    expect(onView).toHaveBeenCalledWith(PASSAGE_UZ);

    await userEvent.click(screen.getByRole("button", { name: "Copy quote" }));
    expect(writeText).toHaveBeenCalledWith(PASSAGE_UZ.quote);
    expect(await screen.findByText("Copied")).toBeTruthy();
  });

  it("has no viewer button when there is no viewer", () => {
    renderIn(<SourceCard passage={PASSAGE_UZ} />);
    expect(screen.queryByRole("button", { name: "View in context" })).toBeNull();
  });
});
