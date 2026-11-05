import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

// The UI is added in the next step; this entry point only proves the build works.
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <p>DocuMind UZ</p>
  </StrictMode>,
);
