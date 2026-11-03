import json, subprocess
import numpy as np


def probe(path):
    out = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                   "stream=width,height:format=duration", "-of", "json", str(path)])
    d = json.loads(out)
    s = d["streams"][0]
    return s["width"], s["height"], float(d["format"]["duration"])


def frames(path, start, end, fps, width=None):
    """Yield (t, rgb uint8) decoded by ffmpeg at a fixed fps, optionally scaled to width."""
    w, h, _ = probe(path)
    if width and width < w:
        h = int(round(h * width / w / 2) * 2); w = width
    vf = f"fps={fps}" + (f",scale={w}:{h}" if width else "")
    cmd = ["ffmpeg", "-v", "error", "-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", str(path),
           "-vf", vf, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    n = 0
    while True:
        buf = p.stdout.read(w * h * 3)
        if len(buf) < w * h * 3:
            break
        yield start + n / fps, np.frombuffer(buf, np.uint8).reshape(h, w, 3)
        n += 1
    p.wait()
