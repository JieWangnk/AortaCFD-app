# Lesson 6 — Scale to HPC

Goal: submit a 50–100 case Sobol sweep to a SLURM cluster, monitor
progress, and pull results back. Same code, different runner.

## Prerequisites

- SSH access to a SLURM cluster (this lesson uses CSF3 at Manchester as the example; substitute your own)
- OpenFOAM 12 Foundation available as a module on the cluster
- Your AortaCFD-app cases already packaged (lesson 3) and validated locally on at least one case (lesson 1)

## Steps

### 1. Generate the sweep locally

```bash
cd ~/GitHub/aortacfd-geomgen
python cli.py --spec specs/sample_sobol_50.json --output /tmp/gen_sobol_50

cd ~/GitHub/AortaCFD-app
python -m scripts.package_cases /tmp/gen_sobol_50 \
    --config-template examples/templates/config_sweep_default.json \
    --output cases_input/sobol_50
```

### 2. Set up the cluster config

```bash
cp scripts/hpc/example_cluster.conf scripts/hpc/csf3.conf
$EDITOR scripts/hpc/csf3.conf
```

The four "things that vary between clusters":

- `HPC_HOST` — SSH alias from `~/.ssh/config` or hostname
- `HPC_SCRATCH` — your scratch directory on the cluster
- `HPC_PARTITION` — SLURM partition you can submit to
- `HPC_OF_MODULE` — exact OpenFOAM 12 module name (run `module avail openfoam` on the cluster)

Run the checklist at the bottom of the conf file before going further.

### 3. Generate the SLURM array script

```bash
python run_batch.py --cases-dir cases_input/sobol_50 \
    --slurm \
    --partition multicore_small \
    --time-limit 4:00:00 \
    --cpus-per-task 8 \
    --mem-per-cpu 4G \
    --cluster-conf scripts/hpc/csf3.conf
```

**`--cluster-conf` is critical** — without it, the generated `batch_submit.sh`
won't `module load openfoam/12` and every job will fail with
"`foamRun: command not found`". The script also activates `venv/`
if it's at the repo root, and `cd`s to `$SLURM_SUBMIT_DIR` so paths
work out.

**Need a different SLURM script shape?** If your cluster needs specific
`#SBATCH` directives (accounting, QoS, GPU partitions, custom MPI launcher),
pass a user template via `--slurm-template`:

```bash
cp scripts/hpc/template_slurm.example.sh scripts/hpc/my_cluster.template.sh
$EDITOR scripts/hpc/my_cluster.template.sh   # add --account, --qos, etc.

python run_batch.py --cases-dir cases_input/sobol_50 --slurm \
    --slurm-template scripts/hpc/my_cluster.template.sh \
    --cluster-conf scripts/hpc/my_cluster.conf \
    --partition my_partition --time-limit 4:00:00
```

The template uses `%%TOKEN%%` placeholders. Every variable defined in
your `--cluster-conf` is exposed as a token (so `HPC_ACCOUNT=foo` →
`%%HPC_ACCOUNT%%` in the template). See
[`scripts/hpc/README.md`](../../scripts/hpc/README.md#slurm-template-tokens)
for the full token list.

Inspect the result before submitting:

```bash
cat batch_submit.sh           # should see `module load apps/gcc/openfoam/12`
bash -n batch_submit.sh       # syntax-check (no execution)
```

### 4. Upload, submit, monitor

> **About `scripts/hpc/upload.sh`** — it's tuned for a *single* canonical
> patient run (reads `LOCAL_CASE_DIR` from the conf and rsyncs that ONE
> case dir). For a multi-case sweep, you need a slightly different
> upload: rsync the whole repo (or at least `cases_input/sev_*` plus
> the generated `batch_submit.sh`) to the cluster, then sbatch from
> the submission dir. The single-case `upload.sh` is right for the
> production canonical runs but not for sweeps.

```bash
# Manual batch upload (for a sweep) — adapt the host + remote path
rsync -avz --exclude='output/' --exclude='venv/' --exclude='__pycache__' \
    . csf3:~/scratch/AortaCFD-app/

# Submit (the script auto-detects SLURM_SUBMIT_DIR, so cd matters)
ssh csf3 "cd ~/scratch/AortaCFD-app && sbatch batch_submit.sh"

# Monitor from your laptop
bash scripts/hpc/status.sh scripts/hpc/csf3.conf

# Or:
ssh csf3 "squeue -u $USER"
```

### 5. Pull results back

```bash
bash scripts/hpc/download.sh scripts/hpc/csf3.conf
```

The results land in `output/sobol_50/*` exactly as if you'd run them
locally.

### 6. Aggregate

```bash
python -m scripts.compare_cohort output/sobol_50/
```

## Hybrid: local prep + HPC solver + local post

The flow above (steps 1–6) ships the whole repo to HPC and runs every
workflow step there (case setup, meshing, BCs, solver, reconstruct,
hemodynamics, postprocessing). That's simplest, but it means HPC needs
Python + scipy + all the package's pip deps, and you spend HPC compute
budget on the cheap steps (mesh + BCs take seconds; only the solver
benefits from parallel HPC).

For production runs (large meshes, hours of solver time) the cleaner
pattern is **prep locally, solve on HPC, post-process locally**. The
existing `--steps` and the new `--run-name` flags compose into this
without any new tool. All three phases write into the same
`output/<case>/<run_name>/` so the case dir round-trips intact.

```bash
# ── Phase 1: local prep (case dirs + mesh + BCs, no solver) ──
python run_batch.py --cases-dir cases_input/sobol_50 \
    --steps case,mesh,boundary \
    --run-name hpc_batch \
    --workers 4
# → output/<case>/hpc_batch/openfoam/ is now a ready-to-solve OpenFOAM case

# ── Phase 2a: upload prepped cases ──
bash scripts/hpc/sync_prepared_cases.sh up scripts/hpc/csf3.conf \
    output/sev_001/hpc_batch output/sev_002/hpc_batch ... output/sev_050/hpc_batch

# ── Phase 2b: generate solver-only SLURM script, submit, wait ──
python run_batch.py --cases-dir cases_input/sobol_50 \
    --slurm \
    --steps solver \
    --run-name hpc_batch \
    --partition multicore_small \
    --time-limit 4:00:00 \
    --cpus-per-task 8 \
    --cluster-conf scripts/hpc/csf3.conf

# Upload the generated batch_submit.sh + cases_input/ so the script can
# resolve case names, then submit. (Sketch — adapt paths to your cluster.)
rsync -avz batch_submit.sh cases_input/sobol_50 \
    csf3:~/scratch/AortaCFD-batch/

ssh csf3 "cd ~/scratch/AortaCFD-batch && sbatch batch_submit.sh"
bash scripts/hpc/status.sh scripts/hpc/csf3.conf      # poll until done

# ── Phase 2c: download solved cases back ──
bash scripts/hpc/sync_prepared_cases.sh down scripts/hpc/csf3.conf \
    output/sev_001/hpc_batch output/sev_002/hpc_batch ... output/sev_050/hpc_batch

# ── Phase 3: local post-process + aggregate ──
python run_batch.py --cases-dir cases_input/sobol_50 \
    --steps hemodynamics,post \
    --run-name hpc_batch \
    --workers 4

python -m scripts.compare_cohort output/sobol_50/
```

**Why this works**: `--run-name hpc_batch` makes every `run_batch.py`
invocation write into `output/<case>/hpc_batch/` instead of a new
`run_<timestamp>/`. Phase 1 creates the case and mesh there; Phase 2
adds the solver fields; Phase 3 reads everything back and produces the
QoI summary. The case dir is the unit of transfer between laptop and
cluster.

**When NOT to use the hybrid pattern**: small synthetic sweeps with
fast solves (workshop_quick template, ~95 s/case). The whole-thing-on-HPC
pattern is simpler and the round-trip overhead would dominate. The
hybrid pattern shines when each solver run is hours, not minutes.
```

→ `output/sobol_50/cohort_comparison.csv`, ready for the lesson 5
notebook.

## Resource-sizing rules of thumb

| Cases | Cores/case | Wall-time/case | Job wall-time | Total core-hours |
|---|---|---|---|---|
| 10 (test) | 8 | 1 h | 1 h | 80 |
| 50 (sweep) | 8 | 2 h | 2 h (with --array, all in parallel) | 800 |
| 100 (ML data) | 16 | 4 h | 4 h | 6400 |
| 1000 (PCE) | 16 | 4 h | 4 h | 64 000 |

Multiply by your numerics profile (LES ~10× standard).

## What can go wrong

| Symptom | Likely cause | Fix |
|---|---|---|
| `Could not resolve host` | SSH alias missing | Edit `~/.ssh/config` or use full hostname |
| `sbatch: error: invalid partition` | Wrong partition name | `sinfo` on cluster, fix `HPC_PARTITION` |
| `module: command not found` (in solver log) | Module system not initialised in job | Add `source /etc/profile.d/modules.sh` to job script header |
| Job runs but no output | Walltime too short | Bump `--time-limit`; check `seff <jobid>` for exit code |
| Quota exceeded | Scratch full | `du -sh ~/scratch/*`, archive completed cases off-scratch |

## Customisation

If your cluster has unusual constraints (GPU partitions, account
groups, QoS limits), the `scripts/hpc/example_cluster.conf` annotations
document where to add them. The actual SLURM script generator lives at
`run_batch.py::generate_slurm_script` if you need to extend it.

## Next

You now have the full workflow. The four blocks (geometry → package →
run → aggregate) compose into whatever automation level you want:

- **Manual**: run each block by hand, eyeball outputs at each stage
- **Scripted**: shell pipeline (see `composed_workflow.sh` in your spec dir)
- **Workflow tool**: wrap the four CLI commands in Snakemake / Nextflow / Hydra
  if your sweep grows beyond a few hundred cases
