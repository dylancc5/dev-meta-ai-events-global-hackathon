"""Edit planner. Muse Spark (Meta Model API) when META_API_KEY is set; otherwise a deterministic
heuristic stub over the SAM 3.1 scan stats. The plan records which planner produced it."""
import base64, json, os, urllib.request
from pathlib import Path
from .library import LABELS

# story order (capture time)
CHRONO = ["DJI_0671", "DJI_0672", "DJI_0673", "DJI_0674", "20261016_145623_IMG_7880", "DJI_0680", "DJI_0681",
          "DJI_0682", "DJI_0683", "20261016_221125_IMG_7917", "20261017_040824_IMG_5693", "DJI_0684", "DJI_0676",
          "20261017_184155_IMG_5710", "20261017_201637_IMG_7981", "DJI_0685", "DJI_0686", "DJI_0687", "DJI_0688",
          "DJI_0689", "20261018_052651_IMG_5774", "DJI_0675", "20261018_123728_IMG_8061"]
SPB = 0.5  # seconds per beat at 120 BPM


def _moments(scan):
    """Best 4- or 8-beat sub-window inside every dense-scan window."""
    out = []
    for w in scan["windows"]:
        S = w["samples"]
        best = None
        for beats in (8, 4):
            L = beats * SPB
            for i, s in enumerate(S):
                seg = [x for x in S[i:] if x["t"] < s["t"] + L]
                if s["t"] + L > w["end"] + 0.01 or len(seg) < 2:
                    continue
                pres = sum(1 for x in seg if x["score"] > 0) / len(seg)
                if pres < 0.85:
                    continue
                hit = [x for x in seg if x["score"] > 0]
                area = sum(x["area"] for x in hit) / len(hit)
                conf = sum(x["score"] for x in hit) / len(hit)
                size = min(1.0, area / 0.12)
                v = pres * conf * (0.4 + 0.6 * size) * (1.08 if beats == 8 else 1.0)
                if best is None or v > best["value"]:
                    best = {"clip": w["clip"], "in": round(s["t"], 2), "out": round(s["t"] + L, 2), "beats": beats,
                            "value": round(v, 4), "presence": pres, "area": area, "conf": conf}
        if best:
            out.append(best)
    return out


def heuristic(scan, target_beats=44, max_per_clip=1, exclude=()):
    ms = sorted([m for m in _moments(scan) if m["clip"] not in exclude], key=lambda m: -m["value"])
    chosen, beats, per = [], 0, {}
    for m in ms:
        if beats >= target_beats:
            break
        if per.get(m["clip"], 0) >= max_per_clip:
            continue
        if any(c["clip"] == m["clip"] and not (m["out"] <= c["in"] or m["in"] >= c["out"]) for c in chosen):
            continue
        chosen.append(m); per[m["clip"]] = per.get(m["clip"], 0) + 1; beats += m["beats"]
    chosen.sort(key=lambda m: (CHRONO.index(m["clip"]) if m["clip"] in CHRONO else 99, m["in"]))
    shots = [{"clip": m["clip"], "label": LABELS.get(m["clip"], m["clip"]), "in": m["in"], "out": m["out"],
              "beats": m["beats"], "effect": "follow-crop + color-pop",
              "reason": f"in frame {m['presence'] * 100:.0f}% of samples · fills {m['area'] * 100:.0f}% · SAM {m['conf']:.2f}"}
             for m in chosen]
    return {"planner": "heuristic-stub", "planner_label": "Heuristic planner (stub, Muse Spark pending API key)",
            "bpm": 120, "duration": sum(s["beats"] for s in shots) * SPB, "shots": shots}


SPARK_PROMPT = """You are the editor for FollowCut. The user wants a short beat-synced vertical edit about: "{prompt}".
SAM 3.1 already found the subject; below are candidate moments with stats (presence = share of sampled frames
the subject is in, area = share of the frame the subject's mask covers, conf = SAM score). One keyframe per
candidate is attached, in the same order. Pick moments that tell the trip's story and show the subject's best
moments (laughing, waving, moving), {target} beats total at 120 BPM, each shot 4 or 8 beats, ordered as a story.
Return JSON: {{"shots":[{{"id":<candidate id>,"beats":4|8,"reason":"<=14 words, what happens in the shot"}}]}}"""


def spark(scan, prompt, keyframes, target_beats=44):
    """Muse Spark via the Meta Model API (OpenAI-compatible chat endpoint; base/model are env-configurable)."""
    key = os.environ["META_API_KEY"]
    base = os.environ.get("META_API_BASE", "https://api.llama.com/compat/v1")
    model = os.environ.get("META_MODEL", "muse-spark")
    ms = _moments(scan)
    cands = [{"id": i, "clip": LABELS.get(m["clip"], m["clip"]), "in": m["in"], "out": m["out"],
              "presence": round(m["presence"], 2), "area": round(m["area"], 3), "conf": round(m["conf"], 2)}
             for i, m in enumerate(ms)]
    content = [{"type": "text", "text": SPARK_PROMPT.format(prompt=prompt, target=target_beats) + "\n" + json.dumps(cands)}]
    for m in ms:
        kf = keyframes.get((m["clip"], m["in"]))
        if kf and Path(kf).exists():
            content.append({"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," +
                                                                base64.b64encode(Path(kf).read_bytes()).decode()}})
    body = {"model": model, "messages": [{"role": "user", "content": content}], "response_format": {"type": "json_object"}}
    req = urllib.request.Request(base.rstrip("/") + "/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    resp = json.loads(urllib.request.urlopen(req, timeout=120).read())
    text = resp["choices"][0]["message"]["content"]
    if isinstance(text, list):
        text = "".join(p.get("text", "") for p in text)
    plan = json.loads(text[text.find("{"): text.rfind("}") + 1])
    shots = []
    for s in plan["shots"]:
        m = ms[int(s["id"])]
        beats = 8 if int(s.get("beats", m["beats"])) >= 8 and m["beats"] == 8 else 4
        shots.append({"clip": m["clip"], "label": LABELS.get(m["clip"], m["clip"]), "in": m["in"],
                      "out": round(m["in"] + beats * SPB, 2), "beats": beats, "effect": "follow-crop + color-pop",
                      "reason": s.get("reason", "")})
    return {"planner": f"muse-spark:{model}", "planner_label": f"Muse Spark ({model}) via Meta Model API",
            "bpm": 120, "duration": sum(s["beats"] for s in shots) * SPB, "shots": shots}


def plan(scan, prompt, keyframes=None, exclude=()):
    """exclude: clips the user marked "not them" (SAM matches the concept, e.g. any woman; cross-clip re-ID is future work)."""
    scan = {**scan, "windows": [w for w in scan["windows"] if w["clip"] not in exclude]}
    if os.environ.get("META_API_KEY"):
        try:
            return spark(scan, prompt, keyframes or {})
        except Exception as e:  # never let the demo die on the network; record why
            p = heuristic(scan)
            p["planner_label"] += f" (Spark call failed: {type(e).__name__})"
            return p
    return heuristic(scan)
