// The phone start screen centres its content in the dynamic viewport, and keeps the
// composer above the on-screen keyboard. That needs the viewport meta below; the layout
// itself is CSS (checked in a browser, jsdom has no layout).
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const root = resolve(__dirname, "..");
const html = readFileSync(resolve(root, "index.html"), "utf-8");
const css = readFileSync(resolve(root, "src", "styles.css"), "utf-8");

describe("mobile viewport", () => {
  it("resizes the layout for the keyboard and allows safe-area insets", () => {
    const content = html.match(/<meta name="viewport" content="([^"]+)"/)?.[1] ?? "";
    const parts = content.split(",").map((s) => s.trim());
    expect(parts).toEqual(expect.arrayContaining([
      "width=device-width", "initial-scale=1.0", "viewport-fit=cover", "interactive-widget=resizes-content",
    ]));
    expect(content).not.toMatch(/user-scalable=no|maximum-scale/); // zoom stays available
  });

  it("sizes the shell with dynamic viewport units, with a fallback, and pads for insets", () => {
    expect(css).toMatch(/height: 100vh;\s*height: 100dvh;/);
    for (const inset of ["top", "bottom", "left", "right"]) {
      expect(css).toContain(`env(safe-area-inset-${inset})`);
    }
  });
});
