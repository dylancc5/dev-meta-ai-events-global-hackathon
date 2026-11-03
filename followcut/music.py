"""Build a 120 BPM royalty-free bed from Apple Loops (GarageBand loops are licensed for use in
your own compositions). Beat 0 lands at t=0, so the beat grid is exact: t = k * 0.5 s."""
import json, subprocess, sys
from pathlib import Path

L = Path("/Library/Audio/Apple Loops/Apple")
BPM = 120.0
PARTS = {  # path, start bar (4 beats = 2 s), gain
    "pad": (L / "08 Indie Disco/Disco Pop Synth Pad.caf", 0, 0.7),
    "drums": (L / "13 Drummer/Julian - Chorus.caf", 4, 0.9),
    "bass": (L / "08 Indie Disco/Disco Pop Bass.caf", 4, 0.9),
    "gtr": (L / "08 Indie Disco/Disco Pop Rhythm Guitar.caf", 8, 0.6),
    "stabs": (L / "08 Indie Disco/Disco Pop Synth Stabs.caf", 12, 0.5),
}


def build(out: Path, seconds: float):
    inputs, filters = [], []
    for i, (name, (p, bar, g)) in enumerate(PARTS.items()):
        inputs += ["-stream_loop", "-1", "-i", str(p)]
        d = int(bar * 2000)
        filters.append(f"[{i}:a]atrim=0:{seconds - bar * 2:.3f},volume={g},adelay={d}|{d}[a{i}]")
    mix = "".join(f"[a{i}]" for i in range(len(PARTS)))
    fade = max(0, seconds - 1.5)
    filters.append(f"{mix}amix=inputs={len(PARTS)}:normalize=0,atrim=0:{seconds:.3f},afade=t=out:st={fade:.3f}:d=1.5,"
                   f"loudnorm=I=-16:TP=-1.5[out]")
    subprocess.check_call(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(filters),
                           "-map", "[out]", "-ar", "48000", "-ac", "2", str(out)])
    beats = [round(k * 60 / BPM, 3) for k in range(int(seconds * BPM / 60) + 1)]
    return {"bpm": BPM, "beats": beats, "source": "Apple Loops (GarageBand), royalty-free"}


if __name__ == "__main__":
    print(json.dumps(build(Path(sys.argv[1]), float(sys.argv[2])))[:200])
