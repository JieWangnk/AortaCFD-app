#!/usr/bin/env python3
"""Statistics of the complexity-ladder runs, read from the saved OpenFOAM fields (one cycle per run).

For every run (4 levels x 3 mesh levels) over the last saved cycle (L0-L2: 0.016-0.8 s; L3: 1.616-2.4 s, the
third cycle), frame by frame:
  inlet and outlet flow from the face velocities against the cap normals of the exported bundle (outward);
  the inlet flow is the flow record: on Ladder 3 the outlet condition damps the normal velocity written on
  inflow faces (betaN 0.3), so the outlet flow summed from face velocities reads about 7 % low in the lobe,
  the inlet-to-outlet pressure difference (area-weighted means; p relative to the outlet mean, as on the site),
  the wall shear vector per wall face (x 1060 kg/m3), the 99.9th percentile of |U| over the cells,
  the outlet area fraction in backflow (U . n_out < 0).
Over the cycle: TAWSS and OSI per face; area-weighted statistics over the wall with a 4 mm band at the inlet and
outlet planes left out (where the imposed profile and the outlet condition meet the wall layers); the pressure
difference's cycle mean (time-weighted: 50 evenly spaced frames), maximum and minimum; the peak-inflow frame's
shear percentiles, pressure difference and speed; the mean pressure along the straight leg that ends at the
outlet at the peak frame (render_arms.leg_profile), which for L2/L3 crosses the narrowing.

Usage: python3 ladder_stats.py [name-or-level ...]      -> stats/<run>.json (skips runs already done) + stats/summary.csv
  LADDER_STATS_DIR=<dir> changes the output folder; LADDER_RUN_PREFIX=<prefix> scores output/ladder_<L>/<prefix><mesh>
  instead of gallery_<mesh> (the bundle meta of the gallery run supplies the cap normals, which depend on the mesh only).
"""
import csv
import json
import os
import pathlib
import sys
import time

import numpy as np

APP = pathlib.Path(os.environ.get("AORTACFD_APP", pathlib.Path(__file__).resolve().parents[3]))
WEB = pathlib.Path(os.environ.get("AORTACFD_WEB", APP.parent / "AortaCFD-web"))
sys.path.insert(0, str(WEB / "scripts"))  # render_case.py: the field reader
import render_arms as ra  # noqa: E402
import render_case as rc  # noqa: E402

OUT = pathlib.Path(os.environ.get("LADDER_STATS_DIR", pathlib.Path(__file__).resolve().parent / "stats"))
RUN_PREFIX = os.environ.get("LADDER_RUN_PREFIX", "gallery_")  # e.g. nodamp_ for the damping-off Ladder 3 runs
LEVELS = ("L0", "L1", "L2", "L3")
MESHES = ("coarse_span12", "mid_span18", "fine_span26")
BAND_M = 0.004
LOW_TAWSS_PA = 0.4
OSI_HIGH = 0.3


def wpct(x, w, q):
    """Area-weighted percentile q (0-100) of x with weights w."""
    i = np.argsort(x)
    x, w = x[i], w[i]
    c = (np.cumsum(w) - 0.5 * w) / w.sum()
    return float(np.interp(q / 100.0, c, x))


def areas(ds):
    return np.asarray(ds.compute_cell_sizes(length=False, area=True, volume=False)["Area"], float)


def centres(ds):
    return np.asarray(ds.cell_centers().points, float)


def band_mask(wall_c, caps):
    """True for wall faces farther than BAND_M from both cap planes (near each cap only: the inlet plane of a
    twisted geometry, extended, would cut the descending leg)."""
    keep = np.ones(len(wall_c), bool)
    for c, n, r in caps:
        d_plane = np.abs((wall_c - c) @ n)
        d_axis = np.linalg.norm(wall_c - c, axis=1)
        keep &= ~((d_plane < BAND_M) & (d_axis < 1.8 * r))
    return keep


def run_stats(level, tag):
    name = f"ladder_{level}__gallery_{tag}"
    run = APP / "output" / f"ladder_{level}" / f"{RUN_PREFIX}{tag}"
    foam = next((run / "openfoam").glob("*.foam"))
    meta = json.loads((APP / "output/_ladder/bundles" / name / "meta.json").read_text())
    caps = meta["caps"]
    n_in = np.asarray(caps["inlet"]["normal"], float)
    n_out = np.asarray(caps["outlet1"]["normal"], float)
    n_in /= np.linalg.norm(n_in)
    n_out /= np.linalg.norm(n_out)
    c = rc.Case(foam)
    t_from = 1.6 if level == "L3" else 0.0
    times = [t for t in c.times if t > t_from + 1e-9]
    t0 = time.time()
    Qin, Qout, dP, umax, umax_abs, back_frac, back_q = [], [], [], [], [], [], []
    sum_mag = sum_vec = A_w = keep = None
    frames_wss = []
    peak_cache = {}
    for k, t in enumerate(times):
        internal, wall, inlet, bnd = c.read(t)
        outlet = bnd["outlet1"]
        if A_w is None:
            A_in, A_out, A_w = areas(inlet), areas(outlet), areas(wall)
            cap_in = (np.asarray(inlet.center), n_in, caps["inlet"]["radius_mm"] / 1000.0)
            cap_out = (np.asarray(outlet.center), n_out, caps["outlet1"]["radius_mm"] / 1000.0)
            keep = band_mask(centres(wall), [cap_in, cap_out])
            sum_mag = np.zeros(wall.n_cells)
            sum_vec = np.zeros((wall.n_cells, 3))
        u_in = inlet.cell_data["U"] @ n_in
        u_out = outlet.cell_data["U"] @ n_out
        Qin.append(float(-np.sum(u_in * A_in) * 60000.0))
        Qout.append(float(np.sum(u_out * A_out) * 60000.0))
        rev = u_out < 0.0
        back_frac.append(float(A_out[rev].sum() / A_out.sum()))
        back_q.append(float(np.sum(u_out[rev] * A_out[rev]) * 60000.0))
        p_in = float(np.sum(inlet.cell_data["p"] * A_in) / A_in.sum())
        p_out = float(np.sum(outlet.cell_data["p"] * A_out) / A_out.sum())
        dP.append((p_in - p_out) * rc.RHO / rc.MMHG)
        um = np.asarray(internal.cell_data["Umag"])
        umax.append(float(np.percentile(um, 99.9)))
        umax_abs.append(float(um.max()))
        tau = np.asarray(wall.cell_data["wallShearStress"], float) * rc.RHO if "wallShearStress" in wall.cell_data else np.zeros((wall.n_cells, 3))
        mag = np.linalg.norm(tau, axis=1)
        sum_mag += mag
        sum_vec += tau
        frames_wss.append(mag)
        if k % 10 == 0:
            print(f"  {name} t = {t:.3f}  Qin {Qin[-1]:6.2f} L/min  dP {dP[-1]:+.3f} mmHg  back {back_frac[-1]:.2f}  ({time.time() - t0:.0f} s)", flush=True)
    Qin, Qout, dP, umax = map(np.array, (Qin, Qout, dP, umax))
    k_peak = len(Qin) - 1 - int(np.argmax(Qin[::-1]))
    t_peak = times[k_peak]
    nT = len(times)
    tawss = sum_mag / nT
    osi = np.where(tawss > 0, 0.5 * (1.0 - np.linalg.norm(sum_vec, axis=1) / nT / np.maximum(tawss, 1e-30)), 0.0)
    w = A_w[keep]
    wss_peak = frames_wss[k_peak][keep]
    # pressure along the leg that ends at the outlet, at the peak frame
    internal, wall, inlet, bnd = c.read(t_peak)
    up = -n_out  # the outlet axis, pointing into the vessel
    s_mm, p_leg = ra.leg_profile(internal, bnd["outlet1"], up)
    res = dict(
        run=name, level=level, mesh=tag, cells=int(internal.n_cells), n_wall_faces=int(wall.n_cells),
        wall_faces_kept=int(keep.sum()), wall_area_kept_frac=float(w.sum() / A_w.sum()), band_mm=BAND_M * 1000,
        times=[float(t) for t in times], t_peak=float(t_peak),
        Q_in_L_min=dict(mean=float(Qin.mean()), peak=float(Qin.max()), min=float(Qin.min()), series=[float(x) for x in Qin]),
        Q_out_L_min=dict(mean=float(Qout.mean()), series=[float(x) for x in Qout]),
        balance=float((Qout.mean() - Qin.mean()) / Qin.mean()),
        dP_mmHg=dict(mean=float(dP.mean()), max=float(dP.max()), t_max=float(times[int(np.argmax(dP))]), min=float(dP.min()),
                     t_min=float(times[int(np.argmin(dP))]), at_peak=float(dP[k_peak]), series=[float(x) for x in dP]),
        umax_p999_m_s=dict(cycle_max=float(umax.max()), at_peak=float(umax[k_peak]), series=[float(x) for x in umax]),
        umax_abs_m_s=dict(cycle_max=float(max(umax_abs)), at_peak=float(umax_abs[k_peak])),
        backflow_outlet=dict(area_frac_max=float(max(back_frac)), t_area_frac_max=float(times[int(np.argmax(back_frac))]),
                             area_frac_end=float(back_frac[-1]), reverse_flow_L_min_min=float(min(back_q)), series=[float(x) for x in back_frac]),
        wss_peak_Pa=dict(mean=float(np.sum(wss_peak * w) / w.sum()), p95=wpct(wss_peak, w, 95), p99=wpct(wss_peak, w, 99), max=float(wss_peak.max())),
        tawss_Pa=dict(mean=float(np.sum(tawss[keep] * w) / w.sum()), p95=wpct(tawss[keep], w, 95), p99=wpct(tawss[keep], w, 99), max=float(tawss[keep].max()),
                      low_area_frac=float(w[tawss[keep] < LOW_TAWSS_PA].sum() / w.sum())),
        osi=dict(mean=float(np.sum(osi[keep] * w) / w.sum()), p95=wpct(osi[keep], w, 95), max=float(osi[keep].max()),
                 high_area_frac=float(w[osi[keep] > OSI_HIGH].sum() / w.sum())),
        leg_profile_peak=dict(s_mm=[float(x) for x in s_mm], p_mmHg=[float(x) for x in p_leg]),
        seconds=float(time.time() - t0),
    )
    print(f"{name}: {nT} frames, peak {t_peak:.3f} s ({Qin.max():.2f} L/min); dP mean {dP.mean():+.3f} max {dP.max():+.2f} min {dP.min():+.2f} mmHg; "
          f"TAWSS mean {res['tawss_Pa']['mean']:.3f} p99 {res['tawss_Pa']['p99']:.3f}; OSI mean {res['osi']['mean']:.3f}; "
          f"umax {umax.max():.3f} m/s; backflow max {max(back_frac):.2f}; leg {s_mm[0]:.0f}-{s_mm[-1]:.0f} mm  ({time.time() - t0:.0f} s)", flush=True)
    return res


def summary():
    rows = []
    for level in LEVELS:
        for tag in MESHES:
            p = OUT / f"ladder_{level}__gallery_{tag}.json"
            if not p.exists():
                continue
            r = json.loads(p.read_text())
            rows.append(dict(level=level, mesh=tag, cells=r["cells"], Qin_mean=r["Q_in_L_min"]["mean"], Qin_peak=r["Q_in_L_min"]["peak"],
                             balance_pct=100 * r["balance"], dP_mean=r["dP_mmHg"]["mean"], dP_max=r["dP_mmHg"]["max"], dP_min=r["dP_mmHg"]["min"],
                             dP_peak=r["dP_mmHg"]["at_peak"], umax_p999=r["umax_p999_m_s"]["cycle_max"], umax_abs=r["umax_abs_m_s"]["cycle_max"],
                             wss_peak_p99=r["wss_peak_Pa"]["p99"], wss_peak_max=r["wss_peak_Pa"]["max"],
                             tawss_mean=r["tawss_Pa"]["mean"], tawss_p95=r["tawss_Pa"]["p95"], tawss_p99=r["tawss_Pa"]["p99"], tawss_max=r["tawss_Pa"]["max"],
                             low_tawss_frac=r["tawss_Pa"]["low_area_frac"], osi_mean=r["osi"]["mean"], osi_high_frac=r["osi"]["high_area_frac"],
                             backflow_max=r["backflow_outlet"]["area_frac_max"], backflow_end=r["backflow_outlet"]["area_frac_end"]))
    if rows:
        with open(OUT / "summary.csv", "w", newline="") as f:
            wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            wr.writeheader()
            wr.writerows(rows)
    return rows


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    only = sys.argv[1:]
    for level in LEVELS:
        for tag in MESHES:
            name = f"ladder_{level}__gallery_{tag}"
            if only and name not in only and level not in only:
                continue
            out = OUT / f"{name}.json"
            if out.exists():
                print(f"{name}: done already")
                continue
            res = run_stats(level, tag)
            out.write_text(json.dumps(res, indent=1))
    rows = summary()
    print(f"summary: {len(rows)} runs -> {OUT / 'summary.csv'}")
