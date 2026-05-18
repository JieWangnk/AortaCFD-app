# Slide deck outline — AortaCFD parametric study workshop

Content scaffold for a 15-18 slide deck. Each slide has: a title, the
bullet content (what's actually on the slide), and a "speaker notes"
hint (what you say). Designed to fit a 45-60 minute workshop slot
(20 min slides + 15 min embedded demo + 10 min Q&A).

Targets for visual polish: PowerPoint / Keynote / Marp / reveal.js — your
choice. The structure below is layout-agnostic. Screenshot placeholders
are marked `[FIG: ...]` so you know what image to drop where.

---

## SECTION 1 — Why are we here? (4 slides)

### Slide 1: Title

```
Reproducible parametric CFD for cardiovascular AI

AortaCFD-app + aortacfd-geomgen
Workshop, <date>
Jie Wang — University of Manchester
```

**Notes:** 30 seconds. Welcome people, your name, the two GitHub URLs.

---

### Slide 2: Why parametric CFD?

```
ONE case = anecdote
TEN  cases = sensitivity                   [FIG: pressure-drop vs severity, 10 dots]
HUNDRED cases = global statistics + Sobol indices
THOUSANDS = ML surrogate training data
```

**Notes:** This is the motivation slide. The progression is the argument
for why a *pipeline* matters more than any single well-meshed case.
Mention the downstream goal: feeding cardiovascular AI surrogate
models.

---

### Slide 3: What people usually do (and why it falls apart)

```
The DIY pipeline:
  for c in cases:
      cp template/ case_$c/                    ← config drift
      $EDITOR case_$c/config.json
      ./mesh.sh case_$c                        ← manual mesh QC
      ./solve.sh case_$c                       ← no resume, no parallelism
      python plot.py case_$c/results           ← no cohort view

→ At ~10 cases you're fine. At 50 you've lost track of which case had which params.
```

**Notes:** Be honest about the failure mode. This is what every CFD
researcher has done at some point. Set up the contrast for what
comes next.

---

### Slide 4: What we'll show today

```
1. Run one case          (10 min — confirm install)
2. Generate synthetic    (5 min — Blender sweep)
3. Package + batch       (10 min — local 10-case run)
4. Aggregate + analyse   (10 min — sensitivity)
5. Scale to HPC          (10 min — SLURM)

Goal: at the end you can do all five for your own geometry.
```

**Notes:** Promise mapping. Each lesson is independent — pick one and
follow.

---

## SECTION 2 — Architecture (3 slides)

### Slide 5: Four independent blocks

```
[FIG: 4-block architecture diagram — A → B → C → D]

A  Geometry    aortacfd-geomgen       (Blender, optional)
B  Packaging   scripts/package_cases  (drop config onto STLs)
C  Running    run_patient / run_batch (1 / N / HPC)
D  Aggregate   scripts/compare_cohort (CSV: params × QoI)

  No block knows about the others. Hand-off via filesystem.
```

**Notes:** This is the conceptual core. The "no Python imports between
blocks" is the discipline that makes the system composable. Each block
is a CLI tool you can run by hand.

---

### Slide 6: The case directory is the unit of work

```
cases_input/<case_id>/
  inlet.stl   outlet1..N.stl   wall_aorta.stl   ← geometry (Block A or yours)
  config.json                                   ← physics + numerics (Block B)
  case.meta.json                                ← provenance (sweep params, seed)

output/<case_id>/<run_name>/
  openfoam/                       ← mesh + fields + logs (Block C)
  reports/results/
    qoi_summary.json              ← QoIs (read by Block D)
  manifest.json                   ← status, git sha, wall_seconds
```

**Notes:** Show the directory layout once. Every later command refers
to this shape. The case dir round-trips between laptop and HPC.

---

### Slide 7: Three compute tiers, same code

```
Local single        python run_patient.py BPM120          ← debugging
Local parallel      run_batch.py --cases ... --workers N  ← workstation
HPC SLURM array     run_batch.py --slurm ...              ← cluster

  Same CLI everywhere. The runner doesn't know which tier it's in.
```

**Notes:** Important: the runner doesn't have HPC-specific code paths.
SLURM is just a script generator that wraps the same `run_patient.py`
loop.

---

## SECTION 3 — The customisation surface (3 slides)

### Slide 8: Discover what you can change

```
$ python cli.py --list-params              ← Block A
Available parameters (21):
  Main tube
    diameter            float  default=24.0  range=18-40  Main lumen diameter [mm]
    arch_span           float  default=70.0  range=55-90  Arch span [mm]
    ...

[FIG: screenshot of --list-params output, ~10 rows visible]

Same data in PARAMETERS.md (auto-generated).
```

**Notes:** Show how participants find what's tweakable. Avoid the trap
of reading source code or guessing parameter names.

---

### Slide 9: Three customisation recipes

```
A. Edit a spec file                      cp specs/sweep_severity.json mine.json
                                         $EDITOR mine.json

B. Override on the CLI (no file edits)   python cli.py --spec X --param diameter=28

C. Author a new spec from scratch        python cli.py --list-params
                                         (find the param) → write a spec
```

**Notes:** Three workflows for three comfort levels. The CLI override
is the demo-time live-tweak path.

---

### Slide 10: Robust by default

```
$ python cli.py --spec my_sweep.json --output out
Error: Unknown parameter 'diametr' in my_sweep.json.params.
       Did you mean 'diameter'?
       Run `python cli.py --list-params` for the full list.

[notice] This spec will produce 100 cases. Block A will take ~50 min.
         CFD on top adds ~1-2 min/case.

✓ typo detection with "did you mean"
✓ range validation (low < high, n ≥ 2)
✓ cost warning before launching
✓ no Python tracebacks for user errors
```

**Notes:** This is the "robust" half of the "robust + flexible"
handshake. Mistakes fail fast and helpfully.

---

## SECTION 4 — Live demo  (1 slide + embedded video)

### Slide 11: Live demo

```
[EMBED: docs/workshop/demo.recording.mp4  (10-15 min walkthrough)]

10 cases, severity 0% → 90%, in ~12 minutes.
Block A → Block B → Block C → Block D → ParaView.
```

**Notes:** Press play. Talk over the silent demo as it runs (or use a
pre-recorded narration). Highlight the moments worth pointing at:
- the spec being loaded
- 10 Blender subprocesses firing
- `--dry-run` showing the planned commands
- the cohort CSV appearing
- the sensitivity plot at the end

---

## SECTION 5 — Scaling up + closing (4 slides)

### Slide 12: HPC: one extra flag

```
Local:
  python run_batch.py --cases A B C --workers 4

HPC:
  python run_batch.py --cases A B C --slurm \
      --partition multicore_small \
      --cluster-conf scripts/hpc/csf3.conf

Generates batch_submit.sh with `#SBATCH --array=0-2`. Submit, monitor, download.
```

**Notes:** Show that going from local to HPC is one flag (plus a conf
file). No code refactor. No re-architecting the workflow.

---

### Slide 13: Different cluster? Use a template

```
%%KEY%% tokens in scripts/hpc/template_slurm.example.sh:

#SBATCH --account=%%HPC_ACCOUNT%%        ← from your conf
#SBATCH --array=0-%%ARRAY_MAX%%          ← from CLI
#SBATCH --partition=%%PARTITION%%        ← from CLI

%%CLUSTER_ENV_SETUP%%                    ← module load, source $foamDotFile

CASES=(%%CASES%%)
python run_patient.py "$CASE_ID" --steps %%STEPS%%%%RUN_NAME_FLAG%%
```

**Notes:** Briefly: every cluster is different (accounting, QoS,
GPU partitions, custom modules). The template + conf pattern means
you don't have to change the AortaCFD code to support a new cluster —
just drop a new .conf and .template.sh in `scripts/hpc/`.

---

### Slide 14: Two workshop tracks

```
TRACK A — "I have patients"                TRACK B — "I want synthetic data"
  Lesson 1: run one case                     Lessons 1-6 (whole thing)
  Lesson 4: run a batch                      
  Lesson 5: aggregate                        Includes Blender geometry
  Lesson 6: scale to HPC                     and Sobol sampling

  No need for aortacfd-geomgen.              Needs Blender + the sibling repo.
```

**Notes:** Important framing. Many CFD researchers only care about
their own patients; they shouldn't feel the synthetic-geometry track
is mandatory.

---

### Slide 15: Where to go next

```
docs/workshop/                            ← these lessons
docs/workshop/CHEATSHEET.md               ← one-page reference
docs/workshop/demo.sh                     ← one-shot end-to-end demo

GitHub
  AortaCFD-app          full pipeline + workshop
  aortacfd-geomgen      Blender geometry (Block A — optional)

Cite (Zenodo)
  10.5281/zenodo.20184620                 ← stable DOI per release
```

**Notes:** Last useful slide. Take a screenshot of the docs/workshop
landing page so people know what they're looking for.

---

### Slide 16: Acknowledgements + Q&A

```
Funded by: <funders>
Built on: OpenFOAM Foundation 12, Blender, scipy, SALib, ParaView

Questions?
  jie.wang-2@manchester.ac.uk
  github.com/JieWangnk
```

**Notes:** Standard close. Have a 17/18 backup slide with FAQs if you
expect technical questions about specific cluster setups.

---

## Backup slides (if Q&A demands)

### Slide 17 (backup): What's NOT in the workshop

```
Not yet (future work):
  - Full-field ML training export (currently: params → scalar QoIs)
  - Valve geometry integration (V1 tricuspid, V2 bicuspid)
  - Apptainer container for HPC reproducibility
  - GUI / web interface
```

### Slide 18 (backup): How small is the codebase?

```
AortaCFD-app:        ~25K LOC Python, 2240 tests passing
aortacfd-geomgen:    ~1500 LOC Python + 1 Blender script (~800 LOC), 42 tests passing
Workshop docs:       6 lesson markdowns + 1 notebook + 2 helper scripts
```

---

## Production checklist before workshop day

- [ ] Render slides to PDF + give yourself a backup copy on a USB stick
- [ ] Pre-record the demo (OBS) so you don't depend on live execution
- [ ] Test the laptop on the projector — colours, fonts, font size from back row
- [ ] Cheat sheet printed (one per attendee)
- [ ] Repo + sibling repo cloned on a clean shell before opening slide 11
- [ ] `/usr/bin/paraview` works on a fresh shell (NOT the OF12-bundled one)
- [ ] Pre-flight one HPC submission on csf3 — don't discover quirks live

## Effort breakdown

- 1-2 hours: drop the bullet content into your slide tool of choice, apply your template
- 1-2 hours: capture / edit the ~15 screenshots referenced as `[FIG: ...]`
- 30 min: record the embedded demo voice-over (one take, no need for cinema-quality)
- 30 min: dress rehearsal — talk through start to finish with a timer
