# FollowCut

**Hours of trip footage → the moments worth reliving, centered on the people you love.**

**Live demo:** https://dylancc5.github.io/dev-meta-ai-events-global-hackathon/ (replay of cached on-device runs)

You come back from a trip with 23 clips and 56 minutes of footage and you never edit any of it. FollowCut asks one question: *who is this video about?* Type "the woman with long hair", "the man" or "the dog". **SAM 3.1** finds that subject in every clip. A planner picks their best moments on the beat, and the renderer cuts a vertical 9:16 edit where the camera follows them, they stay in full color, and the rest of the world fades to gray.

Built for the **Meta Global AI Developer Hackathon 2026** · Indie track · theme: *Build for Your World*.

## The problem
Auto-editors cut on faces, speech or whoever is biggest in frame. They can't follow *a specific person* or "the dog", and they reframe 16:9 footage around the wrong subject. Vacation footage is almost all two-shots and group shots, so "who is it about" is the whole edit. You can't answer that with a face detector. You can with a text-prompted segmenter.

## What it does
1. **Scan.** For a text prompt, SAM 3.1 segments every clip in the library. It takes a coarse pass on every clip ("is she in this clip at all?") and a dense 3 fps pass on candidate windows (where, how big, how confident). Clips without the subject (driving POV, the bridge at night) drop out.
2. **Plan.** FollowCut scores every 4-, 6- and 8-beat moment by presence, mask area and SAM confidence. Then **Muse Spark** gets the candidate stats, a reference crop of the subject and one keyframe per moment with SAM's pick boxed. It rejects look-alikes (a stranger who also matches "the man"), picks the moments worth keeping, and returns a shot list on a 120 BPM grid with a reason for every shot. The plan is checked before render: ids in range, one shot per clip, story order, length near target.
3. **Render.** Each chosen shot is segmented again at full frame rate (30 fps). The mask centroid is smoothed into a 9:16 follow-crop with a slow push-in. The mask, feathered, drives a subject-only color grade (subject in color, world desaturated) and a spotlight vignette. The output is a 720×1280 H.264 edit plus a side-by-side raw-vs-edit video.
4. **Re-cut.** Retype the prompt and the same footage cuts into a different film about a different person.

The web app (`web/`) is a deterministic **replay viewer** of cached runs, so the demo can't fail live. SAM 3.1 runs locally on Apple silicon (an M5 Pro over MPS), not on a serverless host.

## Meta tech
| | How it's used |
|---|---|
| **SAM 3.1** (open weights) | Text-prompted concept segmentation is the core of the product. Masks drive clip selection, the follow-crop path and every visual effect. On an M5 Pro over MPS in fp16 it takes 0.42 s/frame; a full run is ~1,200 segmented frames. Weights load through transformers `Sam3Model` from `unsloth/sam3.1`, a mirror of `facebook/sam3.1` under the SAM License. |
| **Muse Spark** (`muse-spark-1.3`, Meta Model API) | The edit planner and identity checker (`followcut/planner.py::spark`). One multimodal call per run with the SAM stats, a reference crop and a boxed keyframe per candidate. It returns JSON with the shots (in/out, beats, reason) and the rejected look-alikes (with a reason), and the UI shows both. In the demo's "the man" run, Spark threw out a stranger at the airport on its own, with no manual exclude list. Without `META_API_KEY`, or if the call fails, a deterministic heuristic planner runs and the UI labels it as one. |

## Run it
```bash
# pipeline (macOS, Apple silicon; Python 3.12)
uv venv -p 3.12 .venv && uv pip install --python .venv/bin/python torch torchvision transformers pillow opencv-python-headless numpy accelerate
export FOOTAGE_DIR=~/path/to/trip   # raw/dji/*.MP4 and raw/shared_album/*.mp4
.venv/bin/python -m followcut.run "the woman with long hair" woman W1   # scan → plan → render → web/public/data
# META_API_KEY=... plans with Muse Spark (falls back to a heuristic without it); EXCLUDE=<clip ids> for look-alikes Spark misses

# viewer
cd web && npm install && npm run build && npm start   # http://localhost:3123
```

## How it's built
- `followcut/sam.py`: SAM 3.1 wrapper, plus an IoU-based identity lock that keeps one subject through a shot.
- `followcut/scan.py`: coarse + dense library scan, writing per-clip presence/score and mask-outline thumbnails.
- `followcut/planner.py`: moment scoring, the heuristic planner, and the Muse Spark planner.
- `followcut/render.py`: full-rate masks → smoothed follow-crop → mask-driven grade → ffmpeg.
- `followcut/music.py`: a 120 BPM bed assembled from Apple Loops (royalty-free), with an exact beat grid.
- `web/`: a Next.js static replay viewer covering scan animation, the 9:16 player, raw-vs-edit and the plan.

## Honest limitations
- **SAM finds concepts, not identities.** "The man" also matches a stranger at the gate. Muse Spark catches most of these by comparing each boxed keyframe to a reference crop. A per-run exclude list (`EXCLUDE=`) is still there for what it misses, and the UI marks those "not them". Embedding-based re-identification across clips is next.
- The library's dense-scan windows are a curated shortlist of each long clip; every clip still gets a coarse scan. Scanning whole 10-minute clips densely is a batching job, not a design change.
- The footage is the author's own trip footage. Media files are kept out of the repo.

## What's next
- SAM 3.1 video tracking (Object Multiplex) in place of per-frame detection + IoU linking.
- Captions tucked behind the subject (mask-aware text), and speaker-filtered captions.
- Phone app: pick an album, type a name, share the reel.

## Credits
- SAM 3.1 © Meta, under the SAM License. Weights via the `unsloth/sam3.1` mirror of `facebook/sam3.1`.
- Music: Apple Loops (GarageBand), royalty-free.
- The beat-grid / cut approach draws on the author's earlier personal clip-editing scripts. This repo's pipeline was written during the hackathon.
- **Built with AI assistance (Claude Code).**

MIT license for the code in this repo.
