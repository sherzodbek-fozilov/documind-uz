import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { renderIn } from "../test/render";
import { PASSAGE_RU, PASSAGE_UZ } from "../test/samples";
import { ResultCard } from "./ResultCard";

describe("ResultCard", () => {
  it("highlights exactly the quote inside the whole passage", () => {
    const { container } = renderIn(<ResultCard passage={PASSAGE_UZ} title="Namuna kodeksi" />);
    const marks = container.querySelectorAll("mark");
    expect(marks).toHaveLength(1);
    expect(marks[0].textContent).toBe(PASSAGE_UZ.quote);
    const p = container.querySelector(".result__passage")!;
    expect(p.textContent).toBe(PASSAGE_UZ.text);
    expect(p.getAttribute("lang")).toBe("uz-Latn");
  });

  it("shows the title, article, chunk and a link to the source anchor", () => {
    renderIn(<ResultCard passage={PASSAGE_UZ} title="Namuna kodeksi" />);
    const card = screen.getByRole("article", { name: "Namuna kodeksi" });
    expect(within(card).getByText("#1")).toBeTruthy();
    expect(within(card).getByText("1-modda. Ijara haqi", { selector: "dd" })).toBeTruthy();
    expect(within(card).getByText("namuna-uz:0001")).toBeTruthy();
    const link = within(card).getByRole("link");
    expect(link.getAttribute("href")).toBe("https://lex.uz/ru/docs/-9999#-103");
    expect(link.getAttribute("rel")).toBe("noopener noreferrer");
    expect(link.textContent).toContain("#-103");
  });

  it("says when there is no online source, and falls back to the document id", () => {
    renderIn(<ResultCard passage={PASSAGE_RU} />, "ru");
    const card = screen.getByRole("article", { name: "obrazets-ru" });
    expect(within(card).queryByRole("link")).toBeNull();
    expect(within(card).getByText("Нет онлайн-источника")).toBeTruthy();
    expect(within(card).getByText("Статья")).toBeTruthy();
  });

  it("never links to a non-http source", () => {
    renderIn(<ResultCard passage={{ ...PASSAGE_UZ, link: "javascript:alert(1)" }} />);
    expect(screen.queryByRole("link")).toBeNull();
  });

  it("shows the quote separately, without a highlight, when it is not in the passage", () => {
    const broken = { ...PASSAGE_UZ, quote: "Bu matn parchada yoʻq.", quote_start: 0, quote_end: 21 };
    const { container } = renderIn(<ResultCard passage={broken} />, "uz");
    expect(container.querySelector("mark")).toBeNull();
    expect(screen.getByRole("note").textContent).toContain("Iqtibos parcha ichida topilmadi");
    expect(container.querySelector("blockquote")!.textContent).toBe("Bu matn parchada yoʻq.");
    expect(container.querySelector(".result__passage")!.textContent).toBe(PASSAGE_UZ.text);
  });

  it("collapses blank lines around the quote but never inside it", () => {
    const text = "1-bob. Ijara\n\n1-modda. Muddat\n\nBirinchi qism.\n\nIkkinchi qism.\n\nOxiri.";
    const quote = "Birinchi qism.\n\nIkkinchi qism.";
    const start = text.indexOf(quote);
    const { container } = renderIn(<ResultCard passage={{ ...PASSAGE_UZ, text, quote,
      quote_start: start, quote_end: start + quote.length }} />);
    expect(container.querySelector("mark")!.textContent).toBe(quote);
    expect(container.querySelector(".result__passage")!.textContent)
      .toBe("1-bob. Ijara\n1-modda. Muddat\nBirinchi qism.\n\nIkkinchi qism.\nOxiri.");
  });
});
