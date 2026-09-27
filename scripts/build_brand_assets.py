"""Build the NiceBank brand assets from the logo source image (docs/brand/nicebank-logo-source.jpg).

Finds the burgundy app-icon symbol (rounded square with the N, chip and shield) in the light version, crops it,
restores transparent rounded corners and writes every size the product uses:

- frontend/public/brand/  favicon-32.png, apple-touch-icon.png (180), nicebank-mark-512.png
- infra/keycloak/themes/nicebank/login/resources/img/nicebank-mark.png (128) for the login theme
- backend/internal/notify/assets/nicebank-mark.png (96) embedded in emails as an inline image

Usage: poetry run python scripts/build_brand_assets.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "brand" / "nicebank-logo-source.jpg"
CORNER = 0.19  # corner radius of the symbol, as a share of its side (measured on the source)
OUTPUTS = {
    ROOT / "frontend" / "public" / "brand" / "favicon-32.png": 32,
    ROOT / "frontend" / "public" / "brand" / "apple-touch-icon.png": 180,
    ROOT / "frontend" / "public" / "brand" / "nicebank-mark-512.png": 512,
    ROOT / "infra" / "keycloak" / "themes" / "nicebank" / "login" / "resources" / "img" / "nicebank-mark.png": 128,
    ROOT / "backend" / "internal" / "notify" / "assets" / "nicebank-mark.png": 96,
}


def is_burgundy(px: tuple[int, int, int]) -> bool:
    r, g, b = px
    return r > 90 and r - g > 55 and r - b > 25 and g < 70


def find_symbol(img: Image.Image, step: int = 3) -> tuple[int, int, int, int]:
    """Bounding box of the burgundy square: the connected burgundy region holding the leftmost burgundy pixel
    of the light version (the "Nice" wordmark next to it is a separate region)."""
    w, h = img.size
    px = img.load()
    gw, gh = w // step, int(h * 0.62) // step
    grid = [[is_burgundy(px[x * step, y * step]) for x in range(gw)] for y in range(gh)]
    start = next(((x, y) for x in range(gw) for y in range(gh) if grid[y][x]), None)
    if start is None:
        raise SystemExit("symbol not found in the source image")
    seen, stack = {start}, [start]
    while stack:
        x, y = stack.pop()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < gw and 0 <= ny < gh and (nx, ny) not in seen and grid[ny][nx]:
                seen.add((nx, ny))
                stack.append((nx, ny))
    xs, ys = [p[0] for p in seen], [p[1] for p in seen]
    left, top, right, bottom = min(xs) * step, min(ys) * step, (max(xs) + 1) * step, (max(ys) + 1) * step
    side = max(right - left, bottom - top)  # force a square
    return left, top, left + side, top + side


def rounded_mask(size: int, radius: int, scale: int = 4) -> Image.Image:
    big = Image.new("L", (size * scale, size * scale), 0)
    ImageDraw.Draw(big).rounded_rectangle((0, 0, size * scale - 1, size * scale - 1), radius=radius * scale, fill=255)
    return big.resize((size, size), Image.LANCZOS)


def main() -> None:
    img = Image.open(SOURCE).convert("RGB")
    box = find_symbol(img)
    symbol = img.crop(box).convert("RGBA")
    side = symbol.width
    # Slightly inset the mask so light JPEG fringe pixels at the corners are dropped.
    inset = max(2, side // 120)
    symbol = symbol.crop((inset, inset, side - inset, side - inset))
    side = symbol.width
    symbol.putalpha(rounded_mask(side, int(side * CORNER)))
    print(f"symbol found at {box}, {side}px")
    for path, size in OUTPUTS.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        symbol.resize((size, size), Image.LANCZOS).save(path, optimize=True)
        print(f"wrote {path.relative_to(ROOT)} ({size}px)")


if __name__ == "__main__":
    main()
