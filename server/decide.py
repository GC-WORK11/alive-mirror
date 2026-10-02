"""The decision layer — turns compare() options into one recommendation.

Safety first, then dose, then time. Mode risk tiers are coarse multipliers
anchored to MoRTH "Road Accidents in India" fatality shares (two-wheelers
and pedestrians dominate deaths). Street-level risk comes from
blackspots.py — the official Delhi Traffic Police crash-prone zones —
applied to open modes that cross a zone after dark (DTP's own Table 6.38
night-time zones show the worst night crash concentration).
"""
from blackspots import spots_near_geometry

# relative crash-risk tier by mode class (1.0 = car baseline) — MoRTH
# fatality shares normalised, coarse by design
MODE_RISK = {
    "car": 1.0, "car_open": 1.0, "bus": 0.85, "metro": 0.55,
    "auto": 1.35, "bike": 2.3, "cycle": 2.0, "walk": 2.4,
}

# exposed modes get riskier in rain or poor visibility (wet road, low
# sight distance) — the weather half of 'safety first'
_OPEN = {"bike", "cycle", "walk", "auto"}

W_DOSE, W_RISK, W_TIME = 0.50, 0.30, 0.20

# each black spot a night-time open-mode route enters adds to its risk —
# the DTP zones are 500m circles, ~25% per zone crossing, capped
NIGHT_SPOT_PENALTY = 0.25
NIGHT_SPOT_CAP = 0.60


def _risk(vehicle: str, wx: dict, spot_hits=None) -> float:
    r = MODE_RISK.get(vehicle, 1.5)
    if vehicle in _OPEN and wx:
        if (wx.get("precip_mm") or 0) > 0 or (wx.get("visibility_m") or 99999) < 2000:
            r *= 1.25
        if wx.get("is_day") == 0:
            r *= 1.2
            if spot_hits:
                r *= 1 + min(NIGHT_SPOT_CAP, NIGHT_SPOT_PENALTY * len(spot_hits))
    return r


def _spot_hits(o: dict, wx: dict):
    """Official crash zones this option's geometry enters — only computed
    for open modes at night, where the penalty applies."""
    if o.get("vehicle") not in _OPEN or wx.get("is_day") != 0:
        return []
    return spots_near_geometry(o.get("geometry"))


def _norm(xs):
    lo, hi = min(xs), max(xs)
    if hi - lo < 1e-9:
        return [0.0] * len(xs)
    return [(x - lo) / (hi - lo) for x in xs]


def rank(options: list, wx: dict = None) -> dict:
    """Score every option on dose + mode-risk + time; return ranked list
    with a plain-English reason per option. wx = ambient conditions."""
    wx = wx or {}
    scored = [o for o in options
              if (o.get("exposure") or {}).get("dose_ug") is not None
              and o.get("duration_s")]
    if not scored:
        return {"decision": None, "options": options}

    hits = [_spot_hits(o, wx) for o in scored]
    risks_raw = [_risk(o["vehicle"], wx, h) for o, h in zip(scored, hits)]
    doses = _norm([o["exposure"]["dose_ug"] for o in scored])
    times = _norm([o["duration_s"] for o in scored])
    risks = _norm(risks_raw)

    best_d = min(o["exposure"]["dose_ug"] for o in scored)
    best_t = min(o["duration_s"] for o in scored)
    best_r = min(risks_raw)

    worst_d = max(o["exposure"]["dose_ug"] for o in scored)
    bad_wx = bool(wx) and ((wx.get("precip_mm") or 0) > 0 or
                           (wx.get("visibility_m") or 99999) < 2000)
    night = wx.get("is_day") == 0

    for o, nd, nt, nr, h in zip(scored, doses, times, risks, hits):
        o["decision_score"] = round(100 - (W_DOSE * nd + W_RISK * nr + W_TIME * nt) * 100, 1)
        if h:
            o["night_black_spots"] = [
                {"name": s["name"], "severity": s["severity"],
                 "dist_m": d} for s, d in h]
        reasons = []
        e = o["exposure"]
        is_worst = e["dose_ug"] >= worst_d and len(scored) > 1
        # one plain sentence per row — a rider who never heard of AQI
        # should get it instantly; no units, no jargon
        if is_worst:
            reasons.append("the smokiest way to go")
        elif e["dose_ug"] <= best_d * 1.15:
            reasons.append("you'd breathe the least smoke on this one")
        if o["duration_s"] <= best_t * 1.1 and not is_worst:
            reasons.append("the quickest way there")
        if _risk(o["vehicle"], wx, h) <= best_r + 0.05:
            reasons.append("the safest way to travel")
        if bad_wx and o["vehicle"] in _OPEN:
            reasons.append("open ride in bad weather — riskier")
        elif night and o["vehicle"] in _OPEN:
            if h:
                names = h[0][0]["name"] if len(h) == 1 else \
                    f"{h[0][0]['name']} +{len(h) - 1} more"
                reasons.append(
                    f"enters a crash black spot after dark ({names})")
            else:
                reasons.append("open ride after dark — riskier")
        vs = e.get("ug_saved_vs_worst")
        if vs and vs > 5 and not is_worst:
            reasons.append("much less smoke than the smokiest")
        if not reasons:
            reasons.append("more smoke and slower than the best")
        o["decision_reasons"] = reasons

    scored.sort(key=lambda o: -o["decision_score"])
    others = [o for o in options if o not in scored]
    return {"decision": scored[0], "options": scored + others}
