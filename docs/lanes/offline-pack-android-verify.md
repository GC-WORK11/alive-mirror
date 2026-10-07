# Lane report: offline-pack verify — Android emulator (real device run)

**Fix under test:** `54a296e` — `OfflineManager.createPack` gets `mapStyle = http://65.2.28.40/v2-light.json` instead of a `file://` dump. Pack `delhi-ncr-z9-13-r2` (dead `r1` row deleted on sight).
**Goal:** `region_tiles > 0` (expect ~744) in `mbgl-offline.db` on Android + no `Mbgl-HttpRequest: Unable to parse resourceUrl` in logcat.

## Verdict: PASS — pack downloads on real Android, exactly the expected numbers

| Check | Expected | Observed |
|---|---|---|
| `select count(*) from region_tiles` | ~744, > 0 | **744** |
| `select count(*) from regions` | 1 | **1** |
| `select count(*) from region_resources` | (iOS evidence: 297) | **297** |
| region `definition.style_url` | `http://65.2.28.40/v2-light.json` | **exact match** |
| region `description.metadata.name` | `delhi-ncr-z9-13-r2` | **exact match**, no `r1` row |
| logcat `Mbgl-HttpRequest: Unable to parse resourceUrl` | absent | **0 hits** (main + all buffers, whole run) |
| logcat `Mbgl-*` / `HttpRequest` errors | none | **0 hits** of any `Mbgl*`/`HttpRequest` tag |

Region row (verbatim):
```
1|{"style_url":"http://65.2.28.40/v2-light.json","min_zoom":9.0,"max_zoom":13.0,
  "pixel_ratio":2.625,"include_ideographs":false,"bounds":[28.2,76.8,28.95,77.9]}|
 {"migrationVersion":1,"id":"e1fef544-329f-4e19-9365-af39ca6788b9",
  "metadata":"{\"name\":\"delhi-ncr-z9-13-r2\"}"}
```

Tiles are real data, not phantom rows: `tiles` table has 745 rows (744 pack
tiles + 1 ambient `z8` from the live map view — ambient cache working as
before), z-range 8–13, `sum(length(data)) = 13,462,758` bytes of
`https://tiles.openfreemap.org/planet/20261004_113936_pt/{z}/{x}/{y}.pbf`
vector tiles. Region tiles per zoom: `z9=6, z10=16, z11=48, z12=154, z13=520`
(total 744). `resources` = 297 rows / 6,538,788 bytes: style (1), tilejson (1),
glyphs (291), sprites (2×2) — the same 744/297/1 shape the iOS sim produced
(`offline-pack-fix-report.md`).

**Timeline** (all UTC, logcat timestamps): process start 14:31:12.09 →
`MLRNOfflineModule: No packs need migration` 14:31:16.95 → tile `accessed`
epochs 14:31:14→14:31:19 — the whole pack landed in ~5 s on datacenter
bandwidth. The root `<Map>` mounts at App level (`App.tsx:178`
`onDidFinishRenderingMapFully → onMapFullyRendered → warmBasemap(STYLE_URL)`),
so the first full render fired behind the onboarding screens — no navigation
was needed for the pack; the notification + location dialogs and "Skip" were
dismissed afterward and the map screenshot-verified fully rendered (v2-light
streets/parks/water) at 14:33.

## Environment

| Item | Value |
|---|---|
| Host | Ubuntu 22.04 (Linux), 8 vCPU, 31 GiB RAM, **KVM present** (`/dev/kvm`, chmod 666) |
| Emulator | Android emulator 37.2.12.0 (build 16428233) |
| AVD | `demo` — `system-images;android-35;google_apis;x86_64`, `pixel_7` |
| Guest | Android 15, x86_64, kernel 6.6, `google/sdk_gphone64_x86_64/emu64xa:15/AE3A.240806.043/12960925:userdebug/dev-keys` |
| adb | 1.0.41 (platform-tools 37.0.1); `adb root` OK (userdebug image) |
| Repo | `github.com/<owner>/Delhi-Air-108` @ `base/v2` HEAD `e4dc87a` (rebased mid-run); `git merge-base --is-ancestor 54a296e HEAD` → yes |
| Toolchain | openjdk 17.0.19, node v20.19.0 (tarball), npm 10.8.2, sqlite3 3.37.2 |

## Build

`cd Mobile && npm ci` → clean.
`cd Mobile/android && EXPO_PUBLIC_API_URL=http://65.2.28.40 ./gradlew assembleRelease`
→ **failed in 17 s** exactly as the sibling lane predicted:
`org.gradle.toolchains.foojay-resolver-convention:1.0.0` unresolvable
(shared-egress 429 on repo.maven.apache.org).
Retry with the repo's init script (path corrected by parent lane —
`Mobile/scripts/` → repo-root `scripts/`):

```
EXPO_PUBLIC_API_URL=http://65.2.28.40 \
  ./gradlew -I ../../scripts/gradle-init-mirror.gradle assembleRelease
```

→ **BUILD SUCCESSFUL in 3 m 45 s** (395 tasks).
`app/build/outputs/apk/release/app-release.apk` = **137,140,424 B**,
sha256 **`e667c3746ef7bb5b11b2cbf873d858f6147d71395d6d4578f34e4e9b10bed0b0`**
(differs from the mac lane's `538b19…` — expected, different box/toolchain;
recorded as required).

## Boot + drive

```
avdmanager create avd -n demo -k 'system-images;android-35;google_apis;x86_64' -d pixel_7 --force
emulator -avd demo -no-window -gpu swiftshader_indirect -no-snapshot-load \
  -no-audio -no-metrics -no-boot-anim -memory 1536 &
adb wait-for-device            # sys.boot_completed=1 in ~30 s (KVM fast)
adb install app-release.apk    # Success
adb root                       # uid=0(root)
adb logcat -c && adb shell am start -n com.anonymous.app/.MainActivity
```

Dialogs dismissed via `input tap` (1080×2400 device px): notifications →
Allow, onboarding → Skip, location → While using the app, then **Air map**
from the home list — map rendered fully (screenshot-verified).

## Evidence — sqlite (via `adb shell 'su 0 sqlite3 /data/data/com.anonymous.app/files/mbgl-offline.db …'`)

```
region_tiles      : 744
regions           : 1
region_resources  : 297
tiles             : 745 rows, z 8–13, Σdata 13,462,758 B
resources         : 297 rows, Σdata 6,538,788 B
region z-dist     : z9=6 z10=16 z11=48 z12=154 z13=520
```

## Evidence — logcat (`adb logcat -d`, plus `-b all -d`; cleared pre-launch, whole run captured, 8 219 lines main)

```
grep -icE 'Unable to parse resourceUrl'   → 0
grep -icE 'Mbgl'                          → 0   (no Mbgl-* tag emitted at all —
                                               Android Mbgl-HttpRequest logs only
                                               on failure; success is silent)
grep -icE 'HttpRequest'                   → 0
only offline-related app line:
  10-07 14:31:16.949  4084  4084 D MLRNOfflineModule: No packs need migration
```

No `Unable to parse resourceUrl`, no `file://` style fetch attempts — the
`Mbgl-HttpRequest` failure mode from the r1 rev is gone.

## What this supersedes

The earlier section of this file (mac lane, commit `6d8f9cc`) was PARTIAL:
`VirtualMac2,1`, `kern.hv_support=0`, no HVF and no TCG fallback — the
emulator could never boot there. Its no-device findings (prod style live +
sha256 `295be2fd…`, 12/12 unit tests, fix strings in the bundle) remain true
and are confirmed end-to-end on-device here. APK sha256 above is this lane's.

## Bottom line

On a real KVM Android-15 emulator running the release build of `base/v2`
(with `54a296e` an ancestor), `OfflineManager.createPack` downloads the
Delhi-NCR z9–13 pack: **744 region tiles + 297 region resources in exactly
one region whose style_url is the http `v2-light.json` route, in ~5 s, with
zero `Mbgl-HttpRequest` errors.** The fix is verified on Android.
