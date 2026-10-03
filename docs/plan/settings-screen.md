# Settings screen — contract + seams

`Mobile/src/screens/SettingsScreen.tsx` — the full settings surface (doc 02 §sidebar item 7, doc 07 §3, doc 10). Same modal-sheet contract as `SearchScreen`.

## Contract

```tsx
<SettingsScreen
  visible={settingsOpen}
  onClose={() => setSettingsOpen(false)}
  lang={lang}
  current={settings}                     // the persisted ShellSettings snapshot
  onChange={onSettingsChange}            // see below
  onArmBrief={flow.armDailyBrief}        // optional seam
/>
```

Fully controlled: the screen never writes the store itself — every edit is reported via `onChange` and the parent persists through `shell/settings.saveSettings` (the same `patchSettings` pattern App.tsx already uses).

`onChange` signature:

```ts
<K extends keyof ShellSettings>(key: K, value: ShellSettings[K]): void;
(key: "editVehicle"): void;             // action seam, no value
```

Suggested wiring: `onChange = (k, v?) => k === "editVehicle" ? openVehicleSheet() : patchSettings({ [k]: v })`.

## Rows → store keys

| Row | Control | Key |
|---|---|---|
| Language | English / हिंदी segmented | `lang` |
| Share anonymous trip data | master switch + plain explainer + "What we store" expander (doc 07 §3 rules, one line each) | `share` |
| My vehicle | current choice + "change" | `editVehicle` seam → S8 vehicle sheet (not in this lane) |
| Leave-later reminders | master switch for "leave at X → breathe ~N% less" pings | `remind` (**new** additive key, default `true`) |
| Morning air alert | daily cleanest-window ping | `brief` (existing; reuses `morningAlert` label) |
| Version | `Constants.expoConfig.version`, falls back to localized "dev build" | — |
| Data sources | static line: "air: model + stations when live" | — |
| How numbers are estimated | static explainer expander (doc 10 honest-bands copy) | — |

## Seams for other lanes

- **`editVehicle`** — the S8 vehicle question sheet (doc 02 §S8) isn't built on this branch; the row's "change" action just emits the key. The integration lane maps it to the vehicle sheet.
- **`remind`** — `CompareSheet`'s depart ping (`flow.remind`) should consult `settings.remind` before offering/arming the notification row. CompareSheet is another lane's file; until wired, the toggle persists but doesn't gate.
- **`brief` + `onArmBrief`** — arming needs OS perms + `scheduleDailyBrief` (notify.ts). The screen calls `onArmBrief()` on toggle-on and persists whatever it returns (`true`/`false`), mirroring the sidebar. Without the prop, the toggle persists the intent directly.
- **Voice toggle** — stays in the sidebar for now (`settings.voice`); the TTS engine lands with the nav lane. Add a row here by emitting `onChange("voice", v)` when wanted.
- **Delete my data** — stays in the sidebar (`settingsDeleteData` + `clearAllData()`); not duplicated on this screen.
- **expo-constants** — used for the version row; it's transitively installed via `expo` (SDK 57 lists it as a dependency). Not in package.json — if the dep ever goes direct, add via `npx expo install expo-constants`.
