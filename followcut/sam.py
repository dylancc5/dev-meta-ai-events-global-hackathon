"""SAM 3.1 text-prompted segmentation (transformers Sam3Model) on Apple-silicon MPS."""
import os, time
import numpy as np
import torch
from PIL import Image

MODEL_ID = os.environ.get("SAM_MODEL", "unsloth/sam3.1")  # SAM 3.1 weights; facebook/sam3.1 once licensed


class Segmenter:
    def __init__(self, device=None, dtype=torch.float16):
        from transformers import Sam3Model, Sam3Processor
        self.device = device or ("mps" if torch.backends.mps.is_available() else "cpu")
        self.dtype = dtype if self.device != "cpu" else torch.float32
        self.model = Sam3Model.from_pretrained(MODEL_ID, dtype=self.dtype).to(self.device).eval()
        self.proc = Sam3Processor.from_pretrained(MODEL_ID)
        self.frames = 0
        self.seconds = 0.0

    @torch.inference_mode()
    def __call__(self, rgb: np.ndarray, prompt: str, threshold=0.45):
        """rgb HxWx3 uint8 -> list of {score, box[x0,y0,x1,y1], mask(HxW bool)} sorted by score."""
        t = time.time()
        inp = self.proc(images=Image.fromarray(rgb), text=prompt, return_tensors="pt").to(self.device)
        inp = {k: (v.to(self.dtype) if v.is_floating_point() else v) for k, v in inp.items()}
        out = self.model(**inp)
        r = self.proc.post_process_instance_segmentation(
            out, threshold=threshold, mask_threshold=0.5, target_sizes=inp["original_sizes"].tolist())[0]
        dets = [{"score": float(s), "box": [float(x) for x in b], "mask": m.cpu().numpy().astype(bool)}
                for s, b, m in zip(r["scores"], r["boxes"], r["masks"])]
        self.frames += 1
        self.seconds += time.time() - t
        return sorted(dets, key=lambda d: -d["score"])


def iou(a, b):
    x0, y0, x1, y1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, x1 - x0) * max(0, y1 - y0)
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / ua if ua > 0 else 0.0


def pick(dets, prev_box):
    """Keep one identity through a shot: best IoU with the previous box, else top score."""
    if not dets:
        return None
    if prev_box is not None:
        best = max(dets, key=lambda d: iou(d["box"], prev_box) + 0.25 * d["score"])
        if iou(best["box"], prev_box) > 0.1:
            return best
    return dets[0]
