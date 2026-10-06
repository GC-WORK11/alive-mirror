# lane: welcome-loading — the first-breath moment

Owner directive (verbatim, abridged): "a video of the AI component… I would use in a
welcome screen of our Android app, something very cool welcome… In admin app also,
in landing page, of course, it's a CI/CD component where the hell you going to use.
But don't make cringe things." Plus: his old project ent-01.vercel.app has a loading
screen he loves — "a very complex message but aesthetic way… 10 seconds loading…
the level I'm at."

## The two references (decoded by lead — do not re-derive)

**ent-01.vercel.app boot**: a black overlay `#boot` flips ~6 REAL product film
frames (`./film/frames/g1..g7.png`) every 720ms — a projector strip of actual UI
stills — for min ~4.3s / max 9.5s, then `boot--done` fades it into the hero.
Complex product, communicated by its own footage, zero words needed.

**ASCII Magic video** (owner attachment, w8-etqnWwUq6QD-1.mp4): brutalist-editorial
mono canvas, near-black field of faint ASCII chars, hairline frame marks, WHITE
mono type, color reserved ONLY for the artwork, snappy hard cuts, blinking block
cursor. Discipline: nothing decorative, type does the work.

## What to build — our own version, not a copy

### 1. App welcome (Mobile) — `Mobile/src/screens/WelcomeScreen.tsx` (NEW)
A one-time first-launch cinematic (AsyncStorage flag `welcome_seen_v1`, lives in
the existing store pattern — check how onboarding gates). The register:

- Dark canvas is ALLOWED here even though the app is light-theme — this is the
  one cinematic moment (projector-room grammar), IF it reads as intentional.
  Alternative that may be even more "us": the light paper canvas with the
  ASCII-air field in ink. Try the dark one first; judge against the anti-slop
  bar (docs/20-design-soul.md if present, else the register: no neon, no glow,
  no 3D, no stock icons).
- Content = the product's own data rendered as ASCII/type: e.g. a field of
  faint mono digits/characters that resolve into "28.7" — the city's real live
  PM2.5 (fetch /v2/city or the baked last-known; if offline show nothing fake —
  honest-degrade to a static frame), then a second beat: the same number turning
  band-colored with one word ("heavy"). Then out → onboarding/home.
- Mono typeface for the welcome = the app's existing mono (`mono(lang)`); big
  numeral = Satoshi-Light. No new font deps.
- Max ~4.5s or skippable on tap (never trap a returning user; show once only).
- reduce-motion → static frame, no flip.
- MUST degrade: if no field data yet, run the type-only version — never fake
  a number.

### 2. Web boot strip — `server/landing.html` (+ reuse on `admin.html` if clean)
Same idea adapted to one HTML file each, no build step (they're static files
served by FastAPI): a lightweight intro overlay — NOT a blocking loader that
annoys; max ~2.5s, once per session (sessionStorage), skipped instantly on
click/scroll/second visit. Content: our own mini film-strip — 3–4 frames built
from real UI stills or typographic beats ("what Delhi breathed" → live number
→ "what you breathed"). Zero images needed if type alone carries it — prefer
type+number beats over PNGs (no heavyweight assets, instant).

### 3. Loading discipline
- If you add a real loading state anywhere (e.g. admin data fetch), the same
  strip language applies — mono beats, not spinners-as-decoration.

## Hard rules
- NO cringe copy. No "loading magic". Text beats must be product-true.
- No external assets/CDNs. No new npm deps. `tsc --noEmit` + `expo lint` clean.
- Screenshots/screenrecord proof attached in your report (sim UDID
  D0B64A8A-D5F1-4668-8FFC-A86B400AF527 runs the dev client via the running Metro
  on :8081 — `curl localhost:8081/reload` after edits; see
  docs/lanes/register-card.md for the design system).
- Commit to base/v2 in small commits. Report → docs/lanes/welcome-loading-report.md.
- File ownership: WelcomeScreen.tsx (new), App.tsx or the app-entry wiring for
  the once-gate, landing.html, admin.html. The lead owns
  HomeScreen/DelhiToday/Ledger/Settings/Onboarding/strings/theme — do NOT touch.
