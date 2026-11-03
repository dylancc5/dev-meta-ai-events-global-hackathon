import sys, json
from pathlib import Path
from .scan import scan
from .sam import Segmenter
prompt, slug, track = sys.argv[1], sys.argv[2], sys.argv[3]
d = scan(prompt, slug, Path("cache") / slug, Segmenter(), track=track)
print(json.dumps({k: d[k] for k in ("frames", "sam_seconds", "wall")}))
for c in d["clips"]:
    print(c["clip"], c["found"], c["presence"], c["score"])
