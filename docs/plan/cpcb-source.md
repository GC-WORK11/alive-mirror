# CPCB live-station source — data.gov.in OGD API

Adapter: `server/ingest_cpcb.py` · Tests: `server/tests/test_ingest_cpcb.py`
Probed 2026-10-03 ~03:35–04:30 UTC from the build box. Supersedes the
"no CPCB endpoint reachable" note in `server/validate_field.py` §CPCB —
`airquality.cpcb.gov.in` now answers (it TCP-timed-out in that probe).

## 1. Reachability — what each endpoint returns unauthenticated

| Endpoint | Result from this box (evidence) |
|---|---|
| `GET https://api.data.gov.in/resource/3b01bcb8-…ba69?format=json&limit=2` | **TCP refused** — `curl (7) Failed to connect… port 443` (~0.11 s). Same on :80 and :8443. DNS → NAT64 `64:ff9b::a464:3dc6` (NIC 164.100.61.198). Blocked for this egress; the resource itself is live (portal lists it, "Updated On: 25/09/2026"). |
| `GET https://api.data.gov.in/lists?format=json` | TCP refused (same host). |
| `GET https://(www.)data.gov.in/` | **200** — OGD 2.0 Nuxt SPA (Akamai + NIC). |
| `GET https://data.gov.in/backend/dms/v1/rss.xml` | **200** `application/rss+xml`, no auth — latest catalogs feed; contains `Real time Air Quality Index` → `/catalog/real-time-air-quality-index`. |
| `GET https://www.data.gov.in/catalog/real-time-air-quality-index` | **200** (1.0 MB SSR page) — CPCB catalog: `nid 804641`, `uuid a3e7afc6-b799-4ede-b143-8e074b27e062`, publisher **Central Pollution Control Board**, `moderation_state: Published`, `updated_date 25/09/2026`. Resource list loads client-side via session API. |
| `GET https://data.gov.in/backend/dmspublic/v1/{catalogs,resources,search,resources_noaggs}` | **401** `{"error":{"type":"UNAUTHENTICATED"}}` — needs a real user bearer token (`authmid/v1` → mygov.in SSO). The portal's embedded `VUE_APP_APIKEY` does **not** satisfy it (tried Bearer/Basic/query). |
| `GET https://data.gov.in/backend/dataapi/v1/…` (portal's own proxy to api.data.gov.in) | **hangs → curl (28) timeout, 0 bytes** — dead upstream even for OGD's backend (same on `smartcities`/`tn` vhosts). |
| `GET https://data.gov.in/backend/dms/v1/search?q=…` | 302 → `/search/node` (legacy Drupal path). |
| `GET https://www.data.gov.in/resource/<uuid>` | 302 → `/not-found` — new portal routes resources by alias, not bare UUID. |
| `GET https://airquality.cpcb.gov.in/` | **301 → /ccr/ → 200** — official "Central Control Room \| Air Quality" Angular app. **Now reachable** (was geo-blocked TCP-timeout in the earlier probe). |
| `GET https://airquality.cpcb.gov.in/caaqms-common/api/reports/caaqm-stations/ncr/pdf` | **200** `application/pdf`, 945 B — returns an EMPTY report (title "CAAQM Stations in Delhi-NCR", no rows) — needs the app's POST params. |
| `POST https://airquality.cpcb.gov.in/insight_proxy_api_v2_0/service.php` | **403** `{"error":"Invalid index"}` — responds, but it's a private dashboard API: obfuscated encrypted bodies (service codes `DASH_003…015`, `REP_001…006`; `Client1` key, `iv`, SHA512/RC4 in JS). Not an open feed; we do not reverse it — official open path is the data.gov.in key. |
| `https://cpcb.gov.in/` | 200 — CMS pages only, no station JSON. |
| `https://app.cpcbccr.com/` | Third-party (per earlier probe: rebranded portal sourcing Open-Meteo, not CPCB instruments). Not a CPCB feed. |

**Verdict:** the open-data API (`api.data.gov.in`) is the right source but is
IP-blocked from this box; the OGD catalog/metadata surface confirms the
resource is alive and updated daily. The adapter ships ready: key + a
routable network (or the ECS ap-south-1 worker — India region) and it's live.

## 2. The resource

- **Name:** "Real time Air Quality Index from various locations"
- **Resource id:** `3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69`
- **Catalog:** `a3e7afc6-b799-4ede-b143-8e074b27e062` (nid 804641), org: MoEFCC → **CPCB**; `active: 1`; hourly-ish updates ("last_update" per station).
- **Endpoint:** `GET https://api.data.gov.in/resource/{rid}` params:
  `api-key` (required), `format=json|xml|csv`, `limit` (default 10, use 1000),
  `offset`, `filters[field_id]=value` (multi-value comma-separated),
  `sort[field_id]=asc|desc`, `fields=id1,id2` (subset).
- **Response:** `{index_name, title, org, field:[{id,name,type}], status:"ok",
  total, count, limit, offset, records:[…]}`.

### Field mapping (per record — one row per station×pollutant)

| API field | Type | → station-obs field | Notes |
|---|---|---|---|
| `station` | keyword | `name` (via registry normalisation) | "Income Tax Office, Delhi - CPCB" — no lat/lon! |
| `state` | keyword | — | filter: `Delhi`, `Haryana`, `Uttar_Pradesh`, `Rajasthan` (underscores) |
| `city` | keyword | — | e.g. Delhi, Gurugram, Noida, Faridabad |
| `pollutant_id` | keyword | →`pm25` when `PM2.5`; all values kept in `pollutants{}` | PM2.5, PM10, CO, OZONE, NO2, SO2, NH3 |
| `pollutant_avg` | double | `pm25` (µg/m³ for PM) | drop non-finite / >1500 |
| `pollutant_min`/`max` | double | `series` `[min, avg, max]` | all-equal ⇒ downstream flatline trips |
| `pollutant_unit` | keyword | — | often "NA"; PM rows are µg/m³ |
| `last_update` | date | `ts` (epoch) | `"DD-MM-YYYY HH:MM:SS"` **IST** |
| `id`, `country`, `resource_uuid`, `document_id` | — | ignored | bookkeeping |

Station→lat/lon: `data/delhi_climatology.json.gz` (125 NCR stations, same
registry `openaq_archive.py` uses). Names share the "…, City - AGENCY[-id]"
convention; `_norm_station` strips agency suffix + city tags. Unresolved
stations are skipped and counted (`report.skipped.unresolved_coords` +
`unresolved_names`) — never placed by guessing.

## 3. Key signup flow (free, owner blocker)

1. Register/login at **data.gov.in** — SSO via `auth.mygov.in` (Google or
   mygov account).
2. Open the resource page from catalog "Real time Air Quality Index" (or any
   API-format resource) → **"Generate API Key"** button. The portal calls
   `POST /backend/dataapi/v1/api-key/v2/create` (authenticated) and shows the
   key in the API-key modal; it also appears in account settings and can be
   regenerated (`api-key/v2/regenerate`).
3. Put it in the environment as **`CPCB_API_KEY`** — `ingest_cpcb.fetch()`
   reads it by default. A portal-demo key (`VUE_APP_APIKEY`) is embedded in
   the public SPA for previews — shared/rate-limited; not for production.

**Rate limits:** not directly observable from here (host refused). Published
OGD guidance is fair-use; `limit≤1000` per page with `offset` paging and a
`total` count — adapter pages per state (≤4 pages) and needs 1 page per
state today (~200–500 PM2.5 rows each). Re-check observed behaviour once the
key lands; retries and backoff are already in the fetch loop shape (one
failing page does not sink other states).

## 4. What stays open / honest caveats

- Records carry **no coordinates** — NCR stations not in the climatology
  registry are dropped loudly; extend the registry (owner) if coverage is thin.
- `series=[min,avg,max]` is a 24 h window summary, not a per-hour history —
  a frozen station still flatline-drops, but partial flatlines are
  undetectable from one snapshot (same limit as any single-shot source).
- `airquality.cpcb.gov.in/ccr` is live again but its JSON API is a private
  encrypted contract — do not wire it; if data.gov.in stays blocked, the
  fallback is the OpenAQ S3 archive path already in `openaq_archive.py`
  (lagged, no key) or an India-region egress for `api.data.gov.in`.
