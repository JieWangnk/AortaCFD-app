# The complexity ladder

Scripts behind the ladder cases `cases_input/ladder_L0` to `ladder_L3` and the
convergence map on the OpenCardioFlow site (Research, "The complexity ladder").
Four levels of flow complexity on one synthetic vessel, each at 12, 18 and 26 cells
across the inlet:

| Level | Added | Geometry (vascular geometry engine, aorta template, no branches) |
|---|---|---|
| L0 | nothing: the planar 180-degree bend with the U-bend's calibre and lengths | twist 0 |
| L1 | torsion | twist 108 degrees along the arch, rotated so the outlet cap faces -z |
| L2 | a narrowing | L1 with a 50 % area cosine coarctation, 30 mm long, 15 mm past the bend |
| L3 | a reversing inflow | the L2 geometry; waveform with a reverse lobe, three cycles |

## Scripts

- `build_cases.py`: builds the geometries with the engine (`vascular_geometry`), writes
  the STL files and the three configuration files per level from the U-bend gallery
  configs (only geometry, inflow and cycle count change). Needs the geometry engine on
  the Python path (`geometry-generation-trial`).
- `split_stl.py`: splits a closed engine STL into `wall_aorta.stl`, `inlet.stl` and
  `outlet1.stl`; `--align-outlet` rotates the geometry so the outlet cap is exactly
  axis-aligned and records the rotation in `geometry.meta.json`. A pressure outlet cap
  cut diagonally by snappyHexMesh gives sliver rim cells and a time-step collapse in
  diastole; a velocity inlet tolerates a tilt.
- `make_reversing_inflow.py`: writes `reversing_inflow.csv` (half-sine systole, a
  reverse lobe of -3.6 L/min peak from 0.40 to 0.52 s, a small forward flow to 0.8 s).
- `wait_ladder.sh`: waiter for the batch run as a user service; exits on the ALL_DONE
  marker, on a time-step collapse (deltaT under 1e-8 or Time not advancing between
  polls) or when the service dies.
- `ladder_stats.py`: reads the saved fields of each run (PyVista, through the site's
  `scripts/render_case.py`) and writes one JSON per run plus `stats/summary.csv`:
  inlet and outlet flow, pressure difference over the cycle (area means on the two
  planes), peak speed, wall shear at peak inflow, TAWSS and OSI area-weighted with a
  4 mm band off each cap left out, outlet backflow area, and the pressure profile along
  the descending leg at peak inflow.
- `convergence_map.py`: classifies every quantity per level by its 12-to-18 and
  18-to-26 changes relative to the 26-cell value (tolerance 5 %) and draws
  `convergence_map.png`; also writes `map.json` and `map.csv`.
- `bc_test.sh`: restart test of the outlet backflow damping on the stalled 26-cell
  Ladder 3 run (copies the decomposed case at a saved time, sets `betaT`/`betaN` in every
  processor's `U` file, runs the solver on 4 cores and stops it on a time-step collapse).
- `compare_damping.py`: tables the effect of the normal damping on the Ladder 3
  statistics (damped `stats/` against damping-off `stats_nodamp/`, written by
  `ladder_stats.py` with `LADDER_STATS_DIR` and `LADDER_RUN_PREFIX=nodamp_`).
- `../runs_ladder_L3_rerun.txt`: the run list of the repeated Ladder 3 batch (fine
  mesh first, so a late failure shows within two hours).

## Running the ladder

```bash
cd AortaCFD-app && source venv/bin/activate && source /opt/openfoam12/etc/bashrc
RUNS=scripts/gallery/runs_ladder.txt GALLERY_DIR=output/_ladder bash scripts/gallery/run_gallery.sh
```

or one run at a time:

```bash
python run_patient.py ladder_L2 --config cases_input/ladder_L2/config_gallery_mid_span18.json
```

The batch of 23 November 2026 took 4.6 hours of solver time on 4 laptop cores for the
twelve runs. The first Ladder 3 batch ran before the inlet mapping kept the sign of a
reverse flow rate (fixed 24 November 2026, commit "Keep the sign of a reverse inflow in
the inlet mapping"); the three Ladder 3 runs were repeated after the fix.

## Outlet backflow damping on Ladder 3

With the reverse lobe the whole outlet takes in fluid for about 0.1 s per cycle. The
outlet velocity condition `stabilizedWindkesselVelocity` damps only the tangential part
of a backflow by default (`betaT` 0.3, `betaN` 0). On the 26-cell mesh the normal inflow
in the first boundary-layer cell at the wall/cap corner of the outlet grew without bound
(1.5 m/s against a mean reverse speed of 0.13 m/s at t = 0.464 s) and the time step
collapsed at t = 0.468 s of the first cycle; the 12- and 18-cell meshes damped it
numerically. A restart of the fine case from 0.432 s with `betaN` 0.3 ran through the
lobe with a smooth inflow, so the three Ladder 3 configurations set `betaT` 0.3 and
`betaN` 0.3 (`windkessel_settings`), and all three runs were repeated with it on
24 November 2026 (fine mesh first). Levels 0 to 2 keep the default `betaN` 0; their
outlet backflow covers part of the outlet only.

Two things to keep in mind when reading Ladder 3 fields: the velocity written on the
outlet faces during inflow is the damped blend, so an outlet flow rate summed from face
velocities reads about 7 % low in the lobe (`ladder_stats.py` records the inlet flow rate
as the flow record); and during the lobe the inlet acts as an outlet with a forced
parabolic exit profile, which squeezes the arriving flow into that shape within one cell
(0.8 to 0.9 m/s in the cells beside the inlet against 0.2 m/s on the face, on every mesh).
