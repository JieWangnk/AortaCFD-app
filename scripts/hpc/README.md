# HPC scripts

Helper scripts for transferring AortaCFD cases to a SLURM cluster,
monitoring status, and pulling results back.

The CFD pipeline does not know anything about your cluster — only the
config file in this directory does. To run on a new cluster, copy
[`example_cluster.conf`](example_cluster.conf) to `<your_cluster>.conf`,
edit the four "things that vary between clusters" (SSH host, scratch
path, partition name, OpenFOAM module), then pass it to the helper
scripts.

## Files

| File | What it does |
|---|---|
| `example_cluster.conf` | Annotated example — copy and edit for your cluster |
| `hpc.conf` | Default config (used if no explicit path is passed). Currently configured for `csf3`. |
| `upload.sh [conf]` | rsync the local OpenFOAM case to `$HPC_SCRATCH` on the cluster |
| `status.sh [conf]` | SSH in, poll the SLURM queue + tail solver log |
| `download.sh [conf]` | rsync the cluster results back to the local `output/` dir |

## Typical workflow

```bash
# 1. Generate the SLURM job-array script for a batch of cases
python run_batch.py --cases sobol_demo_001 sobol_demo_002 ... --slurm --partition multicore
# -> writes batch_submit.sh

# 2. (Optional) Copy the per-cluster conf
cp scripts/hpc/example_cluster.conf scripts/hpc/csf3.conf
$EDITOR scripts/hpc/csf3.conf

# 3. Upload cases to the cluster
bash scripts/hpc/upload.sh scripts/hpc/csf3.conf

# 4. SSH in and submit
ssh csf3
cd ~/scratch
sbatch /path/to/batch_submit.sh

# 5. From your laptop, monitor progress
bash scripts/hpc/status.sh scripts/hpc/csf3.conf

# 6. When done, pull results back
bash scripts/hpc/download.sh scripts/hpc/csf3.conf

# 7. Aggregate the cohort
python -m scripts.compare_cohort output/
```

## How to adapt to a new cluster

1. Run `module avail openfoam` on the cluster to find the exact module name
2. Run `sinfo -o "%P %D %c %l"` to find available partitions, their core counts, and walltime limits
3. Run `myquota` or `df -h ~` to find your scratch path
4. Copy `example_cluster.conf` → `<sitename>.conf`, fill in the four
   variables, commit it to a private branch (the conf is not in the
   production graph — it's a user file).

## Pre-existing cluster confs in this repo

| Conf | Cluster | Notes |
|---|---|---|
| `hpc.conf` | csf3 (Manchester CSF3) | Default fallback |
| `hpc_G1.conf` ... `hpc_G6.conf` | csf3 | Per-case overrides for the G-series benchmark runs |

These are kept as references — feel free to use them as starting points
for your own conf, but do not assume their settings will work on your
cluster.
