# Alive — X posts (3 drafts, his voice)

*Rules applied: plain words only; banned — "dosimeter", "body count",
and by the house copy law: no AQI/PM2.5/µg in lead lines (µg allowed
once, paired, when a number earns it). Every drifting number is "about"
— re-check `curl -s http://65.2.28.40/health` + one plan call at post
time, never transcribe stale numbers. All lowercase is deliberate —
fix it if he doesn't post like that.*

Verified numbers to lean on (checked 2026-10-08):

- same trip, same minute: ~9 µg in an AC car vs ~310 µg on foot — about
  a 35× spread on the demo OD (live number; say "about thirty times")
- the field runs off ~46 live government/WAQI stations + satellite air
  model, re-solving every ~15 min
- 1.07M Delhi-NCR road edges, ~903k priced by the smoke on them
- receipts land in a ledger on the phone — today arc, week strip
- sharing off = zero trip data leaves the phone (pcap-verified); what
  publishes is group counts only, never one person, minimum 3 devices
- works offline: bundled place list + Delhi map pack
- Delhi/NCR only; Android only; sideload; debug-signed; the wire to the
  server is plain HTTP tonight (he says this out loud — it's the honesty
  brand)

---

## Post 1 — day-1: the landing reveal

> delhi's air takes years off a life, one commute at a time.
>
> so i built a thing that shows it. type where you're going and every
> way there gets priced in what your lungs pay — same trip, same
> minute, your feet can cost you about thirty times a closed car.
>
> the site is live. no signup, no install for this part.

**Attach:** `docs/lanes/landing-final-pack/phone/scroll.mp4` (18.6 s —
the film-gate scroll reads best on mobile). Still fallback:
`docs/lanes/landing-v11-shots/landing-1440-hero.png`.
**Link in first reply:** the Vercel URL once deployed — or
`http://65.2.28.40/` if the HTTPS live-widgets gap reads too empty
(launch-kit §3 17:45).
**Why it works:** the whole product in the first two lines; the 30×
line is the clip the numbers on the page can defend live.

---

## Post 2 — launch: the APK is out

> alive is out. android apk, delhi-ncr only, sideload — the play
> protect warning is normal, it's a demo build.
>
> install to first number, one take:
> it asks once about sharing your trips (off is complete), then it
> just tells you the air where you are and starts counting your day.
>
> your phone measures nothing — it crosses your timeline with a live
> field rebuilt from ~46 delhi monitors every 15 min. sharing stays
> anonymous and group-only, or off entirely.
>
> link below.

**Attach:** `alive-install-to-first-number.mp4` (78 s, 1.9 MB — cut
this session from the verified v4 take: launcher → onboarding → consent
→ relaunch → live "moderate · 0 min old" home. On the lane session as
an attachment; or re-cut: `ffmpeg -i alive-v4-take.mp4` of
0:00–0:38 + 2:15–2:55.)
**First reply:** direct asset URL
`github.com/<owner>/<NEW>/releases/download/v1.0.0-demo/alive-06919ca.apk`
+ sha256 line for the careful ones.
**Why it works:** the permission dialogs and the Play Protect caveat
are IN the clip — the honesty is visible, not claimed.

---

## Post 3 — demo-day recap (post-quiet, ~20:00+)

> demo day done. what held up:
>
> — the number on stage was the number on everyone's phone — live
>   field, no canned demo
> — "same trip, thirty times" landed: an AC car vs your feet is a
>   ~35× breath gap and nobody had seen it priced before
> — the honesty page got the best questions. the app says what it
>   doesn't know — stale readings say "min old", empty installs stay
>   empty, group counts never show one person
>
> built in the hackathon window, runs on about ₹0 of aws. delhi first.
> everything checked on camera, 13 min one take, zero crashes.
>
> apk + repo in bio.

**Attach:** the submission twitter cut if rendered
(`alive108-twitter-64s.mp4` from the video lane fits X free — 64 s);
else `docs/video/cut1.mp4` trimmed to ≤140 s (`-t 135`), else the
`landing-1440-mid.png` + `city-1440-hero.png` still pair.
**Honesty guard:** "zero crashes" = the v4 take's result on this binary,
true as stated; "₹0" = the verified 7-day bill (credits), say "about"
or keep the exact framing "$0.00 last week".
**Swap if the room had a different best moment:** keep the honest-three
shape — what held up / what surprised / what's next — and replace the
middle bullet with whatever the judges actually leaned into.

---

## Posting mechanics

- X free tier caps video at ~140 s — both chosen clips fit; cut1/cut2
  (161/157 s) must be trimmed or replaced by the 64 s twitter cut.
- Direct download links go in replies, not the post body (X
  deprioritises outbound links less in replies; the release page URL
  in bio carries the evergreen link).
- If the repo release 404s at post time, hold post 2 — post 1 is
  safe alone; never post an APK link you haven't incognito-tested.
