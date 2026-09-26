# -*- coding: utf-8 -*-
"""PDF -> PWG raster (image/pwg-raster)，给只接受光栅的打印机用（如 HP LaserJet MFP M29w）。

PWG 头结构严格按 CUPS raster-stream.c 的 CUPS_RASTER_WRITE_PWG 写入逻辑：
"RaS2" 同步字 + cups_page_header2_t（大端序，大部分字段清零）。
实测打印机声明 pwg-raster-document-type-supported = sgray_8。
"""
from __future__ import annotations

import struct
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

# CUPS_CSPACE_SW = 18 (sGray)，对应 sgray_8
CUPS_CSPACE_SW = 18


def _u32(v: int) -> bytes:
    return struct.pack(">I", v)


def _str64(s: str) -> bytes:
    b = s.encode("utf-8")[:63]
    return b + b"\x00" * (64 - len(b))


def pwg_page_header(width: int, height: int, dpi: int = 300,
                    page_w_pt: int = 842, page_h_pt: int = 595,
                    page_size_name: str = "iso_a4_210x297mm") -> bytes:
    """构造一页的 PWG 头（cups_page_header2_t，大端序）。"""
    h = b""
    h += _str64("PwgRaster")      # MediaClass
    h += _str64("")               # MediaColor
    h += _str64("")               # MediaType
    h += _str64("")               # OutputType
    h += _u32(0)                  # AdvanceDistance
    h += _u32(0)                  # AdvanceMedia
    h += _u32(0)                  # Collate
    h += _u32(0)                  # CutMedia
    h += _u32(0)                  # Duplex
    h += _u32(dpi) + _u32(dpi)    # HWResolution
    h += _u32(0) * 4              # ImagingBoundingBox
    h += _u32(0)                  # InsertSheet
    h += _u32(0)                  # Jog
    h += _u32(0)                  # LeadingEdge
    h += _u32(0) + _u32(0)        # Margins
    h += _u32(0)                  # ManualFeed
    h += _u32(0)                  # MediaPosition
    h += _u32(0)                  # MediaWeight
    h += _u32(0)                  # MirrorPrint
    h += _u32(0)                  # NegativePrint
    h += _u32(1)                  # NumCopies
    h += _u32(0)                  # Orientation
    h += _u32(0)                  # OutputFaceUp
    h += _u32(page_w_pt) + _u32(page_h_pt)  # PageSize (points)
    h += _u32(0)                  # Separations
    h += _u32(0)                  # TraySwitch
    h += _u32(0)                  # Tumble
    h += _u32(width)              # cupsWidth
    h += _u32(height)             # cupsHeight
    h += _u32(0)                  # cupsMediaType
    h += _u32(8)                  # cupsBitsPerColor
    h += _u32(8)                  # cupsBitsPerPixel
    h += _u32(width)              # cupsBytesPerLine
    h += _u32(0)                  # cupsColorOrder (chunked)
    h += _u32(CUPS_CSPACE_SW)     # cupsColorSpace (sGray)
    h += _u32(0)                  # cupsCompression (none)
    h += _u32(0)                  # cupsRowCount
    h += _u32(0)                  # cupsRowFeed
    h += _u32(0)                  # cupsRowStep
    h += _u32(1)                  # cupsNumColors
    h += struct.pack(">f", 0.0)   # cupsBorderlessScalingFactor
    h += struct.pack(">f", 0.0) * 2   # cupsPageSize
    h += struct.pack(">f", 0.0) * 4   # cupsImagingBBox
    h += _u32(0) * 8              # cupsInteger[0..7]
    h += struct.pack(">f", 0.0) * 16  # cupsReal[16]
    h += _str64("") * 16          # cupsString[16]
    h += _str64("")               # cupsMarkerType
    h += _str64("")               # cupsRenderingIntent
    h += _str64(page_size_name)   # cupsPageSizeName
    return h


def pdf_to_pwg(pdf_path: str, pwg_path: str, dpi: int = 300) -> int:
    """PDF 转 PWG raster 文件。返回页数。"""
    with tempfile.TemporaryDirectory() as tmp:
        prefix = str(Path(tmp) / "page")
        subprocess.run(
            ["pdftoppm", "-r", str(dpi), "-gray", "-png", pdf_path, prefix],
            check=True, capture_output=True,
        )
        pngs = sorted(Path(tmp).glob("page-*.png"))
        if not pngs:
            raise RuntimeError("pdftoppm 未生成任何页面")
        with open(pwg_path, "wb") as out:
            out.write(b"RaS2")  # PWG 同步字
            for png in pngs:
                img = Image.open(png).convert("L")
                w, hgt = img.size
                out.write(pwg_page_header(w, hgt, dpi))
                out.write(img.tobytes())
        return len(pngs)


if __name__ == "__main__":
    import sys
    n = pdf_to_pwg(sys.argv[1], sys.argv[2])
    print(f"pages={n}")
