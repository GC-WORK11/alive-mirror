# 14 — Ambient Mode + departure alerts

The ask was "always-on display shows our air data when the phone locks."
The honest version of that:

## What the OS allows

True Always-On Display pixels are drawn by the OS, not apps.
- **iOS**: AOD content on the lock screen is Live Activities (app-owned
  but lock-screen-rendered) — requires the `NSSupportsLiveActivities`
  entitlement; a dev-build path we can add later, not fakeable.
- **Android**: true AOD is OEM-only. The legal approximation is a
  foreground-service persistent notification.

So we ship the two honest approximations and say so — faking an AOD
claim is exactly what this product refuses to do.

## In-app Ambient Mode (shipped)

`src/components/AmbientMode.tsx` — a near-black `#06070a` screen from
the crescent button:

- HH:MM clock (1 s tick)
- the live PM2.5 at your destination, huge
- "breathes least at HH:30 · −N%" from the departure optimizer
- a 4-second breathing pulse dot
- tap anywhere to exit

That's what you glance at when the phone sits on a desk or handlebar.

## Leave-later alerts (shipped)

`src/notify.ts` — local (not push, no server account) notification via
expo-notifications. "remind me" on a depart hint schedules a
TIME_INTERVAL notification firing at the computed best departure:
*"same trip now — N% less PM2.5."* Android channel `departures`; iOS
requests permission on first use. This is the lock-screen surface the
OS does grant us — the optimizer's answer appearing where a real
always-on number can't.
