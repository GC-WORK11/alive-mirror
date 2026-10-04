# Self-hosted OSRM — sidecar in the Fargate task

Why: `/v2/plan`, `/v2/plan/full`, `/route`, `/compare`, `/directions` and
the quieter-route probes all used to ride `router.project-osrm.org` —
a rate-limited public demo that could 429 mid-demo. The task-def never
set `OSRM_URL`, so the local-first chain in `server/v2/deps.py`
(`routing_local`, default `http://127.0.0.1:5001`) always fell through
to the demo. There is no EC2 host in the account and never was — the
`scripts/geo/run_stack.sh` docker layout was dev-machine shaped, so the
sidecar is the deployment-shaped version of the same stack.

## Architecture

- One `osrm` container in the SAME Fargate task (awsvpc = shared net
  namespace → the API reaches it on `127.0.0.1:5000`, no service
  discovery, no NLB change, ~$0 infra beyond +1 GB task memory).
- Image `alive108-osrm:<tag>` = `osrm/osrm-backend` + the Delhi-NCR MLD
  graph baked into `/data` (built by `scripts/geo/buildspec-osrm.yml`
  in CodeBuild — this Mac has no docker).
- Graph: Geofabrik `asia/india/northern-zone` clipped to the NCR bbox
  `76.80,28.20,77.90,28.95` (same bbox as `deps.NCR_BBOX` /
  `scripts/geo/common.sh`), `car` profile, MLD pipeline
  (extract → partition → customize — same as `build_osrm.sh`).
- Car-graph-for-all-profiles is **parity** with the demo it replaces:
  the public server is driving-only too, so `/route/v1/cycling|walking`
  answered by our daemon returns the same car geometry the demo would.
- Fallback is unchanged and honest: dead/slow sidecar → public demo,
  flagged (`osrm-public-demo`, `demo_rate_limited`) — an osrm crash
  degrades, it never takes the API down (`essential: false`, hard
  `memory: 1024` cap; task bumped 2048 → 3072).

## Provenance

- `/admin/api/sources` → `routing.backend` (OSRM_LAST) reports the
  backend of the last real route call: `osrm-local` | `osrm-public-demo`,
  plus ms and age — observed from traffic, never a synthetic ping.
- `/v2/plan` rows carry `steps_source: 'osrm'` (the engine), not which
  backend answered — the backend signal is the admin endpoint above.
- `routing_local` also tags the route dict internally (`source`,
  `demo_rate_limited`) if a future lane wants to forward it.

## Verified live (2026-10-04)

- CodeBuild `alive108-osrm-build`: extract → MLD graph (489 MB,
  4.4 M edges) → `alive108-osrm:ncr-20261004` + `:latest` (269 MB
  compressed) → in-build smoke test Connaught Place → Gurugram
  31.1 km / 23 turn steps → pushed to ECR.
- Deployed as task-def rev 103 (`SKIP_BUILD=1 IMAGE_TAG=fa332d76
  OSRM_TAG=latest` — same API image, only the sidecar added); osrm
  container HEALTHY, NLB target healthy.
- `/v2/plan` Delhi OD ×3 → 24 options each; `/admin/api/sources`
  `routing.backend="osrm-local"`, ms ≈ 116–148 (was ~600 ms +
  rate-limit risk on the public demo).

## Build a new graph image

```bash
git archive --format=zip -o /tmp/geo-src.zip HEAD:scripts/geo
aws s3 cp /tmp/geo-src.zip s3://alive108-build-$ACCOUNT/geo-src.zip
aws codebuild start-build --project-name alive108-osrm-build
```

The buildspec apt-installs `osmium-tool`, runs `fetch_extract.sh` +
`OSRM_MODES=driving build_osrm.sh`, bakes `Dockerfile.osrm`, then
**smoke-tests the image**: `osrm-routed` serving a Connaught Place →
Gurugram OD on the build host — `docker push` only happens after a real
route with real turn steps comes back. The graph tarball archive to
`s3://alive108-build-<acct>/geo/` is best-effort — the codebuild role
has no `s3:PutObject` on that bucket, so the step warns and continues
(the ECR image is the real artifact).

Env overrides: `OSRM_TAG` (image tag, default `ncr-<date>`),
`OSRM_MODES` (add `walking cycling` to ship 3 daemons later — needs
memory headroom the task doesn't have yet), `OSRM_IMAGE` (base).

## Deploy / rollback

`scripts/deploy.sh` adds the sidecar by default (`OSRM_SIDECAR=1`)
and sets `OSRM_URL=http://127.0.0.1:5000` on the API container.
Deploy fails fast if the ECR image is absent.

- API-only deploy: `OSRM_SIDECAR=0 ./scripts/deploy.sh`
- Full revert: `OSRM_SIDECAR=0 ./scripts/deploy.sh rollback <sha>`
- NLB/service shape untouched — rollback = previous task-def revision.

## What it costs / what it is not

- +1 GB Fargate task memory (2048 → 3072) + ECR storage (~0.27 GB).
- Not traffic-aware (freeflow durations, same as before) and not real
  cycle/walk graphs (car parity, as the demo). Adding the two missing
  profiles is `OSRM_MODES="driving walking cycling"` + two more
  sidecars + a bigger task — post-hackathon.
