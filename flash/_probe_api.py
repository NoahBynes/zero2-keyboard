#!/usr/bin/env python3
"""Query the real 8BitDo API for /firmware/loadNewVersion to learn the schema."""
import json
import urllib.request

BASE = "http://dl.8bitdo.com:8080"
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def post(path, headers, data=b""):
    req = urllib.request.Request(BASE + path, data=data, method="POST",
                                 headers=dict({"User-Agent": "zero2-probe"}, **headers))
    with opener.open(req, timeout=20) as r:
        body = r.read()
    print("==", path, headers)
    print("status:", r.status, "ctype:", r.headers.get("Content-Type"), "len:", len(body))
    try:
        print(json.dumps(json.loads(body.decode("utf-8")), indent=2, ensure_ascii=False)[:4000])
    except Exception:
        print(body[:1000])


for hdrs in ({"Beta": "1", "Type": "30"},):
    for path in ("/firmware/loadNewVersion", "/firmware/select"):
        try:
            post(path, hdrs)
        except Exception as e:
            print(path, "ERROR", e)
