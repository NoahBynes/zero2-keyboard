#!/usr/bin/env python3
"""Read-only HID probe of the Zero 2 bootloader: try legacy 8BitDo command
packets with report IDs 0..15 and see if ANY reply arrives.

Nothing here writes/erases flash: only GET_VERSION / GET_ID-like read commands.
"""
import ctypes
import ctypes.wintypes as wt

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
hid = ctypes.WinDLL("hid", use_last_error=True)

PATH = (r"\\?\hid#vid_0483&pid_5760#7&fbca8a5&0&0000"
        r"#{4d1e55b2-f16f-11cf-88cb-001111000030}")
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
SHARE = 0x3
OPEN_EXISTING = 3
FILE_FLAG_OVERLAPPED = 0x40000000
INVALID = wt.HANDLE(-1).value


class OVERLAPPED(ctypes.Structure):
    _fields_ = [("Internal", ctypes.c_size_t), ("InternalHigh", ctypes.c_size_t),
                ("Offset", wt.DWORD), ("OffsetHigh", wt.DWORD), ("hEvent", wt.HANDLE)]


def open_dev(overlapped=True):
    h = k32.CreateFileW(PATH, GENERIC_READ | GENERIC_WRITE, SHARE, None,
                        OPEN_EXISTING, FILE_FLAG_OVERLAPPED if overlapped else 0, None)
    if h == INVALID:
        raise OSError(ctypes.get_last_error(), "CreateFile failed")
    return h


def write_raw(h, data):
    ov = OVERLAPPED()
    ov.hEvent = k32.CreateEventW(None, True, False, None)
    buf = ctypes.create_string_buffer(bytes(data), len(data))
    n = wt.DWORD()
    ok = k32.WriteFile(h, buf, len(data), ctypes.byref(n), ctypes.byref(ov))
    err = ctypes.get_last_error()
    if not ok and err == 997:
        if k32.WaitForSingleObject(ov.hEvent, 1500) != 0:
            k32.CancelIo(h)
            k32.CloseHandle(ov.hEvent)
            return False
        got = wt.DWORD()
        k32.GetOverlappedResult(h, ctypes.byref(ov), ctypes.byref(got), False)
    elif not ok:
        k32.CloseHandle(ov.hEvent)
        return False
    k32.CloseHandle(ov.hEvent)
    return True


def read_raw(h, timeout_ms=350, size=256):
    ov = OVERLAPPED()
    ov.hEvent = k32.CreateEventW(None, True, False, None)
    buf = ctypes.create_string_buffer(size)
    n = wt.DWORD()
    ok = k32.ReadFile(h, buf, size, ctypes.byref(n), ctypes.byref(ov))
    err = ctypes.get_last_error()
    if not ok and err == 997:
        if k32.WaitForSingleObject(ov.hEvent, timeout_ms) != 0:
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


def v1_pkt(pkt_type, subtype, cmd, payload=b""):
    body = bytearray([0, pkt_type, subtype, 0, 0, cmd, 0, 0])
    if payload:
        body[4:6] = (len(payload) + 3).to_bytes(2, "little")
        body[6:8] = len(payload).to_bytes(2, "little")
        body += payload
        body[0] = len(payload) + 7
    else:
        body[4:6] = (1).to_bytes(2, "little")
        body[0] = 5
    return bytes(body)


VARIANTS = [
    ("UserCmd/UpdateFwData/FwGetVersion", 0x00, 0x16, 0x04),
    ("UserCmd/UpdateFwData/GetVersion", 0x00, 0x16, 0x21),
    ("UserCmd/GetVersion", 0x00, 0x00, 0x21),
    ("UserCmd/FwGetVersion", 0x00, 0x00, 0x04),
    ("MidCmd/GetVersion", 0x02, 0x00, 0x21),
]


def main():
    h = open_dev(True)
    print("opened device")
    try:
        # drain any stale input report
        for _ in range(4):
            if read_raw(h, 60) is None:
                break
        for report_id in range(0x00, 0x10):
            for name, t, st, cmd in VARIANTS:
                pkt = v1_pkt(t, st, cmd)
                out = bytes([report_id]) + pkt + b"\x00" * (64 - len(pkt))
                ok = write_raw(h, out)
                resp = read_raw(h, 250)
                if resp:
                    print(f"REPLY report_id={report_id:02x} {name}: {resp.hex()}")
                elif ok:
                    pass
        # also try 64-byte payload without report-id byte
        for name, t, st, cmd in VARIANTS:
            pkt = v1_pkt(t, st, cmd)
            ok = write_raw(h, pkt + b"\x00" * (64 - len(pkt)))
            resp = read_raw(h, 250)
            if resp:
                print(f"REPLY no_report_id {name}: {resp.hex()}")
        print("probe finished")
    finally:
        k32.CloseHandle(h)


if __name__ == "__main__":
    main()
