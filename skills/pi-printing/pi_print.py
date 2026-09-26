# -*- coding: utf-8 -*-
"""经 Raspberry Pi 用 IPP 协议向家中打印机发送 PDF 打印任务。

用法: python3 pi_print.py <pdf_path> [printer_ip]
默认打印机: HP LaserJet MFP M29w @ 192.168.1.220（2026-09-26 实测）
"""
from __future__ import annotations

import http.client
import struct
import sys

PRINTER_IP = "192.168.1.220"
IPP_PATH = "/ipp/print"

# IPP value tags
TAG_CHARSET = 0x47
TAG_LANG = 0x48
TAG_URI = 0x45
TAG_NAME = 0x42
TAG_MIMETYPE = 0x49


def _attr(tag: int, name: str, value: str) -> bytes:
    nb = name.encode("utf-8")
    vb = value.encode("utf-8")
    return struct.pack(">B", tag) + struct.pack(">H", len(nb)) + nb + struct.pack(">H", len(vb)) + vb


def build_print_job(pdf_data: bytes, user: str = "aurelius") -> bytes:
    body = struct.pack(">BBHI", 0x01, 0x01, 0x0002, 1)  # v1.1, Print-Job, req-id 1
    body += struct.pack(">B", 0x01)  # operation-attributes-tag
    body += _attr(TAG_CHARSET, "attributes-charset", "utf-8")
    body += _attr(TAG_LANG, "attributes-natural-language", "en")
    body += _attr(TAG_URI, "printer-uri", f"ipp://{PRINTER_IP}{IPP_PATH}")
    body += _attr(TAG_NAME, "requesting-user-name", user)
    body += _attr(TAG_MIMETYPE, "document-format", "application/octet-stream")
    body += struct.pack(">B", 0x03)  # end-of-attributes-tag
    return body + pdf_data


def print_pdf(pdf_path: str, printer_ip: str = PRINTER_IP) -> int:
    with open(pdf_path, "rb") as f:
        pdf_data = f.read()
    body = build_print_job(pdf_data)
    conn = http.client.HTTPConnection(printer_ip, 631, timeout=60)
    conn.request("POST", IPP_PATH, body=body, headers={"Content-Type": "application/ipp"})
    resp = conn.getresponse()
    data = resp.read()
    ipp_status = struct.unpack(">H", data[2:4])[0] if len(data) >= 4 else -1
    print(f"http={resp.status} ipp-status=0x{ipp_status:04x}")
    return ipp_status


if __name__ == "__main__":
    sys.exit(0 if print_pdf(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else PRINTER_IP) == 0 else 1)
