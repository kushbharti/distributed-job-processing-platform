"""Renders the app icons (PNG) from an SVG. Run once; the PNGs are committed.

    uv run python scripts/make_icons.py
"""

from pathlib import Path

import pymupdf

STATIC = Path(__file__).resolve().parents[1] / "app" / "static"

# Full-bleed square: phones and app launchers round or mask the corners themselves.
ICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">
  <rect width="512" height="512" fill="#0E6B6F"/>
  <rect x="136" y="88" width="240" height="336" rx="28" fill="#ECEFF1"/>
  <path d="M184 188h144M184 252h144M184 316h88" stroke="#0E6B6F" stroke-width="24" stroke-linecap="round"/>
</svg>"""


def render(size: int, filename: str) -> None:
    with pymupdf.open(stream=ICON_SVG.encode(), filetype="svg") as document:
        page = document[0]
        zoom = size / page.rect.width
        pixmap = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
        pixmap.save(STATIC / filename)
    print(f"Created {filename} ({size}x{size})")


if __name__ == "__main__":
    render(180, "apple-touch-icon.png")
    render(192, "icon-192.png")
    render(512, "icon-512.png")