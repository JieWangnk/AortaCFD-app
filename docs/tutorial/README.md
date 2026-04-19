# AortaCFD Tutorial: Patient-Specific Aortic CFD with OpenFOAM

8-week course (2 hours/week) for PhD students with basic OpenFOAM experience.

## Prerequisites
- Basic OpenFOAM knowledge (run tutorials, understand case structure)
- Python basics
- WSL2 or Docker on Windows (or native Linux)

## Course Outline

| Wk | Topic | App Features | CFD Knowledge |
|----|-------|-------------|---------------|
| 1 | [Setup + First Run](SESSION1_SETUP_AND_FIRST_RUN.md) | run_patient.py, --steps, --quick | Cardiac cycle, why aortic CFD is different |
| 2 | [Case Anatomy](SESSION2_CASE_ANATOMY.md) | --update, provenance tracking | Windkessel R/C/Z, kinematic units |
| 3 | [Mesh Generation](SESSION3_MESH_GENERATION.md) | cells_per_diameter, regenerate-numerics, y+ | Boundary layers for WSS, mesh convergence |
| 4 | [Profiles + Solver](SESSION4_PROFILES_AND_SOLVER.md) | Profiles, physics advisor | Re number, transitional flow, limitations |
| 5 | [Inlet BCs](SESSION5_INLET_BCS.md) | All inlet types, inlet QC audit | Womersley number, profile impact |
| 6 | [Post-Processing](SESSION6_POSTPROCESSING.md) | --postprocess, QoI export | TAWSS/OSI/RRT clinical meaning |
| 7 | [New Patient Setup](SESSION7_NEW_PATIENT.md) | Full workflow, HPC, restart | BC choice from clinical data |
| 8 | [Advanced Topics](SESSION8_ADVANCED.md) | RANS, batch, GCI | Clinical applications, modelling assumptions |
| 9 | [LES Deep Dive](SESSION9_LES_DEEP_DIVE.md) | WALE, CFL, LUST schemes | Filtered NS, subgrid modelling, when LES is worth it |

## Pre-computed Results

For sessions where live simulations haven't completed, pre-computed results are
available in [`precomputed_results/`](precomputed_results/):

- `BPM120_hemodynamics_report.txt` — standard profile hemodynamics
- `BPM120_robust_hemodynamics.txt` — robust profile for comparison
- `BPM120_precise_hemodynamics.txt` — precise profile for comparison
- `profile_comparison.txt` — side-by-side profile comparison table
- `BPM120_setup_report.txt` — simulation configuration details

## Quick-Start Config for Tutorials

A coarse serial config is provided for quick demonstrations:
```bash
python run_patient.py BPM120 --config config_tutorial_coarse.json
```
This uses cpd=8, serial, robust profile — completes in ~30 minutes on a laptop.

## Teaching Philosophy

1. **Run first, understand second** — get a result in Session 1
2. **Break things intentionally** — best way to learn what parameters do
3. **Clinical context always** — every OpenFOAM parameter connects to clinical meaning
4. **Incremental complexity** — constant → pulsatile → Windkessel → MRI inlet
5. **Independence by Session 7** — student can set up their own case
