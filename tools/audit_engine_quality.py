#!/usr/bin/env python3
"""Engine-quality audit — least-smoke rows vs the OSRM fast row.

Leg-5 metric battery over the real OD set (shared with
audit_route_quality.py):

  * VALUE: for every OD, is there an engine (alive_core-path) primary
    row whose raster dose saves >=10% vs the OD's fast row while
    costing <=15% extra time? Reported two ways —
      vs FAST: against the single fastest router row of the OD
        (the product claim a user sees: "take this corridor instead"),
      vs MODE: against the same-mode router row (honest mode-for-mode
        physics — a walk can't beat a car's clock).
  * ABSURD DETOUR: engine primary distance > 1.6x the fast row's
    distance — a least-dose path that wanders isn't a corridor.
  * WORSE-DOSE: engine primary raster-mid strictly above the same-mode
    router row's — the least-dose claim failing outright (same
    integrator, same mode).

Prints per-OD table + summary counts + anomalies by severity.
Pure stdlib. Exit 0 always.

    python3 tools/audit_engine_quality.py [API_BASE]
"""
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from audit_route_quality import ODS, _post_plan   # noqa: E402

SAVE_NEED = 0.10      # >=10% dose saved
TIME_BUDGET = 0.15    # <=15% extra time
DETOUR_ABSURD = 1.6   # engine distance / fast distance


def _mid(o):
    d = o.get("dose") or {}
    v = d.get("mid")
    return float(v) if isinstance(v, (int, float)) else None


def _eta(o):
    v = o.get("eta_s")
    if isinstance(v, (int, float)) and v > 0:
        return float(v)
    dm = o.get("duration_min")
    return float(dm) * 60 if isinstance(dm, (int, float)) and dm > 0 \
        else None


def audit():
    rows = []
    anomalies = []           # (severity, od, detail)
    agg = {"ods": 0, "ods_win_fast": 0, "ods_win_mode": 0,
           "eng_rows": 0, "detours": 0, "worse_dose": 0,
           "per_mode": {}}

    for name, a, b, cls in ODS:
        resp, err = _post_plan(a, b)
        if resp is None:
            anomalies.append(("severe", name, f"plan call failed: {err}"))
            rows.append((name, cls, "NO-RESPONSE", {}))
            continue
        opts = resp.get("options") or []
        rtr = [o for o in opts if not o.get("engine")]
        eng = [o for o in opts if o.get("engine") == "alive_core-path"
               and o.get("alternative_index") in (None, 0)]
        if resp.get("error") or not eng:
            if cls != "edge":
                anomalies.append(
                    ("severe", name,
                     "no engine rows: %s" % (resp.get("error") or "empty")))
            rows.append((name, cls, None, {"opts": len(opts)}))
            continue
        if not rtr:
            anomalies.append(("severe", name, "no router rows to compare"))
            rows.append((name, cls, None, {"opts": len(opts)}))
            continue

        agg["ods"] += 1
        fast = min((o for o in rtr if _eta(o)),
                   key=lambda o: _eta(o), default=None)
        f_mid, f_eta, f_dist = (_mid(fast), _eta(fast),
                                fast.get("distance_km")) if fast else \
                               (None, None, None)
        rtr_by_mode = {o.get("mode"): o for o in rtr}

        d = {"opts": len(opts), "eng": len(eng)}
        od_win_fast = od_win_mode = False
        for o in eng:
            m = o.get("mode")
            e_mid, e_eta = _mid(o), _eta(o)
            e_dist = o.get("distance_km")
            agg["eng_rows"] += 1
            pm = agg["per_mode"].setdefault(
                m, {"rows": 0, "win_fast": 0, "win_mode": 0,
                    "worse": 0, "detour": 0})
            pm["rows"] += 1

            # --- vs the OD's fast row -------------------------------
            save = (f_mid - e_mid) / f_mid \
                if (f_mid and e_mid is not None) else None
            cost = (e_eta - f_eta) / f_eta \
                if (f_eta and e_eta) else None
            det = e_dist / f_dist if (f_dist and e_dist) else None
            if save is not None and cost is not None and \
                    save >= SAVE_NEED and cost <= TIME_BUDGET:
                pm["win_fast"] += 1
                od_win_fast = True
            if det is not None and det > DETOUR_ABSURD:
                pm["detour"] += 1
                agg["detours"] += 1
                anomalies.append(
                    ("moderate", name,
                     f"{m}: engine corridor {det:.2f}x the fast "
                     f"distance ({e_dist}km vs {f_dist}km) — absurd "
                     f"detour"))
            d.setdefault("fast", []).append(
                f"{m}:{save * 100:+.0f}%/{cost * 100:+.0f}%"
                if save is not None and cost is not None else
                f"{m}:n/a")

            # --- vs the same-mode router row ------------------------
            r = rtr_by_mode.get(m)
            if not r:
                continue
            r_mid, r_eta = _mid(r), _eta(r)
            msave = (r_mid - e_mid) / r_mid \
                if (r_mid and e_mid is not None) else None
            mcost = (e_eta - r_eta) / r_eta \
                if (r_eta and e_eta) else None
            if msave is not None and mcost is not None and \
                    msave >= SAVE_NEED and mcost <= TIME_BUDGET:
                pm["win_mode"] += 1
                od_win_mode = True
            if msave is not None and msave < 0:
                pm["worse"] += 1
                agg["worse_dose"] += 1
                anomalies.append(
                    ("moderate", name,
                     f"{m}: engine corridor {msave:+.0%} dose vs "
                     f"same-mode router ({e_mid} vs {r_mid} µg) — "
                     f"least-dose claim fails"))
            d.setdefault("mode", []).append(
                f"{m}:{msave * 100:+.0f}%/{mcost * 100:+.0f}%"
                if msave is not None and mcost is not None else
                f"{m}:n/a")

        if od_win_fast:
            agg["ods_win_fast"] += 1
        if od_win_mode:
            agg["ods_win_mode"] += 1
        rows.append((name, cls, None, d))

    # ---------------- report ------------------------------------------
    print(f"\n{'OD':<26} {'cls':<7} {'opts':>4} {'eng':>3}  "
          f"engine rows: save%/cost% vs FAST row")
    for name, cls, err, d in rows:
        if err:
            print(f"{name:<26} {cls:<7} {err}")
            continue
        fast_s = " ".join(d.get("fast") or [])
        mode_s = " ".join(d.get("mode") or [])
        print(f"{name:<26} {cls:<7} {d.get('opts', 0):>4} "
              f"{d.get('eng', 0):>3}  {fast_s}")
        if mode_s:
            print(f"{'':>38}{'':>3}  mode: {mode_s}")

    print(f"\n=== value metric ===")
    print(f"ODs compared:            {agg['ods']}")
    print(f"ODs with a winning row   vs fast row: "
          f"{agg['ods_win_fast']} ({agg['ods_win_fast'] / max(1, agg['ods']):.0%})")
    print(f"ODs with a winning row   vs same-mode: "
          f"{agg['ods_win_mode']} ({agg['ods_win_mode'] / max(1, agg['ods']):.0%})")
    print(f"engine primaries:        {agg['eng_rows']}")
    print(f"absurd detours >{DETOUR_ABSURD}x:      {agg['detours']}")
    print(f"worse-dose rows:         {agg['worse_dose']}")
    print(f"\nper-mode: rows / win-fast / win-mode / worse / detour")
    for m, pm in sorted(agg["per_mode"].items()):
        print(f"  {m:<6} {pm['rows']:>3} / {pm['win_fast']:>3} / "
              f"{pm['win_mode']:>3} / {pm['worse']:>3} / {pm['detour']:>3}")

    sev_rank = {"severe": 0, "moderate": 1, "low": 2}
    anomalies.sort(key=lambda x: (sev_rank[x[0]], x[1]))
    print(f"\n=== {len(anomalies)} anomalies ===")
    for sev, od, msg in anomalies:
        print(f"[{sev:<8}] {od:<26} {msg}")


if __name__ == "__main__":
    audit()
