#!/usr/bin/env python3
"""Read any pending HID input report from the Zero 2 bootloader interface (read-only)."""
import ctypes
import ctypes.wintypes as wt

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
hid = ctypes.WinDLL("hid", use_last_error=True)

PATH = (r"\\?\hid#vid_0483&pid_5760#7&fbca8a5&0&0000"
        r"#{4d1e55b2-f16f-11cf-88cb-001111000030}")
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
OPEN_EXISTING = 3
INVALID_HANDLE_VALUE = wt.HANDLE(-1).value
ERROR_IO_PENDING = 997


class OVERLAPPED(ctypes.Structure):
    _fields_ = [("Internal", ctypes.c_size_t), ("InternalHigh", ctypes.c_size_t),
                ("Offset", wt.DWORD), ("OffsetHigh", wt.DWORD),
                ("hEvent", wt.HANDLE)]


h = k32.CreateFileW(PATH, GENERIC_READ | GENERIC_WRITE, 0x3, None, OPEN_EXISTING, 0, None)
print("handle:", h)
if h == INVALID_HANDLE_VALUE:
    print("open failed:", ctypes.WinError(ctypes.get_last_error()))
    raise SystemExit(1)
try:
    ev = k32.CreateEventW(None, True, False, None)
    ov = OVERLAPPED()
    ov.hEvent = ev
    buf = ctypes.create_string_buffer(257)
    n = wt.DWORD()
    ok = k32.ReadFile(h, buf, 257, ctypes.byref(n), ctypes.byref(ov))
    err = ctypes.get_last_error()
    print(f"ReadFile ok={ok} err={err}")
    if not ok and err == ERROR_IO_PENDING:
        wait = k32.WaitForSingleObject(ev, 2000)
        print("wait (0=signaled, 258=timeout):", wait)
        if wait == 0:
            got = wt.DWORD()
            k32.GetOverlappedResult(h, ctypes.byref(ov), ctypes.byref(got), False)
            print("read bytes:", got.value, "hex:", buf.raw[:got.value].hex())
        else:
            k32.CancelIo(h)
    elif ok:
        print("read bytes:", n.value, "hex:", buf.raw[:n.value].hex())
    k32.CloseHandle(ev)
finally:
    k32.CloseHandle(h)
