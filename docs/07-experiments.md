# 07 · Deep Experiments — Scored

Each: hypothesis / inputs / method / benefit / cost / validation / failure mode / MVP?

## E1 — Exposure field as graph edge weights (not map overlay)
- **Hypothesis**: precomputing per-edge concentration makes route scoring a graph problem — any router/candidate can be scored in O(edges) lookups.
- **Inputs**: OSM edges, hourly field surface, traffic bump.
- **Method**: `edge_exposure(edge, hour_bucket)` table; scorer = Σ over polyline.
- **Benefit**: <50 ms scoring; router-agnostic.
- **Cost**: ~1 day; storage trivial (Delhi ~300k edges × 24 buckets).
- **Validation**: vs per-point sampling on test routes — difference <5%.
- **Failure**: edges crossing cell borders → split at build time.
- **Verdict: MVP** — it's the architecture, not an experiment.

## E2 — Departure-time dose curves from climatology
- **Hypothesis**: hour-of-day climatology × today's field predicts dose(depart=t) better than "now" alone.
- **Inputs**: OpenAQ history → climatology per zone; live field.
- **Method**: `C(x,t) ≈ nowcast × climatology_ratio(zone, hour)`; flag stubble days via FIRMS.
- **Benefit**: the "leave at 11, save 25%" insight — cheap, compelling.
- **Cost**: 1 day after backfill.
- **Validation**: back-test climatology on held-out months; honest error bars.
- **Failure**: unusual days (rain, GRAP events) → widen band, label "typical pattern".
- **Verdict: MVP-lite.**

## E3 — Stubble-fire transport signal → next-day PM load
- **Hypothesis**: upwind (NW sector) fire count/FRP in Punjab+Haryana correlates with next-day Delhi PM2.5 in Oct–Nov (~20% avg, 50–75% event days — published).
- **Inputs**: FIRMS daily by sector + wind direction + OpenAQ history.
- **Method**: regression of Delhi ΔPM on sector fires lagged 0–2 days, conditioned on wind.
- **Benefit**: genuinely Delhi-specific intelligence; visible on `/now`.
- **Cost**: 1–2 days incl. back-test.
- **Validation**: 2020–2025 Oct–Nov correlation coefficient; report actual.
- **Failure**: cloudy days (fires missed), non-season months → deactivate signal outside Oct–Dec.
- **Verdict: MVP if validation ≥ modest correlation; else V2.**

## E4 — Metro legs as exposure "super-highways"
- **Hypothesis**: treating metro travel at near-floor dose produces itineraries road-routers never generate — the differentiator.
- **Inputs**: DMRC GTFS, published metro/road dose ratios.
- **Method**: OTP2 itineraries scored with mode factors; UI highlights "clean segment".
- **Benefit**: 3–6× dose reductions on common corridors — demo gold.
- **Cost**: 0 extra — falls out of mode-aware scoring.
- **Validation**: ordering sanity (§05); spot-check vs published trip doses.
- **Failure**: last-mile walk legs dominate dose → scorer must price them honestly, or recommendation looks wrong.
- **Verdict: MVP.**

## E5 — Uncertainty-aware ranking
- **Hypothesis**: recommending on dose *intervals* (e.g., pick itinerary whose upper bound beats others' lower) is more honest than point ranking.
- **Inputs**: per-itinerary dose posterior.
- **Method**: stochastic-dominance-flavored ranking + display band.
- **Benefit**: defensible recommendations; confidence visible.
- **Cost**: ~half day post-scorer.
- **Validation**: does ranking flip under ±σ? If never → simplify UI to point+band.
- **Failure**: bands overlap almost always → then say "statistically tied" honestly.
- **Verdict: MVP-lite.**

## E6 — Traffic-conditioned concentration (live speeds)
- **Hypothesis**: congestion bumps roadside PM; live speed improves edge exposure.
- **Inputs**: TomTom/Mappls on ~30 key corridors; OSM class priors elsewhere.
- **Method**: speed→emission-proxied increment (bounded, conservative).
- **Benefit**: rush-hour realism on the roads people actually use.
- **Cost**: API limits bind; partial coverage.
- **Validation**: correlate corridor increments w/ speed data on archive days.
- **Failure**: free tier dies mid-demo → priors-only fallback, transparently.
- **Verdict: V2** — priors in MVP, live speeds later.

## E7 — Kalman temporal fusion per station
- **Hypothesis**: station reliability weights should be learned (documented siting violations).
- **Method**: latent state per station vs field posterior; EM over history.
- **Benefit**: self-correcting field; the real technical moat.
- **Cost**: needs months of stored obs + ~3 days math.
- **Verdict: V2** — after historical pipeline matures.

## E8 — Physics-informed / GNN field
- **Hypothesis**: graph-structured spatial model beats kriging where stations are sparse (65% of Delhi unmonitored).
- **Method**: GNN over road graph w/ met covariates; or PINN-advection-lite.
- **Benefit**: accuracy where it matters (unmonitored corridors).
- **Cost**: heavy; needs archive corpus + GPU experimentation.
- **Verdict: V2** — honest moat path, not a hackathon bet.

## E9 — Full dispersion (street canyons, Gaussian plume per corridor)
- **Hypothesis**: mechanistic increments beat empirical bump.
- **Blocker**: requires current emissions inventories (public ones are 2018/2021-stale — why CAQM dropped DSS); canyon geometry data thin.
- **Verdict: CUT** — say why in the writeup; judges respect the honesty.

## E10 — LLM decision narrator
- **Hypothesis**: an LLM explains ranking factors better than templates.
- **Guardrail**: LLM receives only computed numbers; cannot emit numbers it wasn't given (schema-validated).
- **Verdict: Optional garnish — never in the compute path.**

## What we're NOT doing and why (one-liner for judges)

> "We tested the ambitious stuff on paper first. Kriging+empirical-traffic wins the hackathon because it's honest at 46 stations; the Kalman/GNN versions need the historical corpus we're *building now* — that's the moat, not the demo."
