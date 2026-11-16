import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { I18nProvider } from "./i18n/context";
import { applyTheme, storedTheme } from "./state/theme";
import "./styles.css";

applyTheme(storedTheme()); // before the first paint

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <I18nProvider>
      <App />
    </I18nProvider>
  </StrictMode>,
);
