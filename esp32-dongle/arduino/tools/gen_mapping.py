#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_mapping.py -- 把 mapping.json 转成 Arduino 固件用的 mapping.h

只依赖 Python 3.8+ 标准库（无第三方包）。

用法:
    # 在 zero2-keyboard/esp32-dongle/arduino/ 目录下执行
    python tools/gen_mapping.py mapping.example.json --out zero2_kb_dongle/mapping.h

    # 也支持直接覆盖已提交的 mapping.h（先备份，或交给 git）
    python tools/gen_mapping.py my_mapping.json

JSON 结构见 mapping.example.json。id 必须齐全且顺序固定：
    up, down, left, right, a, b, x, y, l, r, select, start
（顺序对应固件里的 12 个按钮 bit 位，见 zero2_kb_dongle.ino 顶部的说明。）

mods 允许: ctrl / shift / alt / gui（对应 HID 左修饰键位）。
key 允许: 单个字母 a-z、数字 0-9、部分符号、功能键，或 null（表示只按住修饰键）。
"""

import argparse
import json
import os
import sys

# ---- HID Keyboard/Keypad Usage ID (USB HID 1.11 附录 B) ----
KEY_TABLE = {}
for _c in "abcdefghijklmnopqrstuvwxyz":
    KEY_TABLE[_c] = 0x04 + (ord(_c) - ord("a"))
for _i, _c in enumerate("1234567890"):
    KEY_TABLE[_c] = 0x1E + _i
KEY_TABLE.update(
    {
        "enter": 0x28,
        "return": 0x28,
        "esc": 0x29,
        "escape": 0x29,
        "backspace": 0x2A,
        "tab": 0x2B,
        "space": 0x2C,
        " ": 0x2C,
        "-": 0x2D,
        "=": 0x2E,
        "[": 0x2F,
        "]": 0x30,
        "\\": 0x31,
        ";": 0x33,
        "'": 0x34,
        "`": 0x35,
        ",": 0x36,
        ".": 0x37,
        "/": 0x38,
        "capslock": 0x39,
        "printscreen": 0x46,
        "scrolllock": 0x47,
        "pause": 0x48,
        "insert": 0x49,
        "home": 0x4A,
        "pageup": 0x4B,
        "delete": 0x4C,
        "del": 0x4C,
        "end": 0x4D,
        "pagedown": 0x4E,
        "right": 0x4F,
        "left": 0x50,
        "down": 0x51,
        "up": 0x52,
        "numlock": 0x53,
    }
)
for _i in range(1, 13):
    KEY_TABLE["f%d" % _i] = 0x3A + (_i - 1)

MOD_BITS = {"ctrl": 0x01, "shift": 0x02, "alt": 0x04, "gui": 0x08, "win": 0x08}

BUTTON_ORDER = [
    "up", "down", "left", "right",
    "a", "b", "x", "y",
    "l", "r", "select", "start",
]


def fail(msg):
    print("错误: " + msg, file=sys.stderr)
    sys.exit(1)


def resolve_key(raw, button_id):
    if raw is None:
        return 0, "null"
    if not isinstance(raw, str):
        fail("%s: key 必须是字符串或 null" % button_id)
    name = raw.strip().lower()
    if name in KEY_TABLE:
        return KEY_TABLE[name], raw
    fail(
        "%s: 不认识的按键 %r（可用: a-z, 0-9, space/tab/esc/enter/backspace, [ ] ; ' , . / \\ - = `, f1-f12, 方向键等）"
        % (button_id, raw)
    )


def build(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        doc = json.load(f)

    buttons = doc.get("buttons")
    if not isinstance(buttons, list):
        fail("JSON 缺少 buttons 数组")

    by_id = {}
    for item in buttons:
        bid = item.get("id")
        if bid not in BUTTON_ORDER:
            fail("未知按钮 id: %r（可用: %s）" % (bid, ", ".join(BUTTON_ORDER)))
        if bid in by_id:
            fail("按钮 id 重复: %s" % bid)
        by_id[bid] = item

    missing = [b for b in BUTTON_ORDER if b not in by_id]
    if missing:
        fail("缺少按钮: %s" % ", ".join(missing))

    entries = []
    for bid in BUTTON_ORDER:
        item = by_id[bid]
        label = str(item.get("label", bid))
        mods_raw = item.get("mods") or []
        if not isinstance(mods_raw, list):
            fail("%s: mods 必须是数组" % bid)
        mod = 0
        for m in mods_raw:
            m = str(m).strip().lower()
            if m not in MOD_BITS:
                fail("%s: 不认识的修饰键 %r（可用 ctrl/shift/alt/gui）" % (bid, m))
            mod |= MOD_BITS[m]
        key, key_text = resolve_key(item.get("key"), bid)
        entries.append((bid, label, mod, key, key_text, str(item.get("desc", ""))))

    return doc, entries


def render(doc, entries):
    lines = []
    lines.append("// =============================================================================")
    lines.append("// mapping.h -- 由 tools/gen_mapping.py 根据 JSON 自动生成，请不要手改这个文件。")
    lines.append("// 想改映射：编辑 JSON 后重新生成，或直接改 mapping.json 再编译。")
    lines.append("//")
    lines.append("// 生成命令（在 zero2-keyboard/esp32-dongle/arduino/ 下）:")
    lines.append("//   python tools/gen_mapping.py mapping.example.json --out zero2_kb_dongle/mapping.h")
    lines.append("// =============================================================================")
    lines.append("#pragma once")
    lines.append("")
    lines.append("#include <stdint.h>")
    lines.append("")
    lines.append('#define ZERO2_MAPPING_VERSION "%s"' % str(doc.get("version", 1)))
    lines.append("#define ZERO2_BUTTON_COUNT 12")
    lines.append("")
    lines.append("// mod 位定义（对应 USB HID 键盘报告第 0 字节的修饰键位）")
    lines.append("#define Z2_MOD_LCTRL  0x01")
    lines.append("#define Z2_MOD_LSHIFT 0x02")
    lines.append("#define Z2_MOD_LALT   0x04")
    lines.append("#define Z2_MOD_LGUI   0x08")
    lines.append("")
    lines.append("typedef struct {")
    lines.append("    const char *id;     // 逻辑 id（与固件按钮 bit 位一一对应）")
    lines.append("    const char *label;  // 实体丝印")
    lines.append("    uint8_t     mod;    // 同时按住的修饰键位掩码")
    lines.append("    uint8_t     key;    // HID Usage ID，0 表示只按修饰键")
    lines.append("    const char *desc;   // 用途说明")
    lines.append("} zero2_map_entry_t;")
    lines.append("")
    lines.append("// 顺序固定 == 固件按钮 bit 顺序：up,down,left,right,a,b,x,y,l,r,select,start")
    lines.append("static const zero2_map_entry_t kZero2Mapping[ZERO2_BUTTON_COUNT] = {")
    for bid, label, mod, key, key_text, desc in entries:
        key_comment = "mod only" if key == 0 else "HID 0x%02X (%s)" % (key, key_text)
        lines.append(
            '    { "%s", "%s", 0x%02X, 0x%02X, "%s" },  // %s'
            % (bid, label, mod, key, desc, key_comment)
        )
    lines.append("};")
    lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="mapping.json -> mapping.h")
    ap.add_argument("json", help="输入 JSON 文件")
    ap.add_argument(
        "--out",
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "zero2_kb_dongle", "mapping.h"),
        help="输出 mapping.h 路径（默认 ../../zero2_kb_dongle/mapping.h 相对脚本位置）",
    )
    args = ap.parse_args()

    doc, entries = build(args.json)
    text = render(doc, entries)

    out = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)

    print("已生成: %s" % out)
    print("按钮数: %d" % len(entries))
    for bid, label, mod, key, key_text, _desc in entries:
        print("  %-7s %-8s mod=0x%02X key=0x%02X (%s)" % (bid, label, mod, key, key_text))


if __name__ == "__main__":
    main()
