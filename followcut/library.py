"""The clip library: source files plus curated candidate windows.

Candidate windows are where the scanner samples densely. Every other clip still gets a
coarse scan (a few frames) so the library view shows where the subject appears at all.
"""
import os
from pathlib import Path

FOOTAGE = Path(os.environ.get("FOOTAGE_DIR", Path.home() / "projects/portland-edits"))
LIBRARY_NAME = "Portland, Oct 16–18"

# id -> (label, path)
CLIPS = {}
for p in sorted((FOOTAGE / "raw/dji").glob("DJI_*.MP4")):
    CLIPS[p.stem] = p
for p in sorted((FOOTAGE / "raw/shared_album").glob("*.mp4")):
    CLIPS[p.stem] = p

LABELS = {
    "DJI_0671": "3:51am curb", "DJI_0672": "Uber no-show", "DJI_0673": "PDX gate",
    "DJI_0674": "Morning walk", "DJI_0675": "Oops", "DJI_0676": "Tanaka matcha",
    "DJI_0680": "Cascade Locks car", "DJI_0681": "Cascade Locks park", "DJI_0682": "Thunder Island",
    "DJI_0683": "Bonneville Hatchery", "DJI_0684": "Car blooper", "DJI_0685": "Downtown drive",
    "DJI_0686": "Canyon road", "DJI_0687": "Washington Park", "DJI_0688": "Birthday dinner",
    "DJI_0689": "Cheese & Crack", "20261016_145623_IMG_7880": "The rental",
    "20261016_221125_IMG_7917": "Bonneville Dam", "20261017_040824_IMG_5693": "Tilikum Crossing",
    "20261017_184155_IMG_5710": "Dessert tasting", "20261017_201637_IMG_7981": "Project Matcha",
    "20261018_052651_IMG_5774": "Locked in the car", "20261018_123728_IMG_8061": "Bye Oregon",
}

# (clip, start, end): dense-scan windows (from a manual pass over the footage)
WINDOWS = [
    ("DJI_0673", 48.0, 56.0),
    ("DJI_0674", 0.5, 8.5), ("DJI_0674", 96.0, 104.0), ("DJI_0674", 106.0, 118.0),
    ("DJI_0674", 188.0, 196.0),
    ("DJI_0680", 30.0, 37.0), ("DJI_0680", 76.6, 80.0),
    ("DJI_0681", 0.5, 4.0), ("DJI_0681", 4.0, 8.0), ("DJI_0681", 8.0, 16.0), ("DJI_0681", 16.5, 21.5),
    ("DJI_0682", 12.0, 15.0), ("DJI_0682", 26.0, 34.0), ("DJI_0682", 15.0, 24.0), ("DJI_0682", 104.0, 106.0),
    ("DJI_0683", 14.0, 18.0), ("DJI_0683", 60.0, 66.0), ("DJI_0683", 95.7, 104.0),
    ("DJI_0685", 146.0, 149.5),
    ("DJI_0686", 20.0, 26.0),
    ("20261017_201637_IMG_7981", 0.2, 7.3),
    ("20261018_123728_IMG_8061", 0.2, 8.0), ("20261018_123728_IMG_8061", 8.0, 13.0),
    ("20261018_123728_IMG_8061", 18.6, 21.8),
]
