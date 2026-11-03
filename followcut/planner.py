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
        for beats in (8, 6, 4):
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
SAM 3.1 already segmented that concept in every clip. Image 1 is the REFERENCE: the user's subject (outlined).
Images 2..N are one raw keyframe per candidate moment, in the same order as the JSON list; the yellow box marks
   the subject SAM tracked in that moment.
1. Identity: SAM matches the concept, not the person. Reject any candidate whose outlined subject is clearly a
   different individual from the reference (judge the boxed person) (a stranger, a statue, a toy).
2. Story: from the rest, pick moments that show the subject at their best (laughing, waving, moving, a reveal),
   {target} beats total at 120 BPM (stay between {target}-4 and {target}+4; use 6-9 shots), each shot 4, 6 or 8 beats, ordered as a story (candidates are chronological).
Stats: presence = share of sampled frames with the subject, area = mask share of frame, conf = SAM score.
Return JSON only: {{"rejected":[{{"id":<id>,"why":"<=10 words"}}],
"shots":[{{"id":<candidate id>,"beats":4|6|8,"reason":"<=14 words: what happens in the shot"}}]}}"""


def spark(scan, prompt, keyframes, target_beats=44, reference=None):
    """Muse Spark via the Meta Model API (OpenAI-compatible chat endpoint; base/model are env-configurable)."""
    key = os.environ["META_API_KEY"]
    base = os.environ.get("META_API_BASE", "https://api.meta.ai/v1")
    model = os.environ.get("META_MODEL", "muse-spark-1.3")
    ms = _moments(scan)
    cands = [{"id": i, "clip": LABELS.get(m["clip"], m["clip"]), "in": m["in"], "out": m["out"],
              "presence": round(m["presence"], 2), "area": round(m["area"], 3), "conf": round(m["conf"], 2)}
             for i, m in enumerate(ms)]
    content = [{"type": "text", "text": SPARK_PROMPT.format(prompt=prompt, target=target_beats).replace(f"{target_beats}-4", str(target_beats - 4)).replace(f"{target_beats}+4", str(target_beats + 4)) + "\n" + json.dumps(cands)}]
    img = lambda path: {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(Path(path).read_bytes()).decode()}}
    if reference and Path(reference).exists():
        content.append(img(reference))
    for m in ms:
        kf = keyframes.get((m["clip"], m["in"]))
        if kf and Path(kf).exists():
            content.append(img(kf))
    body = {"model": model, "messages": [{"role": "user", "content": content}], "response_format": {"type": "json_object"}}
    req = urllib.request.Request(base.rstrip("/") + "/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    resp = json.loads(urllib.request.urlopen(req, timeout=300).read())
    text = resp["choices"][0]["message"]["content"]
    if isinstance(text, list):
        text = "".join(p.get("text", "") for p in text)
    plan = json.loads(text[text.find("{"): text.rfind("}") + 1])
    rej_ids = {int(r["id"]) for r in plan.get("rejected", []) if str(r.get("id", "")).lstrip("-").isdigit()}
    picked, seen, per_clip = [], set(), {}
    for s in plan["shots"]:  # validate: in range, not rejected, each moment once, at most 2 per clip
        i = int(s["id"])
        if not 0 <= i < len(ms) or i in rej_ids or i in seen or per_clip.get(ms[i]["clip"], 0) >= 2:
            continue
        seen.add(i); per_clip[ms[i]["clip"]] = per_clip.get(ms[i]["clip"], 0) + 1; picked.append((i, s))
    if len(picked) < min(3, len(ms) - len(rej_ids)) or not picked:
        raise ValueError(f"Spark plan too short ({len(picked)} shots)")
    picked.sort(key=lambda p: (CHRONO.index(ms[p[0]]["clip"]) if ms[p[0]]["clip"] in CHRONO else 99, ms[p[0]]["in"]))
    shots = []
    for i, s in picked:
        m = ms[i]
        beats = min(int(s.get("beats", m["beats"])), m["beats"])
        beats = 8 if beats >= 8 else 6 if beats >= 6 else 4
        shots.append({"clip": m["clip"], "label": LABELS.get(m["clip"], m["clip"]), "in": m["in"],
                      "out": round(m["in"] + beats * SPB, 2), "beats": beats, "effect": "follow-crop + color-pop",
                      "reason": s.get("reason", "")})
    rejected = [{"clip": ms[int(r["id"])]["clip"], "label": LABELS.get(ms[int(r["id"])]["clip"], ""), "why": r.get("why", "")}
                for r in plan.get("rejected", []) if 0 <= int(r["id"]) < len(ms)]
    rejected = [r for k, r in enumerate(rejected) if r["clip"] not in {x["clip"] for x in rejected[:k]}]
    rejected = [r for r in rejected if r["clip"] not in {sh["clip"] for sh in shots}]  # a clip with a kept shot isn't "not them"
    for sh in sorted(shots, key=lambda x: x["beats"]):  # short plan: let shots run to their full moment
        if sum(x["beats"] for x in shots) >= target_beats - 4:
            break
        m = next(m for m in ms if m["clip"] == sh["clip"] and m["in"] == sh["in"])
        sh["beats"] = m["beats"]; sh["out"] = round(sh["in"] + m["beats"] * SPB, 2)
    while len(shots) > 3 and sum(x["beats"] for x in shots) > target_beats + 8:  # keep near the target length
        shots.pop(min(range(len(shots)), key=lambda k: shots[k]["beats"]))
    return {"planner": f"muse-spark:{model}", "rejected_by_spark": rejected, "planner_label": f"Muse Spark ({model}) via Meta Model API",
            "bpm": 120, "duration": sum(s["beats"] for s in shots) * SPB, "shots": shots}


def moments(scan):
    return _moments(scan)


def plan(scan, prompt, keyframes=None, exclude=(), reference=None):
    """exclude: clips the user marked "not them" (SAM matches the concept, e.g. any woman; cross-clip re-ID is future work)."""
    scan = {**scan, "windows": [w for w in scan["windows"] if w["clip"] not in exclude]}
    if os.environ.get("META_API_KEY"):
        try:
            return spark(scan, prompt, keyframes or {}, reference=reference)
        except Exception as e:  # never let the demo die on the network; record why
            p = heuristic(scan)
            p["planner"] = "heuristic-fallback"
            p["planner_label"] = f"Heuristic planner (fallback: Muse Spark call failed, {type(e).__name__})"
            return p
    return heuristic(scan)
