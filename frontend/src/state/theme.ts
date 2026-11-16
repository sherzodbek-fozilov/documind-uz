import { useCallback, useEffect, useState } from "react";

// Dark is the primary theme; "system" follows the OS setting.
export const THEMES = ["dark", "light", "system"] as const;
export type ThemeChoice = (typeof THEMES)[number];

const STORAGE_KEY = "documind.theme";
const DARK_QUERY = "(prefers-color-scheme: dark)";

function isTheme(value: unknown): value is ThemeChoice {
  return typeof value === "string" && (THEMES as readonly string[]).includes(value);
}

export function storedTheme(): ThemeChoice {
  try {
    const v = window.localStorage.getItem(STORAGE_KEY);
    return isTheme(v) ? v : "dark";
  } catch {
    return "dark";
  }
}

function systemPrefersDark(): boolean {
  return typeof window.matchMedia === "function" ? window.matchMedia(DARK_QUERY).matches : true;
}

export function resolveTheme(choice: ThemeChoice): "dark" | "light" {
  if (choice !== "system") return choice;
  return systemPrefersDark() ? "dark" : "light";
}

/** Set <html data-theme>; the stylesheet has one set of colors per value. */
export function applyTheme(choice: ThemeChoice): void {
  document.documentElement.dataset.theme = resolveTheme(choice);
}

export function useTheme(): [ThemeChoice, (next: ThemeChoice) => void] {
  const [choice, setChoice] = useState<ThemeChoice>(storedTheme);

  useEffect(() => {
    applyTheme(choice);
    if (choice !== "system" || typeof window.matchMedia !== "function") return;
    const media = window.matchMedia(DARK_QUERY);
    const onChange = () => applyTheme("system");
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, [choice]);

  const set = useCallback((next: ThemeChoice) => {
    setChoice(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // storage can be blocked; the choice then lasts until the page is closed
    }
  }, []);

  return [choice, set];
}
