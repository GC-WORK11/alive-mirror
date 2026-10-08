# Squash-baseline runbook — demo morning Oct 8

`scripts/public-repo.sh` creates ONE baseline commit holding the full product
tree and pushes it as `main` to a brand-new **public** repo, so all visible
history sits inside the Oct 8–11 event window. It has been dry-run and
break-tested (rehearsal notes at the bottom).

## Before you run (2 min)

1. **Create the empty public repo on GitHub first.** No README, no .gitignore,
   no license — it must be completely empty. Example name: `Alive`.
2. **Make sure GitHub auth works from this machine** — same auth you use to
   push to the private repo (SSH key, or PAT in your credential helper).
3. Pull latest: `git fetch origin`
4. Git identity set? `git config user.name` / `git config user.email` — the
   script aborts early if not.
5. **Decide the branch.** The script picks the tip-most of `base/v2` and
   `main` (whichever contains the other). If the two have genuinely diverged
   it defaults to `base/v2` and prints a `WARNING: baseline misses N
   commit(s) on main` line for each ref with commits it won't include —
   read that. If those missing commits are product you want public, merge
   them into `base/v2` first (or run with `--ref main`).
   Optional sanity: `bash scripts/public-repo.sh <url> --dry-run` runs every
   check and prints the exact push command without pushing.

## Run it

```bash
cd <your Delhi-Air-108 clone>
bash scripts/public-repo.sh https://github.com/<owner>/<new-public-repo>.git
```

Expected output (abbrev.):

```
>> baseline source: base/v2 @ <sha> <subject>
>> checking remote: https://github.com/<owner>/<new-public-repo>.git
>> baseline commit: <sha> — baseline: Alive — Delhi air-dose engine + apps  (tree identical to base/v2)
To https://github.com/<owner>/<new-public-repo>.git
 * [new branch]      <sha> -> main
>> done: <url> main = <sha>
>> verify on GitHub: exactly 1 commit, <N> files, tree identical to base/v2 (<sha>)
>> your working tree was never touched — still on base/v2
```

## After (30 sec verify)

- GitHub page shows **exactly 1 commit**, all files present.
- `git ls-remote <public-url>` → the `main` sha equals the printed baseline sha.
- Nothing in your local repo changed: same branch, same dirty files, no new
  branches or remotes (check `git status` / `git remote -v`).

## Failure modes and fixes

| Symptom | Meaning | Fix |
|---|---|---|
| `ERROR: cannot reach remote` | URL wrong, repo doesn't exist, or no GitHub auth | Create the repo first; check the URL; fix SSH/PAT auth |
| `refusing to publish possible secrets` | `.env`-like file tracked, or key-shaped string (AWS/GitHub/token) found in tracked content | Scrub/rotate it, or `--force` if a false positive |
| `tracked files exceed GitHub's 100MB limit` | A blob ≥100MB is tracked — GitHub would reject the push anyway | Remove it from the branch, commit, re-run |
| `already has a different main` | The remote repo isn't empty | Use a fresh empty repo, or `--force` to overwrite intentionally |
| `WARNING: baseline misses N commit(s) on main` | `main` has commits the baseline won't contain | Merge into `base/v2` first, or `--ref main` |
| `WARNING: local base/v2 has commits not on origin` | Unpushed local work — it IS included in the baseline | Nothing to do; push it later if you want it on origin too |
| Push dies mid-way (network) | Partial failure | Safe to just re-run the same command — nothing is left half-done |
| Repo shows a different `main` after a previous run | Baseline already pushed | Script prints "already has this exact tree" and exits — done |

Flags: `--dry-run` (everything but the push) · `--ref <branch>` (squash a
different branch) · `--force` (proceed past secret findings / overwrite an
existing remote `main`).

## Why the rewrite (rehearsal findings, Oct 5)

The old version did `git checkout --orphan` + `git add -A` + `git checkout
main` in the working repo. Rehearsal showed:

- it squashed `origin/main` — wrong ref while `base/v2` is the ship branch;
- `git add -A` swept uncommitted edits and untracked files into the **public**
  baseline (private notes would go public);
- `git checkout main` then deleted those files from disk — uncommitted work
  lost, and the user landed on the wrong branch;
- a failed push left you on `public-baseline` with a stale `public-repo`
  remote, and re-running died with "branch already exists";
- no checks for >100MB blobs (GitHub rejects), secrets, or remote reachability.

The rewrite uses `git commit-tree <ref>^{tree}` + `git push <url>
<sha>:refs/heads/main`: the baseline tree is byte-identical to the chosen ref
by construction, and the working tree, index, branches, and remotes are never
touched. Verified in rehearsal: `diff -r` of the published tree vs `base/v2`
is identical, the public repo has exactly one commit and one ref, and
`.env`/`*.pem` files do not appear in it.
