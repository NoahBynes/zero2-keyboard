#!/usr/bin/env python3
"""Zero 2 firmware patcher: decrypt -> patch keyboard-mode key table ->
re-encrypt, and verify the cipher pipeline round-trips byte-exactly.

Uses the 8cryptdo cipher implementation (MIT, AeroModes) and firmware fetched
from 8BitDo's public update API.
"""
import argparse
import hashlib
import json
import os
import struct
import sys
import zlib

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
UP = os.path.join(ROOT, "_upstream")
FP = os.path.join(ROOT, "firmware-patch")
sys.path.insert(0, os.path.join(UP, "8cryptdo"))
import cryptdo8  # noqa: E402

TABLE = bytes.fromhex("0607080911120a0d0b0c0e10")  # 12-byte keyboard map
# Index order proven by the official table values + community key mapping
# (Up=C Down=D Left=E Right=F Select=N Start=O A=G B=J X=H Y=I L=K R=M).
LABELS = ["Up", "Down", "Left", "Right", "Select", "Start", "A", "B", "X", "Y", "L", "R"]


def load(path):
    raw = open(path, "rb").read()
    secs = cryptdo8.parse_sections(raw)
    assert sum(cryptdo8.HEADER_SIZE + s["payload_len"] for s in secs) == len(raw), "bad image"
    out = []
    for i, sec in enumerate(secs):
        cipher = cryptdo8.detect_cipher(raw, sec)
        assert cipher is not None, f"cannot detect cipher for section {i}"
        plain = cryptdo8.decrypt_section(raw, sec, cipher)
        out.append(dict(index=i, sec=sec, cipher=cipher, plain=plain))
    return raw, out


def rebuild(sections):
    """Rebuild a .dat from decrypted sections, preserving header fields."""
    out = b""
    for s in sections:
        sec = s["sec"]
        section = cryptdo8.build_section(
            s["plain"], s["cipher"], sec["id"], sec["addr"],
            sec["payload_len"], sec["pid"])
        out += section
    return out


def find_all(hay, needle):
    out, start = [], 0
    while True:
        i = hay.find(needle, start)
        if i < 0:
            return out
        out.append(i)
        start = i + 1


def crc_probe(name, plain):
    print(f"  [{name}] tail 24 bytes: " + " ".join(f"{b:02x}" for b in plain[-24:]))
    for label, calc in (
        ("crc32(payload[:-4])", lambda d: zlib.crc32(d[:-4]) & 0xFFFFFFFF),
        ("crc32(payload)", lambda d: zlib.crc32(d) & 0xFFFFFFFF),
    ):
        got = calc(plain)
        tail_le = struct.unpack("<I", plain[-4:])[0]
        tail_be = struct.unpack(">I", plain[-4:])[0]
        print(f"    {label}=0x{got:08x}  tail_le=0x{tail_le:08x} match={got == tail_le}  "
              f"tail_be=0x{tail_be:08x} match={got == tail_be}")


def cmd_verify(args):
    raw, sections = load(args.fw)
    print(f"file: {args.fw} ({len(raw)} bytes) sha256={hashlib.sha256(raw).hexdigest()}")
    rebuilt = rebuild(sections)
    print(f"rebuilt: {len(rebuilt)} bytes sha256={hashlib.sha256(rebuilt).hexdigest()}")
    print(f"byte-identical: {rebuilt == raw}")
    if rebuilt != raw:
        diffs = [i for i, (a, b) in enumerate(zip(raw, rebuilt)) if a != b]
        print(f"  first diffs: {[hex(d) for d in diffs[:20]]}  total={len(diffs)}")
    for s in sections:
        crc_probe(f"section{s['index']}", s["plain"])


def cmd_dump(args):
    raw, sections = load(args.fw)
    for s in sections:
        hits = find_all(s["plain"], TABLE)
        print(f"section {s['index']}: cipher={s['cipher'].NAME} addr=0x{s['sec']['addr']:08x} "
              f"len={s['sec']['payload_len']} pid=0x{s['sec']['pid']:04x} "
              f"version={s['sec']['id']} table_copies={[hex(h) for h in hits]}")
        for h in hits:
            vals = s["plain"][h:h + 12]
            print("   " + " ".join(f"0x{v:02x}" for v in vals))


def parse_keycode(v):
    if isinstance(v, int):
        return v
    if isinstance(v, str):
        return int(v, 0)
    raise SystemExit(f"unsupported keycode value: {v!r}")


def cmd_patch(args):
    raw, sections = load(args.fw)
    mapping = json.load(open(args.mapping, encoding="utf-8"))
    # Accept either {"Up": 0x51, ...} by label or {"0": 0x51, ...} by index.
    # Keys starting with "_" are comments and ignored.
    by_index = {}
    for k, v in mapping.items():
        if k.startswith("_"):
            continue
        if k.isdigit():
            by_index[int(k)] = parse_keycode(v)
        else:
            if k not in LABELS:
                raise SystemExit(f"unknown button label {k!r}; use one of {LABELS} or index")
            by_index[LABELS.index(k)] = parse_keycode(v)
    for i, v in by_index.items():
        if not 0 <= i < 12:
            raise SystemExit(f"index out of range: {i}")
        if not 0x00 <= v <= 0xFF:
            raise SystemExit(f"keycode out of range: 0x{v:x}")
    print(f"patch mapping (index:label -> keycode):")
    for i in range(12):
        if i in by_index:
            print(f"  {i:2d} {LABELS[i]:<8} 0x{by_index[i]:02x}")
    patched = []
    for s in sections:
        hits = find_all(s["plain"], TABLE)
        if not hits:
            raise SystemExit(f"section {s['index']}: keyboard table not found")
        if len(hits) > 1:
            print(f"  warning: section {s['index']} has {len(hits)} table copies, patching all")
        data = bytearray(s["plain"])
        for h in hits:
            for i, v in by_index.items():
                data[h + i] = v
        patched.append(dict(s, plain=bytes(data)))
    if args.version is not None:
        for s in patched:
            s["sec"] = dict(s["sec"], id=args.version)
        print(f"header version overridden -> {args.version}")
    out = rebuild(patched)
    open(args.out, "wb").write(out)
    print(f"\nwrote {args.out} ({len(out)} bytes) sha256={hashlib.sha256(out).hexdigest()}")
    # Validate: re-decrypt the patched file and compare against patched plaintext.
    raw2, sections2 = load(args.out)
    ok = all(a["plain"] == b["plain"] for a, b in zip(patched, sections2))
    print(f"self-check (decrypt patched file == patched payloads): {ok}")
    for a, b in zip(patched, sections2):
        h1 = find_all(a["plain"], TABLE)
        h2 = find_all(b["plain"], TABLE)
        print(f"  section {a['index']}: tables before={[hex(x) for x in h1]} "
              f"after={[hex(x) for x in h2]}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("verify"); v.add_argument("fw"); v.set_defaults(func=cmd_verify)
    d = sub.add_parser("dump"); d.add_argument("fw"); d.set_defaults(func=cmd_dump)
    p = sub.add_parser("patch")
    p.add_argument("fw"); p.add_argument("--mapping", required=True); p.add_argument("--out", required=True)
    p.add_argument("--version", type=lambda s: int(s, 0), default=None,
                   help="override section header version (e.g. 109)")
    p.set_defaults(func=cmd_patch)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
