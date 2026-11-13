#!/usr/bin/env python3
"""Analyze the official 8BitDo Zero 2 firmware: parse sections, decrypt both
ciphers, dump payloads, then look for the keyboard-mode key mapping table.

Cipher code by AeroModes (8cryptdo, MIT). Firmware fetched from 8BitDo's
public update API (see _tools/fw_enum.py).
"""
import json
import os
import re
import struct
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
UP = os.path.join(ROOT, "_upstream")
FP = os.path.join(ROOT, "firmware-patch")
sys.path.insert(0, os.path.join(UP, "8cryptdo"))
import cryptdo8  # noqa: E402

FW = os.path.join(FP, "Zero 2 gamepad")

# Fixed keyboard-mode mapping per community reports (8BitDo Zero 2, R+Start):
#   Up->c Down->d Left->e Right->f A->g X->h Y->i B->j L->k R->m
EXPECTED = [0x06, 0x07, 0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x10]
NAMES = ["c", "d", "e", "f", "g", "h", "i", "j", "k", "m"]


def find_all(hay, needle):
    out, start = [], 0
    while True:
        i = hay.find(needle, start)
        if i < 0:
            return out
        out.append(i)
        start = i + 1


def u16_variants(seq):
    return [
        (b"".join(struct.pack("<H", v) for v in seq), "u16le"),
        (b"".join(struct.pack(">H", v) for v in seq), "u16be"),
        (b"".join(struct.pack("<I", v) for v in seq), "u32le"),
        (b"".join(struct.pack(">I", v) for v in seq), "u32be"),
    ]


def search(hay, label):
    hits = []
    for needle, kind in [(bytes(EXPECTED), "u8")] + u16_variants(EXPECTED):
        for off in find_all(hay, needle):
            hits.append((label, kind, off, needle.hex()))
    for seq, tag in ((EXPECTED[:-1], "u8_no_m"), (list(reversed(EXPECTED)), "u8_rev")):
        for off in find_all(hay, bytes(seq)):
            hits.append((label, tag, off, bytes(seq).hex()))
    # ASCII string form
    for s in (b"cdefghijkm", b"CDEFGHIJKM", b"cdefghijk"):
        for off in find_all(hay, s):
            hits.append((label, "ascii", off, s.decode()))
    return hits


def strings(data, minlen=6):
    out = []
    for m in re.finditer(rb"[\x20-\x7e]{%d,}" % minlen, data):
        out.append((m.start(), m.group().decode("ascii", "replace")))
    return out


def main():
    raw = open(FW, "rb").read()
    print(f"firmware file: {len(raw)} bytes")
    secs = cryptdo8.parse_sections(raw)
    print(f"sections: {len(secs)}")
    meta = {}
    for i, sec in enumerate(secs):
        print(f"\n== section {i}: id/version={sec['id']} addr=0x{sec['addr']:08x} "
              f"len={sec['payload_len']} pid=0x{sec['pid']:04x} offset={sec['offset']}")
        cipher = cryptdo8.detect_cipher(raw, sec)
        print(f"   auto-detected cipher: {cipher.NAME if cipher else 'None'}")
        c = cipher if cipher else cryptdo8.CIPHERS["yichip"]
        data = cryptdo8.decrypt_section(raw, sec, c)
        out = os.path.join(FP, "decrypted", f"section{i}_{c.NAME}.bin")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        open(out, "wb").write(data)
        print(f"   decrypted {len(data)} bytes -> {out} entropy={cryptdo8.entropy(data[:8192]):.2f}")
        meta[i] = {"cipher": c.NAME, "payload_len": sec["payload_len"],
                   "addr": sec["addr"], "version": sec["id"], "pid": sec["pid"],
                   "file": os.path.relpath(out, ROOT)}
        for label, kind, off, hx in search(data, f"section{i}"):
            print(f"   [HIT] {kind} offset=0x{off:06x} {hx}")
        # keyword strings
        ss = strings(data)
        kw = [s for s in ss if re.search(r"(?i)(keyboard|key_?code|scancode|hid|report|usage|mode|ble|bt)", s[1])]
        if kw:
            print(f"   keyword strings: {len(kw)} (first 25)")
            for off, s in kw[:25]:
                print(f"     0x{off:06x} {s[:100]}")
    json.dump(meta, open(os.path.join(FP, "decrypted", "sections.json"), "w"), indent=2)


if __name__ == "__main__":
    main()
