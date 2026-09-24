#!/usr/bin/env python3
"""Unit tests for render_reel.py — ZenPixelWalls Reel renderer.

Architecture v3 (2026-09-23, user verdict on v2: "日期没渐变，卡点也不对，
日期的切换完全random"):
- The lockscreen UI is baked onto each slot clip BEFORE the xfade chain:
  [raw{i}][ui_i]overlay -> xfade. The date crossfades WITH the wallpaper,
  so the "卡点" is the transition itself — perfectly synced by construction.
- ONE fixed UI geometry for every slot (UI_TIME_Y / UI_DATE_Y / sizes /
  UI_STYLE font — user: "就一个格式"). Only the text color adapts to
  wallpaper brightness for readability. Identical geometry means the date
  never jumps position or doubles mid-fade (the v1 "还没渐变" ghosting and
  the v2 midpoint hard-cut "random" switching are both gone).
- 0.8s xfade chain (motto -> slots -> end card), total 14.5s.
- No post-xfade UI track, no hard cuts, no -loop 1, no -shortest.

Run: python3 -m pytest test_render_reel.py -v
"""
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest
from PIL import Image
import render_reel
from render_reel import (build_video_cmd, build_lock_ui, UI_STYLE, FPS,
                         MOTTO_D, END_D, XF, UI_TIME_Y, UI_DATE_Y,
                         UI_TIME_SIZE, UI_DATE_SIZE)
import datetime


def make_cfg(n=5, dwells=None, motions=None):
    """Minimal config for build_video_cmd (no image processing)."""
    cfg = {
        "slug": "test",
        "images": [{"src": f"/tmp/fake_{i}.jpg"} for i in range(n)],
    }
    if dwells is not None:
        cfg["slot_dwells"] = dwells
    if motions is not None:
        cfg["motion"] = motions
    return cfg


def make_cmd(n=5, dwell=2.0):
    """Build a command with default dwells; returns (fc, filter, offs)."""
    dwells = [dwell] * n
    clip_ds = [d + XF for d in dwells]  # raw clip length incl. xfade tail
    motions = ["zin"] * n
    fc, offs = build_video_cmd(make_cfg(n), "/tmp/fake", n, dwells,
                               clip_ds, motions)
    idx = fc.index("-filter_complex")
    return fc, fc[idx + 1], offs


def get_inputs(fc):
    """Extract the input section (between 'ffmpeg...' and '-filter_complex')."""
    idx = fc.index("-filter_complex")
    return fc[1:idx]  # skip 'ffmpeg', '-y', '-v', 'error'


class TestXfadeChain:
    """xfade crossfades must be present with correct offsets (user: 加回渐变)."""

    def test_returns_two_tuple(self):
        res = build_video_cmd(make_cfg(5), "/tmp/fake", 5,
                              [2.0] * 5, [2.8] * 5, ["zin"] * 5)
        assert isinstance(res, tuple) and len(res) == 2, \
            "build_video_cmd must return (fc, offs) — no ui_start in v3"
        fc, offs = res
        assert isinstance(offs, list) and len(offs) == 6

    def test_xfade_present(self):
        _, flt, _ = make_cmd()
        assert "xfade=transition=fade" in flt

    def test_xfade_count(self):
        n = 5
        _, flt, _ = make_cmd(n=n)
        cnt = flt.count("xfade=transition=fade")
        assert cnt == n + 1, f"Expected {n+1} xfades, got {cnt}"

    def test_xfade_duration(self):
        _, flt, _ = make_cmd()
        durs = set(re.findall(r"xfade=transition=fade:duration=([\d.]+):", flt))
        assert durs == {str(XF)}, f"xfade durations must all be {XF}, got {durs}"

    def test_xfade_offsets(self):
        n = 5
        _, flt, offs = make_cmd(n=n)
        found = [float(m) for m in
                 re.findall(r"xfade=transition=fade:duration=[\d.]+:offset=([\d.]+)", flt)]
        assert len(found) == n + 1
        assert abs(found[0] - (MOTTO_D - XF)) < 1e-6
        for k in range(1, len(found)):
            assert abs((found[k] - found[k - 1]) - 2.0) < 1e-6
        assert found == pytest.approx(offs)

    def test_total_duration(self):
        fc, _, _ = make_cmd()
        idx = fc.index("-t")
        assert abs(float(fc[idx + 1]) - 14.5) < 1e-6, \
            "Total must be MOTTO_D + sum(dwells) + END_D - XF = 14.5"


class TestUIBakedBeforeXfade:
    """v3 ARCHITECTURE (user 2026-09-23: date must fade WITH the wallpaper).

    The UI is composited onto each slot clip BEFORE the xfade chain, so the
    date goes through the same 0.8s crossfade as the wallpaper — the 卡点 is
    the transition itself, synced by construction. v2's post-xfade UI track
    with hard cuts at midpoints ("日期没渐变，卡点也不对，切换random") is gone.
    """

    def test_ui_baked_onto_each_slot(self):
        """Each slot clip gets [raw{i}][ui]overlay before xfade."""
        n = 5
        _, flt, _ = make_cmd(n=n)
        for i in range(n):
            pat = re.compile(rf"\[raw{i}\]\[\d+:v\]overlay[^;]*\[v{i+1}\]")
            assert pat.search(flt), \
                f"slot {i}: expected [raw{i}][ui]overlay bake -> [v{i+1}]"

    def test_bake_before_first_xfade(self):
        """All UI bakes must appear textually before the first xfade."""
        _, flt, _ = make_cmd()
        first_xfade = flt.index("xfade=transition=fade")
        for m in re.finditer(r"\[raw\d+\]\[\d+:v\]overlay", flt):
            assert m.start() < first_xfade, \
                "UI bake must come before the xfade chain"

    def test_no_post_xfade_ui_track(self):
        """No separate UI video track overlaid after xfade (v2 design)."""
        _, flt, _ = make_cmd()
        assert "eof_action=pass" not in flt, "v2 UI-track overlay must be gone"
        assert "enable='gte(t," not in flt, "v2 midpoint hard-cut must be gone"
        assert "[uiv]" not in flt, "v2 UI concat track must be gone"
        assert "setpts=PTS+" not in flt, "v2 UI delay must be gone"

    def test_final_output_is_xfade_result(self):
        """The mapped output must be the xfade chain result, not a UI overlay."""
        fc, flt, _ = make_cmd()
        # -map [vout]: vout is the last xfade output label
        assert "-map" in fc and "[vout]" in fc
        assert re.search(r"xfade=transition=fade:duration=[\d.]+:offset=[\d.]+\[vout\]", flt), \
            "last xfade must output [vout]"
        assert "[vfinal]" not in flt, "v2 [vfinal] UI-overlay label must be gone"

    def test_ui_inputs_are_single_pngs(self):
        """n single-frame ui PNG inputs (one per slot, color may differ)."""
        n = 5
        fc, _, _ = make_cmd(n=n)
        inputs = get_inputs(fc)
        ui_ins = [inputs[i + 1] for i, v in enumerate(inputs)
                  if v == "-i" and inputs[i + 1].endswith(".png")
                  and "/ui_" in inputs[i + 1]]
        assert len(ui_ins) == n, f"Expected {n} ui PNG inputs, got {len(ui_ins)}"

    def test_no_loop1_race(self):
        """No -loop 1 image inputs (2026-09-23 race fix still holds)."""
        fc, _, _ = make_cmd()
        inputs = get_inputs(fc)
        assert "-loop" not in inputs

    def test_no_shortest(self):
        fc, _, _ = make_cmd()
        assert "-shortest" not in fc


class TestSingleUIGeometry:
    """'就一个格式': identical UI geometry on every slot.

    Only the text color may adapt (readability); position, size and font are
    fixed, so the date can never jump or double mid-fade.
    """

    def test_geometry_constants_sane(self):
        assert 0 < UI_DATE_Y < UI_TIME_Y < 1920
        assert UI_TIME_SIZE > UI_DATE_SIZE > 0

    def test_identical_layout_for_different_colors(self):
        """Same layout (alpha channel) regardless of text color."""
        now = datetime.datetime(2026, 9, 23, 21, 30)
        p1, p2 = "/tmp/t_ui_white.png", "/tmp/t_ui_dark.png"
        build_lock_ui(p1, now, (255, 255, 255))
        build_lock_ui(p2, now, (28, 28, 28))
        a1 = Image.open(p1).split()[3]
        a2 = Image.open(p2).split()[3]
        assert list(a1.getdata()) == list(a2.getdata()), \
            "UI layout must be pixel-identical; only color may differ"

    def test_unified_typography(self):
        """UI_STYLE still the single Inter Light style for all slots."""
        assert UI_STYLE["time_tr"] == 10 and UI_STYLE["date_tr"] == 3

    def test_ui_has_date_and_clock(self):
        """The baked UI actually contains visible date + clock + home bar."""
        now = datetime.datetime(2026, 9, 23, 21, 30)
        p = "/tmp/t_ui_content.png"
        build_lock_ui(p, now, (255, 255, 255))
        im = Image.open(p).convert("L")
        assert im.getbbox() is not None, "UI must not be empty"
        # date band (top) and clock band (middle) both non-empty
        assert im.crop((0, 0, 1080, 400)).getbbox() is not None
        assert im.crop((0, 400, 1080, 700)).getbbox() is not None

    def test_old_build_slot_ui_removed(self):
        """Per-slot adapted-geometry builder must not exist anymore."""
        assert not hasattr(render_reel, "build_slot_ui"), \
            "build_slot_ui (adapted position/size) removed; use build_lock_ui"


class TestAnalyzeWallpaperBand:
    """v3: text color decided by the FIXED UI band, not top-60% average."""

    def test_bright_band_gives_dark_text(self):
        from PIL import Image as PILImage, ImageDraw
        wk = PILImage.new("RGB", (1620, 2880), (30, 30, 30))
        d = ImageDraw.Draw(wk)
        d.rectangle([270, 380, 1350, 500], fill=(230, 230, 230))  # bright date band
        spec = render_reel.analyze_wallpaper(wk)
        assert spec["dark"] is False and spec["color"] == (28, 28, 28)

    def test_dark_band_gives_white_text(self):
        from PIL import Image as PILImage, ImageDraw
        wk = PILImage.new("RGB", (1620, 2880), (200, 200, 200))
        d = ImageDraw.Draw(wk)
        d.rectangle([270, 380, 1350, 500], fill=(20, 20, 20))
        d.rectangle([270, 620, 1350, 830], fill=(20, 20, 20))
        spec = render_reel.analyze_wallpaper(wk)
        assert spec["dark"] is True and spec["color"] == (255, 255, 255)

    def test_brighter_of_two_bands_wins(self):
        """Bright date band + dark clock band -> dark text (date needs it)."""
        from PIL import Image as PILImage, ImageDraw
        wk = PILImage.new("RGB", (1620, 2880), (20, 20, 20))
        d = ImageDraw.Draw(wk)
        d.rectangle([270, 380, 1350, 500], fill=(230, 230, 230))
        spec = render_reel.analyze_wallpaper(wk)
        assert spec["color"] == (28, 28, 28)

    def test_spec_shape(self):
        from PIL import Image as PILImage
        spec = render_reel.analyze_wallpaper(PILImage.new("RGB", (1620, 2880), (0,0,0)))
        assert set(spec.keys()) == {"dark", "color"}
