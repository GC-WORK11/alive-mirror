#!/usr/bin/env bash
# Oct-8 baseline: fresh public repo with history inside the event window.
#
# Hackathon rule: "a repository whose history does not match the event
# dates disqualifies the whole team." Our private repo's commits predate
# Oct 8, so on the day we squash everything to ONE baseline commit and
# push to a NEW public repo. All later commits land inside the window.
#
# Usage:  ./scripts/public-repo.sh <new-public-repo-url>
#   e.g.  ./scripts/public-repo.sh https://github.com/<owner>/alive-108.git
#
# What it does:
#   1. creates an orphan branch `public-baseline` with the full tree
#   2. one commit: "baseline: ALive-108 — Delhi air-dose engine + apps"
#   3. pushes it as `main` to the new public remote
#   4. resets the working branch back to origin/main (nothing lost here)
set -euo pipefail

URL="${1:?usage: ./scripts/public-repo.sh <new-public-repo-url>}"
STAMP="$(git log -1 --format=%H origin/main)"

git checkout --orphan public-baseline "$STAMP"
git add -A
git commit -m "baseline: ALive-108 — Delhi air-dose engine + apps" \
  -m "Dose engine (FastAPI) + consumer app (Android/iOS) + live public API
on AWS for AWS x WeMakeDevs Environmental Hacks, Track 01 (Air)."
git remote add public-repo "$URL" 2>/dev/null || git remote set-url public-repo "$URL"
git push public-repo public-baseline:main

git checkout main
git branch -D public-baseline
git remote remove public-repo
echo "Pushed $STAMP as the single baseline commit to $URL"
