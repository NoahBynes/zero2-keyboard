"""HID keyboard usage codes + built-in presets for Zero 2 keyboard mode."""

# Button order in the Zero 2 keyboard-mode mapping table (main MCU firmware).
BUTTONS = ["Up", "Down", "Left", "Right", "Select", "Start", "A", "B", "X", "Y", "L", "R"]
BUTTON_LABELS = {
    "Up": "十字键 ↑", "Down": "十字键 ↓", "Left": "十字键 ←", "Right": "十字键 →",
    "Select": "Select(-)", "Start": "Start(+)", "A": "A", "B": "B", "X": "X", "Y": "Y",
    "L": "L 肩键", "R": "R 肩键",
}

# Keyboard/Keypad page 0x07 usage IDs.
KEYMAP = {
    "Left Ctrl": 0xE0, "Left Shift": 0xE1, "Left Alt": 0xE2, "Left Win/Cmd": 0xE3,
    "Right Ctrl": 0xE4, "Right Shift": 0xE5, "Right Alt": 0xE6, "Right Win/Cmd": 0xE7,
    "Esc": 0x29, "Enter": 0x28, "Space": 0x2C, "Tab": 0x2B, "Backspace": 0x2A,
    "Delete": 0x4C, "Insert": 0x49, "Caps Lock": 0x39, "Pause": 0x48, "Print Screen": 0x46,
    "Home": 0x4A, "End": 0x4D, "PageUp": 0x4B, "PageDown": 0x4E,
    "Left": 0x50, "Right": 0x4F, "Up": 0x52, "Down": 0x51,
    "-": 0x2D, "=": 0x2E, "[": 0x2F, "]": 0x30, "\\": 0x31, ";": 0x33, "'": 0x34,
    "`": 0x35, ",": 0x36, ".": 0x37, "/": 0x38,
}
for _i, _ch in enumerate("abcdefghijklmnopqrstuvwxyz"):
    KEYMAP[_ch] = 0x04 + _i
for _i, _ch in enumerate("1234567890"):
    KEYMAP[_ch] = 0x1E + _i
for _i in range(1, 13):
    KEYMAP[f"F{_i}"] = 0x39 + _i  # F1=0x3A .. F12=0x45

KEY_ORDER = [
    "Esc", "Enter", "Space", "Tab", "Backspace", "Delete", "Insert", "Caps Lock",
    "PageUp", "PageDown", "Home", "End", "Left", "Right", "Up", "Down",
    "Left Ctrl", "Left Shift", "Left Alt", "Left Win/Cmd",
    "Right Ctrl", "Right Shift", "Right Alt", "Right Win/Cmd",
    "a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m",
    "n", "o", "p", "q", "r", "s", "t", "u", "v", "w", "x", "y", "z",
    "0", "1", "2", "3", "4", "5", "6", "7", "8", "9",
    "-", "=", "[", "]", "\\", ";", "'", "`", ",", ".", "/",
] + [f"F{i}" for i in range(1, 13)]

PRESETS = {
    "identify（校准：F1-F12）": {
        "Up": 0x3A, "Down": 0x3B, "Left": 0x3C, "Right": 0x3D,
        "Select": 0x3E, "Start": 0x3F, "A": 0x40, "B": 0x41,
        "X": 0x42, "Y": 0x43, "L": 0x44, "R": 0x45,
    },
    "翻页器（PageUp/PageDown…）": {
        "Up": 0x4B, "Down": 0x4E, "Left": 0x4A, "Right": 0x4D,
        "Select": 0x29, "Start": 0x28, "A": 0x2C, "B": 0x2B,
        "X": 0x2A, "Y": 0x4C, "L": 0x50, "R": 0x4F,
    },
    "绘画（Ctrl+Z 等）": {
        "Up": 0x52, "Down": 0x51, "Left": 0x50, "Right": 0x4F,
        "Select": 0x29, "Start": 0x2C, "A": 0x1D, "B": 0x1C,
        "X": 0x2F, "Y": 0x30, "L": 0xE0, "R": 0xE1,
    },
    "官方默认（c/d/e/f/n/o/g/j/h/i/k/m）": {
        "Up": 0x06, "Down": 0x07, "Left": 0x08, "Right": 0x09,
        "Select": 0x11, "Start": 0x12, "A": 0x0A, "B": 0x0D,
        "X": 0x0B, "Y": 0x0C, "L": 0x0E, "R": 0x10,
    },
}


def code_to_name(code):
    for name, value in KEYMAP.items():
        if value == code and name in KEY_ORDER:
            return name
    return "0x%02X" % code


def parse_key(value):
    """Parse a UI value (key name, '0x4B', 'Q'...) into a HID usage code."""
    if isinstance(value, int):
        code = value
    else:
        text = str(value).strip()
        if text in KEYMAP:
            code = KEYMAP[text]
        elif text.lower() in ("ctrl", "control"):
            code = 0xE0
        elif text.lower() in ("shift",):
            code = 0xE1
        elif text.lower() in ("alt",):
            code = 0xE2
        elif text.lower() in ("win", "cmd", "meta"):
            code = 0xE3
        else:
            try:
                code = int(text, 0)
            except ValueError:
                raise ValueError(f"不认识的键: {value!r}（可输入键名或 HID 码如 0x4B）")
    if not 0x00 <= code <= 0xFF:
        raise ValueError(f"HID 码超出范围: 0x{code:X}")
    return code


def preset(name):
    """Return a {button: code} dict for a preset display name (or raise)."""
    for key, mapping in PRESETS.items():
        if key == name or key.startswith(name):
            return dict(mapping)
    raise KeyError(name)
