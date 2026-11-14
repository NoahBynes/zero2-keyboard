#!/usr/bin/env python3
"""Draw the Zero2 app icon (a stylized 8BitDo Zero 2 controller) and export .ico.

Design: teal rounded-square tile + white controller glyph (shoulder bumps, D-pad,
ABXY diamond, select/start). Rendered at 1024px and downsampled for crisp small sizes.

Usage:
    python make_icon.py                 # writes zero2.png + zero2.ico next to this file
"""
import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
SIZE = 1024
TEAL = (18, 184, 176, 255)       # #12B8B0
WHITE = (255, 255, 255, 255)
TRANSPARENT = (0, 0, 0, 0)

ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]


def make(size=SIZE):
    img = Image.new("RGBA", (size, size), TRANSPARENT)
    d = ImageDraw.Draw(img)
    s = size / 1024.0

    def P(v):
        return int(round(v * s))

    # rounded-square tile
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=P(225), fill=TEAL)

    # controller glyph (white)
    # shoulder bumps (drawn first; body covers their lower part)
    d.rounded_rectangle([P(238), P(330), P(446), P(486)], radius=P(46), fill=WHITE)
    d.rounded_rectangle([P(578), P(330), P(786), P(486)], radius=P(46), fill=WHITE)
    # body pill
    d.rounded_rectangle([P(170), P(426), P(854), P(726)], radius=P(150), fill=WHITE)

    # D-pad: teal cross cut into the white body
    d.rounded_rectangle([P(328), P(478), P(398), P(712)], radius=P(30), fill=TEAL)
    d.rounded_rectangle([P(266), P(556), P(460), P(626)], radius=P(30), fill=TEAL)

    # ABXY diamond
    cx, cy, off, r = 714, 586, 78, P(28)
    for px, py in ((cx, cy - off), (cx - off, cy), (cx + off, cy), (cx, cy + off)):
        d.ellipse([P(px) - r, P(py) - r, P(px) + r, P(py) + r], fill=TEAL)

    # select / start
    for px in (548, 612):
        r2 = P(18)
        d.ellipse([P(px) - r2, P(682) - r2, P(px) + r2, P(682) + r2], fill=TEAL)

    return img


def main():
    big = make(SIZE)
    png = os.path.join(HERE, "zero2.png")
    ico = os.path.join(HERE, "zero2.ico")
    big.save(png)
    big.save(ico, format="ICO", sizes=[(n, n) for n in ICO_SIZES])
    print("saved:", png)
    print("saved:", ico, "sizes:", ICO_SIZES)


if __name__ == "__main__":
    main()
