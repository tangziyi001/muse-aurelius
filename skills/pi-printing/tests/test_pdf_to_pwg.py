# -*- coding: utf-8 -*-
"""pdf_to_pwg.py 的单元测试：PWG 头结构必须符合 CUPS PWG 写入规范。"""
import struct
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pdf_to_pwg import pwg_page_header, CUPS_CSPACE_SW


def _get_u32(buf: bytes, offset: int) -> int:
    return struct.unpack(">I", buf[offset:offset + 4])[0]


def test_header_starts_with_strings():
    h = pwg_page_header(3508, 2479)
    assert h[:64].rstrip(b"\x00") == b"PwgRaster"


def test_header_dimensions_and_colorspace():
    w, hgt = 3508, 2479
    h = pwg_page_header(w, hgt)
    # 偏移量：4*64 字符串=256；5 个 u32=20；HWResolution 8 字节后是 cupsWidth…
    # 直接按字段顺序数：256 + 4*21 = 340 处是 cupsWidth
    # 逐字段走一遍更可靠，这里用已知偏移
    off = 256
    fields = ["AdvanceDistance", "AdvanceMedia", "Collate", "CutMedia", "Duplex",
              "HWResX", "HWResY", "BB0", "BB1", "BB2", "BB3",
              "InsertSheet", "Jog", "LeadingEdge", "MarginX", "MarginY",
              "ManualFeed", "MediaPosition", "MediaWeight", "MirrorPrint",
              "NegativePrint", "NumCopies", "Orientation", "OutputFaceUp",
              "PageW", "PageH", "Separations", "TraySwitch", "Tumble",
              "cupsWidth", "cupsHeight", "cupsMediaType", "cupsBitsPerColor",
              "cupsBitsPerPixel", "cupsBytesPerLine", "cupsColorOrder",
              "cupsColorSpace", "cupsCompression", "cupsRowCount", "cupsRowFeed",
              "cupsRowStep", "cupsNumColors"]
    vals = {}
    for f in fields:
        vals[f] = _get_u32(h, off)
        off += 4
    assert vals["cupsWidth"] == w
    assert vals["cupsHeight"] == hgt
    assert vals["cupsBitsPerColor"] == 8
    assert vals["cupsBitsPerPixel"] == 8
    assert vals["cupsBytesPerLine"] == w
    assert vals["cupsColorSpace"] == CUPS_CSPACE_SW == 18
    assert vals["cupsNumColors"] == 1
    assert vals["cupsCompression"] == 0
    assert vals["NumCopies"] == 1
    assert vals["HWResX"] == 300 and vals["HWResY"] == 300


def test_header_big_endian():
    h = pwg_page_header(3508, 2479)
    # cupsWidth=3508=0xDB4，大端序字节应为 00 00 0D B4
    assert h[256 + 4 * 29:256 + 4 * 30] == b"\x00\x00\x0d\xb4"
