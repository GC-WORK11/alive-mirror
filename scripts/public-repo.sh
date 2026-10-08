#!/usr/bin/env bash
# Oct-8 baseline: fresh public repo with history inside the event window.
#
# Hackathon rule: "a repository whose history does not match the event
# dates disqualifies the whole team." Our private repo's commits predate
# Oct 8, so on the day we squash everything to ONE baseline commit and
# push to a NEW public repo. All later commits land inside the window.
#
# Usage:
#   ./scripts/public-repo.sh <new-public-repo-url> [--ref <branch>] [--dry-run] [--force]
#   e.g.  ./scripts/public-repo.sh https://github.com/<owner>/Alive.git
#
# Safe by construction: it never touches your working tree, index, checked-
# out branch, or remote config. It writes ONE commit object holding the
# chosen ref's exact tree (`git commit-tree`) and pushes that commit as
# `main` to the new remote. Uncommitted work stays uncommitted; untracked
# and ignored files stay on disk and out of the public history.
#
# What it does:
#   1. picks the baseline ref: --ref if given; else the tip-most of
#      {base/v2, main} (whichever contains the other); on true divergence
#      it defaults to base/v2 and prints exactly what would be missed
#   2. preflights: inside a git repo, committer identity set, remote reachable
#   3. guardrails: aborts on >100MB blobs (GitHub hard-rejects) and obvious
#      secrets; warns on >50MB blobs and commits the baseline would miss
#   4. writes the baseline commit, pushes it as `main`
set -euo pipefail

die()  { echo "ERROR: $*" >&2; exit 1; }
info() { echo ">> $*"; }
warn() { echo "WARNING: $*" >&2; }

URL=""
REF=""
DRY_RUN=0
FORCE=0
while [ $# -gt 0 ]; do
  case "$1" in
    --ref)     REF="${2:?--ref needs a value}"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    --force|-f) FORCE=1; shift ;;
    -h|--help) sed -n '2,25p' "$0"; exit 0 ;;
    -*)        die "unknown flag: $1" ;;
    *)         [ -z "$URL" ] || die "unexpected extra argument: $1"; URL="$1"; shift ;;
  esac
done
[ -n "$URL" ] || die "usage: ./scripts/public-repo.sh <new-public-repo-url> [--ref <branch>] [--dry-run] [--force]"

git rev-parse --is-inside-work-tree >/dev/null 2>&1 \
  || die "not inside a git repo — run this from your clone of Delhi-Air-108"
cd "$(git rev-parse --show-toplevel)"

git var GIT_AUTHOR_IDENT    >/dev/null 2>&1 \
  || die "git identity not set — run: git config --global user.name 'govinda' && git config --global user.email '<you>'"
git var GIT_COMMITTER_IDENT >/dev/null 2>&1 \
  || die "git identity not set — run: git config --global user.name 'govinda' && git config --global user.email '<you>'"

# --- pick the baseline tip -------------------------------------------------
# Local branch first; if origin/<name> strictly contains the local tip it is
# newer and wins. Genuine divergence falls back to the local tip with a warning.
pick_tip() {
  local l o
  l=$(git rev-parse --verify --quiet "$1^{commit}" 2>/dev/null || true)
  o=$(git rev-parse --verify --quiet "origin/$1^{commit}" 2>/dev/null || true)
  if [ -n "$l" ] && [ -n "$o" ] && [ "$l" != "$o" ]; then
    if git merge-base --is-ancestor "$l" "$o"; then
      warn "local $1 is behind origin/$1 — using origin/$1"
      echo "$o"; return
    elif git merge-base --is-ancestor "$o" "$l"; then
      warn "local $1 has commits not on origin/$1 — using local tip (unpushed work included)"
      echo "$l"; return
    else
      warn "local $1 and origin/$1 have diverged — using local tip"
      echo "$l"; return
    fi
  fi
  echo "${l:-$o}"
}

if [ -n "$REF" ]; then
  TIP=$(pick_tip "$REF")
  [ -n "$TIP" ] || die "ref '$REF' not found (tried '$REF' and 'origin/$REF')"
  REFNAME="$REF"
else
  BTIP=$(pick_tip base/v2)
  MTIP=$(pick_tip main)
  if [ -n "$BTIP" ] && [ -n "$MTIP" ] && [ "$BTIP" != "$MTIP" ]; then
    if git merge-base --is-ancestor "$MTIP" "$BTIP"; then
      REFNAME="base/v2"; TIP=$BTIP
    elif git merge-base --is-ancestor "$BTIP" "$MTIP"; then
      REFNAME="main";   TIP=$MTIP
      info "main contains all of base/v2 plus more — using main tip"
    else
      REFNAME="base/v2"; TIP=$BTIP
      warn "base/v2 and main have diverged — defaulting to base/v2"
    fi
  elif [ -n "$BTIP" ]; then
    REFNAME="base/v2"; TIP=$BTIP
  elif [ -n "$MTIP" ]; then
    REFNAME="main"; TIP=$MTIP
  else
    die "no base/v2 or main ref found — fetch first, or pass --ref <branch>"
  fi
fi
info "baseline source: $REFNAME @ $(git log -1 --format='%h %s' "$TIP")"

# --- divergence report: what the baseline will NOT contain -----------------
MISSING=0
for r in base/v2 origin/base/v2 main origin/main; do
  o=$(git rev-parse --verify --quiet "$r^{commit}" 2>/dev/null || true)
  [ -n "$o" ] && [ "$o" != "$TIP" ] || continue
  behind=$(git rev-list --count "$TIP..$o")
  [ "$behind" -gt 0 ] || continue
  warn "baseline misses $behind commit(s) on $r (tip: $(git log -1 --format='%h %s' "$o"))"
  MISSING=1
done
[ "$MISSING" -eq 0 ] || warn "if one of those is intentional product state, re-run with --ref <that-branch>"

# --- preflight: remote reachable --------------------------------------------
info "checking remote: $URL"
LSOUT=$(git ls-remote "$URL" 'refs/heads/main' 2>&1) \
  || die "cannot reach remote — check the URL and your GitHub auth (SSH key or PAT in credential helper). git said:
$LSOUT"
REMOTE_MAIN=$(echo "$LSOUT" | awk 'NF{print $1}')

# --- guardrail: blob sizes (GitHub rejects >100MB, warns >50MB) --------------
BIG=$(git ls-tree -rl "$TIP" | awk -F'\t' '{split($1,a," "); s=a[4]+0;
        if (s >= 104857600) printf "%s (%.0f MB)\n", $2, s/1048576}')
[ -z "$BIG" ] || die "tracked files exceed GitHub's 100MB limit — remove them from $REFNAME first:
$BIG"
WARNSIZE=$(git ls-tree -rl "$TIP" | awk -F'\t' '{split($1,a," "); s=a[4]+0;
        if (s >= 52428800 && s < 104857600) printf "  %s (%.0f MB)\n", $2, s/1048576}')
[ -z "$WARNSIZE" ] || warn "files >50MB — GitHub will warn but accept:
$WARNSIZE"

# --- guardrail: secrets in the tree -----------------------------------------
SECRET_FILES=$(git ls-tree -r --name-only "$TIP" | grep -iE \
  '(^|/)(\.env$|\.env\.(local|prod|production|dev|development|private|secret)[^/]*|id_rsa|id_ed25519|credentials[^/]*\.json|service[-_.]account[^/]*\.json)' \
  | grep -vE '\.(example|sample|template)$' || true)
SECRET_CONTENT=$(git grep -nI -E \
  'AKIA[0-9A-Z]{16}|-----BEGIN (RSA|EC|DSA|OPENSSH|PGP|ENCRYPTED) PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|xox[baprs]-[0-9A-Za-z-]{10,}|AIza[0-9A-Za-z_-]{35}' \
  "$TIP" -- 2>/dev/null | sed "s/^$TIP:/  /" || true)
if [ -n "$SECRET_FILES" ] || [ -n "$SECRET_CONTENT" ]; then
  if [ -n "$SECRET_FILES" ]; then
    echo "suspicious files tracked in $REFNAME:" >&2; echo "$SECRET_FILES" >&2
  fi
  if [ -n "$SECRET_CONTENT" ]; then
    echo "possible secrets in tracked content:" >&2; echo "$SECRET_CONTENT" >&2
  fi
  [ "$FORCE" -eq 1 ] || die "refusing to publish possible secrets — scrub them, or re-run with --force if these are false positives"
  warn "proceeding anyway because --force was passed — double-check the list above"
fi

# --- baseline commit ---------------------------------------------------------
BASE=$(git commit-tree "$TIP^{tree}" \
  -m "baseline: Alive — Delhi air-dose engine + apps" \
  -m "Dose engine (FastAPI) + consumer app (Android/iOS) + live public API
on AWS for AWS x WeMakeDevs Environmental Hacks, Track 01 (Air).")
info "baseline commit: $(git log -1 --format='%h — %s' "$BASE")  (tree identical to $REFNAME)"

if [ "$DRY_RUN" -eq 1 ]; then
  info "dry run — would execute:  git push \"$URL\" $BASE:refs/heads/main"
  exit 0
fi

# --- push --------------------------------------------------------------------
if [ -n "$REMOTE_MAIN" ]; then
  RTREE=$(git rev-parse --verify --quiet "$REMOTE_MAIN^{tree}" 2>/dev/null || true)
  if [ -n "$RTREE" ] && [ "$RTREE" = "$(git rev-parse "$TIP^{tree}")" ]; then
    info "remote main already has this exact tree — nothing to do"
    exit 0
  fi
  [ "$FORCE" -eq 1 ] \
    || die "$URL already has a different main ($REMOTE_MAIN). Refusing to overwrite; re-run with --force only if you mean to replace it."
  warn "force-pushing over existing remote main $REMOTE_MAIN"
  git push --force "$URL" "$BASE:refs/heads/main"
else
  git push "$URL" "$BASE:refs/heads/main"
fi

FILES=$(git ls-tree -r --name-only "$TIP" | wc -l | tr -d ' ')
info "done: $URL main = $BASE"
info "verify on GitHub: exactly 1 commit, $FILES files, tree identical to $REFNAME ($(git rev-parse --short "$TIP"))"
info "your working tree was never touched — still on $(git branch --show-current 2>/dev/null || echo 'detached HEAD')"
