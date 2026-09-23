#!/usr/bin/env python3
"""Unit tests for render_reel.py — ZenPixelWalls Reel renderer.

Covers:
- 2026-09-23: `-loop 1 -t` race fix (deterministic loop filter).
- 2026-09-23 (pm): 0.8s xfade crossfades restored; per-slot UI baked onto the
  slot clip BEFORE the xfade chain so the date fades WITH the wallpaper
  (user: previously published reels did this). Single unified typography
  (UI_STYLE — "就一个格式"), no per-slot font rotation.
- Output -t used instead of -shortest (no silent audio truncation).

Run: python3 -m pytest test_render_reel.py -v
"""
import re
import sys
import os
import inspect

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest
import render_reel
from render_reel import build_video_cmd, UI_STYLE, FPS, MOTTO_D, END_D, XF


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
    """Build a command with default dwells; returns (fc, filter, total_d)."""
    dwells = [dwell] * n
    clip_ds = [d + XF for d in dwells]  # raw clip length incl. xfade tail
    motions = ["zin"] * n
    fc, total_d = build_video_cmd(make_cfg(n), "/tmp/fake", n, dwells,
                                  clip_ds, motions)
    idx = fc.index("-filter_complex")
    return fc, fc[idx + 1], total_d


def get_inputs(fc):
    """Extract the input section (between 'ffmpeg...' and '-filter_complex')."""
    idx = fc.index("-filter_complex")
    return fc[1:idx]  # skip 'ffmpeg', '-y', '-v', 'error'


class TestXfadeRestored:
    """REGRESSION (2026-09-23 pm, user: "加回渐变"): xfade must be back."""

    def test_xfade_present(self):
        """Filtergraph MUST contain xfade transitions (user wants fades back)."""
        _, flt, _ = make_cmd()
        assert "xfade=transition=fade" in flt, \
            "Filtergraph must contain xfade (user asked to restore fades)"

    def test_no_concat_hardcut(self):
        """Clips must NOT be concatenated with hard cuts anymore."""
        _, flt, _ = make_cmd()
        assert "concat=n=" not in flt, \
            "Filtergraph must not concat clips with hard cuts"

    def test_xfade_offsets(self):
        """xfade offsets: first = MOTTO_D - XF, then +dwell each step."""
        n = 5
        _, flt, _ = make_cmd(n=n)
        offs = [float(m) for m in re.findall(r"xfade=transition=fade:duration=[\d.]+:offset=([\d.]+)", flt)]
        assert len(offs) == n + 1, f"Expected {n+1} xfade offsets, got {len(offs)}: {offs}"
        assert abs(offs[0] - (MOTTO_D - XF)) < 1e-6, \
            f"First offset {offs[0]} != MOTTO_D - XF = {MOTTO_D - XF}"
        for k in range(1, len(offs)):
            assert abs((offs[k] - offs[k-1]) - 2.0) < 1e-6, \
                f"Offset step {k} should equal dwell 2.0, got {offs[k] - offs[k-1]}"

    def test_slot_clip_has_xfade_tail(self):
        """Slot zoompan clips must include the XF tail (d=84 for 2.0s dwell)."""
        _, flt, _ = make_cmd()
        assert "d=84" in flt, \
            "Slot clip must be 2.8s (dwell 2.0 + XF 0.8) -> zoompan d=84"

    def test_total_duration_14_5(self):
        """total_d = MOTTO_D + sum(dwells) + END_D - XF = 14.5s."""
        _, _, total_d = make_cmd()
        assert abs(total_d - 14.5) < 1e-9, f"total_d {total_d} != 14.5"

    def test_output_t_14_5(self):
        """Output must be cut with explicit -t 14.5 (not -shortest)."""
        fc, _, _ = make_cmd()
        idx = fc.index("-map")
        tail = fc[idx:]
        assert "-t" in tail and "14.5" in tail, \
            f"Output must use -t 14.5, got tail: {tail[-8:]}"
        assert "-shortest" not in fc, \
            "Must not use -shortest (silent audio truncation)"


class TestUIBakedBeforeXfade:
    """REGRESSION (2026-09-23 pm, user: "日期跟着壁纸一起渐变"):
    the date/time UI must be composited onto each slot clip BEFORE the
    xfade chain, so the whole frame (wallpaper + UI) crossfades as one."""

    def test_per_slot_ui_inputs(self):
        """There must be one ui_{i}.png input per slot (single frames)."""
        n = 5
        fc, _, _ = make_cmd(n=n)
        inputs = get_inputs(fc)
        for i in range(n):
            assert any(f"ui_{i}.png" in a for a in inputs), \
                f"ui_{i}.png input missing"

    def test_ui_inputs_have_no_loop_or_t(self):
        """Per-slot UI inputs must be single frames (no racy -loop/-t)."""
        n = 5
        fc, _, _ = make_cmd(n=n)
        inputs = get_inputs(fc)
        for i, arg in enumerate(inputs):
            if re.search(r"ui_\d+\.png", arg):
                segment = inputs[max(0, i-3):i+1]
                assert "-loop" not in segment, \
                    f"UI input must not use -loop (racy): {segment}"
                assert "-t" not in segment, \
                    f"UI input must not use -t (racy): {segment}"

    def test_ui_overlaid_before_xfade(self):
        """Each [raw{i}][u{i}]overlay must appear BEFORE the first xfade."""
        n = 5
        _, flt, _ = make_cmd(n=n)
        xfade_pos = flt.index("xfade")
        for i in range(n):
            tag = f"[raw{i}][u{i}]overlay"
            assert tag in flt, f"Missing baked UI overlay: {tag}"
            assert flt.index(tag) < xfade_pos, \
                f"{tag} must come BEFORE xfade (UI baked into slot clip)"

    def test_no_post_xfade_ui_track(self):
        """No separate UI video track overlaid after xfade (old hardcut way)."""
        _, flt, _ = make_cmd()
        assert "uivd" not in flt, "Post-xfade UI track must be gone"
        assert "between(t," not in flt, "Hardcut UI enable window must be gone"

    def test_single_format_builder_exists(self):
        """build_slot_ui must exist with NO slot_idx (one format, no rotation)."""
        builder = getattr(render_reel, "build_slot_ui", None)
        assert builder is not None, \
            "build_slot_ui missing (per-slot UI builder with unified style)"
        params = inspect.signature(builder).parameters
        assert "slot_idx" not in params, \
            f"build_slot_ui must not take slot_idx (no per-slot rotation): {list(params)}"

    def test_ui_style_is_single_dict(self):
        """UI_STYLE must be one dict (not a list of rotating styles)."""
        assert isinstance(UI_STYLE, dict), \
            f"UI_STYLE must be a single dict, got {type(UI_STYLE)}"
        assert set(UI_STYLE) >= {"time", "date"}, \
            f"UI_STYLE missing time/date keys: {set(UI_STYLE)}"


class TestNoLoopRace:
    """REGRESSION: `-loop 1 -t` image inputs are racy with many inputs."""

    def test_end_text_has_no_loop(self):
        """End-card text input must avoid -loop 1 -t (same race)."""
        fc, _, _ = make_cmd()
        inputs = get_inputs(fc)
        for i, arg in enumerate(inputs):
            if "end_text.png" in arg:
                segment = inputs[max(0, i-3):i+1]
                assert "-loop" not in segment, \
                    f"end_text input must not use -loop: {segment}"
                assert "-t" not in segment, \
                    f"end_text input must not use -t: {segment}"
                break
        else:
            pytest.fail("end_text.png not found in inputs")

    def test_end_text_loop_filter_count(self):
        """End-card text must use deterministic loop filter."""
        _, flt, _ = make_cmd()
        expected_frames = int(round(END_D * FPS))  # 99
        expected_loop = expected_frames - 2  # 97
        pattern = f"loop=loop={expected_loop}:size=1:start=0"
        assert pattern in flt, \
            f"end_text must use loop=loop={expected_loop} for {expected_frames} frames"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
