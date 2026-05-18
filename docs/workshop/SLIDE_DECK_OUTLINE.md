# Slide deck outline — AortaCFD parametric study workshop

Content scaffold for a ~20-slide deck modelled on Muhammad Ahmad Raza's
*"Implementation of Lumped Parameter Network Boundary Conditions ..."*
(OSCFD2024, Chalmers University). Same visual language, our content.

Designed for a 45-60 minute workshop slot
(~25 min slides + ~15 min embedded demo + ~10 min Q&A).

Each slide entry has: a **title**, the **bullet content** (what's on
the slide), and **speaker notes** (what you say). Figure placeholders
are `[FIG: ...]`. Each numbered figure maps to a file in
`~/Pictures/aortacfd-workshop/`.

---

## Visual design (match Raza's style)

| Element | Specification |
|---|---|
| **Title font** | Serif — Computer Modern, Cambria, or Bookman Old Style. Centered. ~28–32 pt. |
| **Body font** | Same serif family. ~16–20 pt. Black on white. |
| **Bullet markers** | `•` for level 1, `o` for level 2 (Raza uses these literal characters) |
| **Title underline** | Red horizontal rule (~3 pt) under the *title slide* title only |
| **Course banner** (title slide) | Small caps, blue (~RGB 30, 70, 140): "AORTACFD WORKSHOP — A HANDS-ON PARAMETRIC STUDY". Cardiovascular CFD theme. |
| **Footer separator** | Thin black horizontal rule across all content slides (~1.5 pt) |
| **Footer text — left** | Italic blue: `AortaCFD Workshop | Jie Wang` |
| **Footer text — right** | Bold italic blue: workshop date (e.g. `21/05/2026`) |
| **Page number** | Black filled circle (~28 pt diameter), white number inside, bottom-right corner |
| **Layout** | Bullets on left, figure on right (60/40 split). Generous whitespace. |
| **Colour palette** | Blue `#1E468C`, red `#C02020`, black, white. No other colours except in figures. |

If using PowerPoint, set up a master slide with:
- title placeholder centered, serif
- footer rule + left/right text boxes + page-number circle
- content area for bullets + figure

If using Beamer (LaTeX, which is what Raza actually used), the
`Frankfurt` or `Madrid` theme with `\setbeamercolor` overrides gets
close out of the box.

---

## SECTION 1 — Title + clinical motivation (4 slides)

### Slide 1 — Title

```
[course banner, small caps blue]
AORTACFD WORKSHOP
A HANDS-ON PARAMETRIC STUDY USING OPENFOAM 12

[main title, serif, black, centered]
Reproducible Patient-Specific Aortic CFD
with the AortaCFD Pipeline

[red horizontal rule]

[author, serif italic, blue]
Jie Wang, PhD

[affiliation, serif, black]
Department of <X>,
The University of Manchester
jie.wang-2@manchester.ac.uk

[logos row: University of Manchester, OpenFOAM Foundation, Zenodo DOI badge]

[date, bottom-right, bold italic blue]
21/05/2026
```

**Notes:** 30 seconds. Welcome, your name, the GitHub repo URL on the
back of the cheat sheet they'll receive.

---

### Slide 2 — Aortic Anatomy

```
[FIG 2 right side: aortic-arch anatomy diagram with branches labelled —
generic medical illustration, similar to Raza's heart figure]

• The aorta is the largest artery in the body
    o Ascending aorta → arch → descending aorta
    o Three supra-aortic branches: brachiocephalic, left common carotid, left subclavian
    o Diameter: ~24–36 mm in adults, smaller in paediatric cases

• Pulsatile flow, ~5 L/min cardiac output at rest
    o Reynolds number ~1500–4000 (transitional to mild turbulence)
    o Womersley number ~10–15 (strongly unsteady)

• Hemodynamic role
    o Distributes oxygenated blood to systemic circulation
    o "Windkessel" effect: elastic walls smooth pulsatile flow

• Pathologies of interest
    o Coarctation, aneurysm, dissection, valve disease
```

**Notes:** Set the medical context. Most workshop attendees will be CFD
or ML people without clinical background. Don't dwell — 2 minutes.

---

### Slide 3 — Aortic Coarctation

```
[FIG 3 right side: coarctation diagram showing narrowing, distal flow
reduction. Could use a CT slice or schematic.]

• Congenital narrowing of the aorta, typically at the isthmus
    o Affects 5–8 of every 10,000 live births
    o Distal to the left subclavian artery in most cases

• Hemodynamic consequence
    o Pressure drop across the stenosis
    o Reduced perfusion of lower body
    o Increased afterload on the left ventricle

• Severity classification
    o Mild: <30% area reduction, no intervention
    o Moderate: 30–70% area reduction, surveillance
    o Severe: >70% area reduction, surgical/catheter repair

• Clinical question CFD can help answer
    o Is the pressure drop large enough to justify intervention?
    o How will repair (stent/surgery) restore physiological flow?
```

**Notes:** Coarctation is the workshop's running example because it's
geometry-dominated → cleanly parametric. Mention BPM120 (the canonical
case shipped with the repo) as a published coarctation example.

---

### Slide 4 — Why Patient-Specific CFD?

```
• Imaging gives anatomy, not hemodynamics
    o CT/MRI shows the geometry
    o Pressure drop, wall shear stress, oscillatory shear: not directly measurable

• Clinical 4D-flow MRI is expensive + slow
    o ~30 min scan time, ~1 mm spatial resolution
    o Limited temporal resolution at peak systole

• In silico hemodynamic assessment
    o Reproducible, deterministic
    o Per-patient turnaround currently hours; not yet point-of-care
    o ML surrogates trained on CFD data: a path to real-time

• What this workshop is about
    o Going from a single case to many cases — sensitivity, statistics, ML training data
    o Doing it reproducibly + on whatever compute scale you have
```

**Notes:** Pivot from clinical to computational. Set up the next
section's question: how do you go from one CFD case to many?

---

## SECTION 2 — From one case to many (3 slides)

### Slide 5 — The DIY Parametric Study Trap

```
• Manual pipeline most people start with
    o for c in cases: cp template/ case_$c/
    o    $EDITOR case_$c/config.json     ← config drift starts here
    o    ./mesh.sh case_$c                ← manual mesh QC, no record
    o    ./solve.sh case_$c               ← no parallelism, no resume
    o    python plot.py case_$c/result    ← no cohort view

• Fails at scale
    o 10 cases:  fine
    o 50 cases:  you've lost track of which had which parameters
    o 500 cases: every case has been hand-modified at least once

• The hidden tax
    o Reproducibility: not git-tracked, not citeable
    o Provenance: which mesh produced which QoI?
    o Compute waste: solver runs you forgot about
```

**Notes:** Be honest — every researcher in the room has been here.
This is the contrast that sets up our pipeline as the alternative.

---

### Slide 6 — AortaCFD Pipeline Overview

```
[FIG 5 (architecture diagram): full-width 4-block flow]
[rendered from ~/Pictures/aortacfd-workshop/02_architecture.mmd]

• Four composable blocks, filesystem hand-off, no Python imports between them
    o A — Geometry  (aortacfd-geomgen, Blender)
    o B — Packaging (config templates onto STL folders)
    o C — Running   (1 / N / HPC, same code path)
    o D — Aggregate (cohort CSV: params × QoIs)

• Each block is a CLI tool
    o Use one in isolation, or compose all four
    o No framework lock-in (no Snakemake/Hydra/Airflow required)

• Hand-off is by directories
    o A produces  generated/<case>/  with split STLs + metadata
    o B consumes  generated/, produces cases_input/<case>/  with config
    o C consumes  cases_input/, produces  output/<case>/run_*/
    o D consumes  output/, produces  cohort_comparison.csv
```

**Notes:** This is the conceptual core. The "no imports between
blocks" is the discipline that makes the system composable. Highlight
that Block A is *optional* (you can bring your own STLs).

---

### Slide 7 — The Case Directory is the Unit of Work

```
[FIG 6a left: cases_input/BPM120/ listing]
[FIG 6b right: output/<case>/run_<ts>/ tree]

• Input contract
    o cases_input/<case_id>/
    o   inlet.stl, outlet1..N.stl, wall_aorta.stl      ← geometry
    o   config.json                                    ← physics + numerics
    o   case.meta.json                                 ← provenance (sweep params)

• Output contract
    o output/<case_id>/<run_name>/
    o   openfoam/                       ← mesh + fields + logs
    o   reports/results/qoi_summary.json  ← read by Block D
    o   manifest.json                   ← status, git sha, wall_seconds

• The case dir round-trips between laptop and HPC
    o --run-name <X> makes the dir stable across phases
    o Same shape regardless of where it's run
```

**Notes:** Show the directory layout once. Every later command refers
to this shape. Two key things to point at: `case.meta.json` (where
sweep params live) and `qoi_summary.json` (the harvest target).

---

## SECTION 3 — Tools in the pipeline (4 slides)

### Slide 8 — Block A: Parametric Geometry

```
[FIG 4 right: --list-params terminal screenshot]

• Blender-driven aortic-arch generator
    o 21 anatomic parameters: diameter, arch_height, coarctation_*, branch_*
    o Three sampling modes
        ▸ single: one geometry from explicit values
        ▸ sweep:  N linear steps of one parameter
        ▸ sample: Sobol / LHS / random over multiple parameters
        ▸ grid:   explicit cartesian product

• Discoverability
    o python cli.py --list-params       (terminal)
    o PARAMETERS.md                     (markdown reference)

• Reproducibility
    o spec JSON is the experiment definition
    o seed + sampler + params → bit-identical output
    o geometry.meta.json records every choice + patch checksums
```

**Notes:** This slide is the "your sweep is defined by one JSON" pitch.
Show 04_list_params.png at right.

---

### Slide 9 — Customisation: Three Recipes

```
[FIG 5 right: 05_param_override.txt as styled terminal block]

• Recipe A — edit a spec file
    o cp specs/sweep_severity.json mine.json
    o $EDITOR mine.json     ← change sweep.high, fixed.diameter, etc.
    o python cli.py --spec mine.json --output ...

• Recipe B — override at the command line, no file edits
    o python cli.py --spec sweep_severity.json \
                    --param diameter=28 --param arch_height=42 \
                    --output ...

• Recipe C — author a new sweep from scratch
    o python cli.py --list-params           ← find param names
    o copy the closest example spec, edit ranges, run
```

**Notes:** Three workflows for three comfort levels. Recipe B is the
demo-time live-tweak path ("watch what happens with a bigger arch
height").

---

### Slide 10 — Robust by Default

```
[FIG 6 right: 06_validator_typo.txt — the "Did you mean 'diameter'?" error]
[FIG 7 below 6: 07_cost_warning.txt — the [notice] case-count warning]

• Validation at spec-load time
    o Unknown parameter? difflib suggestion ("Did you mean 'diameter'?")
    o sweep.low ≥ sweep.high? clear error before launching
    o n_cases < 4 in sample mode? rejected
    o no Python traceback for user errors — exit code 2 + message

• Cost estimate before launching
    o [notice] block lists case count + estimated wall-clock
    o Prevents accidental 1000-case runs

• No silent fallbacks
    o If the spec is ambiguous, raise at config-build time
    o Avoids the FPE-at-hour-17 failure mode
```

**Notes:** This is the "robust" half of the "robust + flexible"
handshake. Mistakes fail fast and helpfully. Quote the
"Did you mean 'diameter'?" line out loud.

---

### Slide 11 — Block B + Block D: Packaging and Aggregation

```
[FIG right: small architecture inset focused on B + D]

• Block B — package_cases.py
    o Stamps a config template onto a folder of generated cases
    o Templates ship for three regimes
        ▸ config_workshop_quick     — laptop demo, 95 s/case
        ▸ config_sweep_default      — production sweep
        ▸ config_les_precise        — LES research
    o Reads geometry.meta.json, writes case.meta.json combining both

• Block D — compare_cohort.py
    o Walks output/<case>/run_*/results/qoi_summary.json
    o Joins with case.meta.json and run manifest
    o Writes cohort_comparison.csv (params × QoIs, one row per case)
    o Tolerates failures: cases with no qoi_summary get a NaN row
```

**Notes:** Brief — these blocks are "simple plumbing that makes the
rest of the pipeline reproducible". Don't dwell.

---

## SECTION 4 — Running at scale (3 slides)

### Slide 12 — Three Compute Tiers, Same Code Path

```
[FIG 8 right: 08_local_vs_slurm.txt — three command forms]

• Local single case (debugging)
    o python run_patient.py BPM120

• Local parallel (workstation)
    o python run_batch.py --cases A B C --workers N
    o N cases run concurrently; each uses its config's subdomain count

• HPC SLURM job array
    o python run_batch.py --cases A B C --slurm \
                          --partition multicore_small \
                          --cluster-conf scripts/hpc/csf3.conf

• The runner doesn't know which tier it's in
    o Same CLI everywhere
    o --slurm just emits a job-array script that wraps the same loop
```

**Notes:** Important: there's no HPC-specific code in the runner.
SLURM is just a script generator that wraps the same per-case loop.

---

### Slide 13 — HPC: One Extra Flag

```
[FIG 9 right: 09_slurm_script.txt — generated batch_submit.sh head]

• --cluster-conf injects the cluster's OpenFOAM module
    o Reads HPC_OF_MODULE from scripts/hpc/<sitename>.conf
    o Adds `module load apps/gcc/openfoam/12` to the generated script
    o Sources $foamDotFile
    o Activates the local venv if present
    o Fail-fast guard: errors if foamRun is not on PATH

• Generated batch_submit.sh
    o #SBATCH --array=0-N for one task per case
    o cd $SLURM_SUBMIT_DIR; source venv; module load; python run_patient.py
    o Logs to output/slurm_%A_%a.log
```

**Notes:** Stress that the cluster-conf is the "things that vary
between clusters" file (SSH host, partition, walltime, module). The
runner stays cluster-agnostic.

---

### Slide 14 — Different Cluster? Template + Conf

```
[FIG 10 right: 10_slurm_template.txt — template with %%TOKEN%% placeholders]

• %%TOKEN%% substitution in user templates
    o Every cluster-conf key auto-exposed as %%KEY%%
    o HPC_ACCOUNT=myproject → %%HPC_ACCOUNT%% in template
    o Standard tokens: %%PARTITION%%, %%ARRAY_MAX%%, %%CASES%%, ...

• Adding a new cluster
    o cp example_cluster.conf <sitename>.conf      ← edit 4 vars
    o (only if needed) cp template_slurm.example.sh <sitename>.template.sh
    o python run_batch.py --slurm \
        --cluster-conf scripts/hpc/<sitename>.conf \
        --slurm-template scripts/hpc/<sitename>.template.sh

• Hybrid workflows
    o Local prep + HPC solve + local post via --run-name X + --steps
    o Round-trips the case dir between laptop and cluster
```

**Notes:** Don't deep-dive — this is for power users. Mention briefly,
point at lesson 6 for the details.

---

## SECTION 5 — Live demo (1 slide + embedded video)

### Slide 15 — Live Demo

```
[FIG 11: 10–15 min embedded video — docs/workshop/demo.recording.mp4]
[FIG 1 below the video — severity_sweep.png, the finale plot]

• 10 cases, severity 0% → 90%, ~12 minutes wall-clock
• Block A (Blender) → B (package) → C (run --workers 2) → D (cohort CSV) → plot
• Same workflow runs locally and on HPC
```

**Notes:** Press play. Talk over the silent demo as it runs. Call out
the moments worth pointing at:
- spec being loaded
- 10 Blender subprocesses firing
- --dry-run showing the planned commands
- cohort CSV appearing
- the sensitivity plot at the end
This is where the slides hand off to the *artefact* — let the
recording carry the next 10 minutes.

---

## SECTION 6 — Closing (4 slides)

### Slide 16 — Workshop Tracks

```
TRACK A — "I have patients"             TRACK B — "I want synthetic data"
  Lesson 1: run one case                  Lessons 1–6 (whole pipeline)
  Lesson 4: run a batch                   
  Lesson 5: aggregate                     Includes Blender geometry
  Lesson 6: scale to HPC                  + Sobol sampling

  No need for aortacfd-geomgen.           Needs Blender + the sibling repo.
```

**Notes:** Important framing. Many CFD researchers only care about
their own patients; they shouldn't feel the synthetic track is
mandatory. Track A users can skip Blender entirely.

---

### Slide 17 — Where to Go Next

```
[FIG 11 right: 11_workshop_dir.txt — docs/workshop/ listing]

• Workshop materials
    o docs/workshop/                  ← 6 lessons + notebook + demo.sh
    o docs/workshop/CHEATSHEET.md     ← one-page reference (printed handout)

• GitHub
    o JieWangnk/AortaCFD-app          ← main pipeline + workshop docs
    o JieWangnk/aortacfd-geomgen      ← Blender geometry (optional)

• Citation (Zenodo)
    o 10.5281/zenodo.20184620         ← stable DOI per release
    o See CITATION.cff for BibTeX
```

**Notes:** Last useful slide. Make sure participants get the
cheat-sheet handout — that's the most reliable take-home artefact.

---

### Slide 18 — Acknowledgements

```
• Funded by
    o <your funder(s)>

• Built on
    o OpenFOAM Foundation 12
    o Blender (geometry generation)
    o scipy + SALib (sampling + sensitivity)
    o ParaView (visualisation)

• Thanks to
    o The published BPM120 case (Wang et al.)
    o SimVascular VMR (0014_H_AO_COA case)
    o Anyone else who contributed data, ideas, or feedback
```

**Notes:** Standard close.

---

### Slide 19 — Questions

```
[Large blue text, centred]
Questions?

[Below, smaller]
jie.wang-2@manchester.ac.uk
github.com/JieWangnk/AortaCFD-app
github.com/JieWangnk/aortacfd-geomgen
```

**Notes:** Default to 10 minutes for Q&A. Have backup slides ready.

---

## Backup slides (if Q&A demands them)

### Slide B1 — What's NOT in the workshop

```
Not yet (future work):
    o Full-field ML training export (currently: params → scalar QoIs)
    o Valve geometry integration (V1 tricuspid, V2 bicuspid)
    o Apptainer container for HPC reproducibility
    o Web/GUI interface
```

### Slide B2 — Tests + Reproducibility

```
• AortaCFD-app:     2,258 tests, 0 regressions across releases
• aortacfd-geomgen: 42 tests covering samplers + validator + grid mode
• CI: GitHub Actions on every PR
• Every release archived on Zenodo with DOI
• Spec files committed alongside results → bit-reproducible sweeps
```

### Slide B3 — Hybrid local/HPC workflow

```
• Phase 1 (laptop):   --steps case,mesh,boundary --run-name hpc_batch
• Phase 2 (cluster):  --slurm --steps solver --run-name hpc_batch
• Phase 3 (laptop):   --steps hemodynamics,post --run-name hpc_batch
                     + compare_cohort

  Same output/<case>/hpc_batch/ dir round-trips between machines.
  Best for production runs (hours of solver, fast local prep).
```

---

## Mapping: slide → screenshot file

| Slide | Figure file (in `~/Pictures/aortacfd-workshop/`) |
|---|---|
| 1 | Title slide artwork — you compose in PowerPoint with the logos |
| 2 | Aortic anatomy diagram — find/license one (Wikipedia Commons has good ones) |
| 3 | Coarctation diagram — same source |
| 4 | (no figure, all text) |
| 5 | (no figure, all text) |
| 6 | `02_architecture.mmd` (render via mermaid.live → PNG) |
| 7 | `03a_case_input_tree.txt` + `03b_case_output_tree.txt` |
| 8 | `04_list_params.txt` |
| 9 | `05_param_override.txt` |
| 10 | `06_validator_typo.txt` + `07_cost_warning.txt` |
| 11 | (small architecture inset — crop slide 6 figure) |
| 12 | `08_local_vs_slurm.txt` |
| 13 | `09_slurm_script.txt` |
| 14 | `10_slurm_template.txt` |
| 15 | embedded video + `01_severity_sweep.png` |
| 16 | (table, no figure) |
| 17 | `11_workshop_dir.txt` |
| 18 | (logos row, like title slide) |
| 19 | (text only) |

---

## Production checklist before workshop day

- [ ] Render slides to PDF + give yourself a backup copy on a USB stick
- [ ] Pre-record the demo (OBS) so you don't depend on live execution
- [ ] Test the laptop on the projector — colours, fonts, font size from back row
- [ ] Cheat sheet printed (one per attendee + 5 spare)
- [ ] Repo + sibling repo cloned on a clean shell before opening slide 15
- [ ] `/usr/bin/paraview` works on a fresh shell (NOT the OF12-bundled one)
- [ ] Pre-flight one HPC submission on csf3 — don't discover quirks live

## Effort breakdown

- 30 min: source two medical figures (slides 2, 3) — Wikipedia Commons /
  open anatomy resources, check licence before using
- 1-2 hours: drop the bullet content into PowerPoint, apply your serif theme
- 30 min: capture the terminal-style screenshots from the `.txt` files
  in the kit
- 30 min: render the architecture diagram from `02_architecture.mmd`
- 30 min: record the embedded demo voice-over (one take, no need for
  cinema-quality)
- 30 min: dress rehearsal — talk through start to finish with a timer

Total: 4-6 hours of focused work after the kit is staged.
