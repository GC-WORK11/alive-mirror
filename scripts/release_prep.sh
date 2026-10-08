#!/usr/bin/env bash
# scripts/release_prep.sh — prepare the GitHub Release for the freeze-cut APK.
#
# Usage:
#   scripts/release_prep.sh <path-to-apk> [tag]
#
# Given the canonical demo APK it:
#   1. computes sha256 + byte size
#   2. parses the build sha out of the filename (alive108-<sha>.apk) and
#      checks that commit exists in this clone
#   3. fills the placeholders in docs/release/v1.0.0-demo-notes.md
#      (falls back to docs/release/RELEASE-NOTES.md) → <name>.filled.md
#   4. prints BOTH release paths — `gh release create` for a shell where
#      gh is authed, and the manual github.com web steps for when it isn't
#      (it is NOT authed on the work boxes).
#
# It never uploads or pushes anything itself — every action is printed
# for the owner to run.

set -euo pipefail

DEFAULT_TAG="v1.0.0-demo"

die() { echo "release_prep: ERROR: $*" >&2; exit 1; }

[ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ] && { sed -n '2,18p' "$0"; exit 0; }
[ $# -ge 1 ] || die "usage: scripts/release_prep.sh <path-to-apk> [tag]"

APK_PATH="$1"
TAG="${2:-$DEFAULT_TAG}"

[ -f "$APK_PATH" ] || die "no such file: $APK_PATH"
case "$APK_PATH" in *.apk) ;; *) echo "release_prep: WARNING: $APK_PATH is not a .apk" >&2 ;; esac

REPO_ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel 2>/dev/null)" \
  || die "run from inside the Delhi-Air-108 checkout"
# Prefer the tag-named notes file; the older RELEASE-NOTES.md is the fallback.
NOTES="$REPO_ROOT/docs/release/v1.0.0-demo-notes.md"
[ -f "$NOTES" ] || NOTES="$REPO_ROOT/docs/release/RELEASE-NOTES.md"
OUT="${NOTES%.md}.filled.md"
[ -f "$NOTES" ] || die "template missing: $NOTES"

APK_BASE="$(basename "$APK_PATH")"

# --- 1+2. build sha from filename + commit check -------------------------
if [[ "$APK_BASE" =~ ^alive108-([0-9a-f]{7,40})\.apk$ ]]; then
  BUILD_SHA="${BASH_REMATCH[1]}"
elif [ -n "${BUILD_SHA:-}" ]; then
  echo "release_prep: filename carries no sha; using BUILD_SHA env $BUILD_SHA"
else
  die "filename '$APK_BASE' is not alive108-<sha>.apk — rename the APK or export BUILD_SHA=<commit>"
fi

if git -C "$REPO_ROOT" rev-parse --verify --quiet "$BUILD_SHA^{commit}" >/dev/null; then
  BUILD_DESC="$(git -C "$REPO_ROOT" log -1 --format='%h — %s' "$BUILD_SHA")"
  echo "build sha $BUILD_SHA resolves in-repo: $BUILD_DESC"
else
  echo "release_prep: WARNING: $BUILD_SHA is not a commit in this clone." >&2
  echo "  Pull first (git pull origin base/v2) — the tag must point at the freeze commit." >&2
fi

# --- 3. sha256 + size (macOS + Linux) -------------------------------------
if command -v shasum >/dev/null; then SHA="$(shasum -a 256 "$APK_PATH" | awk '{print $1}')"
elif command -v sha256sum >/dev/null; then SHA="$(sha256sum "$APK_PATH" | awk '{print $1}')"
else SHA="$(openssl dgst -sha256 -r "$APK_PATH" | awk '{print $1}')"; fi
SIZE_B="$(wc -c < "$APK_PATH" | tr -d ' ')"
SIZE_MIB="$(awk -v b="$SIZE_B" 'BEGIN{printf "%.1f", b/1048576}')"

echo "sha256  $SHA"
echo "size    $SIZE_B bytes ($SIZE_MIB MiB)"

# --- 4. fill the release body ---------------------------------------------
sed -e "s|^TAG:.*|TAG:    $TAG|" \
    -e "s|^BUILD:.*|BUILD:  $BUILD_SHA|" \
    -e "s|^APK:.*|APK:    $APK_BASE|" \
    -e "s|^SIZE:.*|SIZE:   $SIZE_B bytes ($SIZE_MIB MiB)|" \
    -e "s|^SHA256:.*|SHA256: $SHA|" \
    "$NOTES" > "$OUT"
echo "filled body written → $OUT"

if command -v pbcopy >/dev/null; then pbcopy < "$OUT"; echo "body copied to clipboard (pbcopy)"
elif command -v xclip >/dev/null; then xclip -selection clipboard < "$OUT"; echo "body copied to clipboard (xclip)"; fi

# --- 5. tag target advice ---------------------------------------------------
BASE_TIP="$(git -C "$REPO_ROOT" rev-parse origin/base/v2 2>/dev/null || echo '?')"
BUILD_FULL="$(git -C "$REPO_ROOT" rev-parse --verify --quiet "$BUILD_SHA^{commit}" 2>/dev/null || true)"
if [ -n "$BUILD_FULL" ] && [ "$BUILD_FULL" = "$BASE_TIP" ]; then
  TARGET_LINE='Set **Target** to `base/v2` (the freeze commit IS the branch tip).'
else
  TARGET_LINE="Set **Target** to commit \`$BUILD_SHA\` (base/v2 tip is \`$BASE_TIP\`). If the dropdown won't take the sha, run the two \`git tag\`/\`git push\` lines from path A first — any shell works, no gh needed — then pick the existing tag."
fi

if git -C "$REPO_ROOT" ls-remote --exit-code --tags origin "$TAG" >/dev/null 2>&1; then
  echo "release_prep: WARNING: tag $TAG already exists on origin — pick another tag." >&2
fi

cat <<EOF

================ path A — gh (on a machine where gh is authed) ================

git -C "$REPO_ROOT" fetch origin --tags
# create + push the tag at the freeze commit:
git tag -a $TAG $BUILD_SHA -m "ALive·108 demo build — $BUILD_SHA"
git push origin $TAG
# create the release (pre-release) with the filled body and the APK asset:
gh release create $TAG "$APK_PATH" \\
    --title "ALive·108 — demo build ($TAG)" \\
    --notes-file "$OUT" \\
    --prerelease

================ path B — manual github.com (works anywhere) ================

1. Open https://github.com/<owner>/Delhi-Air-108/releases/new
2. "Choose a tag" → type: $TAG → "Create new tag: $TAG on publish".
3. $TARGET_LINE
4. Title: ALive·108 — demo build ($TAG)
5. Body: paste the contents of $OUT
     (already on your clipboard if pbcopy/xclip ran above)
6. Attach binaries: drag in $APK_BASE
7. Tick "Set as a pre-release".
8. Publish release.

==============================================================================
Tag picked: $TAG  (semver matching versionName 1.0.0 + explicit demo marker;
leaves a plain v1.0.0 free for a future signed store build)
EOF
