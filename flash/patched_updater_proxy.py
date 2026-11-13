#!/usr/bin/env python3
"""Local HTTP proxy/server that makes the official 8BitDo Firmware Updater
download OUR patched Zero 2 firmware instead of the official one.

The official updater downloads firmware over plain HTTP from
``http://dl.8bitdo.com:8080`` / ``http://dl.8bitdo.cn:8080`` and does not verify
any signature. This script answers ``/firmware/select`` with a Zero 2 entry
pointing at our file and serves the patched ``.dat`` bytes for
``/firmwareFile/upload/...``. Everything else is forwarded or answered with an
empty JSON object.

Usage:
    python patched_updater_proxy.py --patched ../firmware-patch/out/Zero2_V1.09_identify.dat
    python patched_updater_proxy.py --patched ... --selftest
"""
import argparse
import hashlib
import json
import os
import sys
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CACHE_JSON = os.path.join(ROOT, "firmware-patch", "firmware.results.json")
API_JSON = os.path.join(ROOT, "_fw-tools", "firmware", "api_type30_all.json")
PATCHED_NAME = "zero2-custom.dat"
DEVICE_TYPES = {29, 30}          # Win tool table says 29, official API uses 30
HOSTS = {"dl.8bitdo.com", "dl.8bitdo.cn", "beta.8bitdo.com"}
REAL_ETAG = 'W/"124472-1749438382378"'
REAL_LASTMOD = "Mon, 09 Jun 2025 03:06:22 GMT"


def log(msg):
    print(time.strftime("[%H:%M:%S] ") + msg, flush=True)


def load_official_lists():
    lists = {}
    if os.path.exists(CACHE_JSON):
        try:
            raw = json.load(open(CACHE_JSON, encoding="utf-8"))
            lists = {int(k): v for k, v in raw.items()}
        except Exception as e:  # noqa: BLE001
            log("! cannot parse %s: %s" % (CACHE_JSON, e))
    if not lists and os.path.exists(API_JSON):
        try:
            lists[30] = json.load(open(API_JSON, encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            log("! cannot parse %s: %s" % (API_JSON, e))
    return lists


class Handler(BaseHTTPRequestHandler):
    server_version = "zero2-patch-proxy"
    protocol_version = "HTTP/1.1"

    # ---------- helpers ----------
    def _read_body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else b""

    def _send(self, code, body=b"", ctype="application/octet-stream", extra=None):
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
            except Exception:  # noqa: BLE001 - client aborted; nothing to do
                pass

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=True).encode("utf-8")
        self._send(code, body, "application/json; charset=utf-8")

    def log_message(self, fmt, *args):
        pass

    # ---------- routing ----------
    def _target(self):
        raw = self.path
        if raw.startswith("http://") or raw.startswith("https://"):
            u = urllib.parse.urlsplit(raw)
            return raw, u.hostname, u.path or "/"
        host = (self.headers.get("Host") or "").split(":")[0]
        return "http://%s%s" % (self.headers.get("Host"), raw), host, raw

    def do_OPTIONS(self):  # noqa: N802
        self._send(200, b"", "text/plain")

    def do_HEAD(self):  # noqa: N802
        self._handle("HEAD")

    def do_GET(self):  # noqa: N802
        self._handle("GET")

    def do_POST(self):  # noqa: N802
        self._handle("POST")

    def _handle(self, method):
        url, host, path = self._target()
        body = self._read_body()
        log("%s %s  (Type=%r len=%d)" % (method, url, self.headers.get("Type"), len(body)))

        # Windows connectivity probes: answer locally instead of forwarding
        if host and "msftconnecttest.com" in host:
            return self._send(200, b"Microsoft Connect Test", "text/plain")
        if host and "msftncsi.com" in host:
            return self._send(200, b"Microsoft NCSI", "text/plain")

        if path.startswith("/firmwareFile/"):
            log("  [hdr] %r reqline=%r version=%r"
                % ({str(k): str(v) for k, v in self.headers.items()},
                   self.requestline, self.request_version))

        if host in HOSTS or host is None or path.startswith("/firmware"):
            if path.rstrip("/") == "/firmware/select":
                return self._firmware_select()
            if path.startswith("/firmwareFile/"):
                return self._firmware_file(path)
            if path.startswith("/firmware/"):
                return self._json({})
        return self._forward(method, url, body)

    # ---------- endpoints ----------
    def _firmware_select(self):
        try:
            dev_type = int(self.headers.get("Type"))
        except (TypeError, ValueError):
            dev_type = 30
        entry = dict(App.patched_entry)
        entry["type"] = dev_type if dev_type in DEVICE_TYPES else 30
        log("  -> serving patched firmware list for type %d (v%s, %d bytes)"
            % (dev_type, entry["version"], entry["fileSize"]))
        self._json({"msgState": 1, "error": "", "list": [entry]})

    def _firmware_file(self, path):
        if not path.rstrip("/").endswith("/" + PATCHED_NAME):
            return self._forward("GET", "http://dl.8bitdo.com:8080" + path, b"")
        data = App.patched_bytes
        extra = {"ETag": REAL_ETAG, "Last-Modified": REAL_LASTMOD}
        log("  -> sending patched firmware (%d bytes, sha256=%s...)"
            % (len(data), hashlib.sha256(data).hexdigest()[:16]))
        rng = self.headers.get("Range")
        if rng:
            log("     Range: %r" % (rng,))
            try:
                spec = rng.split("=", 1)[1].strip()
                a, _, b = spec.partition("-")
                start = int(a) if a else 0
                end = int(b) if b else len(data) - 1
                end = min(end, len(data) - 1)
                part = data[start:end + 1]
                extra["Content-Range"] = "bytes %d-%d/%d" % (start, end, len(data))
                return self._send(206, part, ctype=None, extra=extra)
            except Exception as e:  # noqa: BLE001
                log("     bad Range header (%s); serving full body" % e)
        return self._send(200, data, ctype=None, extra=extra)

    def _forward(self, method, url, body):
        try:
            req = urllib.request.Request(
                url, data=body if method in ("POST", "PUT") else None,
                method=method,
                headers={"User-Agent": self.headers.get("User-Agent", "zero2-proxy")})
            with urllib.request.urlopen(req, timeout=15) as r:
                data = r.read()
            self._send(r.status, data, r.headers.get("Content-Type"))
            log("  -> forwarded %s (%d bytes)" % (url, len(data)))
        except Exception as e:  # noqa: BLE001
            log("  -> forward failed %s: %s" % (url, e))
            self._json({}, 200)


class App:
    patched_bytes = b""
    patched_entry = {}


def build_entry(official_list, patched_path, version):
    data = open(patched_path, "rb").read()
    # The updater's integrity check is weird: Tools.GenerateMD5(length.ToString()),
    # i.e. md5 of the decimal file-size string (not of the file bytes).
    md5 = hashlib.md5(str(len(data)).encode()).hexdigest().upper()
    base = {}
    for entry in official_list or []:
        if entry.get("fileName", "").lower().startswith("zero 2"):
            base = dict(entry)
            break
    if not base and official_list:
        base = dict(official_list[0])
    base.update({
        "date": time.strftime("%Y-%m-%d"),
        "fileName": base.get("fileName", "Zero 2 gamepad"),
        "version": float(version),
        "fileSize": len(data),
        "filePathName": "/firmwareFile/upload/" + PATCHED_NAME,
        "fileURL": "/var/lib/tomcat9/webapps/firmwareFile/upload/" + PATCHED_NAME,
        "exists": True,
        "beta": "",
        "md5": md5,
        "readme": "Zero 2 custom keyboard firmware (local build, own device only)",
        "readme_en": "Zero 2 custom keyboard firmware (local build, own device only)",
    })
    return data, base


def selftest(port):
    proxy = "http://127.0.0.1:%d" % port
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({"http": proxy}))
    url = "http://dl.8bitdo.com:8080/firmware/select"
    req = urllib.request.Request(url, data=b"", method="POST",
                                 headers={"Beta": "1", "Type": "30"})
    with opener.open(req, timeout=10) as r:
        payload = json.loads(r.read().decode("utf-8"))
    entries = payload.get("list") or []
    assert entries, "empty list"
    e = entries[0]
    assert abs(float(e["version"]) - 1.09) < 1e-6, e
    assert e["fileSize"] == len(App.patched_bytes), e
    log("SELFTEST select OK: %s v%s %sB md5=%s"
        % (e["fileName"], e["version"], e["fileSize"], e["md5"]))
    furl = "http://dl.8bitdo.com:8080" + e["filePathName"]
    with opener.open(furl, timeout=30) as r:
        got = r.read()
    want = hashlib.sha256(App.patched_bytes).hexdigest()
    assert hashlib.sha256(got).hexdigest() == want, "downloaded bytes mismatch"
    log("SELFTEST download OK: %d bytes sha256=%s..." % (len(got), want[:16]))
    log("SELFTEST PASSED")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--patched", required=True, help="patched .dat to serve")
    ap.add_argument("--version", type=float, default=1.09, help="advertised version")
    ap.add_argument("--port", type=int, default=8888)
    ap.add_argument("--bind", default="127.0.0.1")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if not os.path.exists(args.patched):
        sys.exit("patched firmware not found: %s" % args.patched)
    official = load_official_lists()
    App.patched_bytes, App.patched_entry = build_entry(
        official.get(30) or official.get(29), args.patched, args.version)
    log("patched file : %s (%d bytes)" % (args.patched, len(App.patched_bytes)))
    log("advertised   : v%s path=%s" % (args.version, App.patched_entry["filePathName"]))
    log("official data: %d device type list(s) cached" % len(official))

    httpd = ThreadingHTTPServer((args.bind, args.port), Handler)
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    log("listening on http://%s:%d  (set this as HTTP proxy)" % (args.bind, args.port))

    if args.selftest:
        try:
            selftest(args.port)
        finally:
            httpd.shutdown()
        return
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log("bye")
        httpd.shutdown()


if __name__ == "__main__":
    main()
