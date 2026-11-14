#!/usr/bin/env python3
"""Draw the Zero2 app icon: minimal black/white D-pad + ABXY only.

Black rounded-square tile with a white D-pad (left) and a white ABXY diamond
(right). No controller body, no shoulders, no labels.

Usage:
    python make_icon.py                 # writes zero2.png + zero2.ico next to this file
"""
import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
SIZE = 1024
BLACK = (17, 17, 17, 255)        # #111111
WHITE = (255, 255, 255, 255)
TRANSPARENT = (0, 0, 0, 0)

ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]


def make(size=SIZE):
    img = Image.new("RGBA", (size, size), TRANSPARENT)
    d = ImageDraw.Draw(img)
    s = size / 1024.0

    def P(v):
        return int(round(v * s))

    # black rounded-square tile
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=P(228), fill=BLACK)

    # D-pad (left): rounded vertical + horizontal bars
    d.rounded_rectangle([P(244), P(366), P(352), P(658)], radius=P(38), fill=WHITE)
    d.rounded_rectangle([P(154), P(460), P(442), P(568)], radius=P(38), fill=WHITE)

    # ABXY diamond (right)
    cx, cy, off, r = 714, 512, 132, P(64)
    for px, py in ((cx, cy - off), (cx - off, cy), (cx + off, cy), (cx, cy + off)):
        d.ellipse([P(px) - r, P(py) - r, P(px) + r, P(py) + r], fill=WHITE)

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
