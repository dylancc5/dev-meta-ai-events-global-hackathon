#!/bin/bash
# Build the static replay viewer and publish it to GitHub Pages (gh-pages branch, media included).
set -euo pipefail
cd "$(dirname "$0")/../web"
REPO=dev-meta-ai-events-global-hackathon
rm -rf out && NEXT_PUBLIC_BASE_PATH=/$REPO npx next build
touch out/.nojekyll
find out -size +95M -print | grep . && { echo "file over 95MB"; exit 1; } || true
TMP=$(mktemp -d); cp -R out/. "$TMP"; cd "$TMP"
git init -q -b gh-pages && git add -A && git commit -qm "Deploy viewer $(date -u +%FT%TZ)"
git push -qf "https://github.com/dylancc5/$REPO.git" gh-pages
cd /; rm -rf "$TMP"
gh api "repos/dylancc5/$REPO/pages" >/dev/null 2>&1 || gh api -X POST "repos/dylancc5/$REPO/pages" -f "source[branch]=gh-pages" -f "source[path]=/" >/dev/null 2>&1 || true
echo "https://dylancc5.github.io/$REPO/"
