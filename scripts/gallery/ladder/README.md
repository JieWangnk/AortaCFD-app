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
- `make_physio_series.py`: writes the physiological waveforms, the twelve `config_physio_*`
  configurations and `../runs_ladder_physio.txt` (the second series, below).

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

## The physiological-waveform series (24 November 2026)

The first series (runs `gallery_*`, the U-bend waveform) has the cycle mean of an adult
aorta (5.0 L/min, Reynolds number 1000 at the mean, Womersley number 20) but a peak
Reynolds number of 3000 at the inlet, about half of physiological: the waveform ejects over
0.4 s with a 14.6 L/min peak, and a real heart ejects its stroke volume in about 0.3 s with
a peak of 20 to 25 L/min. At that peak the flow is a plug and the mid-plane figures looked
alike on every level. The second series keeps everything else (geometry, meshes, numerics,
Windkessel) and changes the waveform: `physio_inflow.csv` is a half-sine ejection over
0.30 s with a stroke volume of 66.7 mL (peak 20.9 L/min at 0.15 s, mean 5.0 L/min, zero
inflow for the rest of the 0.8 s cycle), and `physio_reversing_inflow.csv` (Ladder 3) adds
the same reverse lobe as before (a quarter of the peak, 0.12 s long, now 0.30 to 0.42 s;
mean 4.5 L/min). Peak Reynolds number 4300 at the inlet, 4800 in the descending leg, 6800
in the throat. The outlet backflow damping is `betaT` 0.3 and `betaN` 0.3 on every level in
this series: the steeper deceleration reverses part of the outlet on every level, and the
normal term is what kept the fine Ladder 3 mesh alive in the first series. Run names
`physio_<tag>`, run list `../runs_ladder_physio.txt` (the coarse Ladder 0 run first as a
ten-minute check of the setup, then the fine meshes), batch folder `output/_ladder_physio`:

```bash
systemd-run --user --unit=ocf-ladder --collect --working-directory="$PWD" \
  --setenv=RUNS="$PWD/scripts/gallery/runs_ladder_physio.txt" \
  --setenv=GALLERY_DIR="$PWD/output/_ladder_physio" bash scripts/gallery/run_gallery.sh
GALLERY_DIR="$PWD/output/_ladder_physio" bash scripts/gallery/ladder/wait_ladder.sh
LADDER_STATS_DIR=... LADDER_RUN_PREFIX=physio_ python3 scripts/gallery/ladder/ladder_stats.py
```

The first run of the series (coarse Ladder 0) solved in 2.3 minutes: inlet peak 21.1 L/min
at 0.149 s, mean 5.03 L/min, inertial pressure swing +22.5 / -23.5 mmHg between inlet and
outlet (the first series: +12 / -12), outlet pressure 81 to 135 mmHg over the cycle.

The batch ran 10:32 to 19:36 on 24 November 2026, all twelve runs clean (largest Courant
number 0.81 to 0.89, no pipeline flags, every run to its end time). Solver minutes per run,
coarse / mid / fine: L0 2.2 / 7.5 / 64, L1 2.9 / 8.6 / 47, L2 3.6 / 8.3 / 46, L3 10 / 24 / 145
(three cycles); about 17 % more than the first series, from the smaller time step of the
steeper waveform. The batch log shows 2.7 hours of wall time for the coarse Ladder 3 run
against 10 minutes of solver time: between 16:52 and 19:27 the machine was starved by a
runaway LaTeX build in another repository (see the solver log, ExecutionTime against
ClockTime); the results are unaffected. Statistics are in `stats_physio/`
(`LADDER_STATS_DIR`), the map in `physio_map.json`, `physio_map.csv` and
`physio_convergence_map.png` (`LADDER_MAP_PREFIX=physio_` for `convergence_map.py`). The
per-run JSON files in `stats_physio/` keep the `gallery_` names of the first series because
`convergence_map.py` reads them by that name; the `cells` field inside each file is the
physiological run's own.

Seventeen of the 56 classified cells of the map change class between the series. The
pressure difference at the frame nearest peak inflow goes from "not converged at 26" to
"converged at 12" on every level, a change that comes with the larger denominator rather
than a cleaner answer: that frame (0.144 s, 6 ms before the peak) sits on the inertial ramp,
where the difference across the vessel changes by 3.5 mmHg per 16 ms frame, so the value
there (3.5 mmHg on the bends) is about 60 % viscous loss and 40 % inertial residue. A better
reading of the viscous loss would interpolate the series to the instant of zero acceleration;
that change touches both series and the published pages, so it is left for a decision. The
other changes: the cycle-mean difference settles at 12 with the narrowing (0.59 and 0.53
mmHg) and stays open on the bends (0.17 and 0.19 mmHg); the jet's lowest pressure is open
on Ladder 3 as well now; the 99th-percentile shear at peak inflow is open on Ladder 3; the
TAWSS 99th percentile needs 18 on Ladders 2 and 3; the OSI threshold area (55 to 58 % of
the wall on every level, the zero-flow diastole oscillates the whole wall) is converged on
Ladder 1 and open on Ladder 0; the largest outlet backflow area (55 to 62 %, 100 % on
Ladder 3) is open on Ladders 1 and 2. The drop across the narrowing at peak inflow is 2.89
mmHg (2.56 times the first series' 1.13 mmHg for 1.43 times the peak flow) and rises 4.0 %
then 4.3 % across the meshes, formally within tolerance and still moving.
