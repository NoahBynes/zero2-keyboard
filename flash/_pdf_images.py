#!/usr/bin/env python3
"""Extract embedded JPEG/PNG images from a PDF (for reading upgrade-step screenshots)."""
import os
import re
import sys

path = sys.argv[1]
outdir = sys.argv[2]
os.makedirs(outdir, exist_ok=True)
data = open(path, "rb").read()
count = 0
# JPEG: SOI .. EOI
for m in re.finditer(rb"\xff\xd8\xff", data):
    start = m.start()
    end = data.find(b"\xff\xd9", start)
    if end > 0 and end - start > 5000:
        count += 1
        fn = os.path.join(outdir, f"img_{count:03d}.jpg")
        open(fn, "wb").write(data[start:end + 2])
        print(fn, end - start)
# PNG signature
for m in re.finditer(rb"\x89PNG\r\n\x1a\n", data):
    start = m.start()
    end = data.find(b"IEND", start)
    if end > 0:
        count += 1
        fn = os.path.join(outdir, f"img_{count:03d}.png")
        open(fn, "wb").write(data[start:end + 8])
        print(fn, end + 8 - start)
print("total images:", count)
