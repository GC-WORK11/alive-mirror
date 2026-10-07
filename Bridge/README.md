# Bridge

The shared contract between `Mobile/` (the apps) and `server/` (the engine).

Everything that crosses the wire is defined here once — request/response
types, endpoint names, units — so the apps and the backend can never drift
apart silently.

- `contract.ts` — TypeScript types + endpoint paths for the current API
  surface (`/health`, `/search`, `/route`, `/reverse`, `/v2/plan`,
  `/v2/strip`, `/v2/trip`, `/v2/ledger`, `/v2/city`, `/v2/day`,
  `/v2/outlook`, …). Imported by the mobile app; mirrored by
  `server/main.py` + `server/v2/` (Python is the source of truth for
  behavior, this file is the source of truth for shape).
- Future layers land here too: exposure estimates, dose fields, model
  provenance metadata.

Rules:
- No business logic — types, constants, and pure helpers only.
- Both sides may only depend on this folder for the wire shape.
