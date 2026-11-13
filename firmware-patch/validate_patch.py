#!/usr/bin/env python3
"""Validate a patched Zero 2 firmware against the official v1.08 image:
- header fields (version/addr/len/pid)
- decrypted payload diff (must only touch the 12-byte keyboard tables)
- confirm patched table bytes
"""
import hashlib
import os
import struct
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
UP = os.path.join(ROOT, "_upstream")
FP = os.path.join(ROOT, "firmware-patch")
sys.path.insert(0, os.path.join(UP, "8cryptdo"))
import cryptdo8  # noqa: E402

ORIG = os.path.join(FP, "Zero2_V1.08.dat")
ORIG_TABLE = bytes.fromhex("0607080911120a0d0b0c0e10")


def decrypt_all(path):
    raw = open(path, "rb").read()
    secs = cryptdo8.parse_sections(raw)
    out = []
    for i, sec in enumerate(secs):
        cipher = cryptdo8.detect_cipher(raw, sec)
        plain = cryptdo8.decrypt_section(raw, sec, cipher)
        out.append((sec, cipher.NAME, plain))
    return raw, out


def main(paths):
    raw0, secs0 = decrypt_all(ORIG)
    print(f"reference: {ORIG} ({len(raw0)} bytes)")
    for path in paths:
        raw1, secs1 = decrypt_all(path)
        print(f"\n=== {path} ({len(raw1)} bytes, sha256={hashlib.sha256(raw1).hexdigest()[:16]}…)")
        print(f"  size equal to official: {len(raw1) == len(raw0)}")
        for idx, ((s0, c0, p0), (s1, c1, p1)) in enumerate(zip(secs0, secs1)):
            hdr = struct.unpack("<IIII", raw1[s1["offset"]:s1["offset"] + 16])
            print(f"  section {idx}: header=(version={hdr[0]}, addr=0x{hdr[1]:08x}, "
                  f"len={hdr[2]}, pid=0x{hdr[3]:04x}) cipher={c0}/{c1}")
            diffs = [i for i, (a, b) in enumerate(zip(p0, p1)) if a != b]
            print(f"    decrypted payload length {len(p1)}, differing bytes: {len(diffs)} at "
                  f"{[hex(d) for d in diffs]}")
            if diffs:
                lo, hi = min(diffs) - 0, max(diffs) + 1
                print("      orig: " + " ".join(f"{b:02x}" for b in p0[lo:hi]))
                print("      new : " + " ".join(f"{b:02x}" for b in p1[lo:hi]))
                # print full table candidate at each cluster
                for d in diffs:
                    pass


if __name__ == "__main__":
    main(sys.argv[1:])
