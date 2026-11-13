#!/usr/bin/env python3
"""Enumerate USB/HID device nodes on Windows (read-only) to find the 8BitDo
Zero 2 in runtime or bootloader mode.

Uses SetupAPI + the registry (no WMI), because the WMI path is blocked inside
the DSH sandbox.
"""
import ctypes
import ctypes.wintypes as wt
import sys

DIGCF_PRESENT = 0x2
DIGCF_ALLCLASSES = 0x4
SPDRP_DEVICEDESC = 0x0
SPDRP_HARDWAREID = 0x1
SPDRP_SERVICE = 0x4
SPDRP_CLASS = 0x7
SPDRP_CLASSGUID = 0x8
SPDRP_FRIENDLYNAME = 0xC
SPDRP_LOCATION_INFORMATION = 0xD

TARGET_VIDS = {"2DC8", "0483", "1002", "1235", "2002", "8000"}
KEYWORDS = ("8bitdo", "zero", "hid", "gamepad", "keyboard", "boot")


class GUID(ctypes.Structure):
    _fields_ = [("Data1", wt.DWORD), ("Data2", wt.WORD), ("Data3", wt.WORD),
                ("Data4", ctypes.c_ubyte * 8)]


class SP_DEVINFO_DATA(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD), ("ClassGuid", GUID), ("DevInst", wt.DWORD),
                ("Reserved", ctypes.POINTER(wt.ULONG))]


setupapi = ctypes.WinDLL("setupapi", use_last_error=True)


def get_prop(hdev, devinfo, prop):
    buf = ctypes.create_unicode_buffer(4096)
    regtype = wt.DWORD()
    need = wt.DWORD()
    ok = setupapi.SetupDiGetDeviceRegistryPropertyW(
        hdev, ctypes.byref(devinfo), prop, ctypes.byref(regtype),
        ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte)), ctypes.sizeof(buf),
        ctypes.byref(need))
    if not ok:
        return None
    data = buf[:need.value // ctypes.sizeof(ctypes.c_wchar)]
    if regtype.value == 7:  # REG_MULTI_SZ
        return [s for s in data.split("\x00") if s]
    return data.rstrip("\x00")


def enumerate_devices():
    flags = DIGCF_PRESENT | DIGCF_ALLCLASSES
    hdev = setupapi.SetupDiGetClassDevsW(None, None, None, flags)
    if hdev == -1:
        raise ctypes.WinError(ctypes.get_last_error())
    out = []
    i = 0
    while True:
        dev = SP_DEVINFO_DATA()
        dev.cbSize = ctypes.sizeof(SP_DEVINFO_DATA)
        if not setupapi.SetupDiEnumDeviceInfo(hdev, i, ctypes.byref(dev)):
            break
        i += 1
        hw = get_prop(hdev, dev, SPDRP_HARDWAREID) or []
        desc = get_prop(hdev, dev, SPDRP_DEVICEDESC) or ""
        friendly = get_prop(hdev, dev, SPDRP_FRIENDLYNAME) or ""
        cls = get_prop(hdev, dev, SPDRP_CLASS) or ""
        svc = get_prop(hdev, dev, SPDRP_SERVICE) or ""
        loc = get_prop(hdev, dev, SPDRP_LOCATION_INFORMATION) or ""
        out.append(dict(hwid=hw, desc=desc, friendly=friendly, cls=cls, svc=svc, loc=loc))
    setupapi.SetupDiDestroyDeviceInfoList(hdev)
    return out


def main():
    devices = enumerate_devices()
    print(f"enumerated {len(devices)} present device node(s)")
    print("=" * 78)
    print("8BitDo / interesting USB+HID nodes:")
    hits = 0
    for d in devices:
        hw = d["hwid"]
        blob = " | ".join(hw).upper()
        if not any(("VID_%s" % v) in blob for v in TARGET_VIDS):
            continue
        hits += 1
        print(f"\n  desc      : {d['desc']}")
        print(f"  friendly  : {d['friendly']}")
        print(f"  class     : {d['cls']}   service: {d['svc']}   loc: {d['loc']}")
        for h in hw:
            print(f"  hwid      : {h}")
    if not hits:
        print("  (none)")

    print("\n" + "=" * 78)
    print("All HID-class / keyboard-ish nodes (to spot boot mode):")
    for d in devices:
        cls = (d["cls"] or "").lower()
        blob = (d["desc"] + " " + d["friendly"] + " " + " ".join(d["hwid"])).lower()
        if cls in ("hidclass", "keyboard", "mouse") or "hid\\" in blob:
            print(f"  [{d['cls']}] {d['desc']} | {d['friendly']} | {d['svc']}")
            for h in d["hwid"]:
                print(f"      {h}")


if __name__ == "__main__":
    sys.exit(main())
