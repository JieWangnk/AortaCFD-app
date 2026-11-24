#!/usr/bin/env python3
"""Add the pressure along the descending leg at the two saved frames that bracket the instant of peak inflow to the
Ladder 2 and Ladder 3 statistics, so the drop across the narrowing and the lowest pressure in the jet can be read at
that instant (convergence_map.py interpolates between the two profiles). The saved frame nearest the peak misses
the instant by up to 8 ms, where the inertia of the fluid column still adds or takes about 1.4 mmHg across the
whole vessel. Light: two field reads per run.

Usage: python3 leg_peak_instant.py            (stats/, runs gallery_<mesh>)
       LADDER_STATS_DIR=<dir> LADDER_RUN_PREFIX=physio_ python3 leg_peak_instant.py
Writes the key leg_profile_bracket (t_star, and t, s_mm, p_mmHg of the two frames) into each stats JSON in place.
"""
import json

import numpy as np

import ladder_stats as ls
from convergence_map import peak_instant

ra, rc = ls.ra, ls.rc


def main():
    for level in ("L2", "L3"):
        for tag in ls.MESHES:
            name = f"ladder_{level}__gallery_{tag}"
            path = ls.OUT / f"{name}.json"
            r = json.loads(path.read_text())
            t_star, k0 = peak_instant(r)
            t = r["times"]
            run = ls.APP / "output" / f"ladder_{level}" / f"{ls.RUN_PREFIX}{tag}"
            meta = json.loads((ls.APP / "output/_ladder/bundles" / name / "meta.json").read_text())
            n_out = np.asarray(meta["caps"]["outlet1"]["normal"], float)
            up = -n_out / np.linalg.norm(n_out)
            c = rc.Case(next((run / "openfoam").glob("*.foam")))
            frames = []
            for k in (k0, k0 + 1):
                tk = min(c.times, key=lambda x: abs(x - t[k]))
                internal, wall, inlet, bnd = c.read(tk)
                s_mm, p_leg = ra.leg_profile(internal, bnd["outlet1"], up)
                frames.append(dict(t=float(tk), s_mm=[float(x) for x in s_mm], p_mmHg=[float(x) for x in p_leg]))
            r["leg_profile_bracket"] = dict(t_star=float(t_star), frames=frames)
            path.write_text(json.dumps(r, indent=1))
            print(f"{name}: peak instant {t_star:.4f} s between frames {frames[0]['t']:.3f} and {frames[1]['t']:.3f} s", flush=True)


if __name__ == "__main__":
    main()
