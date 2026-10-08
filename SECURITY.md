# Security & Privacy — Alive

Alive is a Delhi air-quality routing API. Its central privacy claim is
structural, not a promise: **the server holds city-wide aggregates and
anonymous road-cell counts — nothing that identifies a person or a home.**

## Threat model

What we defend against, in order:

1. **A curious or hostile client.** Every POST body is assumed adversarial.
   The server re-runs the privacy pipeline itself (endpoint trim, thinning,
   rounding, cell conversion) — see `server/v2/trip.py`. Clients cannot put
   raw GPS at rest no matter what they send.
2. **Bulk abuse / scraping.** Per-client rate limiting (token bucket) with
   tighter budgets on endpoints that fan out to paid upstreams
   (`/v2/plan`, `/v2/reroute`) or accept uploads (`/v2/trip`,
   `/report`). 429s carry honest `Retry-After` headers.
3. **Memory-exhaustion uploads.** Request bodies are capped (default 2 MiB —
   trip traces are the largest legitimate upload). Oversized bodies are
   refused on `Content-Length` before a byte is read; chunked bodies are
   cut off at the same cap.
4. **Re-identification through the store.** There is no user table. The
   aggregate store (`server/v2/store.py`) is the only thing trips write
   to, and it accepts only already-privacized data.

## Identity & tokens

- No accounts, names, phone numbers, or emails — none are collected.
- Devices send a random anonymous token (`"anon-"` + 16 hex chars —
  64-bit CSPRNG via `expo-crypto`, `Mobile/src/community.ts:8-11`),
  rotated every 30 days and regenerated if app data is
  deleted. It is never linked to anything.
- On the `/v2/trip` path tokens are **SHA-256 truncated-hashed before
  they touch any store or bucket map** — including the rate limiter, so
  raw tokens never sit in server memory structures either. The retired
  `/observe` endpoint (raw-coords, pre-pipeline) now answers
  **410 Gone** — nothing new can be written through it

## What is stored

- **Per-day aggregate counters**: trips, km, dose µg, emission g,
  switched-counts by mode (`alive108-agg` DynamoDB shape).
- **Per-H3-cell (res-8) aggregates**: traversal counts, dose sums, and a
  set of *hashed* tokens used only for the k≥3 publish threshold.
- Field snapshots, daily indices, validation reports on S3 — public data.

## What is never stored

- **Raw GPS at rest.** Trajectories are converted to H3 cell keys in
  memory (endpoints trimmed 300 m, thinned ~100 m, rounded to 4 decimals)
  and the raw payload is discarded in the same request.
- Raw device tokens, IP-to-token mappings, per-trip records.

A corridor or cell is only displayed when **≥3 distinct device tokens**
crossed it within 72 h (the k-threshold rule, `docs/plan/07`).

## Server hardening

`server/middleware.py` (mounted with two lines in `main.py`):
per-token/IP token-bucket rate limiting, request-body size cap, and a
measured security-header set (`nosniff`, `DENY`, `no-referrer`, HSTS on
TLS only). Header-read timeouts are enforced at the edge (NLB idle
timeout + uvicorn `--timeout-keep-alive`), not in middleware — an ASGI
layer only runs after headers are parsed.

## Reporting a vulnerability

Please report security issues privately — do not open a public issue.

- **Contact:** `security@alive108.example` *(placeholder — replace with the
  team's real security contact before launch)*
- Or open a private **GitHub Security Advisory** on this repository.

Please include: affected endpoint/component, reproduction steps, and
whether data was accessed. We aim to acknowledge within **72 hours** and
to keep you updated on remediation. We will not pursue action against
good-faith researchers who stay within this scope and avoid accessing
other users' data.
