# Lane report — fix: remaining server hardening items from server-audit (fd951e8)

Scope: the audit's three remaining server items only. Deploy lag is another
board's lane; `/v2/trip` admission bounds already landed (9f4533b–4110937) and
were not touched. `deploy.sh`, `trip.py`, field math, and response contracts are
unchanged except the additive `token_via` marker below (declared in
`Bridge/contract.ts`, so `test_contract_sync` stays green).

## Finding → fix → evidence

| finding (audit severity) | fix | regression tests |
|---|---|---|
| **med/NIT** — rate limiter keyed buckets on client-supplied `X-Forwarded-For[0]` (`middleware.py:80-82`). Rotating the leftmost hop minted a fresh bucket per request → per-IP budgets defeated. | `_client_key` now derives the IP via new `_client_ip()`: the **rightmost non-empty XFF hop** — the entry an appending balancer (the NLB) wrote — with fallback to the ASGI socket peer when XFF is absent or carries no usable hop. Bucket map, token-priority, hashing, and budget semantics unchanged. | `test_security.py::test_rate_limit_keys_on_rightmost_xff_hop` (three different spoofed leftmost hops + same rightmost share one bucket → 429 on the 3rd), `test_rate_limit_separate_buckets_per_rightmost_ip` (different rightmost IPs get independent buckets; a fresh leftmost hop can't revive an exhausted key), `test_rate_limit_falls_back_to_socket_peer` (no XFF → consistent peer bucket). |
| **low/JUDGE-RISK** — `/v2/ledger` `?token=` back-compat leaks the device read-key into browser history + Referer. | `?token=` still works (shipped-client compat), but any response served on it now carries an additive `token_via: "query"` marker — the deprecation is honest on the wire, not silent. Header path is untouched (no marker emitted). Applies to both GET and DELETE `/v2/ledger`. Declared as `token_via?: "query"` on `V2LedgerResponse` in `Bridge/contract.ts`. | `test_privacy_transport.py`: `test_ledger_query_token_response_admits_the_transport`, `test_ledger_header_response_unmarked`, `test_ledger_delete_query_token_marked`, `test_ledger_delete_header_unmarked`; existing back-compat + header-wins tests unchanged and still green. |
| **low/NIT** — `assert` tripwires in request paths die as `AssertionError` and vanish under `python -O` (`admin_agg.py:514,736`; `observability.py:458`). | k≥3 corridor/global tripwires now `raise HTTPException(500, "k>=3 invariant violated upstream — refusing to publish")` — the codebase's request-path error idiom, a structured `{"detail": ...}` 500. The `observability._emit` denylist tripwire now `raise RuntimeError(...)` — same fail-loud semantics, real exception, `-O`-proof. Startup/init asserts untouched (none existed in request paths beyond these three). | `test_admin_agg.py::test_corridors_k_floor_tripwire` (monkeypatched k<3 store → `HTTPException` 500 both via direct call and through the client), `test_global_k_floor_tripwire` (new — /global had no tripwire test), `test_observability.py::test_denylist_tripwire_is_a_real_exception` (denylisted record field → RuntimeError). |

## Mobile token transport — what the shipped app actually sends

Checked `Mobile/` end to end: the app **never calls `GET /v2/ledger`** — the
ledger surface reads the local store (`src/store/ledger.ts`). The only
`/v2/ledger` call in the client is `DELETE` for "delete my data", in
`Mobile/App.tsx:573`, and it already sends `X-Device-Token` (the in-code comment
says "header, not ?token= — a query-string token lands in access logs and any
future Referer"). Donations POST `device_token` inside the `/v2/trip` JSON body.

**So: the shipped app is already on the preferred header path. `?token=` is a
pure back-compat surface for older/external clients — the `token_via:"query"`
marker now makes its use visible on the wire.**

## Test output

```
$ cd server && PYTHONPATH=core/build312:. .venv312/bin/python -m pytest -q \
    tests/test_security.py tests/test_privacy_transport.py \
    tests/test_admin_agg.py tests/test_observability.py
58 passed in 2.42s

$ cd server && PYTHONPATH=core/build312:. .venv312/bin/python -m pytest -q tests
1194 passed, 5 skipped in 563.42s
```

Lane: fix-server-harden · repo `base/v2` · fixes to `middleware.py`,
`v2/ledger.py`, `admin_agg.py`, `observability.py` + `Bridge/contract.ts`
