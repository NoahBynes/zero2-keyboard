"""Download the official 8BitDo Zero 2 v1.08 firmware from 8BitDo's servers.

This keeps the repository free of 8BitDo's copyrighted firmware binary while
still letting users rebuild/customize it locally.

The official updater API is plain HTTP (no auth):

    POST http://dl.8bitdo.com:8080/firmware/select
    headers: Beta: 1, Type: 30          (Type 30 = Zero 2)
    body: empty
    -> {"msgState":1, "error":"", "list":[{
          "fileName":"Zero 2 gamepad", "version":1.08, "fileSize":124472,
          "filePathName":"/firmwareFile/upload/<uuid>.dat", "md5":"..."}, ...]}

Download URL = http://dl.8bitdo.com:8080 + filePathName.

Notes:
  * the "md5" field in the API is NOT the MD5 of the file content; it is
    MD5(str(fileSize)), which is what the official updater checks. We verify the
    size and a known content SHA-256 instead.
  * the patcher targets exactly v1.08; other versions have different offsets.
"""
import hashlib
import json
import os
import sys
import urllib.request

API_URL = "http://dl.8bitdo.com:8080/firmware/select"
API_ORIGIN = "http://dl.8bitdo.com:8080"
DEVICE_TYPE = "30"          # 8BitDo Zero 2
TARGET_VERSION = 1.08
BETA = ""

KNOWN_SHA256 = "43A313564AC1125DF1DE9C5B47C393FB5EBFC4D9FF70790E519FB72E609DA808"
EXPECTED_SIZE = 124472

# Last known good official URL for v1.08 (fallback if the API list changes/fails)
FALLBACK_PATHS = [
    "/firmwareFile/upload/69749f0f-bdf5-447c-be6a-d32f1394ed1e.dat",
]

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUT = os.path.join(HERE, "Zero2_V1.08.dat")

UA = "Zero2KeyboardToolkit/1.0 (+https://github.com/NoahBynes/zero2-keyboard)"


def _request(url, data=None, headers=None, timeout=40):
    h = {"User-Agent": UA}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h,
                                 method="POST" if data is not None else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def fetch_list(timeout=40):
    """Return the list of type-30 firmware entries."""
    raw = _request(API_URL, data=b"", headers={"Beta": "1", "Type": DEVICE_TYPE},
                   timeout=timeout)
    data = json.loads(raw.decode("utf-8", "replace"))
    if not isinstance(data, dict) or data.get("msgState") != 1:
        raise RuntimeError("官方固件接口返回异常: %s" % str(data)[:200])
    entries = data.get("list") or []
    if not isinstance(entries, list) or not entries:
        raise RuntimeError("官方固件列表为空（Type=%s）" % DEVICE_TYPE)
    return entries


def pick_entry(entries, version=TARGET_VERSION, beta=BETA):
    """Pick the entry whose float version is `version` (1.08)."""
    best = None
    for e in entries:
        try:
            ver = float(e.get("version", 0))
        except (TypeError, ValueError):
            continue
        if abs(ver - version) > 0.005:
            continue
        if str(e.get("beta", "")).strip() != beta:
            continue
        if not e.get("exists", True):
            continue
        best = e
        break
    if best is None:
        available = sorted({float(e.get("version", 0)) for e in entries})
        raise RuntimeError("官方列表里没有 v%.2f（可用版本: %s）"
                           % (version, ", ".join("%.2f" % v for v in available)))
    return best


def _sha256(data):
    return hashlib.sha256(data).hexdigest().upper()


def _md5(data):
    return hashlib.md5(data).hexdigest().upper()


def validate(data, force=False):
    """Validate downloaded bytes. Returns uid; raises on mismatch unless force."""
    if len(data) != EXPECTED_SIZE:
        raise RuntimeError("固件大小不对：%d，期望 %d" % (len(data), EXPECTED_SIZE))
    sha = _sha256(data)
    if sha != KNOWN_SHA256:
        msg = ("固件 SHA-256 与已知 v1.08 不一致（可能官方重新发布了同版本固件）。\n"
               "  期望: %s\n  实际: %s" % (KNOWN_SHA256, sha))
        if not force:
            raise RuntimeError(msg + "\n  如确认可用，请加 --force 重试。")
        print("[warn] " + msg, file=sys.stderr)
    return sha


def download(out=DEFAULT_OUT, force=False, timeout=60, quiet=False):
    """Download the known official v1.08 image to `out`. Returns the output path."""
    out = os.path.abspath(out)
    os.makedirs(os.path.dirname(out), exist_ok=True)

    if os.path.exists(out) and not force:
        data = open(out, "rb").read()
        try:
            sha = validate(data, force=False)
            if not quiet:
                print("[ok] 已存在官方固件：%s" % out)
                print("     size=%d sha256=%s" % (len(data), sha))
            return out
        except RuntimeError as e:
            if not quiet:
                print("[warn] 已存在的固件校验失败，重新下载：%s" % e)

    last_err = None
    urls = []
    try:
        entry = pick_entry(fetch_list(timeout=timeout))
        path = entry.get("filePathName") or ""
        if path.startswith("http://") or path.startswith("https://"):
            urls.append(path)
        elif path:
            urls.append(API_ORIGIN + path)
        if not quiet:
            print("[i] 官方列表：v%.2f size=%s date=%s"
                  % (float(entry.get("version", 0)), entry.get("fileSize"),
                     entry.get("date", "")))
            api_md5 = str(entry.get("md5") or "").upper()
            if api_md5 and api_md5 != _md5(str(entry.get("fileSize", "")).encode()):
                print("[warn] 官方 md5 字段与 MD5(str(fileSize)) 不一致（不致命）")
    except Exception as e:  # noqa: BLE001
        last_err = e
        if not quiet:
            print("[warn] 查询官方固件列表失败：%s" % e)
            print("[i] 尝试使用已知 v1.08 官方直链…")

    for p in FALLBACK_PATHS:
        urls.append(API_ORIGIN + p)
    seen = set()
    for url in urls:
        if not url or url in seen:
            continue
        seen.add(url)
        try:
            if not quiet:
                print("[i] 下载 %s" % url)
            data = _request(url, timeout=timeout)
            sha = validate(data, force=force)
            with open(out, "wb") as f:
                f.write(data)
            if not quiet:
                print("[ok] 已保存 %s" % out)
                print("     size=%d sha256=%s" % (len(data), sha))
            return out
        except Exception as e:  # noqa: BLE001
            last_err = e
            if not quiet:
                print("[warn] 失败：%s" % e)

    raise RuntimeError("无法下载官方 v1.08 固件：%s" % last_err)


if __name__ == "__main__":
    p = download()
    print(p)
