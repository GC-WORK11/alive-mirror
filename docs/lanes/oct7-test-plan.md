# Oct 7 — all-agents testing day plan

Owner's order: "7 October should be available, one entire day of testing
with all five agents... if the numbers are right and wrong and change
in real time and how does the profile of a user and all that stuff."

Five lanes, five surfaces, all verifying LIVE BEHAVIOUR (not code):

## Lane A — field truth (server + prod)
- Sample /aqi at 12 Delhi cells every 15 min for 3 hours; cross-check
  against DPCC real-time station pages (the holdout set, not our
  ingest). Track the diff distribution — are we within instrument
  disagreement distance?
- Watch one field rebuild epoch boundary (15 min): ambient must MOVE
  if reality moves; record before/after means + `field_age_s` reset.
- Fires: compare /v2/why's "stubble smoke" driver claims against
  wind direction each epoch — claimed iff wind actually advects belt→Delhi.
- Output: docs/lanes/testday-field-report.md with numbers table.

## Lane B — app journey, iOS (sim on prod)
- Fresh install → welcome film → onboarding → home with real numbers.
- Real-time updates: leave home open across one field epoch — outside
  number must refresh without restart.
- Profile behaviour: switch profile (commuter/elder/child/etc.) —
  budget µg must change; delete-data must re-arm welcome + wipe ledger.
- **Delete-my-data completeness (new):** after the wipe, inspect the
  sim Documents dir — NO daylog/ledger/daysum/places/vehicle/settings/
  outbox bytes, NO .tmp/.bak residue, and the next recordSample must
  NOT resurrect old samples (the mem-mirror bug's regression check).
- **Air alerts (new):** Settings → Air alerts — master + all kind
  toggles (fires / band / windows / reflect) persist instantly;
  cause-attributed copy reads like the verified banners ("4 → 20
  fires northwest", "heavier than Saturday") — never a bare number.
- **Week strip / symptom lens (new):** must render identical days to
  the old recompute path (it now reads sealed daysum rollups) — any
  drift in a day's µg vs its trip detail = a P0.
- **BandScale (new):** the CPCB band strip under the hero + Delhi
  today renders the current band solid at the live aqi's position.
- Trips: plan a real trip (India Gate → CP), check dose vs live field,
  receive arrival receipt, verify ledger day-grouping.
- Language: flip hi — every surface including hours/strings.
- Output: docs/lanes/testday-ios-report.md + shots.

## Lane C — app journey, Android (KVM child on shipped APK)
- Same checklist as B on alive108-<final>.apk — cold open, welcome,
  home numbers vs prod, search 10 opens, consent-off pcap re-check,
  armed-skip, footer→header CTA single-tap.
- **New surfaces on the APK too** (same as Lane B's added block):
  delete-my-data file-level completeness, Air alerts toggles + kinds,
  week-strip daysum reads, BandScale.
- **"Where to?" touch taps** — the iOS-sim touch-path crash is
  sim-only, but on the APK confirm the search sheet opens on normal
  taps repeatedly (the release target must not share the class).
- Output: docs/lanes/testday-android-report.md + shots + pcap verdict.

## Lane D — web surfaces (live URLs)
- Landing (boot strip once-per-session), /city editorial (numbers vs
  /v2/city), /community, /admin (sign-in chip → token → panels read
  plain-English), all at 390px + desktop widths, light theme.
- Cross-check every number on the pages against its backing endpoint.
- Output: docs/lanes/testday-web-report.md + shots.

## Lane E — edge/honesty hunt (mixed)
- Model-only cells (far NCR edges): does the UI say "estimate" not
  fake-precision? nearest_sample_km = inf handling everywhere it lands.
- Killed-network: does stale data disclose its age everywhere?
- Search: typed, recent, dropped-pin, offline-T0 (airplane mode).
- Consent-off: zero writes pcap re-verify on BOTH platforms.
- Output: docs/lanes/testday-edge-report.md.

## Shared rules
- NEVER POST to prod (GETs + /v2/plan + /v2/reroute only).
- Every claim = a screenshot or a curl number. "Works" without
  evidence = not done.
- Fires/parali season is our demo story — anything that reads wrong
  under high-PM is P0, report to lead immediately.
