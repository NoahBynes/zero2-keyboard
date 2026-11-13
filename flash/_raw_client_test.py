#!/usr/bin/env python3
"""Mimic a minimal raw-socket firmware downloader through the local proxy and
report what it receives. Helps debug why the official updater's download fails.
"""
import socket
import sys

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8888
PATH = "/firmwareFile/upload/zero2-custom.dat"
URL = "http://dl.8bitdo.cn:8080" + PATH

for version in ("HTTP/1.0", "HTTP/1.1"):
    print("=" * 70)
    print("request version:", version)
    s = socket.create_connection(("127.0.0.1", PORT), timeout=10)
    req = ("GET %s %s\r\nHost: dl.8bitdo.cn:8080\r\n\r\n" % (URL, version)).encode()
    s.sendall(req)
    s.settimeout(5)
    chunks = []
    try:
        while True:
            b = s.recv(65536)
            if not b:
                print("  connection closed by server (EOF)")
                break
            chunks.append(b)
    except socket.timeout:
        print("  TIMEOUT waiting for more data (server did not close)")
    s.close()
    data = b"".join(chunks)
    head, _, body = data.partition(b"\r\n\r\n")
    print("  received total:", len(data), "body:", len(body))
    print("  header:")
    for line in head.split(b"\r\n"):
        print("   ", line.decode("latin-1"))
