#!/usr/bin/env python3
"""Effect of the outlet normal backflow damping (betaN 0.3 vs 0) on the Ladder 3 statistics, per mesh level.
Reads stats/ladder_L3__gallery_<mesh>.json (damped) and stats_nodamp/ (damping off); prints a markdown table
of the relative change (damped minus off, as % of the damped value) and writes damping_effect.json next to itself."""
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
Q = [
    ("dP swing, maximum", ("dP_mmHg", "max"), "mmHg"),
    ("dP swing, minimum", ("dP_mmHg", "min"), "mmHg"),
    ("dP at peak inflow", ("dP_mmHg", "at_peak"), "mmHg"),
    ("dP cycle mean", ("dP_mmHg", "mean"), "mmHg"),
    ("Peak speed (99.9th pct)", ("umax_p999_m_s", "cycle_max"), "m/s"),
    ("WSS at peak, mean", ("wss_peak_Pa", "mean"), "Pa"),
    ("WSS at peak, p99", ("wss_peak_Pa", "p99"), "Pa"),
    ("TAWSS mean", ("tawss_Pa", "mean"), "Pa"),
    ("TAWSS p95", ("tawss_Pa", "p95"), "Pa"),
    ("TAWSS p99", ("tawss_Pa", "p99"), "Pa"),
    ("OSI mean", ("osi", "mean"), "-"),
    ("OSI > 0.3 area fraction", ("osi", "high_area_frac"), "-"),
    ("Low-TAWSS area fraction", ("tawss_Pa", "low_area_frac"), "-"),
    ("Outlet backflow area, max", ("backflow_outlet", "area_frac_max"), "-"),
    ("Inlet flow, cycle mean", ("Q_in_L_min", "mean"), "L/min"),
    ("Inlet flow, minimum", ("Q_in_L_min", "min"), "L/min"),
]
meshes = [
    m
    for m in ("coarse_span12", "mid_span18", "fine_span26")
    if (HERE / "stats_nodamp" / f"ladder_L3__gallery_{m}.json").exists()
    and (HERE / "stats" / f"ladder_L3__gallery_{m}.json").exists()
]
out = {}
print("| Quantity | " + " | ".join(f"{m.split('_')[0]} off -> on (change)" for m in meshes) + " |")
print("|---|" + "---|" * len(meshes))
for label, (a, b), unit in Q:
    cells = []
    for m in meshes:
        on = json.loads((HERE / "stats" / f"ladder_L3__gallery_{m}.json").read_text())[a][b]
        off = json.loads((HERE / "stats_nodamp" / f"ladder_L3__gallery_{m}.json").read_text())[a][b]
        rel = (on - off) / abs(on) * 100 if on else float("nan")
        out.setdefault(label, {})[m] = dict(off=off, on=on, change_pct=rel, unit=unit)
        cells.append(f"{off:.3g} -> {on:.3g} ({rel:+.1f} %)")
    print(f"| {label} | " + " | ".join(cells) + " |")
(HERE / "damping_effect.json").write_text(json.dumps(out, indent=1))
