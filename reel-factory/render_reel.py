#!/usr/bin/env python3
"""ZenPixelWalls A/B reel renderer — 14.5s, 4-6 lockscreen slots (configurable dwell), 0.8s crossfades.
Usage: python3 render_reel.py combos.json <slug>   (or 'all')
Outputs to ~/workspace/instagram-setup/ab-test/<slug>/{reel.mp4,cover.jpg,caption.txt,attribution.txt}
"""
import json, os, sys, subprocess, datetime, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageStat

W, H = 1080, 1920
WW, WH = 1620, 2880          # zoompan work size (1.5x)
FPS = 30
# 14.5s cut (2026-09-21): 2.0s motto + 5x2.0s slots + 2.5s end card, 0.8s crossfades.
# Slot clips are 2.8s raw (2.0 dwell + 0.8 xfade tail) -> zoompan d=84; end card 3.3s -> d=99.
MOTTO_D, SLOT_D, END_D, XF = 2.0, 2.8, 3.3, 0.8
DUR = 14.5
HOME = os.path.expanduser("~/workspace/instagram-setup/ab-test")
FONTS = os.path.join(HOME, "fonts")
SRC = "/tmp/ab-src"
MUS = "/tmp/ab-music"

CORM = os.path.join(FONTS, "CormorantGaramond-Light.ttf")
CORMI = os.path.join(FONTS, "CormorantGaramond-Italic[wght].ttf")
INTER = os.path.join(FONTS, "Inter[opsz,wght].ttf")

def inter(size, weight=300):
    f = ImageFont.truetype(INTER, size)
    try: f.set_variation_by_axes([weight])
    except Exception: pass
    return f

def corm(size):
    return ImageFont.truetype(CORM, size)

def cormi(size, weight=300):
    f = ImageFont.truetype(CORMI, size)
    try: f.set_variation_by_axes([weight])
    except Exception: pass
    return f

# Single lockscreen typography style for the whole reel (2026-09-23 user
# feedback: "don't change the date, just one format" — the per-slot font
# rotation looked wrong/jarring). Inter Light, clean and iPhone-like.
UI_STYLE = dict(time=lambda s, w: inter(s, 300), date=lambda s, w: inter(s, 300),
                time_tr=10, date_tr=3, date_fmt="title")

def fmt_date(now):
    return now.strftime("%A, %B") + " " + str(int(now.strftime("%d")))

def track_text(draw, xy, text, font, fill, tracking, anchor="m"):
    """Draw text centered at xy with letter tracking."""
    widths = [draw.textlength(ch, font=font) for ch in text]
    total = sum(widths) + tracking * (len(text) - 1)
    x, y = xy
    x -= total / 2
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    for ch, wch in zip(text, widths):
        d.text((x, y), ch, font=font, fill=fill, anchor="lm")
        x += wch + tracking
    return lay

def shadowed(base, text_layer, blur=10, alpha=130):
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    # text_layer is white text; make black silhouette
    px = text_layer.load()
    sil = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    spx = sil.load()
    # fast path via alpha channel
    a = text_layer.split()[3].point(lambda v: alpha if v > 8 else 0)
    sil.putalpha(a)
    sil = sil.filter(ImageFilter.GaussianBlur(blur))
    out = Image.alpha_composite(base.convert("RGBA"), sil)
    out = Image.alpha_composite(out, text_layer)
    return out.convert("RGB")

def home_bar(fill=(255, 255, 255, 255)):
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    d.rounded_rectangle([W/2 - 200, H - 42, W/2 + 200, H - 32], radius=5, fill=fill)
    return lay

def prep_work(src, anchor="center"):
    """Crop/resize any source to 1620x2880 work image. Horizontals: 9:16 window at anchor."""
    im = Image.open(src).convert("RGB")
    w, h = im.size
    target_ar = WW / WH
    if w / h > target_ar + 0.02:  # wider than 9:16 -> crop width (horizontal)
        win_w = int(h * target_ar)
        if anchor == "left": x0 = 0
        elif anchor == "right": x0 = w - win_w
        else: x0 = (w - win_w) // 2
        im = im.crop((x0, 0, x0 + win_w, h))
    else:  # crop height to 9:16
        win_h = int(w / target_ar)
        y0 = (h - win_h) // 2
        im = im.crop((0, y0, w, y0 + win_h))
    return im.resize((WW, WH), Image.LANCZOS)

def needs_scrim(work):
    top = work.crop((0, 0, WW, WH // 2)).convert("L")
    return ImageStat.Stat(top).mean[0] / 255.0 > 0.52

def apply_scrim(work, strength=0.42):
    scrim = Image.new("L", (1, WH))
    for y in range(WH):
        t = y / (WH * 0.55)
        a = max(0.0, 1.0 - t) * 255 * strength
        scrim.putpixel((0, y), int(a))
    scrim = scrim.resize((WW, WH)).filter(ImageFilter.GaussianBlur(30))
    black = Image.new("RGB", (WW, WH), (0, 0, 0))
    return Image.composite(black, work, scrim).convert("RGB")

def analyze_wallpaper(wk):
    """Per-slot typography spec from the wallpaper itself (2026-09-21 user feedback:
    date/time must feel designed for each wallpaper, not stamped on).
    Returns dict(dark, time_y, time_size, color, date_w, time_w).
    - dark: white text (+dark scrim baked separately); light: dark text, no scrim.
    - time_y: vertical center of the clock, snapped to the calmest horizontal band
      (low edge energy + low luminance variance) in the upper region.
    - time_size shrinks slightly on very busy wallpapers."""
    top = wk.crop((0, 0, WW, int(WH * 0.60))).convert("L")
    lum = ImageStat.Stat(top).mean[0] / 255.0
    dark = lum <= 0.52
    small = wk.convert("L").resize((270, 480), Image.LANCZOS)
    edges = small.filter(ImageFilter.FIND_EDGES)
    best_y, best_score = 640, None
    for yc in range(400, 801, 40):  # candidate clock centers, output coords
        y0 = max(0, int((yc - 210) / 4)); y1 = min(480, int((yc + 210) / 4))
        e = ImageStat.Stat(edges.crop((40, y0, 230, y1))).mean[0]
        v = ImageStat.Stat(small.crop((40, y0, 230, y1))).stddev[0]
        score = e + v * 0.6
        if best_score is None or score < best_score:
            best_score, best_y = score, yc
    time_size = 190 if best_score < 28 else 168
    if dark:
        color, dw, tw = (255, 255, 255), 300, 300
    else:
        color, dw, tw = (28, 28, 28), 500, 500
    return {"dark": dark, "time_y": best_y, "time_size": time_size,
            "color": color, "date_w": dw, "time_w": tw}

def build_slot_ui(path, now, spec, clock="9:41"):
    """Per-slot lockscreen UI, baked onto the slot clip BEFORE the xfade chain,
    so the date/time fades WITH the wallpaper (2026-09-23 pm user feedback:
    previously published reels faded the date together with the wallpaper —
    restore that). Single unified typography (UI_STYLE, "就一个格式"):
    position/color are still adapted per wallpaper for readability, but the
    font and date format never change between slots, so the crossfade never
    ghosts two different fonts."""
    style = UI_STYLE
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    col = spec["color"] + (255,)
    ty = spec["time_y"]
    date_str = fmt_date(now)
    dt = track_text(d, (W/2, ty - 190), date_str, style["date"](44, spec["date_w"]), col, style["date_tr"])
    lay = Image.alpha_composite(lay, dt)
    ck = track_text(d, (W/2, ty), clock, style["time"](spec["time_size"], spec["time_w"]), col, style["time_tr"])
    lay = Image.alpha_composite(lay, ck)
    lay = Image.alpha_composite(lay, home_bar(fill=col))
    lay.save(path)

def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        print("CMD FAILED:", " ".join(cmd[:6]), "...")
        print(r.stderr[-3000:])
        raise SystemExit(1)
    return r

def tonal_card_bg(src_big, tmp, name):
    """Blurred tonal card background sampled from a wallpaper.
    Returns the text fill (r,g,b,255): light wallpapers -> soft light card + dark
    text; dark wallpapers -> darkened card + white text. Keeps every reel's
    motto/end cards inside that reel's own palette (2026-09-21 user feedback:
    no more one black card for everything)."""
    im = Image.open(src_big).convert("RGB").resize((W, H), Image.LANCZOS)
    im = im.filter(ImageFilter.GaussianBlur(50))
    lum = ImageStat.Stat(im.convert("L")).mean[0]
    if lum > 140:
        bg = Image.blend(im, Image.new("RGB", (W, H), (255, 255, 255)), 0.35)
        txt = (35, 35, 35, 255)
    else:
        bg = Image.blend(im, Image.new("RGB", (W, H), (0, 0, 0)), 0.45)
        txt = (255, 255, 255, 255)
    bg.save(f"{tmp}/{name}.jpg", quality=94)
    return txt

def motto_frames(tmp, bg_path, text_fill, n=60):
    os.makedirs(tmp, exist_ok=True)
    bg = Image.open(bg_path).convert("RGB")
    r, g, b = text_fill[:3]
    fnt = corm(96)
    meas = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    def tw(t, tr):
        return sum(meas.textlength(ch, font=fnt) for ch in t) + tr * (len(t) - 1)
    tr_max = 18
    while tw("most-viewed screen", tr_max) > 900 and tr_max > 4:
        tr_max -= 1
    for i in range(n):
        t = i / (n - 1)
        alpha = int(255 * min(1.0, t / 0.45))
        tr = tr_max * 0.4 + (tr_max * 0.6) * min(1.0, t / 0.8)
        yoff = int(26 * (1 - min(1.0, t / 0.8)))
        img = bg.copy()
        d = ImageDraw.Draw(img)
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        l1 = track_text(d, (W/2, 900 + yoff), "Art for your", fnt, (r,g,b,alpha), tr)
        l2 = track_text(d, (W/2, 1046 + yoff), "most-viewed screen", fnt, (r,g,b,alpha), tr)
        lay = Image.alpha_composite(lay, l1); lay = Image.alpha_composite(lay, l2)
        hb = home_bar(fill=(r,g,b,255)); hb.putalpha(hb.split()[3].point(lambda v: int(v * min(1.0, t/0.5))))
        lay = Image.alpha_composite(lay, hb)
        img = Image.alpha_composite(img.convert("RGBA"), lay).convert("RGB")
        img.save(f"{tmp}/motto_{i:02d}.png")

LOGO_PNG = os.path.join(os.path.expanduser("~"),
    "workspace/your_files/etsy-shop-branding/zenpixelwalls-logo-500x500.png")

def logo_mark(text_fill, size=54):
    """Monochrome ZenPixelWalls enso mark, recolored to the card's text color.
    The source PNG has a cream paper background; ink pixels are extracted by
    darkness and used as alpha for a solid-color mark."""
    logo = Image.open(LOGO_PNG).convert("L")
    a = np.array(logo).astype(np.float32)
    alpha = np.clip((200.0 - a) * 255.0 / 160.0, 0, 255).astype(np.uint8)
    r, g, b = text_fill[:3]
    solid = Image.new("RGBA", logo.size, (r, g, b, 255))
    solid.putalpha(Image.fromarray(alpha))
    return solid.resize((size, size), Image.LANCZOS)

def end_text_png(tmp, text_fill):
    # NOTE 2026-09-21: the bundled CormorantGaramond-Light.ttf maps U+2665 to a
    # garbage glyph (vertical "HATCH ON" strip) even though textlength > 5.
    # (Heart no longer used; 2026-09-22 user: use the brand logo mark instead.)
    # NOTE 2026-09-22 (user): end card = big shop name, small "Link in bio" line below.
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    meas = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    def twd(t, fnt, tr):
        return sum(meas.textlength(ch, font=fnt) for ch in t) + tr * (len(t) - 1)
    # main: shop name, fit within 940px
    size, tr = 120, 16
    while size > 60:
        fnt = corm(size)
        if twd("ZenPixelWalls", fnt, tr) <= 940:
            break
        size -= 4
    t1 = track_text(d, (W/2, 880), "ZenPixelWalls", corm(size), text_fill, tr)
    lay = Image.alpha_composite(lay, t1)
    # sub: small "Link in bio", centered, no icon
    # (2026-09-22 user: heart was unclear, logo rejected — plain text only)
    f2, tr2 = corm(52), 10
    t2 = track_text(d, (W/2, 1062), "Link in bio", f2, text_fill, tr2)
    lay = Image.alpha_composite(lay, t2)
    out = f"{tmp}/end_text.png"
    lay.save(out)
    return out

def best_music_window(mp3, slug, seg=14.5):
    # unique temp wav per process: parallel renders must not share one path
    wav = f"/tmp/_vol_{slug}_{os.getpid()}.wav"
    run(["ffmpeg", "-y", "-v", "error", "-i", mp3, "-ac", "1", "-ar", "22050", wav])
    import wave
    wv = wave.open(wav); n = wv.getnframes(); sr = wv.getframerate()
    pcm = np.frombuffer(wv.readframes(n), dtype=np.int16).astype(np.float32)
    wv.close(); os.remove(wav)
    hop = int(sr * 0.5); win = int(seg * sr)
    rms = np.array([np.sqrt(np.mean(pcm[i:i+hop]**2) + 1e-9) for i in range(0, n - hop, hop)])
    if rms.max() < 1e-6: return 5.0
    wsteps = int(seg / 0.5)
    means = np.convolve(rms, np.ones(wsteps)/wsteps, mode="valid")
    lo, hi = int(5/0.5), max(int(5/0.5)+1, len(means) - int(5/0.5))
    s = lo + int(np.argmax(means[lo:hi]))
    return round(s * 0.5, 2)

def build_video_cmd(cfg, tmp, n, dwells, clip_ds, motions):
    """Build the ffmpeg video-pass command (pure: no side effects, no ffmpeg run).
    Returns (fc, total_d) where fc is the command list and total_d the duration.
    2026-09-23 (pm) redesign (user feedback): 0.8s xfade crossfades restored;
    each slot's lockscreen UI is baked onto its clip BEFORE the xfade chain, so
    the date/time fades WITH the wallpaper (like the originally published reels).
    Typography stays a single unified style across slots (UI_STYLE, "就一个格式")
    — no per-slot font rotation — so the crossfade never ghosts two fonts.
    Extracted 2026-09-23 for unit testing (user rule: code must have tests).
    """
    # ---- pass 1: video ----
    fc = ["ffmpeg", "-y", "-v", "error"]
    inputs = []
    inputs += ["-framerate", str(FPS), "-i", f"{tmp}/motto/motto_%02d.png"]
    for i in range(n):
        inputs += ["-i", f"{tmp}/workbig_{i}.jpg"]
    inputs += ["-i", f"{tmp}/endbg.jpg"]
    for i in range(n):
        inputs += ["-i", f"{tmp}/ui_{i}.png"]
    # end_text: single frame + loop filter (deterministic frame count).
    # BUGFIX 2026-09-23: was "-loop 1 -t {END_D}" which is RACY with multiple
    # inputs (demuxer -t check vs loop timing) -> non-deterministic durations.
    end_frames = int(round(END_D * FPS))
    inputs += ["-i", f"{tmp}/homebar.png",
               "-framerate", str(FPS),
               "-i", f"{tmp}/end_text.png"]
    # input map: 0 motto, 1..n workbig, n+1 endbg, n+2..2n+1 ui_0..ui_{n-1},
    #            2n+2 homebar, 2n+3 end_text
    fc += inputs
    flt = []
    # v0 motto
    flt.append(f"[0:v]format=yuv420p,settb=AVTB,fps={FPS}[v0]")
    for i in range(n):
        flt.append(f"[{n+2+i}:v]format=rgba[u{i}]")
    vi = 1
    for i, m in enumerate(motions):
        fr = int(round(clip_ds[i] * FPS))          # zoompan frame count for this slot
        om = fr - 1
        if m == "zin":
            zp = f"zoompan=z='1+0.07*on/{om}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={fr}:s={W}x{H}:fps={FPS}"
        elif m == "zout":
            zp = f"zoompan=z='1.07-0.07*on/{om}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={fr}:s={W}x{H}:fps={FPS}"
        else:
            zp = (f"zoompan=z=1.07:x='(iw-iw/zoom)*on/{om}':y='(ih-ih/zoom)/2':"
                  f"d={fr}:s={W}x{H}:fps={FPS}")
        flt.append(f"[{vi}:v]{zp},format=yuv420p,settb=AVTB[raw{i}]")
        # UI baked onto the slot clip BEFORE xfade: the whole frame (wallpaper
        # + date/time) crossfades as one. The single-frame PNG is held by
        # overlay's default eof_action=repeat.
        flt.append(f"[raw{i}][u{i}]overlay=0:0:format=auto,format=yuv420p,settb=AVTB[v{i+1}]")
        vi += 1
    # end card
    flt.append(f"[{vi}:v]zoompan=z='1+0.035*on/98':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=99:s={W}x{H}:fps={FPS},format=yuv420p,settb=AVTB[eraw]")
    flt.append(f"[{2*n+3}:v]format=rgba,loop=loop={end_frames-2}:size=1:start=0,"
               f"fade=t=in:st=0.9:d=0.7:alpha=1,settb=AVTB[etxt]")
    flt.append("[eraw][etxt]overlay=0:0:format=auto[etmp]")
    flt.append(f"[etmp][{2*n+2}:v]overlay=0:0:format=auto,format=yuv420p,settb=AVTB[v{n+1}]")
    # normalize timebases + broadcast range before xfade
    for k in range(n + 2):
        flt.append(f"[v{k}]settb=AVTB,fps={FPS},scale=out_range=mpeg,format=yuv420p[vn{k}]")
    # xfade chain: vn0..vn{n+1} (n+2 clips), offsets;
    # total = MOTTO_D + sum(dwells) + END_D - XF = 14.5
    offs = [MOTTO_D - XF]
    acc = MOTTO_D - XF
    for d in dwells:
        acc += d
        offs.append(acc)
    cur = "vn0"
    for k in range(n + 1):
        nxt = f"vn{k+1}"
        out = f"x{k}" if k < n else "vout"
        flt.append(f"[{cur}][{nxt}]xfade=transition=fade:duration={XF}:offset={offs[k]:.4f}[{out}]")
        cur = out
    total_d = MOTTO_D + sum(dwells) + END_D - XF
    fc += ["-filter_complex", ";".join(flt), "-map", "[vout]", "-t", f"{total_d:.1f}",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-color_range", "mpeg",
           "-b:v", "1400k", "-maxrate", "1800k", "-bufsize", "3600k",
           "-preset", "medium", "-r", str(FPS), f"{tmp}/video.mp4"]
    return fc, total_d



def build(cfg):
    slug = cfg["slug"]
    outdir = os.path.join(HOME, slug)
    os.makedirs(outdir, exist_ok=True)
    tmp = f"/tmp/ab-render/{slug}"
    os.makedirs(tmp, exist_ok=True)
    now = datetime.datetime.now()
    date_str = now.strftime("%A, %B") + " " + str(int(now.strftime("%d")))
    clock = cfg.get("clock_time", "9:41")

    works = []
    specs = []
    for idx, im in enumerate(cfg["images"]):
        wk = prep_work(im["src"], im.get("anchor", "center"))
        spec = analyze_wallpaper(wk)
        if spec["dark"] and needs_scrim(wk):
            wk = apply_scrim(wk)
        p = f"{tmp}/work_{idx}.jpg"
        wk.resize((W, H), Image.LANCZOS).save(p, quality=95)
        wk.save(f"{tmp}/workbig_{idx}.jpg", quality=94)
        works.append(p)
        specs.append(spec)

    n = len(cfg["images"])
    # Per-slot UI, baked onto each slot clip before xfade (2026-09-23 pm:
    # date fades WITH the wallpaper). Unified format via UI_STYLE; only
    # position/color adapt per wallpaper.
    for idx, spec in enumerate(specs):
        build_slot_ui(f"{tmp}/ui_{idx}.png", now, spec, clock)

    # per-slot dwell (visible seconds); sum must be 10.0 so total stays 14.5s
    # (= MOTTO_D + END_D - XF budget: 2.0 + 3.3 - 0.8)
    dwells = cfg.get("slot_dwells") or [10.0 / n] * n
    assert len(dwells) == n and abs(sum(dwells) - 10.0) < 0.01, \
        f"slot_dwells must have {n} entries summing to 10.0, got {dwells}"
    clip_ds = [d + XF for d in dwells]  # raw clip length incl. xfade tail

    # tonal cards: blurred wallpaper behind text, sampled from this reel's own palette
    motto_txt = tonal_card_bg(f"{tmp}/workbig_0.jpg", tmp, "mottobg")
    motto_frames(f"{tmp}/motto", f"{tmp}/mottobg.jpg", motto_txt)
    end_txt = tonal_card_bg(f"{tmp}/workbig_{n-1}.jpg", tmp, "endbg")
    end_text_png(tmp, end_txt)
    home_bar(fill=end_txt).save(f"{tmp}/homebar.png")

    # ---- pass 1: video (command built by testable pure function) ----
    motions = cfg.get("motion", ["zin", "zout", "pan", "zin", "zin"])
    motions = [motions[i % len(motions)] for i in range(n)]
    fc, total_d = build_video_cmd(cfg, tmp, n, dwells, clip_ds, motions)
    run(fc)

    # ---- pass 2: audio + mux ----
    music = cfg.get("music")
    music_ok = bool(music) and os.path.exists(music) and os.path.getsize(music) > 1000
    if not music_ok:
        print(f"[{slug}] WARNING: music missing/unreadable -> rendering SILENT", flush=True)
        cfg["music_start"] = None
        run(["ffmpeg", "-y", "-v", "error", "-i", f"{tmp}/video.mp4",
             "-c:v", "copy", "-movflags", "+faststart",
             os.path.join(outdir, "reel.mp4")])
    else:
        start = cfg.get("music_start")
        if start is None:
            start = best_music_window(music, slug)
            cfg["music_start"] = start
        print(f"[{slug}] music start={start}s date='{date_str}'", flush=True)
        total_s = f"{total_d:.1f}"
        fade_out_st = f"{total_d - 0.5:.1f}"
        # NOTE 2026-09-23 (pm): explicit output -t instead of -shortest.
        # -shortest silently truncated the video when the music ran short
        # (that's how 15.3s targets shipped as 14.5s files). Output is now
        # always exactly total_d, regardless of audio length.
        run(["ffmpeg", "-y", "-v", "error", "-i", f"{tmp}/video.mp4",
             "-ss", f"{start}", "-t", total_s, "-i", music,
             "-filter_complex", f"[1:a]afade=t=in:st=0:d=0.5,afade=t=out:st={fade_out_st}:d=0.5[aout]",
             "-map", "0:v", "-map", "[aout]", "-c:v", "copy",
             "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
             "-t", total_s,
             "-movflags", "+faststart",
             os.path.join(outdir, "reel.mp4")])
    print(f"[{slug}] DONE", flush=True)

    # cover: middle slot with its own baked UI
    cover = Image.open(works[2]).convert("RGBA")
    cover = Image.alpha_composite(cover, Image.open(f"{tmp}/ui_2.png"))
    cover.convert("RGB").save(os.path.join(outdir, "cover.jpg"), quality=92)
    with open(os.path.join(outdir, "caption.txt"), "w") as f:
        f.write(cfg["caption"])
    with open(os.path.join(outdir, "attribution.txt"), "w") as f:
        f.write(cfg["attribution"])
    with open(os.path.join(outdir, "manifest.json"), "w") as f:
        json.dump({k: cfg[k] for k in ("slug", "images", "music", "music_start")}, f, indent=1)
    print(f"[{slug}] DONE", flush=True)

if __name__ == "__main__":
    combos = json.load(open(sys.argv[1]))
    which = sys.argv[2] if len(sys.argv) > 2 else "all"
    for c in combos:
        if which in ("all", c["slug"]):
            build(c)
