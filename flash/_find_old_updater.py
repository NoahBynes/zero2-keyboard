#!/usr/bin/env python3
"""Look for older 8BitDo firmware updater builds in the Wayback Machine and on
the official download host (read-only probes)."""
import json
import urllib.request

UA = {"User-Agent": "Mozilla/5.0"}
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def get(url, timeout=30):
    req = urllib.request.Request(url, headers=UA)
    with opener.open(req, timeout=timeout) as r:
        return r.read()


def cdx(pattern, limit=100):
    url = ("http://web.archive.org/cdx/search/cdx?url=" + urllib.parse.quote(pattern, safe="")
           + "&output=json&limit=%d&filter=statuscode:200" % limit)
    try:
        data = json.loads(get(url).decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        print("CDX ERROR", pattern, e)
        return
    print("==", pattern)
    for row in data[:limit]:
        if len(row) >= 3:
            print("  ", row[1], row[2])


import urllib.parse  # noqa: E402

for pat in (
    "download.8bitdo.com/Tools/FirmwareUpdater/*",
    "download.8bitdo.cn/Tools/FirmwareUpdater/*",
    "support.8bitdo.com/firmware-updater.html",
):
    cdx(pat, 60)

# probe some plausible older file names
for name in (
    "8BitDo_Firmware_Updater_Win_V1.0.zip",
    "8BitDo_Firmware_Updater_Win_V2.0.zip",
    "8BitDo_Firmware_Updater_Win_2019.zip",
    "8BitDo_Firmware_Updater_Win_2020.zip",
    "8BitDo_Firmware_Updater_Win_2.0.zip",
    "8BitDo_FirmwareUpdater_Win.zip",
):
    url = "https://download.8bitdo.cn/Tools/FirmwareUpdater/" + name
    try:
        req = urllib.request.Request(url, method="HEAD", headers=UA)
        with opener.open(req, timeout=15) as r:
            print("HEAD", url, r.status, r.headers.get("Content-Length"))
    except Exception as e:  # noqa: BLE001
        print("HEAD", url, "->", e)
