# -*- coding: utf-8 -*-
"""pi_print.py 的单元测试：IPP 请求报文结构必须合法。"""
import struct
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pi_print import build_print_job


def test_ipp_envelope():
    body = build_print_job(b"%PDF-1.4 fake")
    # version 1.1
    assert body[0] == 0x01 and body[1] == 0x01
    # operation-id Print-Job
    assert struct.unpack(">H", body[2:4])[0] == 0x0002
    # operation-attributes-tag
    assert body[8] == 0x01
    # end-of-attributes-tag 出现在 PDF 数据之前
    assert b"\x03%PDF-1.4 fake" in body


def test_required_attributes_present():
    body = build_print_job(b"DATA")
    for name in [b"attributes-charset", b"printer-uri", b"document-format",
                 b"requesting-user-name", b"attributes-natural-language"]:
        assert name in body
    assert b"application/octet-stream" in body
    assert b"ipp://192.168.1.220/ipp/print" in body


def test_pdf_appended_after_end_tag():
    pdf = b"%PDF-FAKEDATA-12345"
    body = build_print_job(pdf)
    assert body.endswith(pdf)
