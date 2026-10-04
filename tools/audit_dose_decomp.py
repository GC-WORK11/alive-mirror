#!/usr/bin/env python3
"""Worse-dose decomposition — WHY does an engine primary's raster
dose.mid sit above the same-mode router row's?

The display dose is one integrator for every row:

    dose.mid = VE · me · C̄ · T          (exposure.dose, flat uplift)
    C̄        = length-weighted mean concentration along the path
               (wire field `dose.avg_conc_ugm3`, includes me)
    T        = declared duration (wire field `eta_s`)

so for a same-mode engine/router pair (VE, me cancel):

    dose_ratio = conc_ratio · dist_ratio · (r_speed / e_speed)
               = (C̄e/C̄r) · (Te/Tr)

Three honest factors, all on the wire:
  * conc_ratio  — corridor air quality per metre (PURE path choice)
  * time_ratio  — declared durations; factors further into
    dist_ratio (corridor length) and implied-speed ratio
    (e_dist/e_eta vs r_dist/r_eta — the two duration models)
  * equal_speed_ratio = conc_ratio · dist_ratio — the dose a user
    pays if both vehicles run the SAME speed profile. <1 means the
    engine corridor is genuinely the lung-cheaper path; the
    wire's worse-dose flag is then purely a duration-model artefact.

Classification per engine row whose dose.mid > router's:
  * "speed-model"   — equal_speed_ratio <= 1.0: path is fine, the
                      displayed gap is the duration models' doing.
  * "corridor"      — equal_speed_ratio > 1.0: even at equal speed
                      the engine corridor costs more dose — a real
                      path-quality failure to explain in the priced
                      objective.

    python3 tools/audit_dose_decomp.py [API_BASE]

Pure stdlib. Exit 0 always.
"""
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from audit_route_quality import ODS, _post_plan   # noqa: E402


def _mid(o):
    v = (o.get("dose") or {}).get("mid")
    return float(v) if isinstance(v, (int, float)) and v > 0 else None


def _conc(o):
    v = (o.get("dose") or {}).get("avg_conc_ugm3")
    return float(v) if isinstance(v, (int, float)) and v > 0 else None


def _eta(o):
    v = o.get("eta_s")
    return float(v) if isinstance(v, (int, float)) and v > 0 else None


def _dist(o):
    v = o.get("distance_km")
    return float(v) if isinstance(v, (int, float)) and v > 0 else None


def audit():
    rows = []
    agg = {"pairs": 0, "worse": 0, "speed_model": 0, "corridor": 0,
           "no_conc": 0}
    speed_eng, speed_rtr = [], []

    for name, a, b, cls in ODS:
        resp, err = _post_plan(a, b)
        if resp is None or resp.get("error"):
            continue
        opts = resp.get("options") or []
        rtr = {o.get("mode"): o for o in opts if not o.get("engine")}
        for o in opts:
            if o.get("engine") != "alive_core-path" or \
                    o.get("alternative_index") not in (None, 0):
                continue
            m = o.get("mode")
            r = rtr.get(m)
            if r is None:
                continue
            e_mid, r_mid = _mid(o), _mid(r)
            e_eta, r_eta = _eta(o), _eta(r)
            e_dst, r_dst = _dist(o), _dist(r)
            e_cnc, r_cnc = _conc(o), _conc(r)
            if not all([e_mid, r_mid, e_eta, r_eta, e_dst, r_dst]):
                continue
            agg["pairs"] += 1
            e_spd = e_dst / e_eta * 3600.0
            r_spd = r_dst / r_eta * 3600.0
            speed_eng.append(e_spd)
            speed_rtr.append(r_spd)
            dose_r = e_mid / r_mid
            time_r = e_eta / r_eta
            dist_r = e_dst / r_dst
            if e_cnc and r_cnc:
                conc_r = e_cnc / r_cnc
            else:
                conc_r = None
                agg["no_conc"] += 1
            # dose at one shared speed profile: VE·me·C̄·dist/v cancels v
            eq_r = ((e_cnc or 0) * e_dst) / ((r_cnc or 1) * r_dst) \
                if e_cnc and r_cnc else None
            worse = dose_r > 1.0
            if worse:
                agg["worse"] += 1
                if eq_r is not None:
                    if eq_r <= 1.0:
                        agg["speed_model"] += 1
                        kind = "speed-model"
                    else:
                        agg["corridor"] += 1
                        kind = "CORRIDOR"
                else:
                    kind = "?"
            else:
                kind = "wins"
            rows.append({
                "od": name, "cls": cls, "mode": m,
                "dose_r": dose_r, "time_r": time_r, "dist_r": dist_r,
                "conc_r": conc_r, "eq_r": eq_r,
                "e_spd": e_spd, "r_spd": r_spd,
                "e_mid": e_mid, "r_mid": r_mid,
                "worse": worse, "kind": kind})

    hdr = (f"{'OD':<24} {'mode':<6} {'dose':>6} {'time':>6} {'dist':>6} "
           f"{'conc':>6} {'eqspd':>6} {'e km/h':>6} {'r km/h':>6}  verdict")
    print("\n" + hdr)
    for x in rows:
        if not x["worse"]:
            continue
        conc = f"{x['conc_r']:>6.3f}" if x["conc_r"] else "   n/a"
        eq = f"{x['eq_r']:>6.3f}" if x["eq_r"] else "   n/a"
        print(f"{x['od']:<24} {x['mode']:<6} {x['dose_r']:>6.3f} "
              f"{x['time_r']:>6.3f} {x['dist_r']:>6.3f} {conc} {eq} "
              f"{x['e_spd']:>6.1f} {x['r_spd']:>6.1f}  {x['kind']}")

    speed_eng.sort()
    speed_rtr.sort()
    med = lambda v: v[len(v) // 2] if v else 0
    print(f"\n=== decomposition summary ===")
    print(f"same-mode pairs:           {agg['pairs']}")
    print(f"worse-dose rows:           {agg['worse']}")
    print(f"  explained by speed model (equal-speed dose <= router): "
          f"{agg['speed_model']}")
    print(f"  residual corridor failures (equal-speed dose > router): "
          f"{agg['corridor']}")
    print(f"  missing avg_conc (unclassified): {agg['no_conc']}")
    print(f"median implied speed  engine {med(speed_eng):.1f} km/h "
          f"vs router {med(speed_rtr):.1f} km/h")
    cr = [x["conc_r"] for x in rows if x["conc_r"]]
    er = [x["eq_r"] for x in rows if x["eq_r"]]
    if cr:
        cr.sort()
        print(f"median conc_ratio (engine C̄ / router C̄): "
              f"{med(cr):.3f}")
    if er:
        er.sort()
        print(f"median equal-speed dose ratio:              "
              f"{med(er):.3f}")

    worst = sorted((x for x in rows if x["kind"] == "CORRIDOR"),
                   key=lambda x: -(x["eq_r"] or 0))[:12]
    if worst:
        print(f"\n=== worst corridor failures (equal-speed dose ratio) ===")
        for x in worst:
            print(f"  {x['od']:<24} {x['mode']:<6} eq {x['eq_r']:.3f} "
                  f"conc {x['conc_r']:.3f} dist {x['dist_r']:.3f} "
                  f"(e {x['e_mid']} vs r {x['r_mid']} µg)")


if __name__ == "__main__":
    audit()
