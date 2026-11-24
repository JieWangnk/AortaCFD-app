#!/usr/bin/env python3
"""The convergence map of the complexity ladder: for every level (L0 planar bend, L1 + torsion, L2 + narrowing,
L3 + reversing inflow) and every quantity, the change from 12 to 18 and from 18 to 26 cells across, both relative
to the 26-cell value, and the mesh level at which the quantity is converged to within TOL:
  12   both changes within TOL (the coarse level is enough)
  18   only the 18 -> 26 change within TOL
  >26  the 18 -> 26 change is larger than TOL (not converged at the finest level run)
  n/a  the quantity is near zero at this level (a relative change means nothing)
Reads stats/<run>.json (ladder_stats.py); writes map.json, map.csv and convergence_map.png.
"""
import csv
import json
import pathlib

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
ST = HERE / "stats"
LEVELS = ("L0", "L1", "L2", "L3")
MESHES = ("coarse_span12", "mid_span18", "fine_span26")
TOL = 0.05
LEVEL_NAME = {"L0": "L0 planar bend", "L1": "L1 + torsion", "L2": "L2 + narrowing", "L3": "L3 + reversing inflow"}


def leg_numbers(r):
    """Pressure drop across the narrowing at peak inflow from the leg profile: one diameter upstream of the throat
    minus two diameters downstream (net loss), and upstream minus the minimum (the dip in the throat)."""
    s = np.array(r["leg_profile_peak"]["s_mm"])
    p = np.array(r["leg_profile_peak"]["p_mmHg"])
    if r["level"] not in ("L2", "L3"):
        return None, None
    s_thr = 196.95 - 11.86  # mm from the outlet plane to the throat centre (engine centreline, see centreline_stations.json)
    p_up = float(np.interp(s_thr + 26.0, s, p))
    p_rec = float(np.interp(s_thr - 52.0, s, p))
    p_min = float(p[(s > s_thr - 30) & (s < s_thr + 30)].min())
    return p_up - p_rec, p_up - p_min


QUANTITIES = [
    # key, label, unit, getter, near-zero floor (absolute), decimals
    ("dP_acc", "Pressure difference, acceleration peak", "mmHg", lambda r: r["dP_mmHg"]["max"], 0.1, 2),
    ("dP_dec", "Pressure difference, deceleration trough", "mmHg", lambda r: r["dP_mmHg"]["min"], 0.1, 2),
    ("dP_peak", "Pressure difference at peak inflow", "mmHg", lambda r: r["dP_mmHg"]["at_peak"], 0.1, 2),
    ("dP_mean", "Pressure difference, cycle mean", "mmHg", lambda r: r["dP_mmHg"]["mean"], 0.05, 3),
    ("dP_narrowing", "Pressure drop across the narrowing at peak inflow", "mmHg", lambda r: leg_numbers(r)[0], 0.1, 2),
    ("dP_dip", "Lowest pressure in the jet past the throat, below upstream, at peak inflow", "mmHg", lambda r: leg_numbers(r)[1], 0.1, 2),
    ("umax", "Peak speed (99.9th percentile over the cycle)", "m/s", lambda r: r["umax_p999_m_s"]["cycle_max"], 0.05, 3),
    ("wss_p99", "Wall shear at peak inflow, 99th percentile", "Pa", lambda r: r["wss_peak_Pa"]["p99"], 0.1, 2),
    ("wss_max", "Wall shear at peak inflow, maximum", "Pa", lambda r: r["wss_peak_Pa"]["max"], 0.1, 2),
    ("tawss_mean", "TAWSS, area mean", "Pa", lambda r: r["tawss_Pa"]["mean"], 0.05, 3),
    ("tawss_p95", "TAWSS, 95th percentile", "Pa", lambda r: r["tawss_Pa"]["p95"], 0.05, 3),
    ("tawss_p99", "TAWSS, 99th percentile", "Pa", lambda r: r["tawss_Pa"]["p99"], 0.05, 3),
    ("low_tawss", "Wall area with TAWSS below 0.4 Pa", "%", lambda r: 100 * r["tawss_Pa"]["low_area_frac"], 1.0, 1),
    ("osi_mean", "OSI, area mean", "-", lambda r: r["osi"]["mean"], 0.02, 3),
    ("osi_high", "Wall area with OSI above 0.3", "%", lambda r: 100 * r["osi"]["high_area_frac"], 1.0, 1),
    ("backflow", "Outlet area in backflow, largest over the cycle", "%", lambda r: 100 * r["backflow_outlet"]["area_frac_max"], 1.0, 1),
]


def classify(v12, v18, v26, floor):
    if any(v is None for v in (v12, v18, v26)):
        return None, None, "n/a"
    if abs(v26) < floor:
        return None, None, "n/a"
    c1 = (v18 - v12) / abs(v26)
    c2 = (v26 - v18) / abs(v26)
    if abs(c1) <= TOL and abs(c2) <= TOL:
        cls = "12"
    elif abs(c2) <= TOL:
        cls = "18"
    else:
        cls = ">26"
    return c1, c2, cls


def main():
    runs = {(L, m): json.loads((ST / f"ladder_{L}__gallery_{m}.json").read_text()) for L in LEVELS for m in MESHES}
    table = {}
    rows = []
    for key, label, unit, get, floor, dec in QUANTITIES:
        table[key] = dict(label=label, unit=unit, levels={})
        for L in LEVELS:
            vals = [get(runs[(L, m)]) for m in MESHES]
            c1, c2, cls = classify(*vals, floor)
            table[key]["levels"][L] = dict(values=vals, change_12_18=c1, change_18_26=c2, converged_at=cls)
            rows.append(dict(quantity=label, unit=unit, level=L, v12=vals[0], v18=vals[1], v26=vals[2],
                             change_12_18_pct=None if c1 is None else 100 * c1, change_18_26_pct=None if c2 is None else 100 * c2, converged_at=cls))
    (HERE / "map.json").write_text(json.dumps(dict(tolerance=TOL, quantities=table, level_names=LEVEL_NAME), indent=1))
    with open(HERE / "map.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    # the figure
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    colours = {"12": "#cfe8d3", "18": "#fde7b0", ">26": "#f5c6c0", "n/a": "#ececec"}
    text_col = {"12": "#1f5b2b", "18": "#7a5200", ">26": "#8a1c1c", "n/a": "#777777"}
    nq, nl = len(QUANTITIES), len(LEVELS)
    fig, ax = plt.subplots(figsize=(13.2, 0.62 * nq + 1.9), dpi=170)
    ax.set_xlim(0, nl)
    ax.set_ylim(0, nq)
    ax.invert_yaxis()
    ax.set_xticks([i + 0.5 for i in range(nl)])
    ax.set_xticklabels([LEVEL_NAME[L] for L in LEVELS], fontsize=11.5)
    ax.xaxis.tick_top()
    ax.set_yticks([i + 0.5 for i in range(nq)])
    ax.set_yticklabels([f"{q[1]} ({q[2]})" for q in QUANTITIES], fontsize=10.5)
    ax.tick_params(length=0)
    for sp in ax.spines.values():
        sp.set_visible(False)
    for i, (key, label, unit, get, floor, dec) in enumerate(QUANTITIES):
        for j, L in enumerate(LEVELS):
            d = table[key]["levels"][L]
            cls = d["converged_at"]
            ax.add_patch(Rectangle((j, i), 1, 1, facecolor=colours[cls], edgecolor="white", lw=2))
            v = d["values"]
            if cls == "n/a":
                txt = "near zero" if v[2] is not None else "not defined"
                ax.text(j + 0.5, i + 0.5, txt, ha="center", va="center", fontsize=9.5, color=text_col[cls])
            else:
                head = f"{v[2]:.{dec}f} {unit}".replace(" -", "") if unit != "%" else f"{v[2]:.{dec}f} %"
                sub = f"12→18: {100 * d['change_12_18']:+.1f} %   18→26: {100 * d['change_18_26']:+.1f} %"
                ax.text(j + 0.5, i + 0.36, head, ha="center", va="center", fontsize=10, color="black", fontweight="bold")
                ax.text(j + 0.5, i + 0.72, sub, ha="center", va="center", fontsize=8.6, color=text_col[cls])
    handles = [Rectangle((0, 0), 1, 1, facecolor=colours[c]) for c in ("12", "18", ">26", "n/a")]
    ax.legend(handles, [f"converged at 12 cells across (both changes within {100 * TOL:.0f} %)", "converged at 18 (only the 18→26 change within tolerance)",
                        "not converged at 26 (the 18→26 change is larger)", "near zero: no relative change to read"],
              loc="upper center", bbox_to_anchor=(0.5, -0.01), ncol=2, frameon=False, fontsize=9.5)
    fig.suptitle("Which quantity is converged at which mesh level, as the flow gets more complicated\n"
                 "(value at 26 cells across; changes relative to that value; 12, 18 and 26 cells across the 27 mm inlet)", fontsize=12, y=0.995)
    fig.tight_layout(rect=(0, 0.02, 1, 0.95))
    fig.savefig(HERE / "convergence_map.png", facecolor="white")
    print(f"wrote convergence_map.png, map.json, map.csv ({nq} quantities x {nl} levels)")
    for key, label, unit, get, floor, dec in QUANTITIES:
        print(f"{label:55s}", "  ".join(f"{L}:{table[key]['levels'][L]['converged_at']:>4s}" for L in LEVELS))


if __name__ == "__main__":
    main()
