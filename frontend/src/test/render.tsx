import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { I18nProvider } from "../i18n/context";
import type { Lang } from "../i18n/messages";

/** Render inside the i18n provider; `rerender` keeps the provider and the language. */
export function renderIn(ui: ReactElement, lang: Lang = "en") {
  const wrap = (el: ReactElement) => <I18nProvider lang={lang}>{el}</I18nProvider>;
  const result = render(wrap(ui));
  return { ...result, rerender: (el: ReactElement) => result.rerender(wrap(el)) };
}
