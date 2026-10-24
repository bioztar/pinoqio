"""Cut docs/img/options/E-stages.png (five heads, nose short -> long) into aligned frames for the UI.

Run once, output is committed: uv run --with pillow python scripts/cut_nose.py
Each frame is a window anchored on that head's left ear; pixels belonging to the neighbouring head are
painted with the background colour so crossfading never shows a second head.
"""
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs" / "img" / "options" / "E-stages.png"
OUT = ROOT / "pinoqio" / "ui" / "static" / "nose"

STARTS = (10, 292, 574, 892, 1197)   # window left edge per frame (x in the source)
LIMITS = (288, 570, 888, 1190, 1672)  # first x that belongs to the next head
WIDTH, TOP, BOTTOM = 460, 40, 445     # common canvas: 460 x 405


def main() -> None:
    src = Image.open(SRC).convert("RGB")
    bg = src.getpixel((4, 4))  # dark navy corner
    OUT.mkdir(parents=True, exist_ok=True)
    for i, (x0, limit) in enumerate(zip(STARTS, LIMITS)):
        frame = Image.new("RGB", (WIDTH, BOTTOM - TOP), bg)
        keep = min(limit - x0, WIDTH, src.width - x0)
        frame.paste(src.crop((x0, TOP, x0 + keep, BOTTOM)), (0, 0))
        keyed = key_out_background(frame, bg)
        keyed.save(OUT / f"{i}.webp", quality=88, alpha_quality=95)
        print(OUT / f"{i}.webp", keyed.size, "bg", bg)


def key_out_background(frame: Image.Image, bg: tuple[int, int, int]) -> Image.Image:
    """The source background is a soft navy gradient, so make everything near it transparent
    (soft edge) and the frame sits on any dark page without a visible rectangle."""
    px = np.asarray(frame, dtype=np.float32)
    dist = np.sqrt(((px - np.array(bg, dtype=np.float32)) ** 2).sum(axis=2))
    alpha = np.clip((dist - 22.0) / 22.0, 0.0, 1.0)
    rgba = np.dstack([px, alpha * 255.0]).astype(np.uint8)
    return Image.fromarray(rgba, "RGBA")


if __name__ == "__main__":
    main()
