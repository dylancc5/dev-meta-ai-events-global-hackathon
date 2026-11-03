"""Scan the library for a text-defined subject with SAM 3.1.

Coarse pass: 4 frames from every clip (is the subject in this clip at all?).
Dense pass: 3 fps over each candidate window (where exactly, how big, how confident).
"""
import json, time
from pathlib import Path
import cv2
import numpy as np
from .library import CLIPS, WINDOWS
from .sam import Segmenter, pick
from .video import probe, frames

ACCENT = (255, 176, 64)  # RGB warm amber


def outline_thumb(rgb, det, badge, out_path, width=480):
    img = rgb.copy()
    if det is not None:
        m = det["mask"].astype(np.uint8)
        dim = (img * 0.45).astype(np.uint8)
        img = np.where(m[..., None] > 0, img, dim)
        cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(img, cnts, -1, ACCENT, max(2, rgb.shape[1] // 300), lineType=cv2.LINE_AA)
    h = int(img.shape[0] * width / img.shape[1])
    cv2.imwrite(str(out_path), cv2.cvtColor(cv2.resize(img, (width, h), interpolation=cv2.INTER_AREA), cv2.COLOR_RGB2BGR),
                [cv2.IMWRITE_JPEG_QUALITY, 85])


def summarize(rgb_shape, det):
    h, w = rgb_shape[:2]
    if det is None:
        return None
    x0, y0, x1, y1 = det["box"]
    return {"score": round(det["score"], 3), "box": [round(x0 / w, 4), round(y0 / h, 4), round(x1 / w, 4), round(y1 / h, 4)],
            "area": round(float(det["mask"].mean()), 4)}


def scan(prompt, slug, out_dir: Path, seg: Segmenter = None, track="S1", dense_fps=3):
    seg = seg or Segmenter()
    f0, s0 = seg.frames, seg.seconds
    t_start = time.time()
    (out_dir / "scan").mkdir(parents=True, exist_ok=True)
    clips, windows = {}, []
    best = {}  # clip -> (score, rgb, det)

    def consider(cid, rgb, det):
        if det is not None and (cid not in best or det["score"] * (0.5 + det["mask"].mean()) > best[cid][0]):
            best[cid] = (det["score"] * (0.5 + det["mask"].mean()), rgb, det)
        elif cid not in best:
            best[cid] = (-1, rgb, None)

    for cid, path in CLIPS.items():
        _, _, dur = probe(path)
        hits = []
        ts = [dur * (i + 0.5) / 4 for i in range(4)]
        for t in ts:
            for _, rgb in frames(path, t, t + 0.04, 30, width=960):
                dets = seg(rgb, prompt)
                det = dets[0] if dets else None
                hits.append(det is not None)
                consider(cid, rgb, det)
                break
        clips[cid] = {"coarse_hits": int(sum(hits)), "coarse_frames": len(hits)}

    for cid, a, b in WINDOWS:
        path = CLIPS[cid]
        samples, prev = [], None
        for t, rgb in frames(path, a, b, dense_fps, width=960):
            det = pick(seg(rgb, prompt), prev)
            prev = det["box"] if det else prev
            s = summarize(rgb.shape, det)
            samples.append({"t": round(t, 3), **(s or {"score": 0.0, "box": None, "area": 0.0})})
            consider(cid, rgb, det)
        windows.append({"clip": cid, "start": a, "end": b, "samples": samples})

    result = []
    for cid in CLIPS:
        c = clips[cid]
        ws = [w for w in windows if w["clip"] == cid]
        dense = [s for w in ws for s in w["samples"]]
        n = c["coarse_frames"] + len(dense)
        found_n = c["coarse_hits"] + sum(1 for s in dense if s["score"] > 0)
        scores = [s["score"] for s in dense if s["score"] > 0]
        sc, rgb, det = best[cid]
        found = det is not None
        badge = f"{track} {det['score']:.2f}" if found else ""
        thumb = out_dir / "scan" / f"{cid}.jpg"
        outline_thumb(rgb, det, badge, thumb)
        result.append({"clip": cid, "found": found, "presence": round(found_n / max(1, n), 3),
                       "score": round(float(np.mean(scores)) if scores else (det["score"] if found else 0.0), 3),
                       "track": track if found else None, "frames": n,
                       "thumb": f"scan/{cid}.jpg"})
    data = {"prompt": prompt, "slug": slug, "clips": result, "windows": windows,
            "frames": seg.frames - f0, "sam_seconds": round(seg.seconds - s0, 1), "wall": round(time.time() - t_start, 1)}
    (out_dir / "scan.json").write_text(json.dumps(data, indent=1))
    return data
