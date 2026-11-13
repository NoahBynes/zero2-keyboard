"""8BitDo Zero 2 custom keyboard GUI (Xbox-Accessories-style layout).

Left: a clean line-art Zero 2; click a button, assign a key on the right.
Right: selected button + key picker + "my profiles" (save/load) + firmware/flash.

CLI is preserved: --build / --flash / --selftest / --patch.
"""
import argparse
import json
import os
import queue
import sys
import threading
import traceback
from pathlib import Path

import tkinter as tk
from tkinter import ttk, messagebox

import fwlib
import hidmap
import flasher

BASE = Path(__file__).resolve().parent
if getattr(sys, "frozen", False):
    BASE = Path(sys.executable).resolve().parent
CONFIG = BASE / "config.json"
PROFILES = BASE / "saved_profiles.json"
OUT_DIR = (BASE.parent if not getattr(sys, "frozen", False) else BASE) / "firmware-patch" / "out"

# windowed PyInstaller builds have sys.stdout/stderr = None; redirect to a log file
# so print()/traceback never raise (and we keep a debug log next to the exe).
if getattr(sys, "frozen", False):
    try:
        _log = open(BASE / "runtime.log", "a", encoding="utf-8", buffering=1)
        if sys.stdout is None:
            sys.stdout = _log
        if sys.stderr is None:
            sys.stderr = _log
    except Exception:
        try:
            _null = open(os.devnull, "w", encoding="utf-8")
            if sys.stdout is None:
                sys.stdout = _null
            if sys.stderr is None:
                sys.stderr = _null
        except Exception:
            pass

DEFAULT_MAPPING = hidmap.preset("翻页器")
DEFAULT_BASE = 108       # official 1.08 baseline; label is 1.08.N
DEFAULT_PATCH = 1

# default label positions (canvas coords); all labels are draggable
DEFAULT_LABEL_POS = {
    "L": (62, 23), "R": (620, 24),
    "Up": (48, 120), "Down": (53, 233),
    "Left": (48, 178), "Right": (50, 287),
    "X": (630, 124), "Y": (640, 285), "A": (640, 177), "B": (625, 232),
    "Select": (312, 368), "Start": (365, 368),
}

# palette (light theme)
BG = "#F3F4F6"
CARD = "#FFFFFF"
BORDER = "#E5E7EB"
TEXT = "#111827"
SUB = "#6B7280"
FAINT = "#9CA3AF"
ACCENT = "#2563EB"
ACCENT_DARK = "#1D4ED8"
GREEN = "#10B981"
SOFT = "#EEF2F7"
SOFT_HOVER = "#E2E8F0"

BODY_FILL = "#FBFCFD"
BODY_LINE = "#C6CCD3"
PAD_LINE = "#4B5563"
HUM_FILL = "#F1F3F5"
A_COLOR = "#22C55E"
B_COLOR = "#EF4444"
X_COLOR = "#3B82F6"
Y_COLOR = "#F59E0B"


# --------------------------------------------------------------------------- #
# version helpers: firmware header stays 108 (official 1.08); label 1.08.N
# --------------------------------------------------------------------------- #
def fmt_label(base, patch):
    return "1.%02d.%d" % (base % 100, patch)


def list_version(base, patch):
    return base / 100.0 + patch / 1000.0


def fmt_version(version):
    return "%.2f" % (version / 100.0)


# --------------------------------------------------------------------------- #
# config / profile helpers
# --------------------------------------------------------------------------- #
def load_config():
    cfg = {"mapping": dict(DEFAULT_MAPPING), "base": DEFAULT_BASE, "patch": DEFAULT_PATCH,
           "profile_name": ""}
    try:
        raw = json.loads(CONFIG.read_text(encoding="utf-8"))
        mapping = raw.get("mapping") or {}
        for b in hidmap.BUTTONS:
            if b in mapping:
                cfg["mapping"][b] = hidmap.parse_key(mapping[b])
        if isinstance(raw.get("base"), int):
            cfg["base"] = raw["base"]
        if isinstance(raw.get("patch"), int) and raw["patch"] > 0:
            cfg["patch"] = raw["patch"]
        elif isinstance(raw.get("next_version"), int):
            cfg["patch"] = max(1, raw["next_version"] - DEFAULT_BASE)
        if isinstance(raw.get("profile_name"), str):
            cfg["profile_name"] = raw["profile_name"]
    except FileNotFoundError:
        pass
    except Exception:
        pass
    return cfg


def save_config(cfg):
    try:
        CONFIG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def load_profiles():
    data = {}
    try:
        raw = json.loads(PROFILES.read_text(encoding="utf-8"))
        for name, mapping in (raw or {}).items():
            if not isinstance(mapping, dict):
                continue
            clean = {}
            for b in hidmap.BUTTONS:
                if b in mapping:
                    clean[b] = hidmap.parse_key(mapping[b])
            if len(clean) == len(hidmap.BUTTONS):
                data[str(name)] = clean
    except FileNotFoundError:
        pass
    except Exception:
        pass
    return data


def save_profiles(data):
    try:
        PROFILES.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except Exception:
        return False


def preset_slug(name):
    table = {"identify（校准：F1-F12）": "identify", "翻页器（PageUp/PageDown…）": "page-turner",
             "绘画（Ctrl+Z 等）": "drawing", "官方默认（c/d/e/f/n/o/g/j/h/i/k/m）": "stock"}
    for key, slug in table.items():
        if name == key or key.startswith(name) or name.startswith(key):
            return slug
    return "custom"


def build_file(mapping, header_version, label, preset_name="custom", log=print):
    out = OUT_DIR / ("Zero2_%s_%s.dat" % (label, preset_slug(preset_name)))
    log("正在生成固件（标签 %s，固件头保持 1.08 基线）…" % label)
    info = fwlib.build_firmware(mapping, header_version, out)
    log("固件已生成：%s（%d 字节，sha256=%s…）" % (out, info["size"], info["sha256"][:16]))
    log("已改动键位表：%s" % json.dumps(info["tables"], ensure_ascii=False))
    return info


# --------------------------------------------------------------------------- #
# CLI mode
# --------------------------------------------------------------------------- #
def run_cli(args):
    cfg = load_config()
    preset_name = args.preset or "custom"
    mapping = hidmap.preset(args.preset) if args.preset else cfg["mapping"]
    base = cfg["base"]
    patch = args.patch if args.patch is not None else cfg["patch"]
    label = fmt_label(base, patch)
    lv = list_version(base, patch)
    if args.selftest:
        info = build_file(hidmap.preset("identify"), base, "1.08.selftest")
        assert Path(info["path"]).stat().st_size == 124472
        print("SELFTEST OK:", info["path"])
        return 0
    info = build_file(mapping, base, label, preset_name,
                      log=lambda m: print("[build]", m, flush=True))
    if args.build:
        return 0
    if args.flash:
        result = flasher.flash(info["path"], lv, label,
                               log=lambda m: print("[flash]", m, flush=True))
        print("[done]", result)
    return 0


# --------------------------------------------------------------------------- #
# ui helpers
# --------------------------------------------------------------------------- #
def card(parent, **kw):
    return tk.Frame(parent, bg=CARD, highlightbackground=BORDER, highlightthickness=1, bd=0, **kw)


def flat_button(parent, text, command, kind="primary", width=None):
    colors = {
        "primary": (ACCENT, "#FFFFFF", ACCENT_DARK),
        "soft": (SOFT, TEXT, SOFT_HOVER),
        "ghost": (CARD, SUB, SOFT),
    }
    bg, fg, hover = colors.get(kind, colors["soft"])
    btn = tk.Button(parent, text=text, command=command, bg=bg, fg=fg,
                    activebackground=hover, activeforeground=fg,
                    relief="flat", bd=0, padx=14, pady=8, cursor="hand2",
                    font=("Segoe UI", 11))
    if width:
        btn.configure(width=width)
    return btn


def rounded_rect(canvas, x1, y1, x2, y2, r, **kw):
    points = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
        x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kw)


# --------------------------------------------------------------------------- #
# main application
# --------------------------------------------------------------------------- #
class Zero2App:
    CW, CH = 680, 380
    IMG_W, IMG_H = 475, 238
    IMG_OX, IMG_OY = 102, 56
    SX = IMG_W / 660.0
    SY = IMG_H / 330.0
    SCALE = (SX + SY) / 2.0

    def __init__(self, root, cfg):
        self.root = root
        self.base = int(cfg["base"])
        self.patch = int(cfg["patch"])
        self.mapping = dict(cfg["mapping"])
        self.profiles = load_profiles()
        self.profile_name = cfg.get("profile_name", "") if isinstance(cfg, dict) else ""
        self.selected = "A"
        self.busy = False
        self.q = queue.Queue()

        self.geo = {}
        self.map_labels = {}
        self.text_pos = {}

        self._build_ui()
        self._draw_controller()
        self._update_labels()
        self._select("A")
        self.refresh_device()
        self.root.after(120, self._pump)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.log("就绪。当前固件标签 %s；点击手柄上的按键，再在右侧选择要输出的键。"
                 % fmt_label(self.base, self.patch))

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        self.root.title("8BitDo Zero 2 · 按键映射")
        self.root.configure(bg=BG)
        self.root.geometry("1160x840")
        self.root.minsize(1060, 760)

        # header -------------------------------------------------------
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=20, pady=(16, 8))
        tk.Label(header, text="8BitDo Zero 2", bg=BG, fg=TEXT,
                 font=("Segoe UI", 20)).pack(side="left")
        tk.Label(header, text="  自定义键盘 · 按键映射", bg=BG, fg=SUB,
                 font=("Segoe UI", 12)).pack(side="left", pady=(6, 0))

        self.dev_dot = tk.Label(header, text="●", bg=BG, fg=FAINT, font=("Segoe UI", 12))
        self.dev_dot.pack(side="right", padx=(8, 0))
        self.dev_text = tk.Label(header, text="检查设备中…", bg=BG, fg=SUB, font=("Segoe UI", 11))
        self.dev_text.pack(side="right")
        flat_button(header, "刷新设备", self.refresh_device, "ghost").pack(side="right", padx=(0, 10))

        # content ------------------------------------------------------
        content = tk.Frame(self.root, bg=BG)
        content.pack(fill="both", expand=True, padx=20, pady=(4, 10))

        left = card(content)
        left.pack(side="left", fill="both", expand=True)
        tk.Label(left, text="点击手柄上的按键改键；右侧选择它要输出的键",
                 bg=CARD, fg=SUB, font=("Segoe UI", 10)).pack(anchor="w", padx=16, pady=(12, 0))
        self.canvas = tk.Canvas(left, width=self.CW, height=self.CH, bg=CARD,
                                highlightthickness=0)
        self.canvas.pack(expand=True, padx=8, pady=4)
        self.photo = tk.PhotoImage(file=str(BASE / "controller_small.png"))

        right = tk.Frame(content, bg=BG, width=400)
        right.pack(side="left", fill="y", padx=(14, 0))
        right.pack_propagate(False)

        # selected button + key picker
        pick = card(right)
        pick.pack(fill="x")
        tk.Label(pick, text="当前按键", bg=CARD, fg=SUB, font=("Segoe UI", 10)).pack(
            anchor="w", padx=16, pady=(12, 0))
        self.sel_title = tk.Label(pick, text="A", bg=CARD, fg=TEXT,
                                  font=("Segoe UI", 22))
        self.sel_title.pack(anchor="w", padx=16)
        self.sel_sub = tk.Label(pick, text="当前输出：Space", bg=CARD, fg=SUB,
                                font=("Segoe UI", 11))
        self.sel_sub.pack(anchor="w", padx=16, pady=(0, 8))

        row = tk.Frame(pick, bg=CARD)
        row.pack(fill="x", padx=16, pady=(0, 6))
        self.key_var = tk.StringVar()
        self.key_box = ttk.Combobox(row, textvariable=self.key_var, values=hidmap.KEY_ORDER,
                                    state="normal", width=16)
        self.key_box.pack(side="left")
        self.key_box.bind("<<ComboboxSelected>>", lambda _e: self._apply_key_text())
        self.key_box.bind("<Return>", lambda _e: self._apply_key_text())
        flat_button(row, "应用", self._apply_key_text, "soft").pack(side="left", padx=8)
        tk.Label(pick, text="可直接输入键名，或 HID 码如 0x4B / 75", bg=CARD, fg=FAINT,
                 font=("Segoe UI", 9)).pack(anchor="w", padx=16)
        tk.Label(pick, text="提示：肩键 + A/B/X/Y 可同时按出组合（如 L+A = Ctrl+Z）", bg=CARD,
                 fg=FAINT, font=("Segoe UI", 9)).pack(anchor="w", padx=16, pady=(2, 12))

        # my profiles (save / load)
        prof = card(right)
        prof.pack(fill="x", pady=(12, 0))
        tk.Label(prof, text="我的设定", bg=CARD, fg=SUB, font=("Segoe UI", 10)).pack(
            anchor="w", padx=16, pady=(12, 4))

        name_row = tk.Frame(prof, bg=CARD)
        name_row.pack(fill="x", padx=16)
        self.name_var = tk.StringVar(value=self.profile_name)
        tk.Label(name_row, text="名称", bg=CARD, fg=SUB, font=("Segoe UI", 10)).pack(side="left")
        self.name_entry = tk.Entry(name_row, textvariable=self.name_var, width=14,
                                   relief="flat", bg=SOFT, fg=TEXT,
                                   insertbackground=TEXT, font=("Segoe UI", 11))
        self.name_entry.pack(side="left", padx=8, ipady=4)
        flat_button(name_row, "保存设定", self._save_profile, "soft").pack(side="left")

        load_row = tk.Frame(prof, bg=CARD)
        load_row.pack(fill="x", padx=16, pady=(8, 4))
        tk.Label(load_row, text="载入", bg=CARD, fg=SUB, font=("Segoe UI", 10)).pack(side="left")
        self.saved_var = tk.StringVar()
        self.saved_box = ttk.Combobox(load_row, textvariable=self.saved_var,
                                      values=sorted(self.profiles.keys()),
                                      state="readonly", width=16)
        self.saved_box.pack(side="left", padx=8)
        self.saved_box.bind("<<ComboboxSelected>>", lambda _e: self._load_profile())
        tk.Label(prof, text="改好键位 + 填名称 → 保存；选中已保存项自动载入",
                 bg=CARD, fg=FAINT, font=("Segoe UI", 9)).pack(anchor="w", padx=16, pady=(0, 12))

        # firmware + actions
        fw = card(right)
        fw.pack(fill="x", pady=(12, 0))
        tk.Label(fw, text="固件", bg=CARD, fg=SUB, font=("Segoe UI", 10)).pack(
            anchor="w", padx=16, pady=(12, 0))
        self.ver_label = tk.Label(fw, text=fmt_label(self.base, self.patch), bg=CARD,
                                  fg=TEXT, font=("Segoe UI", 22))
        self.ver_label.pack(anchor="w", padx=16)
        tk.Label(fw, text="基于官方 1.08 · 刷写成功后 .N 自动 +1", bg=CARD, fg=SUB,
                 font=("Segoe UI", 9)).pack(anchor="w", padx=16, pady=(0, 10))
        btns = tk.Frame(fw, bg=CARD)
        btns.pack(fill="x", padx=16, pady=(0, 14))
        self.flash_btn = flat_button(btns, "刷写到手柄", self.do_flash, "primary")
        self.flash_btn.pack(side="left")
        self.build_btn = flat_button(btns, "生成固件", self.do_build, "soft")
        self.build_btn.pack(side="left", padx=8)
        flat_button(btns, "输出目录", self.open_out, "ghost").pack(side="left")

        # log ----------------------------------------------------------
        log_card = card(self.root)
        log_card.pack(fill="x", padx=20, pady=(0, 14))
        bar = tk.Frame(log_card, bg=CARD)
        bar.pack(fill="x", padx=12, pady=(8, 0))
        tk.Label(bar, text="日志", bg=CARD, fg=SUB, font=("Segoe UI", 10)).pack(side="left")
        self.log_box = tk.Text(log_card, height=4, bg="#FAFAFA", fg="#374151", bd=0,
                               relief="flat", font=("Consolas", 10), wrap="word")
        self.log_box.pack(fill="x", padx=12, pady=(2, 10))

    # ------------------------------------------------------- controller
    def _tx(self, x, y):
        return self.IMG_OX + x * self.SX, self.IMG_OY + y * self.SY

    def _draw_controller(self):
        c = self.canvas
        c.create_image(self.IMG_OX, self.IMG_OY, anchor="nw", image=self.photo)
        # hotspot geometry, in coordinates of the 660x330 source render
        orig_geo = {
            "Up": ("rect", 120, 85, 195, 140),
            "Down": ("rect", 120, 200, 195, 255),
            "Left": ("rect", 73, 145, 136, 195),
            "Right": ("rect", 180, 145, 242, 195),
            "X": ("circle", 501, 103, 31),
            "Y": ("circle", 433, 170, 31),
            "A": ("circle", 568, 171, 31),
            "B": ("circle", 501, 238, 31),
            "Select": ("circle", 293, 245, 25),
            "Start": ("circle", 365, 245, 25),
            "L": ("rect", 55, 15, 300, 85),
            "R": ("rect", 360, 15, 605, 85),
        }
        self.geo = {}
        for name, g in orig_geo.items():
            if g[0] == "circle":
                cx, cy = self._tx(g[1], g[2])
                self.geo[name] = ("circle", cx, cy, g[3] * self.SCALE)
            else:
                x1, y1 = self._tx(g[1], g[2])
                x2, y2 = self._tx(g[3], g[4])
                self.geo[name] = ("rect", x1, y1, x2, y2)

        # each button has its own label; labels are draggable (positions saved)
        label_targets = {
            "L": (177, 50), "R": (482, 50),
            "Up": (158, 112), "Down": (158, 228),
            "Left": (95, 170), "Right": (222, 170),
            "X": (501, 103), "Y": (433, 170),
            "A": (568, 171), "B": (501, 238),
            "Select": (293, 258), "Start": (365, 258),
        }
        self.leaders = {}
        for b, target in label_targets.items():
            tx, ty = self._tx(target[0], target[1])
            px, py = DEFAULT_LABEL_POS[b]
            line = c.create_line(0, 0, 0, 0, fill="#B9C0C8", width=1)
            text_id = c.create_text(px, py, anchor="center", text="",
                                    fill="#374151", font=("Segoe UI", 11))
            self.leaders[b] = (line, text_id, (tx, ty))
        self._update_labels()
        self._update_selection_ring()
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.canvas.bind("<Motion>", self._on_canvas_motion)

    def _hit_test(self, x, y):
        for b, g in self.geo.items():
            if g[0] == "circle":
                _, cx, cy, r = g
                if (x - cx) ** 2 + (y - cy) ** 2 <= (r + 14) ** 2:
                    return b
            else:
                _, x1, y1, x2, y2 = g
                if x1 - 10 <= x <= x2 + 10 and y1 - 10 <= y <= y2 + 10:
                    return b
        return None

    def _on_canvas_click(self, event):
        b = self._hit_test(event.x, event.y)
        if b:
            self._select(b)

    def _on_canvas_motion(self, event):
        self.canvas.configure(cursor="hand2" if self._hit_test(event.x, event.y) else "")

    def _route(self, b):
        line, text_id, target = self.leaders[b]
        tx, ty = target
        bb = self.canvas.bbox(text_id)
        if not bb:
            return
        x1, y1, x2, y2 = bb
        cx = (x1 + x2) / 2.0
        cy = (y1 + y2) / 2.0
        dx = tx - cx
        dy = ty - cy
        if abs(dx) >= abs(dy):
            sx = x2 if dx > 0 else x1
            self.canvas.coords(line, sx, cy, tx, cy, tx, ty)
        else:
            sy = y2 if dy > 0 else y1
            self.canvas.coords(line, cx, sy, cx, ty, tx, ty)

    def _update_labels(self):
        sel = self.selected
        for b in hidmap.BUTTONS:
            txt = hidmap.code_to_name(self.mapping[b])
            line, text_id, target = self.leaders[b]
            px, py = DEFAULT_LABEL_POS[b]
            self.canvas.coords(text_id, px, py)
            self.canvas.itemconfigure(line, fill=ACCENT if b == sel else "#B9C0C8",
                                      width=2 if b == sel else 1)
            self.canvas.itemconfigure(text_id, text=txt,
                                      fill=ACCENT_DARK if b == sel else "#374151",
                                      font=("Segoe UI", 11) if b == sel else ("Segoe UI", 11))
            self._route(b)

    def _update_selection_ring(self):
        self.canvas.delete("selring")
        g = self.geo.get(self.selected)
        if not g:
            return
        if g[0] == "circle":
            _, cx, cy, r = g
            self.canvas.create_oval(cx - r - 7, cy - r - 7, cx + r + 7, cy + r + 7,
                                    outline=ACCENT, width=3, tags="selring")
        else:
            _, x1, y1, x2, y2 = g
            self.canvas.create_rectangle(x1 - 5, y1 - 5, x2 + 5, y2 + 5,
                                         outline=ACCENT, width=3, tags="selring")
        for line, text_id, target in self.leaders.values():
            self.canvas.tag_raise(line)
            self.canvas.tag_raise(text_id)

    # -------------------------------------------------------- selection
    def _select(self, button):
        self.selected = button
        self.sel_title.configure(text=hidmap.BUTTON_LABELS.get(button, button))
        self._update_labels()
        self._update_selection_ring()
        self.key_var.set(hidmap.code_to_name(self.mapping[button]))
        self.sel_sub.configure(text="当前输出：%s   (%s)" % (
            hidmap.code_to_name(self.mapping[button]),
            "0x%02X" % self.mapping[button]))

    def _apply_key_text(self):
        text = self.key_var.get().strip()
        try:
            code = hidmap.parse_key(text)
        except ValueError as e:
            messagebox.showerror("键名无效", str(e))
            return
        self.mapping[self.selected] = code
        self._update_labels()
        self._select(self.selected)
        self._save()

    # -------------------------------------------------------- profiles
    def _save_profile(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("需要名称", "先给这套设定起个名字，再点保存。")
            return
        self.profiles[name] = dict(self.mapping)
        if not save_profiles(self.profiles):
            messagebox.showerror("保存失败", "写入 saved_profiles.json 失败。")
            return
        self.saved_box.configure(values=sorted(self.profiles.keys()))
        self.log("已保存设定：%s" % name)
        self._save()

    def _load_profile(self):
        name = self.saved_var.get().strip()
        if name not in self.profiles:
            return
        self.mapping = dict(self.profiles[name])
        self.name_var.set(name)
        self._update_labels()
        self._select(self.selected)
        self._save()
        self.log("已载入设定：%s" % name)

    # ------------------------------------------------------------ device
    def refresh_device(self):
        self.dev_text.configure(text="检查设备中…")
        self.dev_dot.configure(fg=FAINT)

        def work():
            ok = False
            try:
                ok = flasher.device_present()
            except Exception:
                ok = False
            self.root.after(0, lambda: self._set_device(ok))

        threading.Thread(target=work, daemon=True).start()

    def _set_device(self, ok):
        if ok:
            self.dev_dot.configure(fg=GREEN)
            self.dev_text.configure(text="已连接（普通模式 2DC8:9018）")
        else:
            self.dev_dot.configure(fg=FAINT)
            self.dev_text.configure(text="未检测到（按 START 开机后用 USB 连接）")

    # -------------------------------------------------------------- log
    def log(self, msg):
        self.q.put(str(msg) + "\n")

    def _pump(self):
        try:
            while True:
                self.log_box.insert("end", self.q.get_nowait())
                self.log_box.see("end")
        except queue.Empty:
            pass
        self.root.after(120, self._pump)

    # ------------------------------------------------------------ actions
    def _set_busy(self, busy):
        self.busy = busy
        state = "disabled" if busy else "normal"
        for b in (self.flash_btn, self.build_btn):
            try:
                b.configure(state=state)
            except Exception:
                pass

    def do_build(self):
        if self.busy:
            return
        self._set_busy(True)
        self.log("=" * 56)

        def work():
            try:
                label = fmt_label(self.base, self.patch)
                info = build_file(self.mapping, self.base, label, "自定义", log=self.log)
                self.log("提示：点『刷写到手柄』可把这个固件写进手柄。")
                return info
            except Exception as e:  # noqa: BLE001
                self.log("生成失败：" + str(e))
                traceback.print_exc()
                return None
            finally:
                self.root.after(0, lambda: self._set_busy(False))

        threading.Thread(target=work, daemon=True).start()

    def do_flash(self):
        if self.busy:
            return
        self._set_busy(True)
        self.log("=" * 56)

        def work():
            try:
                label = fmt_label(self.base, self.patch)
                lv = list_version(self.base, self.patch)
                self._save()
                info = build_file(self.mapping, self.base, label, "自定义", log=self.log)
                flasher.flash(info["path"], lv, label, log=self.log)
                self.patch += 1
                self.root.after(0, self._after_flash_ok)
            except flasher.FlashError as e:
                self.log("❌ 刷写失败：%s" % e)
                self.log("   如果设备停在升级模式：打开官方更新器直接用官方固件刷回 1.08。")
                self.root.after(0, lambda: messagebox.showerror("刷写失败", str(e)))
            except Exception as e:  # noqa: BLE001
                self.log("❌ 出错：%s" % e)
                traceback.print_exc()
                self.root.after(0, lambda: messagebox.showerror("出错", str(e)))
            finally:
                self.root.after(0, lambda: self._set_busy(False))

        threading.Thread(target=work, daemon=True).start()

    def _after_flash_ok(self):
        self.ver_label.configure(text=fmt_label(self.base, self.patch))
        self.log("✅ 刷写成功！拔线 → R+Start 键盘模式 → 配对设备即可使用。")
        messagebox.showinfo("刷写成功",
                            "自定义键盘固件已写入手柄。\n\n"
                            "拔掉 USB，按 R+Start 进入键盘模式，重新配对目标设备即可。")

    def open_out(self):
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        try:
            import os
            os.startfile(str(OUT_DIR))
        except Exception:
            pass

    def _save(self):
        save_config({"mapping": self.mapping, "base": self.base, "patch": self.patch,
                     "profile_name": self.name_var.get().strip()})

    def _on_close(self):
        self._save()
        self.root.destroy()


def run_gui():
    cfg = load_config()
    root = tk.Tk()
    try:
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("TCombobox", font=("Segoe UI", 11), fieldbackground=CARD, background=CARD,
                        bordercolor=BORDER, lightcolor=CARD, darkcolor=CARD,
                        arrowcolor=TEXT, padding=4)
        style.map("TCombobox", fieldbackground=[("readonly", CARD)])
    except Exception:
        pass
    Zero2App(root, cfg)
    root.mainloop()


def main():
    ap = argparse.ArgumentParser(description="8BitDo Zero 2 custom keyboard builder/flasher")
    ap.add_argument("--build", action="store_true", help="只生成 .dat")
    ap.add_argument("--flash", action="store_true", help="生成并刷写")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--preset", help="预设名（identify/翻页器/绘画/官方默认）")
    ap.add_argument("--patch", type=int, help="版本补丁号 N（标签 1.08.N）")
    args = ap.parse_args()
    if args.build or args.flash or args.selftest:
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
        return run_cli(args)
    run_gui()
    return 0


if __name__ == "__main__":
    sys.exit(main())
