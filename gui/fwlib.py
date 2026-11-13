"""Build custom-keyboard firmware for 8BitDo Zero 2 from a 12-button mapping.

Uses the 8cryptdo cipher implementation (MIT, AeroModes) to decrypt the official
v1.08 .dat, patch the 12-byte keyboard-mode table in every section, then
re-encrypt with an increased version header.
"""
import hashlib
import os
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if getattr(sys, "frozen", False):
    BASE = Path(sys.executable).resolve().parent
else:
    BASE = HERE.parent                       # zero2-keyboard/
FW_OFFICIAL = BASE / "firmware-patch" / "Zero2_V1.08.dat"
CRYPT_DIR = BASE / "_upstream" / "8cryptdo"
TABLE = bytes.fromhex("0607080911120a0d0b0c0e10")   # original c d e f n o g j h i k m
BUTTONS = ["Up", "Down", "Left", "Right", "Select", "Start", "A", "B", "X", "Y", "L", "R"]

if not FW_OFFICIAL.exists():
    raise SystemExit(f"缺少官方固件：{FW_OFFICIAL}")
if not CRYPT_DIR.exists():
    raise SystemExit(f"缺少 8cryptdo：{CRYPT_DIR}")
sys.path.insert(0, str(CRYPT_DIR))
import cryptdo8  # noqa: E402


def find_all(hay, needle):
    out, start = [], 0
    while True:
        i = hay.find(needle, start)
        if i < 0:
            return out
        out.append(i)
        start = i + 1


def load_sections(path=None):
    raw = Path(path or FW_OFFICIAL).read_bytes()
    secs = cryptdo8.parse_sections(raw)
    if sum(cryptdo8.HEADER_SIZE + s["payload_len"] for s in secs) != len(raw):
        raise ValueError("官方固件结构异常")
    result = []
    for i, sec in enumerate(secs):
        cipher = cryptdo8.detect_cipher(raw, sec)
        if cipher is None:
            raise ValueError(f"段 {i} 无法识别加密方式")
        plain = cryptdo8.decrypt_section(raw, sec, cipher)
        result.append(dict(index=i, sec=sec, cipher=cipher, plain=plain))
    return raw, result


def build_firmware(mapping, version, out_path):
    """mapping: {button: hid_code} for the 12 buttons; version: int (e.g. 110)."""
    missing = [b for b in BUTTONS if b not in mapping]
    if missing:
        raise ValueError(f"缺少按键映射: {missing}")
    values = [int(mapping[b]) for b in BUTTONS]
    for v in values:
        if not 0x00 <= v <= 0xFF:
            raise ValueError(f"HID 码超出范围: 0x{v:X}")
    raw, sections = load_sections()
    patched = []
    patched_tables = {}
    for s in sections:
        hits = find_all(s["plain"], TABLE)
        if not hits:
            raise ValueError(f"段 {s['index']} 中找不到键盘映射表（固件版本不匹配？）")
        data = bytearray(s["plain"])
        for h in hits:
            for i, v in enumerate(values):
                data[h + i] = v
        patched.append(dict(s, plain=bytes(data)))
        patched_tables[s["index"]] = hits
    out = bytearray()
    for s in patched:
        sec = dict(s["sec"], id=int(version))
        out += cryptdo8.build_section(s["plain"], s["cipher"], sec["id"],
                                      sec["addr"], sec["payload_len"], sec["pid"])
    out = bytes(out)
    if len(out) != len(raw):
        raise ValueError(f"重建文件大小异常: {len(out)} != {len(raw)}")
    # self check: decrypt the rebuilt file and compare against patched payloads
    secs2 = cryptdo8.parse_sections(out)
    for s, sec in zip(patched, secs2):
        cipher = cryptdo8.detect_cipher(out, sec)
        plain2 = cryptdo8.decrypt_section(out, sec, cipher)
        if plain2 != s["plain"]:
            raise ValueError("重加密自检失败")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(out)
    return {
        "path": str(out_path),
        "size": len(out),
        "version": int(version),
        "sha256": hashlib.sha256(out).hexdigest(),
        "tables": {k: [hex(v) for v in vs] for k, vs in patched_tables.items()},
        "mapping": dict(mapping),
    }


def stock_mapping():
    return dict(zip(BUTTONS, TABLE))


if __name__ == "__main__":
    import json
    info = build_firmware(stock_mapping(), 110, BASE / "gui" / "_test_stock.dat")
    print(json.dumps(info, indent=2))
