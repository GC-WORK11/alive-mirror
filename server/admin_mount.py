"""The ops console's mount point — the one file that names it.

Security by obscurity layered ON TOP of the real auth (nothing here
replaces _admin_guard / the HMAC cookie / the login rate bucket): the
engine-room page, its API and its session endpoints all hang under one
high-entropy path so internet path scans for /admin, /console,
/wp-admin etc. get an honest 404 — zero existence signal, not a
redirect that admits something lives there.

The path is committed on purpose: the operator reads it from here and
docs/plan/admin-login.md. It is a location secret, not a credential —
the token still lives only in AWS Secrets Manager.

Rotate by editing this constant and redeploying (keep the same shape,
/a-<32 urlsafe chars>; regenerate with `secrets.token_urlsafe(24)`).
Every consumer imports it — never hardcode the literal elsewhere.
"""

# generated 2026-10-08 via secrets.token_urlsafe(24) — 192 bits
ADMIN_MOUNT = "/a-AFiVSpmZ1Oc4YhaaQyhRie5yqnlKV_qs"
