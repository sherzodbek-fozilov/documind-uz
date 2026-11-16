import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../api/client";
import type { ApiClient } from "../api/client";
import type { DocumentOutline } from "../api/types";
import { renderIn } from "../test/render";
import { DOCUMENTS, OUTLINE } from "../test/samples";
import { DocumentDetails } from "./DocumentDetails";

function fakeApi(outline: ApiClient["outline"]): ApiClient {
  const unused = async () => { throw new Error("not used here"); };
  return { health: unused, documents: unused, ask: unused, passages: unused, outline };
}

function setup(outline: ApiClient["outline"], over: Partial<Parameters<typeof DocumentDetails>[0]> = {}) {
  const props = {
    document: DOCUMENTS[0], api: fakeApi(outline), selected: false, onSelect: vi.fn(), onBack: vi.fn(),
    onOpenSection: vi.fn(), ...over,
  };
  renderIn(<DocumentDetails {...props} />);
  return props;
}

describe("DocumentDetails", () => {
  it("shows what is known about the document and its structure", async () => {
    const p = setup(async () => OUTLINE);
    expect(screen.getByRole("status").textContent).toContain("Loading the structure…");
    const details = screen.getByRole("region", { name: "01.02.2003. Namuna kodeksi" });
    expect(within(details).getByText("Edition: 05.06.2026")).toBeTruthy();
    expect(within(details).getByText("Law")).toBeTruthy();
    expect(within(details).getByRole("link").getAttribute("href")).toBe("https://lex.uz/ru/docs/-9999");

    const items = await within(details).findAllByRole("listitem");
    expect(items.map((li) => within(li).getByRole("button").textContent))
      .toEqual(["Untitled section", "1-modda. Ijara haqi", "2-modda. Shartnomani bekor qilish"]);
    expect(within(items[2]).getByText("1-bob. Ijara")).toBeTruthy(); // the headings above it
    expect(within(details).getByText("3 sections")).toBeTruthy();

    await userEvent.click(within(items[1]).getByRole("button"));
    expect(p.onOpenSection).toHaveBeenCalledWith(OUTLINE.sections[1]);
  });

  it("selects the document for the search and goes back", async () => {
    const p = setup(async () => OUTLINE);
    await userEvent.click(screen.getByRole("button", { name: "Search only here" }));
    expect(p.onSelect).toHaveBeenCalledWith("namuna-uz");
    await userEvent.click(screen.getByRole("button", { name: "Back to the library" }));
    expect(p.onBack).toHaveBeenCalledOnce();
  });

  it("filters a long structure by heading", async () => {
    const long: DocumentOutline = {
      document_id: "namuna-uz", n_passages: 12,
      sections: Array.from({ length: 12 }, (_, i) => ({
        idx: i, chunk_id: `namuna-uz:${i}`, title: `${i + 1}-modda. Qoida ${i + 1}`, chapter: 1, n_passages: 1,
      })),
    };
    setup(async () => long);
    const search = await screen.findByRole("searchbox", { name: "Find a section" });
    await userEvent.type(search, "12-modda");
    expect(screen.getAllByRole("listitem")).toHaveLength(1);
    await userEvent.type(search, "x");
    expect(screen.getByText("No sections match.")).toBeTruthy();
  });

  it("reports a failed structure request and retries it", async () => {
    const outline = vi.fn()
      .mockRejectedValueOnce(new ApiError("server", 500, "Internal Server Error"))
      .mockResolvedValue(OUTLINE);
    setup(outline);
    const alert = await screen.findByRole("alert");
    await userEvent.click(within(alert).getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("button", { name: "1-modda. Ijara haqi" })).toBeTruthy();
    expect(outline).toHaveBeenCalledTimes(2);
  });
});
