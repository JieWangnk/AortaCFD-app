#!/usr/bin/env python3
"""The physiological-waveform series of the complexity ladder (24 November 2026).

The first series ran the U-bend gallery waveform (half-sine ejection over 0.4 s, peak 14.6 L/min, 0.73 L/min
trickle in diastole): cycle mean 5.0 L/min and Womersley number 20 as in an adult aorta, but a peak Reynolds
number of 3000 at the inlet, about half of the physiological 5000 to 7000, because a real heart ejects its stroke
volume in about 0.3 s. This script writes the second series:

* `physio_inflow.csv` (levels 0 to 2): half-sine ejection over 0.30 s, stroke volume 66.7 mL, so the peak is
  20.9 L/min at 0.15 s and the cycle mean stays 5.0 L/min at 75 beats per minute; zero inflow for the rest of the
  0.8 s cycle (closed valve).
* `physio_reversing_inflow.csv` (level 3): the same ejection followed by the reverse lobe of the first series
  (a quarter of the peak, 0.12 s long, here 0.30 to 0.42 s), zero afterwards; cycle mean 4.5 L/min.
* twelve configurations `config_physio_<tag>.json` copied from `config_gallery_<tag>.json` with the new waveform
  and the outlet backflow damping of Ladder 3 on every level (`betaT` 0.3, `betaN` 0.3): the steeper deceleration
  reverses part of the outlet on every level, and the normal term is what kept the fine Ladder 3 mesh alive.
* the run list `scripts/gallery/runs_ladder_physio.txt` (run names `physio_<tag>`; the coarse Ladder 0 run first
  as a ten-minute check of the setup, then the fine meshes so a late failure shows early).

Usage: python3 make_physio_series.py [--plot OUT_PNG]
"""
import argparse
import copy
import json
import pathlib

import numpy as np

APP = pathlib.Path(__file__).resolve().parents[3]
CASES = APP / "cases_input"
T_CYCLE, DT = 0.8, 0.005
T_EJECT = 0.30
SV_M3 = 5.0 / 60000 * T_CYCLE  # stroke volume for a 5.0 L/min cycle mean, m3
Q_PEAK = SV_M3 / (2 / np.pi * T_EJECT)  # half-sine: mean over the ejection is 2/pi of the peak
LOBE_FRACTION, LOBE_LEN = 0.25, 0.12
TAGS = ("coarse_span12", "mid_span18", "fine_span26")
LEVELS = ("ladder_L0", "ladder_L1", "ladder_L2", "ladder_L3")


def waveform(reverse_lobe: bool):
    t = np.round(np.arange(0.0, T_CYCLE + DT / 2, DT), 6)
    q = np.zeros_like(t)
    m = t < T_EJECT
    q[m] = Q_PEAK * np.sin(np.pi * t[m] / T_EJECT)
    if reverse_lobe:
        m = (t >= T_EJECT) & (t < T_EJECT + LOBE_LEN)
        q[m] = -LOBE_FRACTION * Q_PEAK * np.sin(np.pi * (t[m] - T_EJECT) / LOBE_LEN)
    q[-1] = 0.0
    return t, q


def write_csv(path: pathlib.Path, t, q):
    with open(path, "w") as f:
        f.write("Time,Flowrate\n")
        for ti, qi in zip(t, q):
            f.write(f"{ti:.6e},{qi:.6e}\n")


def describe(t, q):
    mean = np.trapezoid(q, t) / (t[-1] - t[0])
    s = f"peak {q.max() * 6e4:.2f} L/min at {t[q.argmax()]:.3f} s, mean {mean * 6e4:.2f} L/min"
    if q.min() < 0:
        s += f", reverse peak {q.min() * 6e4:.2f} L/min at {t[q.argmin()]:.3f} s"
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plot", help="check plot of the two waveforms against the first series")
    a = ap.parse_args()
    t, q = waveform(False)
    t3, q3 = waveform(True)
    text = {False: describe(t, q), True: describe(t3, q3)}
    print("levels 0 to 2:", text[False])
    print("level 3:      ", text[True])
    runs = []
    for level in LEVELS:
        rev = level == "ladder_L3"
        csv = "physio_reversing_inflow.csv" if rev else "physio_inflow.csv"
        write_csv(CASES / level / csv, *(waveform(rev)))
        for tag in TAGS:
            src = CASES / level / f"config_gallery_{tag}.json"
            c = copy.deepcopy(json.loads(src.read_text()))
            c["boundary_conditions"]["inlet"]["csv_file"] = csv
            wk = c["boundary_conditions"]["outlets"]["windkessel_settings"]
            wk.update({"enable_stabilization": True, "betaT": 0.3, "betaN": 0.3})
            note = (f"Physiological-waveform series (24 November 2026): {csv}, half-sine ejection over {T_EJECT:g} s "
                    f"({text[rev]}), zero inflow for the rest of the {T_CYCLE:g} s cycle; outlet backflow damping betaT 0.3 "
                    "and betaN 0.3 on every level (the fine Ladder 3 mesh of the first series collapsed with betaN 0).")
            c["_doc"] = c["_doc"].replace(f"config_gallery_{tag}.json", f"config_physio_{tag}.json") + " " + note
            if "case_info" in c and "description" in c["case_info"]:
                c["case_info"]["description"] += "; physiological waveform (0.30 s ejection, peak 20.9 L/min)"
            dst = CASES / level / f"config_physio_{tag}.json"
            dst.write_text(json.dumps(c, indent=2) + "\n")
            runs.append(f"{level} physio_{tag} cases_input/{level}/config_physio_{tag}.json")
    order = (["ladder_L0 physio_coarse_span12"]
             + [f"{lv} physio_fine_span26" for lv in ("ladder_L3", "ladder_L2", "ladder_L1", "ladder_L0")]
             + [f"{lv} physio_mid_span18" for lv in ("ladder_L3", "ladder_L2", "ladder_L1", "ladder_L0")]
             + [f"{lv} physio_coarse_span12" for lv in ("ladder_L3", "ladder_L2", "ladder_L1")])
    by_key = {" ".join(r.split()[:2]): r for r in runs}
    out = APP / "scripts/gallery/runs_ladder_physio.txt"
    out.write_text("\n".join(by_key[k] for k in order) + "\n")
    print(f"wrote 2 waveforms x 4 levels, 12 configurations and {out.relative_to(APP)}")
    if a.plot:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        u = np.genfromtxt(CASES / "ladder_L0/ubend_inflow.csv", delimiter=",", names=True)
        fig, ax = plt.subplots(figsize=(8, 3.6), dpi=160)
        ax.plot(u["Time"], u["Flowrate"] * 6e4, color="#6f7784", lw=2, label="first series (U-bend waveform)")
        ax.plot(t, q * 6e4, color="#1f5fa8", lw=2, label="physiological, levels 0 to 2")
        ax.plot(t3, q3 * 6e4, color="#b83232", lw=1.6, ls="--", label="physiological, level 3 (reverse lobe)")
        ax.axhline(0, color="k", lw=0.8)
        ax.set_xlabel("time (s)")
        ax.set_ylabel("inlet flow (L/min)")
        ax.legend(frameon=False)
        ax.grid(alpha=0.3)
        fig.tight_layout()
        fig.savefig(a.plot)


if __name__ == "__main__":
    main()
