import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { renderIn } from "../test/render";
import { EXAMPLES, MOBILE_EXAMPLES, WelcomeScreen } from "./WelcomeScreen";

/** Pretend the viewport is a phone (or not) for the (max-width: 640px) query. */
function viewport(phone: boolean) {
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: phone, media: query, onchange: null,
    addEventListener: () => {}, removeEventListener: () => {},
    addListener: () => {}, removeListener: () => {}, dispatchEvent: () => false,
  }));
}

function examples() {
  return screen.getAllByRole("button").filter((b) => b.classList.contains("example"))
    .map((b) => b.textContent);
}

afterEach(() => vi.unstubAllGlobals());

describe("WelcomeScreen", () => {
  it("shows every example and the product facts on wide screens", () => {
    viewport(false);
    renderIn(<WelcomeScreen onExample={() => {}} disabled={false}><form /></WelcomeScreen>);
    expect(examples()).toEqual(EXAMPLES.map((e) => e.text));
    expect(screen.queryByRole("button", { name: "Show more" })).toBeNull();
    expect(screen.getByText("Exact quotes").closest("details")).toBeNull();
  });

  it("shows two examples on a phone and reveals the rest on request", async () => {
    viewport(true);
    renderIn(<WelcomeScreen onExample={() => {}} disabled={false}><form /></WelcomeScreen>, "ru");
    expect(examples()).toEqual(EXAMPLES.slice(0, MOBILE_EXAMPLES).map((e) => e.text));
    const more = screen.getByRole("button", { name: "Показать ещё" });
    expect(more.getAttribute("aria-expanded")).toBe("false");
    await userEvent.click(more);
    expect(examples()).toHaveLength(EXAMPLES.length);
    const less = screen.getByRole("button", { name: "Свернуть" });
    expect(less.getAttribute("aria-expanded")).toBe("true");
    await userEvent.click(less);
    expect(examples()).toHaveLength(MOBILE_EXAMPLES);
  });

  it("folds the product facts into an About section on a phone", () => {
    viewport(true);
    renderIn(<WelcomeScreen onExample={() => {}} disabled={false}><form /></WelcomeScreen>, "uz");
    const about = screen.getByText("DocuMind haqida").closest("details")!;
    expect(about.open).toBe(false);
    expect(about.textContent).toContain("Aniq iqtiboslar");
  });

  it("asks an example question", async () => {
    viewport(true);
    const onExample = vi.fn();
    renderIn(<WelcomeScreen onExample={onExample} disabled={false}><form /></WelcomeScreen>);
    await userEvent.click(screen.getByRole("button", { name: EXAMPLES[1].text }));
    expect(onExample).toHaveBeenCalledWith(EXAMPLES[1].text);
  });
});
