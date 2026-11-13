#!/usr/bin/env python3
"""Dump the exact keyboard mapping table context and look for code references."""
import os
import struct
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FP = os.path.join(ROOT, "firmware-patch", "decrypted")


def hexdump(data, start, end, base_vaddr):
    print(f"\n-- hexdump [0x{start:06x}..0x{end:06x}) vaddr=0x{base_vaddr + start:08x}")
    row = start - (start % 16)
    while row < end:
        chunk = data[row:row + 16]
        hexs = " ".join(f"{b:02x}" for b in chunk)
        asci = "".join(chr(b) if 0x20 <= b < 0x7f else "." for b in chunk)
        mark = "  <<<" if row <= start and start < row + 16 else ""
        print(f"  {row:06x} (+0x{row:05x}) {hexs:<48} {asci}{mark}")
        row += 16


def find_refs(data, addr, label):
    print(f"\n== references to 0x{addr:08x} in {label}")
    for a in {addr, addr | 1, addr + 4, addr - 4}:
        pat = struct.pack("<I", a) + b"\x00" * 0
        offs, start = [], 0
        while True:
            i = data.find(pat, start)
            if i < 0:
                break
            offs.append(i)
            start = i + 1
        # also alignment-agnostic search
        print(f"   0x{a:08x}: {len(offs)} hit(s) at {[hex(o) for o in offs[:8]]}")


def main():
    s0 = open(os.path.join(FP, "section0_gd32.bin"), "rb").read()
    s1 = open(os.path.join(FP, "section1_yichip.bin"), "rb").read()

    print("section0 table region around 0xaf68")
    hexdump(s0, 0x00af20, 0x00afc0, 0x08003400)
    print("\nsection1 table region around 0x103a3")
    hexdump(s1, 0x010360, 0x0103f0, 0x01018000)

    print("\n== bytes at exact table offsets")
    print("  s0[0x00af58:0x00af80] =", " ".join(f"{b:02x}" for b in s0[0x00af58:0x00af80]))
    print("  s1[0x010393:0x0103c0] =", " ".join(f"{b:02x}" for b in s1[0x010393:0x0103c0]))

    find_refs(s0, 0x08003400 + 0x00af68, "section0")
    find_refs(s1, 0x01018000 + 0x0103a3, "section1")

    # Look for a longer table: are Select/Start keycodes stored right after 0x10?
    print("\n== candidate full table region (bytes 0x00..0xff) around table")
    for label, data, off in (("s0", s0, 0x00af68), ("s1", s1, 0x0103a3)):
        chunk = data[off - 8:off + 24]
        print(f"  {label}: " + " ".join(f"{b:02x}" for b in chunk))

    # decode as ASCII strings near table
    print("\n== printable runs near table")
    for label, data, off in (("s0", s0, 0x00af68), ("s1", s1, 0x0103a3)):
        lo, hi = max(0, off - 160), min(len(data), off + 160)
        chunk = data[lo:hi]
        cur = []
        for i, b in enumerate(chunk):
            if 0x20 <= b < 0x7f:
                cur.append(chr(b))
            else:
                if len(cur) >= 4:
                    print(f"  {label} 0x{lo + i - len(cur):06x}: {''.join(cur)}")
                cur = []


if __name__ == "__main__":
    main()
