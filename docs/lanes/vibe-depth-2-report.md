# Lane report: vibe-depth-2 — second-order polish vs design-refs

**Date:** 2026-10-06 · **Diffs: 4** · Gates: tsc clean, expo lint clean, store 18/18, nav 68/68 · Repro: iOS dev client on iPhone-17 sim (Android impossible on this box), state seeded via `Documents/` files, local `uvicorn` backend — live API untouched (GETs only happen via the app's normal reads).

## Audit — felt-quality gaps found (each with its one-line fix)

| # | Gap (where seen in apk-final shots) | Fix |
|---|---|---|
| 1 | **Lone-needle day arc reads like a rendering scratch.** Sparse days paint a single 2px dark tick in an empty 52px column strip (36, 38) — at one needle it doesn't read as data, it reads as a defect. | `arcBar.width` 2→3 — the needle becomes a mark. |
| 2 | **The compare card's verdict is its quietest ink.** `+3 vs lightest` renders at 11px under a 26px numeral, *smaller than the 13px ETA below it* (21, 27). design-refs §5 wants the gap felt; the sheet was whispering the answer. | `optGap.fontSize` micro(11)→label(13). |
| 3 | **Ledger week evidence wraps mid-phrase.** `weekLine` at label(13) splits "≈4.5µg" from "breathed" — the number divorces its noun (39). | `weekLine.fontSize` label(13)→micro(11); common case fits one line, `numberOfLines={2}` still guards long data. |
| 4 | **Two chrome-label trackings.** Search `sectionLabel` tracks 0.6 while the same uppercase-semi label grammar tracks 0.8 in Settings, Sidebar, Ledger, LayersSheet. | `sectionLabel.letterSpacing` 0.6→0.8. |

## Found and deliberately left (honest audit — no forced diffs)

- **Nav HUD eyebrows are Inter, not Plex Mono** (`cellLbl` — "SMOKE YOU BREATHE"). Register says mono eyebrows; the fix is a font-family change — **forbidden surface**.
- **Vehicle-sheet group labels are the app's only lowercase, untracked labels** ("your own" / "shared" / "no engine" — iOS repro shot shows them clean but register-weak). Real fix needs uppercase — that's copy, **forbidden**.
- **9px annotation step is off-scale** (`oaDay`, `arcHr`, `barLbl`, `sparkHr`, `heroWeekLbl`, `heroOfBudget`, `gaugePct`, `fcHr` all sit 2px below the type floor). But it's one *consistent* whisper-register used identically everywhere — the consistency is the register. Changing it re-tunes a deliberate hierarchy; left alone.
- **`brandSub` 1.4 vs `cardEyebrow` 1.8 tracking** — same mono-micro face, different air. Reads as deliberate rhythm contrast (long dateline vs short eyebrow); left.
- **Receipt "about" qualifier floats mid-line after "µg"** (31) — honesty-by-design qualifier inline with the hero; copy-adjacent, frozen.
- **Dangling "·" when compare label wraps to "your usual"** (27) — a wrap artifact; the fix is copy/structure, frozen.
- **Ledger zero-day stubs** (`barFill minHeight 3` render as dashes) — honest "no trips" read; a 1px nudge wouldn't change felt quality.
- **Sparse DayCard arc columns + orphaned hour labels** — coverage-only arc is the product's honesty; not a defect.
- **DelhiToday forecast bars / all number surfaces verified mono** — `fcVal`/`fcHr`/`cSub`/`barLbl` all route through `famMonoText`; no Inter leak found in number positions. (Initial audit flag cleared on inspection.)

## Before / after

| Change | Before (apk-final, Android @0b11123) | After (iOS dev client, this commit) |
|---|---|---|
| `arcBar.width` 2→3 | [36-home-checkin](https://app.devin.ai/attachments/17be83ca-6f75-48e2-8838-9e32ca68a137/36-home-checkin.png) · [38-checkin](https://app.devin.ai/attachments/bba9f53a-06ea-4ab5-9948-7a0e3203a419/38-checkin.png) — lone needle | [after-arc](https://app.devin.ai/attachments/8da8771f-5088-49a1-84e6-e6d6532d84b7/after-arc.png) — marks read as marks |
| `optGap` 11→13 | [27-picked](https://app.devin.ai/attachments/f9513d1f-1d9d-488f-b81d-07312ef9c11f/27-picked.png) · [21-compare](https://app.devin.ai/attachments/233642b9-7880-43b9-be49-b941bee9b0c6/21-compare.png) — gap whispered under the numeral | [after-compare](https://app.devin.ai/attachments/adcc5908-536b-42c5-a23a-78c947718a46/after-compare-crop.png) — "+1 vs lightest" carries its weight ([full frame](https://app.devin.ai/attachments/1641df1a-23ca-4f30-8c84-90c0e17559a6/after-compare.png)) |
| `weekLine` 13→11 | [39-ledger](https://app.devin.ai/attachments/cb224d4a-c4e5-4cd1-8306-566887000b8f/39-ledger.png) — "≈4.5µg" splits from "breathed" | [after-ledger](https://app.devin.ai/attachments/fa7d4f8d-58e6-4df1-aaa5-fa48aaf99df1/after-ledger-crop.png) — "10 trips · ≈ 51 µg · about 6.6 kg put out" one line ([full frame](https://app.devin.ai/attachments/22fd289b-26f7-4a17-a45d-89315ff0341c/after-ledger.png)) |
| `sectionLabel` 0.6→0.8 | [15-search](https://app.devin.ai/attachments/4a6f3f2f-a308-46d1-ae3f-4ee9e60e0ab2/15-search.png) — 0.6 tracking | [after-search](https://app.devin.ai/attachments/756c6cec-6b35-489d-95ca-8a056e227c94/after-search-crop.png) — same air as Settings/Sidebar/Ledger ([full frame](https://app.devin.ai/attachments/93b203f4-a72f-4347-a391-719ac72e158c/after-search.png)) |

## Diff surface (allowed constants only)

```
Mobile/src/screens/HomeScreen.tsx      arcBar.width: 2 → 3
Mobile/src/components/shell/CompareSheet.tsx  optGap.fontSize: micro → label
Mobile/src/screens/LedgerScreen.tsx    weekLine.fontSize: label → micro
Mobile/src/screens/SearchScreen.tsx    sectionLabel.letterSpacing: 0.6 → 0.8
```

No components, no surfaces, no copy, no tokens touched. Theme contract (`V2T`/`V2Type`/`V2Radius`/`fam` keys) untouched — only consumption-site values moved.

## Gates

- `npx tsc --noEmit` — clean (after `npm install` restored `@expo-google-fonts/{fraunces,ibm-plex-mono}` + `expo-device` into the box's stale `node_modules`)
- `npx expo lint` — clean
- `node src/store/test-runner.mjs` — 18 pass / 0 fail
- `node src/nav/test-runner.mjs` — 68 pass / 0 fail

## What a rebuild must re-verify

The 4 diffs are dead-safe constants, but the apk-final 14/14 set stays the bar. Priority re-checks on the next binary:

1. **Compare cards en + hi** — `optGap` is nested in `optDoseSub` (`numberOfLines={1}`): confirm "सबसे हल्के से +{n}" doesn't truncate at 13px on a narrow device.
2. **Ledger week line at heavy data** — a week with >9 trips and ≥100µg totals: confirm one line at 11px (and 2-line fallback intact).
3. **Sparse day card** — one-sample day still reads honest-empty; arc needles at 3px don't crowd dense days.
4. **Search sheet labels** — SAVED PLACES / RECENT / NEARBY rhythm against the settings labels.
5. All 14 apk-final rows unchanged in structure (no layout shift expected — diffs are size/tracking only).
