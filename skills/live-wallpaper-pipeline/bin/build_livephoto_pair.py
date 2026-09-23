#!/usr/bin/env python3
"""Build an Apple Live Photo pair (JPEG + MOV) on Linux.

Recipe (publicly verified):
  1. JPEG: EXIF Apple MakerNote, tag 0x0011 (ContentIdentifier) = UUID string.
     MakerNote layout per exiftool's reverse-engineered spec
     (lib/Image/ExifTool/MakerNotes.pm + Apple.pm):
       bytes 0-9   : b"Apple iOS\\x00"
       bytes 10-13 : b"II*\\x00" (mini TIFF header: little-endian, magic 42)
       bytes 14+   : TIFF IFD, offsets relative to MakerNote start
  2. MOV: QuickTime Keys (mdta) com.apple.quicktime.content.identifier = same UUID
     -> written with exiftool (verified writable).
  3. still-image-time timed metadata track is NOT written (makelive, the
     reference tool, doesn't write it either; its pairs still import as Live
     Photos into Apple Photos). Whether the pair works as a *wallpaper*
     must be confirmed on a real iPhone.
"""
import struct
import subprocess
import sys
import uuid

import piexif


def build_apple_makernote(content_id: str) -> bytes:
    cid = content_id.encode("ascii")
    assert len(cid) == 36, "ContentIdentifier must be a 36-char UUID string"
    data = cid + b"\x00"  # 37 bytes incl. NUL

    blob = bytearray()
    blob += b"Apple iOS\x00"          # 0-9: signature
    blob += b"II*\x00"               # 10-13: mini TIFF header (LE, magic 42)
    # IFD starts at offset 14
    blob += struct.pack("<H", 1)     # 14-15: 1 entry
    str_offset = 14 + 2 + 12 + 4     # = 32: string data right after IFD
    blob += struct.pack("<HHI", 0x0011, 2, 37)  # tag, type=ASCII, count=37
    blob += struct.pack("<I", str_offset)        # value offset (rel. to MakerNote start)
    blob += struct.pack("<I", 0)     # next IFD offset = 0
    assert len(blob) == str_offset
    blob += data
    return bytes(blob)


def main():
    workdir, jpg_in, mov_in, base, cid = sys.argv[1:6]
    cid = cid.upper()

    # 1) JPEG with Apple MakerNote
    jpg_out = f"{workdir}/{base}.JPG"
    exif_dict = {
        "0th": {
            piexif.ImageIFD.Make: "Apple",
            piexif.ImageIFD.Model: "iPhone",
            piexif.ImageIFD.Software: "ZenPixelWalls Live",
        },
        "Exif": {
            piexif.ExifIFD.MakerNote: build_apple_makernote(cid),
            piexif.ExifIFD.ColorSpace: 1,
        },
    }
    piexif.insert(piexif.dump(exif_dict), jpg_in, jpg_out)

    # 2) MOV with matching ContentIdentifier (exiftool-verified writable)
    mov_out = f"{workdir}/{base}.MOV"
    subprocess.run(["cp", mov_in, mov_out], check=True)
    subprocess.run(
        ["/tmp/exiftool-src/exiftool", "-overwrite_original",
         f"-QuickTime:ContentIdentifier={cid}", mov_out],
        check=True, capture_output=True,
    )
    print(f"pair built: {jpg_out} + {mov_out}  CID={cid}")


if __name__ == "__main__":
    main()
