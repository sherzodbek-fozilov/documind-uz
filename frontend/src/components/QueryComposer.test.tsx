import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { renderIn } from "../test/render";
import { DOCUMENTS } from "../test/samples";
import { choose, selected } from "../test/select";
import { QueryComposer } from "./QueryComposer";

function setup(over: Partial<Parameters<typeof QueryComposer>[0]> = {}) {
  const props = {
    corpus: "real" as const, onCorpusChange: vi.fn(), documents: DOCUMENTS.slice(0, 2),
    scope: null, onScopeChange: vi.fn(), loading: false, onAsk: vi.fn(), ...over,
  };
  renderIn(<QueryComposer {...props} />);
  return props;
}

describe("QueryComposer", () => {
  it("asks a trimmed Uzbek or Russian question with the button or Enter", async () => {
    const p = setup();
    const box = screen.getByLabelText("Your question");
    const ask = screen.getByRole("button", { name: "Ask" });
    expect((ask as HTMLButtonElement).disabled).toBe(true); // empty question

    await userEvent.type(box, "  Penya qachon hisoblanadi?  ");
    await userEvent.click(ask);
    expect(p.onAsk).toHaveBeenLastCalledWith("Penya qachon hisoblanadi?");
    expect((box as HTMLTextAreaElement).value).toBe(""); // ready for the next question

    await userEvent.clear(box);
    await userEvent.type(box, "Когда вносится плата?{Enter}");
    expect(p.onAsk).toHaveBeenLastCalledWith("Когда вносится плата?");
    expect(p.onAsk).toHaveBeenCalledTimes(2);
  });

  it("keeps Shift+Enter as a new line and does not ask a blank question", async () => {
    const p = setup();
    const box = screen.getByLabelText("Your question") as HTMLTextAreaElement;
    await userEvent.type(box, "   {Enter}");
    await userEvent.type(box, "a{Shift>}{Enter}{/Shift}b");
    expect(p.onAsk).not.toHaveBeenCalled();
    expect(box.value).toBe("   a\nb");
    expect(box.maxLength).toBe(1000);
  });

  it("changes the collection and the document scope", async () => {
    const p = setup();
    expect(selected("Collection")).toBe("Real documents");
    await choose("Collection", "Synthetic (test) documents");
    expect(p.onCorpusChange).toHaveBeenCalledWith("synthetic");

    expect(selected("Search in")).toBe("All documents");
    await userEvent.click(screen.getByRole("combobox", { name: "Search in" }));
    expect(screen.getAllByRole("option").map((o) => o.textContent))
      .toEqual(["All documents", "01.02.2003. Namuna kodeksi", "Образец договора аренды"]);
    await userEvent.click(screen.getByRole("option", { name: "Образец договора аренды" }));
    expect(p.onScopeChange).toHaveBeenLastCalledWith("obrazets-ru");
    expect(screen.queryByRole("option")).toBeNull(); // the list closes after a choice
  });

  it("opens the scope list from the keyboard and lifts the scope", async () => {
    const p = setup({ scope: "obrazets-ru" });
    const scope = screen.getByRole("combobox", { name: "Search in" });
    expect(scope.textContent).toBe("Образец договора аренды");
    scope.focus();
    await userEvent.keyboard("{Enter}");
    expect(screen.getByRole("listbox")).toBeTruthy();
    await userEvent.keyboard("{Home}{Enter}");
    expect(p.onScopeChange).toHaveBeenLastCalledWith(null);
    expect(document.activeElement).toBe(scope); // the focus returns to the control
  });

  it("disables asking while a request is running", async () => {
    const p = setup({ loading: true });
    await userEvent.type(screen.getByLabelText("Your question"), "x{Enter}");
    const busy = screen.getByRole("button", { name: "Searching…" }) as HTMLButtonElement;
    expect(busy.disabled).toBe(true);
    expect(p.onAsk).not.toHaveBeenCalled();
  });

  it("takes the focus when asked to and counts characters near the limit", async () => {
    const props = {
      corpus: "real" as const, onCorpusChange: vi.fn(), documents: [], scope: null,
      onScopeChange: vi.fn(), loading: false, onAsk: vi.fn(),
    };
    const { rerender } = renderIn(<QueryComposer {...props} />);
    const box = screen.getByLabelText("Your question") as HTMLTextAreaElement;
    expect(document.activeElement).not.toBe(box);
    rerender(<QueryComposer {...props} focusKey={1} />);
    expect(document.activeElement).toBe(box);

    expect(screen.queryByText(/\/ 1000/)).toBeNull();
    await userEvent.click(box);
    await userEvent.paste("x".repeat(800));
    expect(screen.getByText("800 / 1000")).toBeTruthy();
  });
});
