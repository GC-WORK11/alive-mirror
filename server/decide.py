"""The decision layer — turns compare() options into one recommendation.

Safety first, then dose, then time. Mode risk tiers are coarse multipliers
anchored to MoRTH "Road Accidents in India" fatality shares (two-wheelers
and pedestrians dominate deaths); they are class-level, not street-level —
Delhi has no public lat/lon black-spot feed, so we do not fabricate one.
"""

# relative crash-risk tier by mode class (1.0 = car baseline) — MoRTH
# fatality shares normalised, coarse by design
MODE_RISK = {
    "car": 1.0, "car_open": 1.0, "bus": 0.85, "metro": 0.55,
    "auto": 1.35, "bike": 2.3, "cycle": 2.0, "walk": 2.4,
}

W_DOSE, W_RISK, W_TIME = 0.50, 0.30, 0.20


def _norm(xs):
    lo, hi = min(xs), max(xs)
    if hi - lo < 1e-9:
        return [0.0] * len(xs)
    return [(x - lo) / (hi - lo) for x in xs]


def rank(options: list) -> dict:
    """Score every option on dose + mode-risk + time; return ranked list
    with a plain-English reason per option."""
    scored = [o for o in options
              if (o.get("exposure") or {}).get("dose_ug") is not None
              and o.get("duration_s")]
    if not scored:
        return {"decision": None, "options": options}

    doses = _norm([o["exposure"]["dose_ug"] for o in scored])
    times = _norm([o["duration_s"] for o in scored])
    risks = _norm([MODE_RISK.get(o["vehicle"], 1.5) for o in scored])

    best_d = min(o["exposure"]["dose_ug"] for o in scored)
    best_t = min(o["duration_s"] for o in scored)
    best_r = min(MODE_RISK.get(o["vehicle"], 1.5) for o in scored)

    for o, nd, nt, nr in zip(scored, doses, times, risks):
        o["decision_score"] = round(100 - (W_DOSE * nd + W_RISK * nr + W_TIME * nt) * 100, 1)
        reasons = []
        e = o["exposure"]
        if o["exposure"]["dose_ug"] <= best_d * 1.15:
            reasons.append("breathes least")
        if MODE_RISK.get(o["vehicle"], 1.5) <= best_r + 0.05:
            reasons.append("safest mode class")
        if o["duration_s"] <= best_t * 1.1:
            reasons.append("fastest")
        vs = e.get("ug_saved_vs_worst")
        if vs and vs > 5:
            reasons.append(f"avoids {vs:.0f} µg vs worst option")
        if not reasons:
            t_over = round((o["duration_s"] - best_t) / 60)
            d_over = e.get("dose_vs_best_pct", 0)
            reasons.append(f"+{d_over:.0f}% dose, +{t_over} min vs best")
        o["decision_reasons"] = reasons

    scored.sort(key=lambda o: -o["decision_score"])
    others = [o for o in options if o not in scored]
    return {"decision": scored[0], "options": scored + others}
