# Notifications — channels, copy, permission flow

Local notifications only (no push/FCM). All copy goes through `src/i18n/strings.ts`
(en + hi), consumer voice per doc 02 — "smoke", never PM2.5/AQI. Audit target:
`expo-notifications@~57` (SDK 57).

## What exists

| Notification | Armed from | Trigger | Channel |
|---|---|---|---|
| Departure ping — "leave now" | `CompareSheet` row "leave {time} → breathe ~{n}% less" → `useShellFlow.remind()` | one-shot `DATE` at `/depart` best window | `departures` |
| Morning brief — "cleanest window today" | sidebar "morning air alert" switch → `useShellFlow.armDailyBrief()` (fetches `/today`) | one-shot `DATE` at 06:45 next morning | `daily-brief` |

Both re-arm on each call with fixed identifiers (`alive-departure`,
`alive-daily-brief`) — `scheduleNotificationAsync` cancels the previous request
first, so arming twice never stacks pings. `cancelDeparture()` /
`cancelDailyBrief()` are exported for future "turn it off" wiring.

## Android channels

| id | Purpose | Importance | Sound/vibrate | Behaviour |
|---|---|---|---|---|
| `departures` | leave-time reminder the user asked for | `HIGH` (heads-up) | default + vibrate | banners over other apps |
| `daily-brief` | ambient morning info | `LOW` | silent, no vibrate | shade only |

Channel names are localized (`notify_chan_*`); Android keeps the name from
first creation per channel id, so a language switch only renames future
fresh installs (platform limitation).

No `nav-alerts` channel yet — no navigation alert notifications exist in the
codebase. When the nav lane adds one (e.g. "heavier air on this stretch"),
create a third channel; `MIN`/`LOW` if ambient, `DEFAULT` if actionable.

## Quiet hours

Fire times land inside quiet hours → pushed to the quiet end.

- Keys read from `settings.json`: `quietStart`, `quietEnd` (hours 0–23;
  `start === end` disables). Overnight windows like 22→7 handled.
- **Defaults 22:00 → 07:00** hold until the settings lane adds the keys —
  `loadSettings()` spreads unknown JSON keys, so they take effect with no
  notify-side change.
- Daily brief: 06:45 → slides to quiet end (07:00 with defaults).
- Departure: slides to quiet end **max 2h** — beyond that the air window is
  gone and a "leave now" ping would be a lie, so it returns `null` (caller
  sees "not armed" and the bell icon stays hollow).
- `settings.ts` itself untouched (owned by the shell lane) — additive keys
  `quietStart`/`quietEnd` + `DEFAULT_SETTINGS` entries are the integrator step.

## Copy table

| Key | en | hi | Vars |
|---|---|---|---|
| `notify_departure_title` | leave now — lighter air | निकलने का समय — हवा हल्की है | — |
| `notify_departure_body` | same trip, ~{p}% less smoke than the smoky hours | यही यात्रा — धुआँदार घंटों से ~{p}% कम धुआँ | `{p}` saved % |
| `notify_brief_title` | delhi's cleanest window today | आज दिल्ली की सबसे साफ़ घड़ी | — |
| `notify_brief_body` | {win} — air runs {p}% lighter. plan the smoky trips around it. | {win} — हवा {p}% हल्की रहेगी। धुआँदार काम इसी समय रखें। | `{win}` "5am–8am", `{p}` drop % |
| `notify_chan_departure` | leave-time reminders | निकलने की याद-दहानी | — |
| `notify_chan_brief` | morning air brief | सुबह की हवा-जानकारी | — |

Killed in the rewrite: title "ALive-108" (brand, not information) and
"PM2.5" (jargon, doc 02 §3). Claims stay honest per doc 10 — "less smoke" is
the same relative claim the compare sheet makes, no new numbers.

## Permission flow

```
user taps "we'll ping you" / "morning air alert" switch
        │
        ▼
requestPerms()
        │ ensureChannels(lang)          ← Android 13+: the OS prompt will not
        ▼                                  appear until ≥1 channel exists
getPermissionsAsync()
        │
 granted / iOS PROVISIONAL·EPHEMERAL ──► true (schedule)
        │
 canAskAgain === false ──────────────► false (user said no; OS won't re-ask —
        │                                  caller leaves toggle off, no nags)
        ▼
requestPermissionsAsync() ──► granted() ──► true / false
```

- Every schedule call returns `Promise<string|null>` — any failure (denied
  perms, past fire time, native throw) is an honest `null`; callers already
  treat `!= null` as armed.
- Foreground behaviour: banner + list, no sound, no badge
  (`setNotificationHandler` in `src/notify.ts`).

## Platform behaviour / reboot

- **Reschedule after reboot is built in.** `expo-notifications` adds
  `RECEIVE_BOOT_COMPLETED` via its own manifest and its receiver re-arms
  scheduled notifications on boot. No config plugin, no `android/` edits.
- One-shot `DATE` triggers (not `TIME_INTERVAL`) — wall-clock intent, immune
  to drift from reboot/deep-sleep delays.
- iOS: no channel concept; channelId is ignored. Sound on the departure
  content is the pre-Android-8 fallback too.

## Gaps for the integrator

1. **`SCHEDULE_EXACT_ALARM` (Android 12+)** — not added by the library. Without
   it, `DATE` triggers may fire inexactly on API 31+. Add
   `"android.permission.SCHEDULE_EXACT_ALARM"` to `app.json →
   android.permissions` (app.json is owned by another lane — do not hand-edit
   `android/`). Consider whether we want the Play-review attention that comes
   with an exact-alarm permission; brief+reminder can arguably live with
   inexact, so this is a product call.
2. **Toggle-off doesn't cancel** — flipping "morning air alert" off sets
   `settings.brief = false` but the already-scheduled notification still
   fires once. Fix: call `cancelDailyBrief()` from the switch's off branch in
   `Sidebar.tsx` / `useShellFlow` (those files belong to the shell lane).
3. **Brief re-arm cadence** — fires once next morning by design (copy depends
   on that day's `/today` curve). It only re-arms when the toggle is flipped
   on again. A daily `DAILY` repeating trigger or an app-open re-arm hook in
   `App.tsx` is a product decision; the current flow is "toggle on = one
   brief".
4. **`quietStart`/`quietEnd` settings keys + UI** — notify.ts honours them
   today via the JSON spread; the settings lane owns the type additions and
   any settings-screen rows.
5. **Android notification icon** — plugin has no `icon`/`color` set; tray uses
   the default app icon. A 96×96 all-white PNG + accent color would need
   `app.json` plugin config (other lane).
