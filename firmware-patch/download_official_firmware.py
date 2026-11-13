#!/usr/bin/env python3
"""Download the official 8BitDo Zero 2 v1.08 firmware (required before patching).

Usage:
    python download_official_firmware.py              # download to Zero2_V1.08.dat
    python download_official_firmware.py --force      # re-download even if present
    python download_official_firmware.py --out X.dat  # custom output path
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import official_firmware  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="Download official 8BitDo Zero 2 v1.08 firmware")
    ap.add_argument("--out", default=official_firmware.DEFAULT_OUT,
                    help="output path (default: <this dir>/Zero2_V1.08.dat)")
    ap.add_argument("--force", action="store_true", help="re-download even if file exists")
    ap.add_argument("--sha256", action="store_true", help="only print the SHA-256 of the file")
    args = ap.parse_args()

    if args.sha256:
        import hashlib
        p = os.path.abspath(args.out)
        data = open(p, "rb").read()
        print("%s  %s  %d bytes" % (hashlib.sha256(data).hexdigest(), p, len(data)))
        return 0

    try:
        p = official_firmware.download(args.out, force=args.force)
    except Exception as e:  # noqa: BLE001
        print("[error] %s" % e, file=sys.stderr)
        print("\n可以手动下载官方固件后放到：%s\n"
              "官方更新器/产品页：https://support.8bitdo.cn/firmware-updater.html"
              % official_firmware.DEFAULT_OUT, file=sys.stderr)
        return 1
    print("\n完成：%s\n把该文件放在 firmware-patch/ 下即可开始改键/刷写。" % p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
