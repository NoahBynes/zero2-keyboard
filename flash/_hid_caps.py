#!/usr/bin/env python3
"""Inspect the bootloader HID interface of the Zero 2 (read-only caps + probe)."""
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


class HIDP_CAPS(ctypes.Structure):
    _fields_ = [
        ("Usage", wt.USHORT), ("UsagePage", wt.USHORT),
        ("InputReportByteLength", wt.USHORT), ("OutputReportByteLength", wt.USHORT),
        ("FeatureReportByteLength", wt.USHORT),
        ("Reserved", wt.USHORT * 17),
        ("NumberLinkCollectionNodes", wt.USHORT), ("NumberInputButtonCaps", wt.USHORT),
        ("NumberInputValueCaps", wt.USHORT), ("NumberInputDataIndices", wt.USHORT),
        ("NumberOutputButtonCaps", wt.USHORT), ("NumberOutputValueCaps", wt.USHORT),
        ("NumberOutputDataIndices", wt.USHORT), ("NumberFeatureButtonCaps", wt.USHORT),
        ("NumberFeatureValueCaps", wt.USHORT), ("NumberFeatureDataIndices", wt.USHORT),
    ]


class HIDD_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Size", wt.ULONG), ("VendorID", wt.USHORT), ("ProductID", wt.USHORT),
                ("VersionNumber", wt.USHORT)]


h = k32.CreateFileW(PATH, GENERIC_READ | GENERIC_WRITE, 0x3, None, OPEN_EXISTING, 0, None)
print("handle:", h)
if h == INVALID_HANDLE_VALUE:
    print("open failed:", ctypes.WinError(ctypes.get_last_error()))
    raise SystemExit(1)
try:
    attr = HIDD_ATTRIBUTES()
    attr.Size = ctypes.sizeof(HIDD_ATTRIBUTES)
    ok = hid.HidD_GetAttributes(h, ctypes.byref(attr))
    print(f"attributes: ok={ok} vid=0x{attr.VendorID:04x} pid=0x{attr.ProductID:04x} ver=0x{attr.VersionNumber:04x}")
    pp = ctypes.c_void_p()
    ok = hid.HidD_GetPreparsedData(h, ctypes.byref(pp))
    print("preparsed:", ok, bool(pp))
    if ok and pp:
        caps = HIDP_CAPS()
        st = hid.HidP_GetCaps(pp, ctypes.byref(caps))
        print("HidP_GetCaps status:", st)
        print(f"  UsagePage=0x{caps.UsagePage:04x} Usage=0x{caps.Usage:04x}")
        print(f"  InputReportByteLength={caps.InputReportByteLength} "
              f"OutputReportByteLength={caps.OutputReportByteLength} "
              f"FeatureReportByteLength={caps.FeatureReportByteLength}")
        hid.HidD_FreePreparsedData(pp)
    # try a non-blocking-ish read with overlapped I/O (1s)
    overlapped = wt.OVERLAPPED()
    ev = k32.CreateEventW(None, True, False, None)
    overlapped.hEvent = ev
    buf = ctypes.create_string_buffer(256)
    n = wt.DWORD()
    ok = k32.ReadFile(h, buf, 256, ctypes.byref(n), ctypes.byref(overlapped))
    err = ctypes.get_last_error()
    print(f"ReadFile queued: ok={ok} err={err}")
    if not ok and err == 997:  # ERROR_IO_PENDING
        wait = k32.WaitForSingleObject(ev, 1500)
        print("wait result (0=signaled,258=timeout):", wait)
        if wait == 0:
            k32.GetOverlappedResult(h, ctypes.byref(overlapped), ctypes.byref(n), False)
            print("read bytes:", n.value, "data:", buf.raw[:n.value].hex())
        else:
            k32.CancelIo(h)
    k32.CloseHandle(ev)
finally:
    k32.CloseHandle(h)
