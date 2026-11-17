"""Rebuild the raster favicons from public/favicon.svg.

The SVG is the only source. A headless Chrome or Edge renders it once at 1024 px on a
transparent background, and Pillow scales that down to each size:

    public/favicon.ico          16, 32, 48 px
    public/favicon-32x32.png    32 px
    public/apple-touch-icon.png 180 px, on an opaque background (iOS fills
                                transparency with black and rounds the corners itself)

Usage (from frontend/):  python scripts/favicons.py [path/to/chrome]
Needs Pillow; not part of the npm build, the generated files are committed.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

PUBLIC = Path(__file__).resolve().parent.parent / "public"
MASTER = 1024
BRAND_BG = (124, 140, 255, 255)  # --accent (dark theme), the favicon background

CANDIDATES = [
    "chrome", "google-chrome", "chromium", "msedge",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]


def find_browser(explicit: str | None) -> str:
    for name in [explicit, *CANDIDATES]:
        if not name:
            continue
        found = shutil.which(name) or (name if Path(name).is_file() else None)
        if found:
            return found
    sys.exit("No Chrome/Edge found; pass its path as the first argument.")


def render_master(browser: str, tmp: Path) -> Image.Image:
    svg = (PUBLIC / "favicon.svg").read_text(encoding="utf-8")
    page = tmp / "render.html"
    page.write_text(
        "<!doctype html><html><head><style>html,body{margin:0;background:transparent}"
        f"svg{{display:block;width:{MASTER}px;height:{MASTER}px}}</style></head>"
        f"<body>{svg}</body></html>",
        encoding="utf-8",
    )
    out = tmp / "master.png"
    subprocess.run(
        [browser, "--headless=new", "--disable-gpu", "--hide-scrollbars",
         "--default-background-color=00000000", f"--window-size={MASTER},{MASTER}",
         f"--screenshot={out}", page.as_uri()],
        check=True, capture_output=True,
    )
    image = Image.open(out).convert("RGBA")
    if image.size != (MASTER, MASTER) or image.getpixel((0, 0))[3] != 0:
        sys.exit("Unexpected render: wrong size or no transparency.")
    return image


def scaled(master: Image.Image, size: int) -> Image.Image:
    return master.resize((size, size), Image.Resampling.LANCZOS)


def main() -> None:
    browser = find_browser(sys.argv[1] if len(sys.argv) > 1 else None)
    with tempfile.TemporaryDirectory() as tmp:
        master = render_master(browser, Path(tmp))

    scaled(master, 32).save(PUBLIC / "favicon-32x32.png", optimize=True)

    # each ICO entry is scaled from the master, not from each other
    sizes = [16, 32, 48]
    icons = [scaled(master, s) for s in sizes]
    icons[-1].save(PUBLIC / "favicon.ico", format="ICO", sizes=[(s, s) for s in sizes],
                   append_images=icons[:-1])

    touch = Image.new("RGBA", (180, 180), BRAND_BG)
    touch.alpha_composite(scaled(master, 180))
    touch.convert("RGB").save(PUBLIC / "apple-touch-icon.png", optimize=True)
    print("wrote favicon.ico, favicon-32x32.png, apple-touch-icon.png")


if __name__ == "__main__":
    main()
