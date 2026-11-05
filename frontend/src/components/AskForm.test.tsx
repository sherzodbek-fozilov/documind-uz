import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { renderIn } from "../test/render";
import { DOCUMENTS } from "../test/samples";
import { AskForm } from "./AskForm";

function setup(over: Partial<Parameters<typeof AskForm>[0]> = {}) {
  const props = {
    corpus: "real" as const, onCorpusChange: vi.fn(), documents: DOCUMENTS.slice(0, 2),
    scope: null, onScopeChange: vi.fn(), loading: false, onAsk: vi.fn(), ...over,
  };
  renderIn(<AskForm {...props} />);
  return props;
}

describe("AskForm", () => {
  it("asks a trimmed Uzbek or Russian question with the button or Enter", async () => {
    const p = setup();
    const box = screen.getByLabelText("Your question");
    const ask = screen.getByRole("button", { name: "Ask" });
    expect((ask as HTMLButtonElement).disabled).toBe(true); // empty question

    await userEvent.type(box, "  Penya qachon hisoblanadi?  ");
    await userEvent.click(ask);
    expect(p.onAsk).toHaveBeenLastCalledWith("Penya qachon hisoblanadi?");

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
    await userEvent.selectOptions(screen.getByLabelText("Collection"), "synthetic");
    expect(p.onCorpusChange).toHaveBeenCalledWith("synthetic");
    const scope = screen.getByLabelText("Search in");
    expect([...scope.querySelectorAll("option")].map((o) => o.textContent))
      .toEqual(["All documents", "01.02.2003. Namuna kodeksi", "Образец договора аренды"]);
    await userEvent.selectOptions(scope, "obrazets-ru");
    expect(p.onScopeChange).toHaveBeenLastCalledWith("obrazets-ru");
  });

  it("disables asking while a request is running", async () => {
    const p = setup({ loading: true });
    await userEvent.type(screen.getByLabelText("Your question"), "x{Enter}");
    const busy = screen.getByRole("button", { name: "Searching…" }) as HTMLButtonElement;
    expect(busy.disabled).toBe(true);
    expect(p.onAsk).not.toHaveBeenCalled();
  });
});
