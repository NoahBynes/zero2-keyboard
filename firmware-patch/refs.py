#!/usr/bin/env python3
"""Find code references (literal-pool pointers) to the keyboard table / nearby
config structs, and dump the code around them for manual Thumb decoding."""
import os
import struct
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FP = os.path.join(ROOT, "firmware-patch", "decrypted")


def load(name):
    return open(os.path.join(FP, name), "rb").read()


def scan_ptr(data, lo, hi, limit=40):
    hits = []
    for off in range(0, len(data) - 3, 2):
        w = struct.unpack("<I", data[off:off + 4])[0]
        if lo <= w <= hi:
            hits.append((off, w))
            if len(hits) >= limit:
                break
    return hits


def hexdump(data, lo, hi, step=2):
    for row in range(lo - lo % 16, hi, 16):
        chunk = data[row:row + 16]
        words = " ".join(f"{struct.unpack('<H', chunk[i:i+2])[0]:04x}" if i + 2 <= len(chunk) else ""
                         for i in range(0, len(chunk), 2))
        hexs = " ".join(f"{b:02x}" for b in chunk)
        asci = "".join(chr(b) if 0x20 <= b < 0x7f else "." for b in chunk)
        print(f"  {row:06x} {hexs:<48} {asci}")


def main():
    s0 = load("section0_gd32.bin")
    s1 = load("section1_yichip.bin")

    print("== s0 pointers into 0x0800E300..0x0800E400 (table region)")
    hits = scan_ptr(s0, 0x0800E300, 0x0800E400)
    for off, w in hits:
        print(f"   code/data off 0x{off:06x} -> 0x{w:08x}")
    print("\n== s1 pointers into 0x01028300..0x01028480 (table region)")
    hits1 = scan_ptr(s1, 0x01028300, 0x01028480)
    for off, w in hits1:
        print(f"   code/data off 0x{off:06x} -> 0x{w:08x}")

    for off, w in hits[:3]:
        print(f"\n-- s0 hexdump around ref 0x{off:06x} (vaddr 0x{0x08003400 + off:08x})")
        hexdump(s0, max(0, off - 0x60), min(len(s0), off + 0x60))
    for off, w in hits1[:3]:
        print(f"\n-- s1 hexdump around ref 0x{off:06x} (vaddr 0x{0x01018000 + off:08x})")
        hexdump(s1, max(0, off - 0x60), min(len(s1), off + 0x60))


if __name__ == "__main__":
    main()
