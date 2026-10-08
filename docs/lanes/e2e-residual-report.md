# e2e-residual — sweep leftovers, fixed + verified on iOS sim

Lane: e2e-residual · branch `base/v2` @ `6e805c6` (+ this push)
Rig: iPhone 17 sim `EDD9B083` (iOS 26.5), device TZ **PDT** — so IST
rendering is proved against a 12:30 offset, not on an IST box.
Shots: `docs/lanes/e2e-residual-shots/`
Gates: `store/nav/api/offline` runners **100/100 pass**, `tsc --noEmit` **0**,
`expo lint` **0**.

## 1 · P2-3 — post-wipe location-page freeze (sweep #3)

**Root cause.** Every onboarding exit ran a bare `finish()` — the flag
commit rides the cold-boot draw-hold (`useHeldState`, bounded but not
instant), so after the first press the buttons stayed live and silent
while the unmount commit was still queued. On a cold post-wipe boot that
window is exactly when the JS thread is busiest; repeated presses queued
more identical exits with zero visible change. That is the "3+ eaten
presses" the film showed — no OS-dialog swallow, no dead hit-slop: the
buttons were pressed and did nothing *observable*.

**Fix** (`src/screens/OnboardingScreen.tsx`): a `leaving` latch on every
exit path — skip, "turn on location", "not now". First press: haptic →
`disabled` + `accessibilityState {busy, disabled}` → primary label swaps
to `onb_leaving` ("a moment…" / "एक क्षण…", both locales). Second press is
an honest no-op, not an eaten one. Exits still land `finish()` exactly
once; consent write unchanged.

**Evidence.** Post-wipe flow driven live: `01-p23-location-page.png`
(page 5 reached) → **one** press on "turn on location" →
`02-p23-first-press-dialog.png`: sheet unmounted, home rendered, real iOS
"Allow 'Alive' to use your location?" dialog up. First press works.

## 2 · Offline "can't reach the server" pill transient (v5 film)

**Root causes (two, independent).**
(a) *Stall*: `useNetStatus` is born `"online"` and needed 3 probe
failures to flip — but the 20 s interval only re-probed while
`state !== "online"`, and `fetchJson` calls emit no net events. A boot
onto dead net sat at failStreak 1 forever → pill never armed.
(b) *Z-order*: the pill mounted **before** the absolute-fill HomeScreen
and carried `elevation: 4` vs the backdrop's 24 — it painted under the
resting surface. It was rendering; nothing was visible.

**Fixes.** `src/offline/status.ts`: probe once on mount, plus a 4 s
`kick` re-probe chain off any net event while `failStreak > 0`, plus the
interval now also fires while `state === "online" && failStreak > 0`.
`App.tsx`: pill JSX moved after `<HomeScreen>` and `offlineWrap`
elevation → 26 (above the backdrop's 24, still below the sheets' 30).

**Evidence.** Metro restarted with `EXPO_PUBLIC_API_URL` pointed at a
dead port (probes fail fast — same code path as airplane mode):
`06-offline-pill.png` — pill rendered over home within seconds:
"ऑफ़लाइन — पिछली ज्ञात हवा दिख रही है · 3 मिनट पहले अपडेट हुआ"
(the app was still in Hindi locale — also proves the pill itself is
localized).

## 3 · P3-6 — clock/greeting device-TZ lie (sweep #6)

**Fix.** `src/i18n/strings.ts`: `clockLabel`/`hourLabel` now interpret
every `Date|number` instant through the repo's +330-min convention
(`istParts`) — one change fixes header clock, ledger stamps, compare
slots, ETA/arrival labels in one shot; `hourOfDay` added for bare Delhi
hour indices (HourArc cells, move-card windows). `HomeScreen` header
(greeting hour + weekday sub-line) and `HourArc`'s lit hour now compute
the IST wall clock; `CompareSheet` tomorrow-tests compare IST dates.
Server `start` fields are naive-UTC instants (`server/forecast.py`
parses with `tzinfo=timezone.utc`), so instant→IST is correct for all
callers. `dayKey` bucketing untouched — storage convention, not display.
`daylog.test.ts` expectation now derives the IST label from the same
instant (was a device-TZ literal).

**Evidence.** `03-p36-ist-header.png`: device at **1:41 PM PDT** reads
"Up late / Delhi · Friday · **2:11 am**" — 13:41 PDT = 20:41 UTC =
02:11 IST next day. Greeting, clock, and weekday all IST; Hindi variant
"2:13 पूर्वाह्न" in `05-p39-hindi-home.png`.

## 4 · P3-8 — receipt expander a11y-only (sweep #8)

**Root cause.** `toggleRow` ran `LayoutAnimation.configureNext` — which
is global-next-commit: the TripDetail mount riding the same commit as
the expand flag got `easeInEaseOut` applied to a subtree being born
inside a FlatList row. On Fabric that class mounts the detail collapsed —
a11y `expanded` flipped while nothing visibly changed. (Same documented
hazard as `useShellFlow.ts`'s mixed-graph detach guard.)

**Fix** (`src/screens/LedgerScreen.tsx`): `LayoutAnimation` removed from
the toggle; the detail mounts unconditionally like every other
conditional section in the app. Mechanics (tripKey, `extraData`,
TripDetail rows) were already correct.

**Evidence.** A trip seeded into `ledger.json` from the **live**
`/v2/plan` response (CP→Saket auto: dose 27.9, avoided 5.8 = 33.7−27.9,
co2 0.6401 — zero invented numbers; timestamps only).
`04-p38-receipt-expanded.png`: one tap renders the full detail —
"आपने साँस में लिया ≈28 µg / आपकी गाड़ी ने छोड़ा धुआँ ≈0.6 किलो /
सबसे धुआँदार रास्ते से ≈5.8 µg कम / यह यात्रा मिटाएँ". Second tap
collapses cleanly.

## 5 · P3-9 — English a11y age labels under Hindi (sweep #9)

**Fix.** The only non-`t()` a11y leak found by sweeping every
`accessibilityLabel` was `HourArc`'s `` `hour ${h.hour}` `` — now reads
through the localized `dayArcDose/Air/Flat` grammar with `hourOfDay`
("…8 बजे"), matching the scrub readout. Age strings (`hour ago` family)
were already `t()` keys — verified live, they were being rendered
correctly once the surrounding labels stopped leaking English.

**Evidence.** `05-p39-hindi-home.png` (header "देर रात · 2:13 पूर्वाह्न",
"15 मिनट गिने"), sidebar trip row "ऑटो-रिक्शा · 2 घंटे पहले" (age string
localized), `04-p38-receipt-expanded.png` fully Hindi ledger+detail.

## Skipped per lane brief
P2-5 keychain toast (sim-only, needs provisioned device), P3-7
session-scoped toggles (by design), P3-10 seen-at-mount (by design).
