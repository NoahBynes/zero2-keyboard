#!/usr/bin/env python3
"""Probe the Zero 2 bootloader with the legacy 8BitDo V1 packet protocol over
HID reports (read/write probe, no flashing).

V1 packet layout (fwupd ebitdo):
  u8 pkt_len, u8 type, u8 subtype, u16le cmd_len, u8 cmd, u16le payload_len,
  payload ...
  type 0x00 UserCmd, 0x01 UserData, 0x02 MidCmd
  cmd  0x04 FwGetVersion, 0x21 GetVersion, 0x22 GetVersionResponse ...
"""
import ctypes
import ctypes.wintypes as wt

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
hid = ctypes.WinDLL("hid", use_last_error=True)

PATH = (r"\\?\hid#vid_0483&pid_5760#7&fbca8a5&0&0000"
        r"#{4d1e55b2-f16f-11cf-88cb-001111000030}")
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE = 0x3
OPEN_EXISTING = 3
FILE_FLAG_OVERLAPPED = 0x40000000
INVALID = wt.HANDLE(-1).value


class OVERLAPPED(ctypes.Structure):
    _fields_ = [("Internal", ctypes.c_size_t), ("InternalHigh", ctypes.c_size_t),
                ("Offset", wt.DWORD), ("OffsetHigh", wt.DWORD), ("hEvent", wt.HANDLE)]


def open_dev():
    h = k32.CreateFileW(PATH, GENERIC_READ | GENERIC_WRITE, FILE_SHARE, None,
                        OPEN_EXISTING, FILE_FLAG_OVERLAPPED, None)
    if h == INVALID:
        raise OSError(ctypes.get_last_error(), "CreateFile failed")
    return h


def write_report(h, payload65):
    ov = OVERLAPPED()
    ov.hEvent = k32.CreateEventW(None, True, False, None)
    buf = ctypes.create_string_buffer(bytes(payload65), len(payload65))
    n = wt.DWORD()
    ok = k32.WriteFile(h, buf, len(payload65), ctypes.byref(n), ctypes.byref(ov))
    err = ctypes.get_last_error()
    if not ok and err == 997:
        wait = k32.WaitForSingleObject(ov.hEvent, 2000)
        if wait != 0:
            k32.CancelIo(h)
            k32.CloseHandle(ov.hEvent)
            return False, b""
        got = wt.DWORD()
        k32.GetOverlappedResult(h, ctypes.byref(ov), ctypes.byref(got), False)
    k32.CloseHandle(ov.hEvent)
    return True, bytes(n.value)


def read_report(h, timeout_ms=2000):
    ov = OVERLAPPED()
    ov.hEvent = k32.CreateEventW(None, True, False, None)
    buf = ctypes.create_string_buffer(256)
    n = wt.DWORD()
    ok = k32.ReadFile(h, buf, 256, ctypes.byref(n), ctypes.byref(ov))
    err = ctypes.get_last_error()
    if not ok and err == 997:
        wait = k32.WaitForSingleObject(ov.hEvent, timeout_ms)
        if wait != 0:
            k32.CancelIo(h)
            k32.CloseHandle(ov.hEvent)
            return None
        got = wt.DWORD()
        k32.GetOverlappedResult(h, ctypes.byref(ov), ctypes.byref(got), False)
        data = bytes(buf.raw[:got.value])
        k32.CloseHandle(ov.hEvent)
        return data
    k32.CloseHandle(ov.hEvent)
    return bytes(buf.raw[:n.value]) if ok else None


def mk_pkt(pkt_type, subtype, cmd, payload=b""):
    hdr = bytes([0, pkt_type, subtype, 0, 0, cmd, 0, 0])
    body = bytearray(hdr)
    if payload:
        body[4:6] = (len(payload) + 3).to_bytes(2, "little")
        body[6:8] = len(payload).to_bytes(2, "little")
        body += payload
        body[0] = len(payload) + 7
    else:
        body[4:6] = (1).to_bytes(2, "little")
        body[0] = 5
    return bytes(body)


def main():
    h = open_dev()
    print("opened device")
    try:
        tests = [
            ("FwGetVersion", 0x00, 0x16, 0x04, b""),
            ("GetVersion", 0x00, 0x16, 0x21, b""),
            ("GetVersion(alt subtype)", 0x00, 0x00, 0x21, b""),
            ("FwGetVersion(alt subtype)", 0x00, 0x00, 0x04, b""),
        ]
        for report_id in (0x00, 0x01):
            for name, t, st, cmd, payload in tests:
                pkt = mk_pkt(t, st, cmd, payload)
                out = bytes([report_id]) + pkt + b"\x00" * (64 - len(pkt))
                ok, _ = write_report(h, out)
                resp = read_report(h, 1500)
                print(f"report_id={report_id:02x} {name:28s} write={ok} resp={resp.hex() if resp else None}")
    finally:
        k32.CloseHandle(h)


if __name__ == "__main__":
    main()
