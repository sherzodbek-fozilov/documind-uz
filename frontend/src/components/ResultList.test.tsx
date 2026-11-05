import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { renderIn } from "../test/render";
import { PASSAGE_RU, PASSAGE_UZ, askResponse } from "../test/samples";
import { ResultList } from "./ResultList";

describe("ResultList", () => {
  it("lists the passages in rank order with document titles", () => {
    renderIn(<ResultList response={askResponse("Penya?", [PASSAGE_UZ, PASSAGE_RU])}
                         titles={{ "namuna-uz": "Namuna kodeksi", "obrazets-ru": "Образец договора" }} />);
    expect(screen.getByRole("heading", { level: 2 }).textContent).toBe("Passages for: “Penya?”");
    const titles = screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent);
    expect(titles).toEqual(["Namuna kodeksi", "Образец договора"]);
    expect(screen.getByText(/2 passages/).textContent)
      .toContain("Quotes verified against the source text: 2 of 2");
  });

  it("shows an empty state when nothing is found", () => {
    renderIn(<ResultList response={askResponse("Nima?", [])} titles={{}} />, "ru");
    expect(screen.getByRole("status").textContent).toContain("Ничего не найдено");
    expect(screen.queryByRole("article")).toBeNull();
  });
});
