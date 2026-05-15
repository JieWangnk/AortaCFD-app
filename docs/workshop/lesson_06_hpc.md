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
    --partition multicore \
    --time-limit 4:00:00 \
    --cpus-per-task 8 \
    --mem-per-cpu 4G
```

This writes `batch_submit.sh` with `#SBATCH --array=0-49`. Inspect it:

```bash
cat batch_submit.sh
```

### 4. Upload, submit, monitor

```bash
# Upload cases + scripts to the cluster
bash scripts/hpc/upload.sh scripts/hpc/csf3.conf

# Submit
ssh csf3 "cd ~/scratch && sbatch /path/to/AortaCFD-app/batch_submit.sh"

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
