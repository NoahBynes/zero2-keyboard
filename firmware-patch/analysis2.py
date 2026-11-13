#!/usr/bin/env python3
"""Second-stage analysis: compare firmware 1.05/1.08 keyboard tables, dump HID
keyboard report descriptors, and locate all copies of the 12-byte mapping
table."""
import json
import os
import sys
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
UP = os.path.join(ROOT, "_upstream")
FP = os.path.join(ROOT, "firmware-patch")
sys.path.insert(0, os.path.join(UP, "8cryptdo"))
import cryptdo8  # noqa: E402

BASE = "http://dl.8bitdo.com:8080"
TABLE = bytes.fromhex("0607080911120a0d0b0c0e10")  # 12-entry mapping table
NAMES = ["Up", "Down", "Left", "Right", "S?", "S?", "A", "B", "X", "Y", "L", "R"]


def fetch_versions():
    results = json.load(open(os.path.join(FP, "firmware.results.json")))
    fws = results["30"]
    out = {}
    for fw in fws:
        ver = f"{float(fw['version']):.2f}"
        dest = os.path.join(FP, f"Zero2_V{ver}.dat")
        if not os.path.exists(dest):
            url = BASE + fw["filePathName"]
            print(f"downloading v{ver}: {url}")
            urllib.request.urlretrieve(url, dest)
        out[ver] = dest
    return out


def decrypt(path):
    raw = open(path, "rb").read()
    secs = cryptdo8.parse_sections(raw)
    out = []
    for i, sec in enumerate(secs):
        cipher = cryptdo8.detect_cipher(raw, sec)
        c = cipher if cipher else cryptdo8.CIPHERS["yichip"]
        data = cryptdo8.decrypt_section(raw, sec, c)
        out.append((i, sec, c.NAME, data))
    return raw, out


def find_tables(data):
    hits, start = [], 0
    while True:
        i = data.find(TABLE, start)
        if i < 0:
            return hits
        hits.append(i)
        start = i + 1


def hexdump(data, lo, hi, vbase):
    for row in range(lo - lo % 16, hi, 16):
        chunk = data[row:row + 16]
        hexs = " ".join(f"{b:02x}" for b in chunk)
        asci = "".join(chr(b) if 0x20 <= b < 0x7f else "." for b in chunk)
        print(f"  {row:06x} {hexs:<48} {asci}")


def parse_hid(data, off):
    """Very rough HID report-descriptor walker; prints item tree until End
    Collection depth returns to 0."""
    print(f"\n-- HID descriptor at 0x{off:06x} vaddr=0x{0x01018000 + off:08x}")
    i, depth, n = off, 0, 0
    while i < len(data) and n < 200:
        b = data[i]
        size = {0: 0, 1: 1, 2: 2, 3: 4}.get(b & 3, 0)
        typ = (b >> 2) & 3
        tag = b >> 4
        val = int.from_bytes(data[i + 1:i + 1 + size], "little") if size else None
        names = {0: "Main", 1: "Global", 2: "Local"}
        print(f"   {i:06x}: {b:02x} {names[typ]:<6} tag=0x{tag:x} val={val}")
        if typ == 0:
            if tag == 0xA:  # Collection
                depth += 1
            elif tag == 0xC:  # End Collection
                depth -= 1
                if depth <= 0:
                    break
        i += 1 + size
        n += 1
    print(f"   -> ends at 0x{i:06x} ({i - off} bytes)")


def main():
    versions = fetch_versions()
    for ver, path in sorted(versions.items()):
        print(f"\n{'=' * 74}\nFIRMWARE v{ver}  ({path}, {os.path.getsize(path)} bytes)")
        raw, secs = decrypt(path)
        for i, sec, cname, data in secs:
            hits = find_tables(data)
            print(f"  section {i}: cipher={cname} addr=0x{sec['addr']:08x} "
                  f"len={sec['payload_len']} version={sec['id']} pid=0x{sec['pid']:04x}")
            print(f"    12-byte table copies: {[hex(h) for h in hits]}")
            for h in hits:
                print(f"      table@0x{h:06x}: " + " ".join(f"{b:02x}" for b in data[h - 4:h + 16]))
        # descriptors only for newest version, both sections
        if ver == sorted(versions)[-1]:
            for i, sec, cname, data in secs:
                if i == 0:
                    print("\n  section0 HID keyboard descriptor @0xc2ce:")
                    hexdump(data, 0xc2c0, 0xc350, 0x08003400)
                    print("\n  section0 strings around 0xc260:")
                    hexdump(data, 0xc250, 0xc2d0, 0x08003400)
                else:
                    for off in (0xf57a, 0xf5d4, 0x1000c, 0x10fde):
                        parse_hid(data, off)
                    print("\n  section1 around table @0x103a7:")
                    hexdump(data, 0x10360, 0x10400, 0x01018000)


if __name__ == "__main__":
    main()
