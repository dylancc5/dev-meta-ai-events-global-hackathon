#!/usr/bin/env bash
# Generates PLACEHOLDER data under public/data/ (the real pipeline overwrites it).
set -euo pipefail
cd "$(dirname "$0")/.."
D=public/data
rm -rf "$D"; mkdir -p "$D/thumbs"
IDS=(DJI_0681 DJI_0683 DJI_0690 DJI_0694 DJI_0702 DJI_0705 DJI_0711 DJI_0716 DJI_0720 DJI_0724 DJI_0731 DJI_0736)
COLS=("#3b4a5c:#c9895a" "#2f4a3a:#a7c4a0" "#4a3b52:#e0a96d" "#5a4030:#d9b48f" "#263a4f:#8fb3d9" "#3d3d2a:#c2b46b"
      "#4f2f35:#e48a7a" "#2a4040:#7fc4bb" "#40352a:#d1a06a" "#30304a:#a29be0" "#2e4433:#b9d38a" "#4a2e2e:#f0b07a")
q() { ffmpeg -loglevel error -y "$@"; }
for i in "${!IDS[@]}"; do
  IFS=: read -r c0 c1 <<<"${COLS[$i]}"
  q -f lavfi -i "gradients=s=480x270:c0=${c0}:c1=${c1}:x0=0:y0=0:x1=480:y1=270:d=1" -frames:v 1 -q:v 3 "$D/thumbs/${IDS[$i]}.jpg"
done
for run in woman man dog; do
  mkdir -p "$D/runs/$run/scan"
  for i in "${!IDS[@]}"; do
    x=$(( 120 + (i * 37) % 200 )); w=$(( 90 + (i * 13) % 60 ))
    q -i "$D/thumbs/${IDS[$i]}.jpg" -vf "eq=saturation=0.25,drawbox=x=${x}:y=50:w=${w}:h=200:color=#ffb35c@0.35:t=fill,drawbox=x=${x}:y=50:w=${w}:h=200:color=#ffb35c:t=3" -q:v 3 "$D/runs/$run/scan/${IDS[$i]}.jpg"
  done
  q -f lavfi -i "testsrc2=s=720x1280:r=30:d=5" -c:v libx264 -pix_fmt yuv420p -movflags +faststart "$D/runs/$run/edit.mp4"
  q -i "$D/runs/$run/edit.mp4" -frames:v 1 -q:v 3 "$D/runs/$run/poster.jpg"
done
for run in woman man; do
  q -f lavfi -i "testsrc2=s=1920x1080:r=30:d=5" -c:v libx264 -pix_fmt yuv420p -movflags +faststart "$D/runs/$run/compare.mp4"
done
cp scripts/placeholder-manifest.json "$D/manifest.json"
echo "placeholders written to $D"
