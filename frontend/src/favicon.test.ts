// The favicons are static files in public/, copied by Vite to the root of the build.
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const root = resolve(__dirname, "..");
const html = readFileSync(resolve(root, "index.html"), "utf-8");

function bytes(name: string): Buffer {
  return readFileSync(resolve(root, "public", name));
}

/** width and height from a PNG's IHDR chunk */
function pngSize(buf: Buffer): [number, number] {
  expect(buf.subarray(1, 4).toString("latin1")).toBe("PNG");
  return [buf.readUInt32BE(16), buf.readUInt32BE(20)];
}

describe("favicons", () => {
  it("are linked from index.html with root-relative paths", () => {
    const links = [...html.matchAll(/<link rel="(icon|apple-touch-icon)" href="([^"]+)"/g)]
      .map((m) => m[2]);
    expect(links).toEqual(["/favicon.ico", "/favicon.svg", "/favicon-32x32.png", "/apple-touch-icon.png"]);
    for (const href of links) expect(existsSync(resolve(root, "public", href.slice(1))), href).toBe(true);
    expect(html).toContain('type="image/svg+xml"');
  });

  it("have the expected formats and sizes", () => {
    const svg = bytes("favicon.svg").toString("utf-8");
    expect(svg).toMatch(/^<svg xmlns="http:\/\/www\.w3\.org\/2000\/svg" viewBox="0 0 32 32">/);
    expect(svg).not.toMatch(/<text|<image|href=/); // pure vector, no text or embedded images

    expect(pngSize(bytes("favicon-32x32.png"))).toEqual([32, 32]);
    expect(pngSize(bytes("apple-touch-icon.png"))).toEqual([180, 180]);

    // ICO header: reserved 0, type 1 (icon), then one 16-byte entry per size
    const ico = bytes("favicon.ico");
    expect(ico.readUInt16LE(0)).toBe(0);
    expect(ico.readUInt16LE(2)).toBe(1);
    const count = ico.readUInt16LE(4);
    const sizes = Array.from({ length: count }, (_, i) => ico[6 + i * 16] || 256).sort((a, b) => a - b);
    expect(sizes).toEqual([16, 32, 48]);
  });
});
