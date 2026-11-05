import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
import { I18nProvider, useI18n } from "../i18n/context";
import { LanguageSwitch } from "./LanguageSwitch";

function Label() {
  return <p data-testid="label">{useI18n().t("ask.label")}</p>;
}

afterEach(() => window.localStorage.clear());

describe("LanguageSwitch", () => {
  it("switches every label, sets <html lang> and remembers the choice", async () => {
    render(<I18nProvider lang="uz"><LanguageSwitch /><Label /></I18nProvider>);
    expect(screen.getByTestId("label").textContent).toBe("Savolingiz");
    expect(document.documentElement.lang).toBe("uz");

    await userEvent.click(screen.getByRole("button", { name: "RU" }));
    expect(screen.getByTestId("label").textContent).toBe("Ваш вопрос");
    expect(screen.getByRole("button", { name: "RU" }).getAttribute("aria-pressed")).toBe("true");
    expect(document.documentElement.lang).toBe("ru");

    await userEvent.click(screen.getByRole("button", { name: "EN" }));
    expect(screen.getByTestId("label").textContent).toBe("Your question");
    expect(window.localStorage.getItem("documind.lang")).toBe("en");
  });

  it("starts from the remembered language", () => {
    window.localStorage.setItem("documind.lang", "ru");
    render(<I18nProvider><Label /></I18nProvider>);
    expect(screen.getByTestId("label").textContent).toBe("Ваш вопрос");
  });

  it("ignores an unknown remembered value", () => {
    window.localStorage.setItem("documind.lang", "de");
    render(<I18nProvider><Label /></I18nProvider>);
    // jsdom reports navigator.languages = ["en-US", "en"]
    expect(screen.getByTestId("label").textContent).toBe("Your question");
  });
});
