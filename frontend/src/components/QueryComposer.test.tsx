import { fireEvent, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { renderIn } from "../test/render";
import { DOCUMENTS } from "../test/samples";
import { choose, selected } from "../test/select";
import { QueryComposer } from "./QueryComposer";

function setup(over: Partial<Parameters<typeof QueryComposer>[0]> = {}) {
  const props = {
    documents: DOCUMENTS.slice(0, 2),
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

  it("changes the document scope and has no collection switch", async () => {
    const p = setup();
    expect(screen.queryByRole("combobox", { name: "Collection" })).toBeNull();
    expect(screen.getAllByRole("combobox")).toHaveLength(1);

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

  it.each([
    ["ru", "О чём хотите спросить?"],
    ["en", "What would you like to ask?"],
    ["uz", "Nima haqida soʻramoqchisiz?"],
  ] as const)("has a short placeholder in %s", (lang, text) => {
    renderIn(<QueryComposer documents={[]} scope={null} onScopeChange={vi.fn()} loading={false}
                            onAsk={vi.fn()} />, lang);
    expect(screen.getByPlaceholderText(text)).toBeTruthy();
  });

  it("puts the question, then the scope, then the send button in one row", () => {
    setup({ scope: "obrazets-ru" });
    const row = document.querySelector(".composer__box")!;
    expect([...row.children].map((el) => el.className.split(" ")[0]))
      .toEqual(["visually-hidden", "composer__input", "composer__scope", "composer__send"]);
    // keyboard order follows the visual order
    const focusable = [...row.querySelectorAll("textarea, button")];
    expect(focusable.map((el) => el.getAttribute("aria-label") ?? el.tagName))
      .toEqual(["TEXTAREA", "Search in", "Ask"]);
    // the scope keeps an accessible name and a tooltip saying what is selected
    const scope = screen.getByRole("combobox", { name: "Search in" });
    expect(scope.getAttribute("title")).toBe("Search in: Образец договора аренды");
  });

  it("keeps a multiline question and the text when the scope changes", async () => {
    const p = setup();
    const box = screen.getByLabelText("Your question") as HTMLTextAreaElement;
    expect(box.rows).toBe(1);
    await userEvent.type(box, "Birinchi qator{Shift>}{Enter}{/Shift}ikkinchi qator");
    expect(box.value).toBe("Birinchi qator\nikkinchi qator");
    await choose("Search in", "Образец договора аренды");
    expect(p.onScopeChange).toHaveBeenLastCalledWith("obrazets-ru");
    expect(box.value).toBe("Birinchi qator\nikkinchi qator");
    await userEvent.type(box, "{Enter}");
    expect(p.onAsk).toHaveBeenCalledWith("Birinchi qator\nikkinchi qator");
  });

  it("keeps a long unbroken word as typed (the stylesheet wraps it)", async () => {
    const p = setup();
    const box = screen.getByLabelText("Your question") as HTMLTextAreaElement;
    const word = "Oʻzbekistonrespublikasiningfuqarolikkodeksiningikkinchiqismi".repeat(3);
    await userEvent.click(box);
    await userEvent.paste(word);
    expect(box.value).toBe(word);
    expect(box.getAttribute("wrap")).toBeNull(); // default soft wrapping, no "off"
    await userEvent.keyboard("{Enter}");
    expect(p.onAsk).toHaveBeenCalledWith(word);
  });

  it("does not send while an input method is composing", () => {
    const p = setup();
    const box = screen.getByLabelText("Your question") as HTMLTextAreaElement;
    fireEvent.change(box, { target: { value: "Ijara" } });
    fireEvent.keyDown(box, { key: "Enter", isComposing: true });
    expect(p.onAsk).not.toHaveBeenCalled();
    fireEvent.keyDown(box, { key: "Enter" });
    expect(p.onAsk).toHaveBeenCalledWith("Ijara");
  });

  it("takes the focus when asked to and counts characters near the limit", async () => {
    const props = {
      documents: [], scope: null,
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
