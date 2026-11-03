"""Render a FollowCut plan: per-frame SAM 3.1 masks -> smoothed 9:16 follow-crop -> color pop.

Writes edit.mp4 (720x1280, music bed) and compare.mp4 (1920x1080: raw 16:9 with the follow window vs the edit).
"""
import subprocess
from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from .library import CLIPS, FOOTAGE
from .sam import Segmenter, pick
from .video import probe, frames

OW, OH, FPS = 720, 1280, 30
ACCENT = (255, 176, 64)


def _font(size):
    for p in [FOOTAGE / "fonts/Rubik-Bold.ttf", *sorted((FOOTAGE / "fonts").rglob("Rubik*.ttf")),
              Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf")]:
        if Path(p).exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def _smooth(xs, r=10):
    xs = np.asarray(xs, float)
    k = np.ones(2 * r + 1) / (2 * r + 1)
    pad = np.pad(xs, r, mode="edge")
    return np.convolve(pad, k, mode="valid")


def track_shot(seg, path, t_in, n, prompt, seed=None):
    """Full-rate SAM on a downscaled copy; returns frames (full res), masks (sam res), centers."""
    w, h, _ = probe(path)
    sw = 960 if w >= h else 540
    full, small = [], []
    for (_, a), (_, b) in zip(frames(path, t_in, t_in + n / FPS + 0.2, FPS), frames(path, t_in, t_in + n / FPS + 0.2, FPS, width=sw)):
        full.append(a); small.append(b)
        if len(full) == n:
            break
    while len(full) < n:  # clip ended early: hold last frame
        full.append(full[-1]); small.append(small[-1])
    masks, cx, cy, prev, last = [], [], [], None, None
    if seed:  # start on the instance the scan (and Muse Spark) saw, not whoever scores highest in frame 1
        sh_, sw_ = small[0].shape[:2]
        prev = [seed[0] * sw_, seed[1] * sh_, seed[2] * sw_, seed[3] * sh_]
    for f in small:
        det = pick(seg(f, prompt), prev)
        if det is not None:
            prev, last = det["box"], det["mask"]
        m = last if last is not None else np.ones(f.shape[:2], bool)
        masks.append(m)
        ys, xs = np.nonzero(m)
        if len(xs):
            # frame on the head: centroid of the top 40% of the mask, eye line ~30% down
            top, bot = ys.min(), ys.max()
            head = ys <= top + 0.4 * (bot - top)
            cx.append(xs[head].mean() / f.shape[1])
            cy.append((top + 0.3 * (bot - top)) / f.shape[0])
        else:
            cx.append(0.5); cy.append(0.5)
    return full, masks, _smooth(cx), _smooth(cy)


def grade(rgb, mask_full, center, crop_w):
    f = rgb.astype(np.float32) / 255.0
    gray = (f @ np.array([0.299, 0.587, 0.114], np.float32))[..., None].repeat(3, 2)
    bg = gray * np.array([0.86, 0.9, 0.98], np.float32) * 0.82
    mean = f.mean(2, keepdims=True)
    fg = np.clip(mean + (f - mean) * 1.18, 0, 1) * np.array([1.03, 1.0, 0.96], np.float32)
    a = mask_full[..., None]
    out = a * fg + (1 - a) * bg
    h, w = out.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.sqrt(((xx - center[0] * w) / (crop_w * 0.9)) ** 2 + ((yy - center[1] * h) / (h * 0.75)) ** 2)
    out *= np.clip(1.15 - 0.45 * d, 0.6, 1.0)[..., None]
    return (np.clip(out, 0, 1) * 255).astype(np.uint8)


def _title(img, prompt, alpha):
    if alpha <= 0:
        return img
    im = Image.fromarray(img).convert("RGBA")
    ov = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    f1, f2 = _font(30), _font(52)
    a = int(255 * alpha)
    d.text((48, OH - 230), "FOLLOWING", font=f1, fill=(*ACCENT, a))
    d.text((48, OH - 185), prompt, font=f2, fill=(255, 255, 255, a))
    d.text((48, OH - 115), "Portland · Oct 16–18", font=f1, fill=(255, 255, 255, int(a * 0.75)))
    return np.array(Image.alpha_composite(im, ov).convert("RGB"))


def render(plan, prompt, out_dir: Path, music_wav: Path, seg: Segmenter = None, progress=print):
    seg = seg or Segmenter()
    out_dir.mkdir(parents=True, exist_ok=True)
    enc = lambda p, w, h: subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(FPS),
         "-i", "-", "-i", str(music_wav), "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "medium",
         "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(p)],
        stdin=subprocess.PIPE)
    e1, e2 = enc(out_dir / "edit.mp4", OW, OH), enc(out_dir / "compare.mp4", 1920, 1080)
    total, f0 = 0, seg.frames
    for si, shot in enumerate(plan["shots"]):
        path = CLIPS[shot["clip"]]
        n = int(shot["beats"] * 15)
        full, masks, cx, cy = track_shot(seg, path, shot["in"], n, prompt, seed=shot.get("seed"))
        H, W = full[0].shape[:2]
        crop_w = int(round(H * 9 / 16 / 2) * 2) if W > H else W
        for i in range(n):
            mk = cv2.resize(masks[i].astype(np.float32), (W, H), interpolation=cv2.INTER_LINEAR)
            mk = cv2.GaussianBlur(mk, (0, 0), max(2.0, W / 250))
            g = grade(full[i], mk, (cx[i], cy[i]), crop_w)
            x0 = int(np.clip(cx[i] * W - crop_w / 2, 0, W - crop_w))
            # gentle push-in over the shot
            z = 1.0 + 0.04 * i / n
            ch, cw = int(H / z), int(crop_w / z)
            xc, yc = x0 + crop_w / 2, np.clip(cy[i] * H, ch / 2, H - ch / 2)
            xa = int(np.clip(xc - cw / 2, 0, W - cw)); ya = int(np.clip(yc - ch / 2, 0, H - ch))
            frame = cv2.resize(g[ya:ya + ch, xa:xa + cw], (OW, OH), interpolation=cv2.INTER_AREA)
            if i == n // 2:  # poster/keyframe without the burned-in title (the player shows it under the video)
                cv2.imwrite(str(out_dir / f"shot{si:02d}.jpg"), cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
            if si == 0:
                frame = _title(frame, prompt, min(1.0, (n - i) / 12) if i < n else 0)
            e1.stdin.write(frame.tobytes())
            # compare canvas
            can = np.full((1080, 1920, 3), 14, np.uint8)
            if W > H:
                rw, rh = 1200, int(1200 * H / W)
                raw = cv2.resize(full[i], (rw, rh), interpolation=cv2.INTER_AREA)
                s = rw / W
                cv2.rectangle(raw, (int(xa * s), int(ya * s)), (int((xa + cw) * s), int((ya + ch) * s)), ACCENT, 3, cv2.LINE_AA)
            else:
                rh = 900; rw = int(rh * W / H)
                raw = cv2.resize(full[i], (rw, rh), interpolation=cv2.INTER_AREA)
            # SAM 3.1 mask on the raw frame: amber tint + outline, so the follow window visibly comes from the mask
            mr = cv2.resize(masks[i].astype(np.uint8), (rw, rh), interpolation=cv2.INTER_NEAREST)
            raw = raw.copy(); raw[mr > 0] = (0.65 * raw[mr > 0] + 0.35 * np.array(ACCENT)).astype(np.uint8)
            cnts, _ = cv2.findContours(mr, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(raw, cnts, -1, ACCENT, 2, cv2.LINE_AA)
            ox, oy = 80 + (1200 - rw) // 2, (1080 - rh) // 2
            can[oy:oy + rh, ox:ox + rw] = raw
            ew = int(1000 * OW / OH)
            can[40:1040, 1920 - 80 - ew:1920 - 80] = cv2.resize(frame, (ew, 1000), interpolation=cv2.INTER_AREA)
            e2.stdin.write(can.tobytes())
        total += n
        progress(f"shot {si + 1}/{len(plan['shots'])} {shot['clip']} {shot['in']}-{shot['out']} ({n} frames)")
    for e in (e1, e2):
        e.stdin.close(); e.wait()
    return {"frames": seg.frames - f0, "sam_seconds": round(seg.seconds, 1)}
