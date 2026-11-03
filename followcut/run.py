"""python -m followcut.run "<prompt>" <slug> <track>: scan (cached) -> plan -> render -> export to web."""
import json, os, shutil, subprocess, sys, time
from pathlib import Path
from .library import CLIPS, LABELS, LIBRARY_NAME
from .music import build as build_music
from .planner import plan as make_plan
from .render import render
from .sam import Segmenter
from .scan import scan
from .video import probe

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web/public/data"


def export_library():
    (WEB / "thumbs").mkdir(parents=True, exist_ok=True)
    clips = []
    for cid, p in CLIPS.items():
        w, h, dur = probe(p)
        th = WEB / "thumbs" / f"{cid}.jpg"
        if not th.exists():
            subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-ss", f"{dur / 2:.2f}", "-i", str(p), "-frames:v", "1",
                                   "-vf", "scale=480:-2", "-q:v", "4", str(th)])
        clips.append({"id": cid, "label": LABELS.get(cid, cid), "thumb": f"/data/thumbs/{cid}.jpg",
                      "duration": round(dur, 1), "aspect": "16:9" if w > h else "9:16"})
    return {"name": LIBRARY_NAME, "clips": clips}


def spark_inputs(sc, cache, exclude):
    import cv2
    from .planner import moments
    from .video import frames
    kd = cache / "kf"; kd.mkdir(exist_ok=True)
    found = [c for c in sc["clips"] if c["found"] and c["clip"] not in exclude]
    ref = max(found, key=lambda c: c["score"] * c["presence"]) if found else None
    reference = cache / ref["thumb"] if ref else None
    kfs = {}
    for m in moments({**sc, "windows": [w for w in sc["windows"] if w["clip"] not in exclude]}):
        t = (m["in"] + m["out"]) / 2
        for _, rgb in frames(CLIPS[m["clip"]], t, t + 0.04, 30, width=512):
            out = kd / f"{m['clip']}_{m['in']}.jpg"
            cv2.imwrite(str(out), cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 80])
            kfs[(m["clip"], m["in"])] = out
            break
    return kfs, reference


def main(prompt, slug, track):
    cache = ROOT / "cache" / slug
    seg = Segmenter()
    t0 = time.time()
    sc = json.loads((cache / "scan.json").read_text()) if (cache / "scan.json").exists() else scan(prompt, slug, cache, seg, track)
    exclude = [x for x in os.environ.get("EXCLUDE", "").split(",") if x]
    keyframes, reference = {}, None
    if os.environ.get("META_API_KEY"):  # Spark sees one keyframe per candidate + a reference
        keyframes, reference = spark_inputs(sc, cache, exclude)
    p = make_plan(sc, prompt, keyframes=keyframes, exclude=exclude, reference=reference)
    p["excluded"] = [{"clip": c, "label": LABELS.get(c, c), "why": "user marked: not this person"} for c in exclude]
    (cache / "plan.json").write_text(json.dumps(p, indent=1))
    music = cache / "music.wav"
    build_music(music, p["duration"])
    r = render(p, prompt, cache, music, seg)
    dst = WEB / "runs" / slug
    (dst / "scan").mkdir(parents=True, exist_ok=True)
    for f in ("edit.mp4", "compare.mp4"):
        shutil.copy(cache / f, dst / f)
    shutil.copy(cache / "shot00.jpg", dst / "poster.jpg")
    for c in sc["clips"]:
        shutil.copy(cache / c["thumb"], dst / c["thumb"])
    run = {"slug": slug, "prompt": prompt, "edit": f"/data/runs/{slug}/edit.mp4", "poster": f"/data/runs/{slug}/poster.jpg",
           "compare": f"/data/runs/{slug}/compare.mp4",
           "scan": [{**c, "thumb": f"/data/runs/{slug}/{c['thumb']}", **({"excluded": True} if c["clip"] in exclude else {})} for c in sc["clips"]],
           "plan": p,
           "stats": {"frames_segmented": sc["frames"] + r["frames"], "seconds": round(sc["sam_seconds"] + r["sam_seconds"]),
                     "model": "SAM 3.1 (unsloth/sam3.1 mirror, fp16, Apple M5 Pro · MPS)"}}
    mf = WEB / "manifest.json"
    m = json.loads(mf.read_text()) if mf.exists() else {}
    if "library" not in m or any(c["id"] not in CLIPS for c in m["library"].get("clips", [])) or len(m["library"].get("clips", [])) != len(CLIPS):
        m["library"] = export_library()
    runs = [x for x in m.get("runs", []) if x.get("slug") != slug and not x.get("placeholder")]
    order = ["woman", "man", "dog"]
    runs.append(run)
    runs.sort(key=lambda x: order.index(x["slug"]) if x["slug"] in order else 9)
    m["runs"] = runs
    mf.write_text(json.dumps(m, indent=1))
    print(f"done {slug} in {time.time() - t0:.0f}s: {len(p['shots'])} shots, {p['duration']}s")


if __name__ == "__main__":
    main(*sys.argv[1:4])
