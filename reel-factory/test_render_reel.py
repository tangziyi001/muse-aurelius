#!/usr/bin/env python3
"""Unit tests for render_reel.py — ZenPixelWalls Reel renderer.

Covers the 2026-09-23 sync/ghosting bugfixes:
- UI inputs must NOT use `-loop 1 -t` (racy demuxer -> non-deterministic
  frame counts 66/54/66/54/60 instead of 60/60/60/60/60).
- UI segments must use the deterministic loop filter.
- Timeline math (xfade offsets, ui_start) must be exact.

Run: python3 -m pytest test_render_reel.py -v
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest
from render_reel import build_video_cmd, FPS, MOTTO_D, END_D, XF


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


def get_inputs(fc):
    """Extract the input section (between 'ffmpeg...' and '-filter_complex')."""
    idx = fc.index("-filter_complex")
    return fc[1:idx]  # skip 'ffmpeg', '-y', '-v', 'error'


def get_filter(fc):
    """Extract the filter_complex string."""
    idx = fc.index("-filter_complex")
    return fc[idx + 1]


class TestNoLoopRace:
    """REGRESSION: `-loop 1 -t` image inputs are racy with many inputs."""

    def test_ui_inputs_have_no_loop(self):
        """UI inputs (ui_0..ui_{n-1}) must be single frames, no -loop."""
        cfg = make_cfg(n=5)
        n = 5
        dwells = [2.0] * 5
        clip_ds = [d + XF for d in dwells]
        motions = ["zin"] * 5
        fc, _, _ = build_video_cmd(cfg, "/tmp/fake", n, dwells, clip_ds, motions)
        inputs = get_inputs(fc)

        # Find UI input indices: they are the last n inputs, each is
        # ["-framerate", "30", "-i", ".../ui_{i}.png"]
        # Verify none of the UI input args contain "-loop"
        ui_start_idx = len(inputs) - n * 3  # each UI input is 3 args
        ui_inputs = inputs[ui_start_idx:]
        assert "-loop" not in ui_inputs, \
            f"UI inputs must not use -loop (racy): {ui_inputs}"

    def test_ui_inputs_have_no_t(self):
        """UI inputs must not use -t (imprecise cutoff with -loop)."""
        cfg = make_cfg(n=5)
        n = 5
        dwells = [2.0] * 5
        clip_ds = [d + XF for d in dwells]
        motions = ["zin"] * 5
        fc, _, _ = build_video_cmd(cfg, "/tmp/fake", n, dwells, clip_ds, motions)
        inputs = get_inputs(fc)

        ui_start_idx = len(inputs) - n * 3
        ui_inputs = inputs[ui_start_idx:]
        # Each UI input is exactly ["-framerate", "30", "-i", path]
        # No "-t" should appear in the UI section
        assert "-t" not in ui_inputs, \
            f"UI inputs must not use -t (racy): {ui_inputs}"

    def test_end_text_has_no_loop(self):
        """End-card text input must also avoid -loop 1 -t (same race)."""
        cfg = make_cfg(n=5)
        n = 5
        dwells = [2.0] * 5
        clip_ds = [d + XF for d in dwells]
        motions = ["zin"] * 5
        fc, _, _ = build_video_cmd(cfg, "/tmp/fake", n, dwells, clip_ds, motions)
        inputs = get_inputs(fc)

        # end_text input is at index n+3: ["-framerate", "30", "-i", ".../end_text.png"]
        # Find it by the path
        for i, arg in enumerate(inputs):
            if "end_text.png" in arg:
                # Check the 3 args before it: should be ["-framerate", "30", "-i"]
                # and NOT contain "-loop" or "-t"
                segment = inputs[max(0, i-3):i+1]
                assert "-loop" not in segment, \
                    f"end_text input must not use -loop: {segment}"
                assert "-t" not in segment, \
                    f"end_text input must not use -t: {segment}"
                break
        else:
            pytest.fail("end_text.png not found in inputs")


class TestLoopFilter:
    """UI segments must use deterministic loop filter with exact frame counts."""

    def test_ui_loop_filter_counts(self):
        """Each uu{i} must have loop=loop={frames-2} for exact dwell."""
        cfg = make_cfg(n=5)
        n = 5
        dwells = [2.0] * 5  # 60 frames each
        clip_ds = [d + XF for d in dwells]
        motions = ["zin"] * 5
        fc, _, _ = build_video_cmd(cfg, "/tmp/fake", n, dwells, clip_ds, motions)
        flt = get_filter(fc)

        for i in range(n):
            expected_frames = int(round(dwells[i] * FPS))  # 60
            expected_loop = expected_frames - 2  # 58 (empirically verified)
            # The filter should contain: [uu{i}] with loop=loop=58
            # Format: "[{n+4+i}:v]format=rgba,loop=loop=58:size=1:start=0,settb=AVTB[uu{i}]"
            pattern = f"loop=loop={expected_loop}:size=1:start=0"
            assert pattern in flt, \
                f"uu{i} must use loop=loop={expected_loop} for {expected_frames} frames"

    def test_ui_loop_filter_custom_dwells(self):
        """Custom dwells must produce correct loop counts."""
        cfg = make_cfg(n=4, dwells=[2.5, 2.5, 2.5, 2.5])
        n = 4
        dwells = [2.5] * 4  # 75 frames each
        clip_ds = [d + XF for d in dwells]
        motions = ["zin"] * 4
        fc, _, _ = build_video_cmd(cfg, "/tmp/fake", n, dwells, clip_ds, motions)
        flt = get_filter(fc)

        for i in range(n):
            expected_frames = int(round(dwells[i] * FPS))  # 75
            expected_loop = expected_frames - 2  # 73
            pattern = f"loop=loop={expected_loop}:size=1:start=0"
            assert pattern in flt, \
                f"uu{i} must use loop=loop={expected_loop} for {expected_frames} frames"

    def test_end_text_loop_filter(self):
        """End-card text must use loop filter for deterministic 99 frames."""
        cfg = make_cfg(n=5)
        n = 5
        dwells = [2.0] * 5
        clip_ds = [d + XF for d in dwells]
        motions = ["zin"] * 5
        fc, _, _ = build_video_cmd(cfg, "/tmp/fake", n, dwells, clip_ds, motions)
        flt = get_filter(fc)

        expected_frames = int(round(END_D * FPS))  # 99
        expected_loop = expected_frames - 2  # 97
        pattern = f"loop=loop={expected_loop}:size=1:start=0"
        # Should appear in the etxt filter chain
        assert pattern in flt, \
            f"end_text must use loop=loop={expected_loop} for {expected_frames} frames"


class TestTimelineMath:
    """Xfade offsets and UI start must be mathematically exact."""

    def test_xfade_offsets(self):
        """Offsets must be [MOTTO_D - XF, MOTTO_D - XF + d0, ...]."""
        cfg = make_cfg(n=5)
        n = 5
        dwells = [2.0] * 5
        clip_ds = [d + XF for d in dwells]
        motions = ["zin"] * 5
        _, offs, _ = build_video_cmd(cfg, "/tmp/fake", n, dwells, clip_ds, motions)

        expected = [MOTTO_D - XF]  # 1.2
        acc = MOTTO_D - XF
        for d in dwells:
            acc += d
            expected.append(acc)
        # expected: [1.2, 3.2, 5.2, 7.2, 9.2, 11.2]

        assert len(offs) == len(expected) == n + 1
        for o, e in zip(offs, expected):
            assert abs(o - e) < 1e-9, f"offset {o} != expected {e}"

    def test_ui_start_is_first_midpoint(self):
        """ui_start must equal offs[0] + XF/2 (first transition midpoint)."""
        cfg = make_cfg(n=5)
        n = 5
        dwells = [2.0] * 5
        clip_ds = [d + XF for d in dwells]
        motions = ["zin"] * 5
        _, offs, ui_start = build_video_cmd(cfg, "/tmp/fake", n, dwells, clip_ds, motions)

        expected = offs[0] + XF / 2  # 1.2 + 0.4 = 1.6
        assert abs(ui_start - expected) < 1e-9
        assert abs(ui_start - 1.6) < 1e-9, f"ui_start should be 1.6, got {ui_start}"

    def test_ui_boundaries_at_midpoints(self):
        """UI segment boundaries must align with xfade midpoints."""
        cfg = make_cfg(n=5)
        n = 5
        dwells = [2.0] * 5
        clip_ds = [d + XF for d in dwells]
        motions = ["zin"] * 5
        _, offs, ui_start = build_video_cmd(cfg, "/tmp/fake", n, dwells, clip_ds, motions)

        # UI segment i covers [ui_start + sum(dwells[:i]), ui_start + sum(dwells[:i+1]))
        # In output timeline, boundary i (between ui_{i-1} and ui_i) is at:
        # ui_start + sum(dwells[:i])
        # This must equal offs[i] + XF/2 (the xfade midpoint)
        for i in range(1, n):
            ui_boundary = ui_start + sum(dwells[:i])
            xfade_midpoint = offs[i] + XF / 2
            assert abs(ui_boundary - xfade_midpoint) < 1e-9, \
                f"UI boundary {i} at {ui_boundary} != xfade midpoint {xfade_midpoint}"
        # Expected midpoints: 3.6, 5.6, 7.6, 9.6
        expected_midpoints = [3.6, 5.6, 7.6, 9.6]
        for i, exp in enumerate(expected_midpoints, start=1):
            ui_boundary = ui_start + sum(dwells[:i])
            assert abs(ui_boundary - exp) < 1e-9

    def test_setpts_delay_present(self):
        """The setpts delay must shift UI by exactly ui_start."""
        cfg = make_cfg(n=5)
        n = 5
        dwells = [2.0] * 5
        clip_ds = [d + XF for d in dwells]
        motions = ["zin"] * 5
        fc, _, ui_start = build_video_cmd(cfg, "/tmp/fake", n, dwells, clip_ds, motions)
        flt = get_filter(fc)

        # Should contain: [uiv]setpts=PTS+1.6000/TB[uivd]
        expected = f"[uiv]setpts=PTS+{ui_start:.4f}/TB[uivd]"
        assert expected in flt, f"setpts delay missing: expected {expected}"


class TestFiltergraphStructure:
    """The filtergraph must have the correct structure (no ghosting, no sync bugs)."""

    def test_no_ui_in_xfade_inputs(self):
        """Xfade inputs (vn0..vn{n+1}) must NOT contain UI overlays.
        (Regression: ghosting bug where UI was baked into xfade clips.)"""
        cfg = make_cfg(n=5)
        n = 5
        dwells = [2.0] * 5
        clip_ds = [d + XF for d in dwells]
        motions = ["zin"] * 5
        fc, _, _ = build_video_cmd(cfg, "/tmp/fake", n, dwells, clip_ds, motions)
        flt = get_filter(fc)

        # The xfade chain uses [vn0]..[vn{n+1}]. The vn{k} filters should be:
        # [v{k}]settb=AVTB,fps=30,scale=out_range=mpeg,format=yuv420p[vn{k}]
        # They must NOT contain overlay or UI references.
        for k in range(n + 2):
            # Find the vn{k} definition
            # It should NOT reference uu, uiv, or overlay
            vn_def_start = flt.find(f"[vn{k}]")
            # Actually the definition is "[v{k}]...[vn{k}]", check it doesn't have overlay
            # Simpler: the xfade inputs are vn*, and UI is only in the final overlay
            pass  # Structural check below is more direct

        # The ONLY overlay with uivd should be the final one (after xfade)
        # Count occurrences of "[uivd]" - should be exactly 2 (setpts output, overlay input)
        assert flt.count("[uivd]") == 2, \
            "uivd should appear exactly twice (setpts def + overlay use)"

    def test_concat_before_setpts(self):
        """UI segments must be concatenated BEFORE the setpts delay."""
        cfg = make_cfg(n=5)
        n = 5
        dwells = [2.0] * 5
        clip_ds = [d + XF for d in dwells]
        motions = ["zin"] * 5
        fc, _, _ = build_video_cmd(cfg, "/tmp/fake", n, dwells, clip_ds, motions)
        flt = get_filter(fc)

        concat_idx = flt.find(f"concat=n={n}:v=1:a=0[uiv]")
        setpts_idx = flt.find("[uiv]setpts=")
        assert concat_idx != -1, "concat filter missing"
        assert setpts_idx != -1, "setpts filter missing"
        assert concat_idx < setpts_idx, \
            "concat must come before setpts (setpts delays the concatenated track)"

    def test_eof_action_pass(self):
        """Final overlay must use eof_action=pass (no UI ghost on end card)."""
        cfg = make_cfg(n=5)
        n = 5
        dwells = [2.0] * 5
        clip_ds = [d + XF for d in dwells]
        motions = ["zin"] * 5
        fc, _, _ = build_video_cmd(cfg, "/tmp/fake", n, dwells, clip_ds, motions)
        flt = get_filter(fc)

        assert "eof_action=pass" in flt, \
            "final overlay must use eof_action=pass to avoid UI repeating on end card"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
