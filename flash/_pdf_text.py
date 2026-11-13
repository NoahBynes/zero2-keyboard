#!/usr/bin/env python3
"""Crude PDF text extraktor: decompress Flate streams and pull literal strings
from Tj/TJ content operators. Good enough for small manuals."""
import re
import sys
import zlib


def extract(path):
    data = open(path, "rb").read()
    texts = []
    for m in re.finditer(rb"stream\r?\n", data):
        start = m.end()
        end = data.find(b"endstream", start)
        if end < 0:
            continue
        chunk = data[start:end]
        try:
            raw = zlib.decompress(chunk)
        except Exception:
            continue
        if b"Tj" not in raw and b"TJ" not in raw:
            continue
        for sm in re.finditer(rb"\((?:\\.|[^\\)])*\)", raw):
            s = sm.group()[1:-1]
            s = s.replace(b"\\(", b"(").replace(b"\\)", b")").replace(b"\\\\", b"\\")
            s = re.sub(rb"\\[0-7]{1,3}", b"", s)
            try:
                txt = s.decode("utf-8")
            except UnicodeDecodeError:
                txt = s.decode("latin-1", "replace")
            texts.append(txt)
    return " ".join(texts)


if __name__ == "__main__":
    txt = extract(sys.argv[1])
    print("extracted chars:", len(txt))
    print(txt[:6000])
