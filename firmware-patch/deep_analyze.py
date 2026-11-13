#!/usr/bin/env python3
"""Deeper analysis of decrypted Zero 2 firmware sections: find a candidate
keyboard-mode mapping table (any permutation), locate HID descriptors, dump
strings around interesting offsets."""
import os
import re
import struct
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FP = os.path.join(ROOT, "firmware-patch", "decrypted")
EXPECTED = {0x06, 0x07, 0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x10}
NAMES = {0x06: "c", 0x07: "d", 0x08: "e", 0x09: "f", 0x0A: "g", 0x0B: "h",
         0x0C: "i", 0x0D: "j", 0x0E: "k", 0x10: "m"}


def load(name):
    return open(os.path.join(FP, name), "rb").read()


def windows(data, win, need):
    """Yield offsets where a window of `win` bytes contains >= need EXPECTED."""
    for off in range(0, len(data) - win):
        chunk = set(data[off:off + win])
        common = chunk & EXPECTED
        if len(common) >= need:
            vals = list(data[off:off + win])
            yield off, [v for v in vals if v in EXPECTED]


def table_scan(data, label):
    print(f"\n== window scan {label} (len={len(data)})")
    hits = []
    # short windows: table of 8..16 bytes containing the sequential run
    for need, win in ((10, 16), (9, 14), (8, 12), (7, 10), (6, 8), (5, 6)):
        cnt = 0
        for off, vals in windows(data, win, need):
            print(f"   win={win} off=0x{off:06x} n={len(vals)} vals={[f'{v:02x}' for v in vals]}")
            cnt += 1
            if cnt >= 8:
                break
        if cnt:
            hits.append((need, win, cnt))
    print(f"   summary: {hits}")


def hid_descriptor_scan(data, label):
    print(f"\n== HID keyboard descriptor scan {label}")
    patterns = {
        "GDesktop/Keyboard collection": bytes.fromhex("05010906a101"),
        "GDesktop/Keyboard usage": bytes.fromhex("05010906"),
        "report id + keyboard": bytes.fromhex("85010906a101"),
    }
    for name, pat in patterns.items():
        offs = [m.start() for m in re.finditer(re.escape(pat), data)]
        print(f"   {name}: {len(offs)} hit(s) {[hex(o) for o in offs[:10]]}")


def dump_strings(data, lo, hi, minlen=4, label=""):
    print(f"\n== strings {label} [0x{lo:x}, 0x{hi:x})")
    chunk = data[lo:hi]
    for m in re.finditer(rb"[\x20-\x7e]{%d,}" % minlen, chunk):
        print(f"   0x{lo + m.start():06x} {m.group().decode('ascii')}")


def main():
    s0 = load("section0_gd32.bin")
    s1 = load("section1_yichip.bin")

    print("section0 first 32 words (possible vector table):")
    for i in range(0, min(32, len(s0)), 4):
        w = struct.unpack("<I", s0[i:i + 4])[0]
        print(f"  +0x{i:03x}: 0x{w:08x}")
    print("\nsection1 first 32 words:")
    for i in range(0, min(32, len(s1)), 4):
        w = struct.unpack("<I", s1[i:i + 4])[0]
        print(f"  +0x{i:03x}: 0x{w:08x}")

    table_scan(s0, "section0")
    table_scan(s1, "section1")
    hid_descriptor_scan(s0, "section0")
    hid_descriptor_scan(s1, "section1")

    dump_strings(s0, 0x00b000, 0x00d800, 4, "section0 around 'Keyboard'")
    dump_strings(s1, 0x007d00, 0x008200, 4, "section1 mode strings")


if __name__ == "__main__":
    main()
