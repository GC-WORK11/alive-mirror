# Lane: web-cold-eye — hostile comprehension pass on the overhauled WEB surfaces

Repo `<owner>/Delhi-Air-108`, branch `base/v2`, HEAD `d32801e`+.
Web overhaul `c1fbfb8` shipped: landing hero stat tile + door tiles +
band-washed district chips + pastel steps; /city accent chips + day
tiles; admin `.kchip` severity chips + `.cap` provenance captions. Judges
will open the live URLs ON PHONES — nobody has hostile-passed these
surfaces post-redesign.

## Mission — stranger eyes + FIX what you find
Live targets (read-only — never POST to live):
- Landing: http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com/
- City:   http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com/city
- Admin:  http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com/admin
  (token in `~/.alive_admin_token` on this box if needed for deep panels;
  the public shell should still be audited without it)

Audit pass (both desktop ~1280px AND phone ~390px viewports — curl the
HTML and also load in a browser if your box has one; Playwright via
localhost:29229 is available on macOS leads, not required):

1. **3-second test per surface**: can a Delhi person tell what the
   number means and what to do next? Flag every tile that needs a
   second read.
2. **Provenance-line honesty**: `.cap` captions and helper text — do
   they actually say where the number comes from ("median of 24 live
   stations", "your phone only") or do they hand-wave? Fix the copy.
3. **Mini-words**: any label or paragraph that could be a number+unit
   + ≤3-word label instead? Rewrite — words are rationed.
4. **Phone-viewport breakage**: overflow, clipped tiles, horizontal
   scroll, illegible captions at 390px. Fix the CSS.
5. **Anti-list sweep**: neon/cyberpunk/3D/decorative SVG/chocolaty
   green/cheap yellow — flag, don't fix.
6. **Consistency with app register**: serif editorial + muted CPCB
   bands + tinted chips — anything that clashes with the app register
   (docs/plan/design-refs.md) flag it.

## Rules
- Fix in the repo (`web/` statics), commit early+often to base/v2,
  `git pull --rebase` before push.
- Live verification after your changes are deployed is the lead's job —
  note in your report which figures you touched so the deploy check
  can curl them.
- Zero-fake rule: never invent numbers — if a caption can't be verified
  against the live response, say "not verified" in the report.
- Report = `docs/lanes/web-cold-eye-report.md` — fixes with commits,
  flags, per-viewport findings.
