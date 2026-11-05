import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ApiError } from "../api/client";
import { renderIn } from "../test/render";
import { ErrorMessage } from "./ErrorMessage";

describe("ErrorMessage", () => {
  it("explains each kind of failure and keeps the server's reason", () => {
    const cases: [ApiError, string][] = [
      [new ApiError("unavailable", 503, "no real documents ingested"), "No documents have been ingested"],
      [new ApiError("not_found", 404, "document 'x' is not in the real corpus"), "not in the selected collection"],
      [new ApiError("invalid", 422, "String should have at most 1000 characters"), "was not accepted"],
      [new ApiError("server", 500, "Internal Server Error"), "returned an error"],
    ];
    for (const [err, text] of cases) {
      const { unmount } = renderIn(<ErrorMessage error={err} />);
      const alert = screen.getByRole("alert");
      expect(alert.textContent).toContain(text);
      expect(alert.textContent).toContain(`Details: ${err.message}`);
      expect(screen.queryByRole("button")).toBeNull();
      unmount();
    }
  });

  it("treats an unexpected error as a server error", () => {
    renderIn(<ErrorMessage error={new Error("boom")} />, "uz");
    expect(screen.getByRole("alert").textContent).toContain("Server xato qaytardi");
  });
});
