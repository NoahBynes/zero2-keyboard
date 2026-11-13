"""Automatic flashing driver: local firmware proxy + official 8BitDo updater + UI automation.

Verified flow (2026-11-13, Zero 2 v1.05 -> v1.09):
  1. controller must be connected over USB in *normal* mode (VID_2DC8&PID_9018)
  2. start local HTTP proxy serving our patched .dat (md5 = MD5(str(fileSize)))
  3. point the Windows user proxy at it, launch the official updater
  4. click "固件更新" then "更新" (window-relative coordinates)
  5. official tool downloads our firmware, sends jump-boot, writes it, reboots
  6. restore proxy, close updater, report result
"""
import ctypes
import ctypes.wintypes as wt
import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.parse
import winreg
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
if getattr(sys, "frozen", False):
    # running as a PyInstaller exe: assets live next to the exe
    BASE = Path(sys.executable).resolve().parent
else:
    BASE = HERE.parent
UPDATER_DIR = BASE / "_fw-tools" / "win" / "8BitDo_Firmware_Updater_Win"
UPDATER_EXE = UPDATER_DIR / "8BitDo Firmware Updater.exe"
DATA_DIR = UPDATER_DIR / "data"
UPDATE_LOG = DATA_DIR / "updateLog.txt"
DEBUG_LOG = DATA_DIR / "debugLog.txt"
CACHE_JSON = BASE / "firmware-patch" / "firmware.results.json"
LOCAL_PATCHED_NAME = "zero2-custom.dat"
APP_CONFIG = UPDATER_DIR / "8BitDo Firmware Updater.exe.config"


def _clear_update_cache():
    """更新器会复用 updateFile\\zero2-custom.dat：长度对得上就不重新下载。
    每次刷写前必须删掉，否则会刷进上一次缓存的固件（内容不同的同长度文件不会被识别）。"""
    cache = UPDATER_DIR / "updateFile" / LOCAL_PATCHED_NAME
    removed = False
    try:
        if cache.exists():
            cache.unlink()
            removed = True
    except Exception:
        pass
    return removed, cache


def _dat_header_version(path):
    try:
        raw = Path(path).read_bytes()
        return int.from_bytes(raw[0:4], "little")
    except Exception:
        return None


def _proxy_config_xml(port):
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<configuration>\n'
        '  <system.net>\n'
        '    <defaultProxy enabled="true" useDefaultCredentials="false">\n'
        '      <proxy proxyaddress="http://127.0.0.1:%d" bypassonlocal="true" />\n'
        '    </defaultProxy>\n'
        '  </system.net>\n'
        '</configuration>\n' % port
    )


def _install_app_config(port):
    """让更新器只对本进程使用本地代理（写 app.config，不改系统代理/注册表）。"""
    backup = None
    try:
        if APP_CONFIG.exists():
            backup = APP_CONFIG.read_bytes()
        APP_CONFIG.write_text(_proxy_config_xml(port), encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        raise FlashError("无法写入更新器 app.config 代理配置：%s" % e)
    return backup


def _restore_app_config(backup):
    try:
        if backup is None:
            if APP_CONFIG.exists():
                APP_CONFIG.unlink()
        else:
            APP_CONFIG.write_bytes(backup)
    except Exception:
        pass

user32 = ctypes.WinDLL("user32", use_last_error=True)


class FlashError(RuntimeError):
    pass


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _no_window():
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _hidden_proc_kwargs():
    """creationflags + STARTUPINFO that make a child process completely windowless."""
    kw = {"creationflags": _no_window()}
    try:
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE
        kw["startupinfo"] = si
    except Exception:
        pass
    return kw


def run_ps(command, timeout=20):
    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
            capture_output=True, text=True, timeout=timeout, **_hidden_proc_kwargs())
        return (res.stdout or "") + (res.stderr or "")
    except Exception as e:  # noqa: BLE001
        return "ERROR: %s" % e


def device_present():
    out = run_ps("Get-PnpDevice -PresentOnly -Class HIDClass -ErrorAction SilentlyContinue | "
                 "Where-Object { $_.InstanceId -match 'VID_2DC8&PID_9018' } | "
                 "Measure-Object | Select-Object -ExpandProperty Count")
    m = re.search(r"\b(\d+)\b", out or "")
    return bool(m and int(m.group(1)) > 0)


def _file_size(path):
    try:
        return Path(path).stat().st_size
    except OSError:
        return 0


def read_since(path, offset):
    try:
        with open(path, "rb") as f:
            f.seek(offset)
            data = f.read()
    except OSError:
        return "", offset
    return data.decode("utf-8", "replace"), offset + len(data)


def wait_for_text(path, pattern, start_offset, timeout, poll=0.3):
    deadline = time.time() + timeout
    seen = ""
    offset = start_offset
    while time.time() < deadline:
        text, offset = read_since(path, offset)
        if text:
            seen += text
            if pattern in seen:
                return True, offset, seen
        time.sleep(poll)
    return False, offset, seen


# --------------------------------------------------------------------------- #
# local firmware proxy
# --------------------------------------------------------------------------- #
class _ProxyState:
    patched = b""
    version = 109
    events = []
    base_entry = {}


def _load_base_entry():
    try:
        raw = json.load(open(CACHE_JSON, encoding="utf-8"))
        entries = raw.get("30") or raw.get(30) or []
        for e in entries:
            if "zero" in str(e.get("fileName", "")).lower():
                return dict(e)
        if entries:
            return dict(entries[0])
    except Exception:
        pass
    return {}


def _json_bytes(obj):
    return json.dumps(obj, ensure_ascii=False).encode("utf-8")


class _ProxyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def _send(self, code, body=b"", ctype=None, extra=None):
        self.close_connection = True
        self.send_response(code)
        if ctype:
            self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Connection", "close")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD" and body:
            try:
                self.wfile.write(body)
                self.wfile.flush()
            except Exception:
                pass

    def _path(self):
        raw = self.path
        if raw.startswith("http://") or raw.startswith("https://"):
            u = urllib.parse.urlsplit(raw)
            return u.hostname or "", u.path or "/"
        host = (self.headers.get("Host") or "").split(":")[0]
        return host, raw

    def do_HEAD(self):  # noqa: N802
        self._handle()

    def do_GET(self):  # noqa: N802
        self._handle()

    def do_POST(self):  # noqa: N802
        self._handle()

    def _handle(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            self.rfile.read(length)
        host, path = self._path()
        if host and ("msftconnecttest.com" in host or "msftncsi.com" in host):
            return self._send(200, b"")
        if path.rstrip("/") == "/firmware/select":
            _ProxyState.events.append(("select", time.time()))
            entry = dict(_ProxyState.base_entry)
            size = len(_ProxyState.patched)
            entry.update({
                "date": time.strftime("%Y-%m-%d"),
                "fileName": "Zero 2 gamepad",
                "type": 30,
                "version": _ProxyState.version,
                "fileSize": size,
                "filePathName": "/firmwareFile/upload/" + LOCAL_PATCHED_NAME,
                "fileURL": "/var/lib/tomcat9/webapps/firmwareFile/upload/" + LOCAL_PATCHED_NAME,
                "exists": True,
                "beta": "",
                "md5": hashlib.md5(str(size).encode()).hexdigest().upper(),
                "readme": "Zero 2 custom keyboard (local build)",
                "readme_en": "Zero 2 custom keyboard (local build)",
            })
            return self._send(200, _json_bytes({"msgState": 1, "error": "", "list": [entry]}),
                              "application/json; charset=utf-8")
        if path.startswith("/firmwareFile/"):
            if path.rstrip("/").endswith("/" + LOCAL_PATCHED_NAME):
                _ProxyState.events.append(("download", time.time()))
                return self._send(200, _ProxyState.patched, extra={
                    "ETag": 'W/"%d-0"' % len(_ProxyState.patched),
                    "Last-Modified": "Mon, 09 Jun 2025 03:06:22 GMT",
                })
            return self._send(404, b"")
        if path.startswith("/firmware/"):
            return self._send(200, b"{}", "application/json; charset=utf-8")
        return self._send(200, b"")


class FirmwareProxy:
    def __init__(self, patched_path, version):
        self.patched_path = Path(patched_path)
        self.version = float(version)      # list version, e.g. 1.081
        self.httpd = None
        self.thread = None

    @property
    def port(self):
        return self.httpd.server_address[1]

    def start(self):
        _ProxyState.patched = self.patched_path.read_bytes()
        _ProxyState.version = self.version
        _ProxyState.events = []
        _ProxyState.base_entry = _load_base_entry()
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), _ProxyHandler)
        self.httpd.daemon_threads = True
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        return self.port

    def stop(self):
        if self.httpd:
            try:
                self.httpd.shutdown()
                self.httpd.server_close()
            except Exception:
                pass
            self.httpd = None

    def has_event(self, name):
        return any(e[0] == name for e in _ProxyState.events)


# --------------------------------------------------------------------------- #
# Windows proxy settings
# --------------------------------------------------------------------------- #
def set_system_proxy(port):
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, PROXY_SETTINGS_KEY, 0,
                         winreg.KEY_READ | winreg.KEY_WRITE)
    saved = {}
    try:
        for name in ("ProxyEnable", "ProxyServer", "ProxyOverride"):
            try:
                saved[name], _ = winreg.QueryValueEx(key, name)
            except FileNotFoundError:
                saved[name] = None
        winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, "127.0.0.1:%d" % port)
        winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1)
    finally:
        winreg.CloseKey(key)
    return saved


def restore_system_proxy(saved):
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, PROXY_SETTINGS_KEY, 0,
                             winreg.KEY_READ | winreg.KEY_WRITE)
        try:
            if saved.get("ProxyServer") is not None:
                winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, saved["ProxyServer"])
            if saved.get("ProxyEnable") is not None:
                winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, int(saved["ProxyEnable"]))
            if saved.get("ProxyOverride") is not None:
                winreg.SetValueEx(key, "ProxyOverride", 0, winreg.REG_SZ, saved["ProxyOverride"])
        finally:
            winreg.CloseKey(key)
    except Exception:
        pass


# --------------------------------------------------------------------------- #
# updater window automation
# --------------------------------------------------------------------------- #
def _enum_windows_for_pid(pid):
    found = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def _cb(hwnd, _lparam):
        p = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
        if p.value == pid and user32.IsWindowVisible(hwnd):
            n = user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, cls, 256)
            found.append((hwnd, buf.value, cls.value))
        return True

    user32.EnumWindows(_cb, 0)
    return found


def _kill_running_updater():
    try:
        subprocess.run(["taskkill", "/F", "/IM", "8BitDo Firmware Updater.exe"],
                       capture_output=True, text=True, timeout=10,
                       **_hidden_proc_kwargs())
    except Exception:
        pass


def wait_updater_window(proc, timeout=15):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            return None, "process-exited"
        for hwnd, title, cls in _enum_windows_for_pid(proc.pid):
            if "8BitDo Firmware Updater" in title:
                return hwnd, title
            if "Fatal error" in title or cls == "#32770":
                return None, "crash"
        time.sleep(0.4)
    return None, "timeout"


class _RECT(ctypes.Structure):
    _fields_ = [("Left", ctypes.c_long), ("Top", ctypes.c_long),
                ("Right", ctypes.c_long), ("Bottom", ctypes.c_long)]


def _force_foreground(hwnd):
    """Bring a window to the foreground reliably (foreground lock workaround)."""
    user32.ShowWindow(hwnd, 9)      # SW_RESTORE
    user32.SetForegroundWindow(hwnd)
    if user32.GetForegroundWindow() == hwnd:
        return True
    # 按一下 ALT 解除前台锁定，再试
    try:
        user32.keybd_event(0x12, 0, 0, 0)          # ALT down
        user32.keybd_event(0x12, 0, 2, 0)          # ALT up
    except Exception:
        pass
    user32.SetForegroundWindow(hwnd)
    if user32.GetForegroundWindow() == hwnd:
        return True
    # AttachThreadInput 方式
    try:
        fg = user32.GetForegroundWindow()
        tid_fg = user32.GetWindowThreadProcessId(fg, None)
        tid_me = kernel32.GetCurrentThreadId()
        user32.AttachThreadInput(tid_me, tid_fg, True)
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        user32.AttachThreadInput(tid_me, tid_fg, False)
    except Exception:
        pass
    return user32.GetForegroundWindow() == hwnd


def _debug_shot(name):
    try:
        shot = BASE / "flash" / "_shot.ps1"
        if shot.exists():
            subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(shot),
                 "-Out", str(HERE / ("_debug_%s.png" % name))],
                capture_output=True, text=True, timeout=40, **_hidden_proc_kwargs())
    except Exception:
        pass


def _click_relative(hwnd, fx, fy):
    _force_foreground(hwnd)
    time.sleep(0.4)
    rect = _RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    x = rect.Left + int((rect.Right - rect.Left) * fx)
    y = rect.Top + int((rect.Bottom - rect.Top) * fy)
    user32.SetCursorPos(x, y)
    time.sleep(0.15)
    user32.mouse_event(0x0002, 0, 0, 0, 0)   # LEFTDOWN
    time.sleep(0.06)
    user32.mouse_event(0x0004, 0, 0, 0, 0)   # LEFTUP
    return x, y


def _ensure_settings_writable():
    """The .NET updater crashes if it cannot write %LOCALAPPDATA%\\_8BitDoFirmwareUpdater
    (seen inside the DSH sandbox). Redirect it into the workspace with a junction."""
    local = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    link = Path(local) / "_8BitDoFirmwareUpdater"
    target = BASE / "_appdata" / "8BitDoFirmwareUpdater"
    target.mkdir(parents=True, exist_ok=True)
    if link.exists():
        return False
    try:
        subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)],
                       capture_output=True, text=True, timeout=10,
                       **_hidden_proc_kwargs())
    except Exception:
        return False
    return link.exists()


def _click_named_element(match):
    """Click a UI element by name inside the updater (UIA helper, e.g. 高级模式)."""
    script = BASE / "flash" / "_click_name.ps1"
    if not script.exists():
        return False
    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script),
             "-Match", match],
            capture_output=True, text=True, timeout=60, **_hidden_proc_kwargs())
        return "element not found" not in (res.stdout + res.stderr)
    except Exception:
        return False


def _select_product_via_script():
    """Open the updater product page and click the Zero 2 tile using the UIA helper."""
    script = BASE / "flash" / "_select_zero2.ps1"
    if not script.exists():
        return False
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
            capture_output=True, text=True, timeout=90, **_hidden_proc_kwargs())
        return True
    except Exception:
        return False


# --------------------------------------------------------------------------- #
# main flash routine
# --------------------------------------------------------------------------- #
def flash(patched_path, list_version, label=None, log=print):
    """Flash `patched_path` (built by fwlib) into a Zero 2 connected in normal USB mode.

    `list_version` is what the updater is told (float, e.g. 1.081 -> displayed V1.08 but
    numerically newer than the device's 1.08); `label` is our own display string (1.08.1).
    """
    label = label or ("%.3f" % list_version)
    patched_path = Path(patched_path)
    if not patched_path.exists():
        raise FlashError("找不到要刷写的固件文件")
    if not UPDATER_EXE.exists():
        raise FlashError("找不到官方更新器：%s" % UPDATER_EXE)
    if not device_present():
        raise FlashError(
            "没有检测到处于普通模式的手柄（VID_2DC8&PID_9018）。\n"
            "请：① 拔掉 USB；② 按 START 开机（普通模式）；③ 插上 USB 后重试。\n"
            "（刷坏了的话直接把官方更新器打开、用它刷回官方 1.08 即可，不用拆机。）")

    proxy = FirmwareProxy(patched_path, list_version)
    port = proxy.start()
    log("本地固件代理已启动：127.0.0.1:%d（对外版本 %s）" % (port, label))
    cfg_backup = _install_app_config(port)
    log("已给官方更新器写入 app.config 代理（不动系统代理/注册表）")
    proc = None
    success = False
    try:
        dbg0 = _file_size(DEBUG_LOG)
        upd0 = _file_size(UPDATE_LOG)
        removed, cache_path = _clear_update_cache()
        log("已清理更新器下载缓存（防止复用旧固件）" if removed
            else "更新器下载缓存为空（会重新下载）")
        log("启动官方 8BitDo Firmware Updater…")
        _kill_running_updater()
        proc = subprocess.Popen([str(UPDATER_EXE)], cwd=str(UPDATER_DIR))
        hwnd, reason = wait_updater_window(proc, timeout=15)
        if hwnd is None and reason in ("process-exited", "crash"):
            try:
                proc.kill()
            except Exception:
                pass
            log("更新器启动异常（%s），尝试修复设置写入后重试…" % reason)
            if _ensure_settings_writable():
                proc = subprocess.Popen([str(UPDATER_EXE)], cwd=str(UPDATER_DIR))
                hwnd, reason = wait_updater_window(proc, timeout=25)
        if hwnd is None:
            raise FlashError("更新器窗口未出现（%s）" % reason)
        log("更新器已启动，等待识别设备…")
        ok, dbg_off, _ = wait_for_text(DEBUG_LOG, "find device", dbg0, timeout=25)
        if not ok:
            raise FlashError("更新器没有识别到设备，请确认手柄以普通模式连接 USB")
        # 这台环境里更新器写 %LOCALAPPDATA% 设置会崩，检测一下并修复后重启
        time.sleep(4.0)
        wins = _enum_windows_for_pid(proc.pid)
        alive_window = any("8BitDo Firmware Updater" in t for _h, t, _c in wins)
        crashed = any(c == "#32770" or "Fatal error" in t for _h, t, c in wins)
        if crashed or proc.poll() is not None or not alive_window:
            try:
                proc.kill()
            except Exception:
                pass
            log("更新器因设置写入崩溃，修复后重启…")
            if not _ensure_settings_writable():
                raise FlashError("更新器崩溃且无法修复设置目录")
            dbg0 = _file_size(DEBUG_LOG)
            proc = subprocess.Popen([str(UPDATER_EXE)], cwd=str(UPDATER_DIR))
            hwnd, reason = wait_updater_window(proc, timeout=25)
            if hwnd is None:
                raise FlashError("更新器重启失败（%s）" % reason)
            ok, dbg_off, _ = wait_for_text(DEBUG_LOG, "find device", dbg0, timeout=25)
            if not ok:
                raise FlashError("重启后更新器没有识别到设备")
            time.sleep(2.5)
        # 打开菜单 → 高级模式 → 选中 Zero 2 → 等更新页请求固件列表
        log("打开『高级模式』并选择 Zero 2…")
        _debug_shot("01_home")
        _click_relative(hwnd, 0.029, 0.030)     # 左上角菜单按钮
        time.sleep(1.5)
        _debug_shot("02_menu")
        if not _click_named_element("高级模式"):
            log("没找到『高级模式』菜单，再点一次菜单按钮…")
            _click_relative(hwnd, 0.029, 0.030)
            time.sleep(1.2)
            _click_named_element("高级模式")
        time.sleep(2.5)
        _debug_shot("03_advanced")
        _select_product_via_script()
        _debug_shot("04_product_selected")

        select_deadline = time.time() + 30
        while time.time() < select_deadline and not proxy.has_event("select"):
            time.sleep(0.3)
        if not proxy.has_event("select"):
            log("还没等到固件列表请求，重试打开高级模式…")
            _click_relative(hwnd, 0.029, 0.030)
            time.sleep(1.2)
            _click_named_element("高级模式")
            time.sleep(2.0)
            _select_product_via_script()
            select_deadline = time.time() + 25
            while time.time() < select_deadline and not proxy.has_event("select"):
                time.sleep(0.3)
        if not proxy.has_event("select"):
            log("换个方式：点首页的『固件更新』图标重试…")
            _click_relative(hwnd, 0.50, 0.47)
            select_deadline = time.time() + 20
            while time.time() < select_deadline and not proxy.has_event("select"):
                time.sleep(0.3)
        if not proxy.has_event("select"):
            log("更新器没有请求固件列表（页面没打开或系统代理未生效），保存现场截图…")
            try:
                shot = BASE / "flash" / "_shot.ps1"
                if shot.exists():
                    subprocess.run(
                        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                         "-File", str(shot), "-Out", str(HERE / "_flash_debug.png")],
                        capture_output=True, text=True, timeout=40,
                        **_hidden_proc_kwargs())
            except Exception:
                pass
            raise FlashError("更新器没有请求固件列表（页面没打开或系统代理未生效）")
        log("更新器已拿到自定义固件列表，等待页面渲染…")
        time.sleep(1.5)
        x, y = _click_relative(hwnd, 0.50, 0.86)
        log("点击『更新』(%d,%d)，开始刷写…" % (x, y))
        dl_deadline = time.time() + 15
        while time.time() < dl_deadline and not proxy.has_event("download"):
            time.sleep(0.3)
        if proxy.has_event("download"):
            log("更新器已从本地代理下载自定义固件 ✓")
        else:
            log("⚠ 没看到固件下载请求：可能复用了缓存文件，版本可能不对！")

        deadline = time.time() + 300
        last_progress = -1
        success = False
        failure = None
        tail_start = upd0
        last_dlg_check = 0.0
        run_text = ""
        while time.time() < deadline:
            # 刷写途中如果弹出对话框（错误/确认），自动按回车继续
            if time.time() - last_dlg_check > 2.0:
                last_dlg_check = time.time()
                for dh, dtitle, dcls in _enum_windows_for_pid(proc.pid):
                    if dcls == "#32770":
                        log("检测到更新器对话框（%s），自动确认…" % dtitle)
                        _force_foreground(dh)
                        time.sleep(0.2)
                        user32.keybd_event(0x0D, 0, 0, 0)   # Enter down
                        user32.keybd_event(0x0D, 0, 2, 0)   # Enter up
                        time.sleep(0.3)
                        break
            text, upd0 = read_since(UPDATE_LOG, upd0)
            if text:
                run_text += text
                for mm in re.finditer(r"progress\s+(\d+)", text):
                    p = int(mm.group(1))
                    if p >= last_progress + 10 and p > 0:
                        last_progress = p
                        log("刷写进度 %d%%" % p)
                if "update successful" in text:
                    success = True
                    break
                for bad in ("GetUpdateFile Error", "startErashFlash Error",
                            "Update Error", "update Error"):
                    if bad in text:
                        failure = bad
                        break
                if failure:
                    break
                if "resend GET_ID_DATA" in text:
                    log("设备没有应答 GET_ID_DATA（可能是手动进了升级模式），继续等待…")
            time.sleep(0.4)
        if not success:
            tail = read_since(UPDATE_LOG, tail_start)[0][-1500:]
            raise FlashError("刷写失败：%s\n日志尾部：\n%s" % (failure or "超时", tail))
        log("刷写成功！等待设备重启…")
        time.sleep(3.0)
        expected = _dat_header_version(patched_path)
        flashed = None
        vers = re.findall(r"Version:\s*(\d+)", run_text)
        if vers:
            flashed = int(vers[-1])
        if expected is not None and flashed is not None and expected != flashed:
            log("⚠ 警告：更新器写入版本 %d，与固件头 %d 不一致（很可能用了缓存固件）！"
                % (flashed, expected))
        else:
            log("版本校验：固件头版本 %s ✓" % expected)
        log("完成：已写入 %s 自定义键盘固件；拔线后可用 R+Start 测试键盘模式。" % label)
        return {"success": True, "version": label,
                "header_version": expected, "flashed_header_version": flashed,
                "log": str(UPDATE_LOG), "device_events": list(_ProxyState.events)}
    finally:
        # 成功才自动关闭更新器；失败时保留现场，方便用户看错误/重试
        if success and proc is not None and proc.poll() is None:
            try:
                proc.terminate()
                time.sleep(0.5)
                if proc.poll() is None:
                    proc.kill()
            except Exception:
                pass
        elif not success:
            log("更新器窗口保持打开（便于查看错误）；确认后可手动关闭。")
        _restore_app_config(cfg_backup)
        proxy.stop()


if __name__ == "__main__":
    import sys
    p = sys.argv[1] if len(sys.argv) > 1 else str(BASE / "firmware-patch" / "out" /
                                                  "Zero2_1.08.1_page-turner.dat")
    v = float(sys.argv[2]) if len(sys.argv) > 2 else 1.081
    print(flash(p, v, log=lambda m: print("[flash]", m, flush=True)))
