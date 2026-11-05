import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../api/client";
import { renderIn } from "../test/render";
import { DOCUMENTS } from "../test/samples";
import { DocumentList } from "./DocumentList";

describe("DocumentList", () => {
  it("lists documents with language, edition, chunk count and source link", () => {
    renderIn(<DocumentList documents={DOCUMENTS} selectedId={null} onSelect={() => {}} />);
    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(3);
    const first = within(items[0]);
    expect(first.getByText("01.02.2003. Namuna kodeksi")).toBeTruthy();
    expect(items[0].textContent).toContain("Edition: 05.06.2026");
    expect(items[0].textContent).toContain("3 chunks");
    expect(first.getByRole("link").getAttribute("href")).toBe("https://lex.uz/ru/docs/-9999");
    // no link for a missing or non-web source
    expect(within(items[1]).queryByRole("link")).toBeNull();
    expect(within(items[2]).queryByRole("link")).toBeNull();
    expect(items[2].textContent).toContain("synthetic");
  });

  it("selects and unselects a document for the search scope", async () => {
    const onSelect = vi.fn();
    const { rerender } = renderIn(
      <DocumentList documents={DOCUMENTS} selectedId={null} onSelect={onSelect} />, "uz");
    const buttons = screen.getAllByRole("button", { name: "Faqat shu yerda qidirish" });
    await userEvent.click(buttons[1]);
    expect(onSelect).toHaveBeenLastCalledWith("obrazets-ru");

    rerender(<DocumentList documents={DOCUMENTS} selectedId="obrazets-ru" onSelect={onSelect} />);
    const selected = screen.getByRole("button", { name: "Tanlangan" });
    expect(selected.getAttribute("aria-pressed")).toBe("true");
    await userEvent.click(selected);
    expect(onSelect).toHaveBeenLastCalledWith(null);
  });

  it("shows loading, empty and error states", async () => {
    const { rerender } = renderIn(
      <DocumentList documents={null} selectedId={null} onSelect={() => {}} />, "ru");
    expect(screen.getByRole("status").textContent).toBe("Загрузка документов…");

    rerender(<DocumentList documents={[]} selectedId={null} onSelect={() => {}} />);
    expect(screen.getByRole("status").textContent).toContain("documind ingest");

    const onRetry = vi.fn();
    rerender(<DocumentList documents={null} selectedId={null} onSelect={() => {}}
                           error={new ApiError("network", null, "Failed to fetch")}
                           onRetry={onRetry} />);
    const alert = screen.getByRole("alert");
    expect(alert.textContent).toContain("API недоступен");
    expect(alert.textContent).not.toContain("Failed to fetch");
    await userEvent.click(within(alert).getByRole("button", { name: "Повторить" }));
    expect(onRetry).toHaveBeenCalledOnce();
  });
});
