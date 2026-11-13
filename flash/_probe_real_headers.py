#!/usr/bin/env python3
"""Fetch the real 8BitDo firmware URL headers (bypassing any local proxy) so our
local proxy can mimic them byte-for-byte. Read-only network probe."""
import urllib.request

URL = ("http://dl.8bitdo.com:8080/firmwareFile/upload/"
       "69749f0f-bdf5-447c-be6a-d32f1394ed1e.dat")

opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
req = urllib.request.Request(URL, headers={
    "User-Agent": "Mozilla/5.0",
    "Accept": "*/*",
})
with opener.open(req, timeout=60) as r:
    data = r.read()
    print("status:", r.status)
    for k, v in r.headers.items():
        print(f"  {k}: {v}")
    print("body bytes:", len(data))
    print("first 32 bytes hex:", data[:32].hex())
