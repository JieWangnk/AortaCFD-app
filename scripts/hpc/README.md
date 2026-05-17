# HPC scripts

Helper scripts for transferring AortaCFD cases to a SLURM cluster,
monitoring status, and pulling results back.

The CFD pipeline does not know anything about your cluster — only two
files in this directory do:

1. **A cluster conf** (`<sitename>.conf`) — bash `KEY=VALUE` pairs
   defining the SSH host, scratch path, partition name, OpenFOAM
   module, etc. Read by the transfer scripts AND injected as
   substitution tokens into the SLURM job template.
2. **A SLURM template** (`<sitename>.template.sh`, optional) — the
   full job script with `%%TOKEN%%` placeholders. Only needed if the
   default template (in `run_batch.py::_DEFAULT_SLURM_TEMPLATE`)
   doesn't fit your cluster. See `template_slurm.example.sh` for a
   working starting point.

To run on a new cluster, copy
[`example_cluster.conf`](example_cluster.conf) to `<your_cluster>.conf`,
edit the four "things that vary between clusters" (SSH host, scratch
path, partition name, OpenFOAM module), then pass it to the helper
scripts. Add a `<your_cluster>.template.sh` only if you need to.

## Files

| File | What it does |
|---|---|
| `example_cluster.conf` | Annotated example — copy and edit for your cluster |
| `template_slurm.example.sh` | Starting-point SLURM template with %%TOKEN%% placeholders |
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
5. If your cluster needs custom `#SBATCH` directives (accounting,
   QoS, GPU partitions, custom modules), copy
   `template_slurm.example.sh` → `<sitename>.template.sh` and edit.
   Pass it as `--slurm-template scripts/hpc/<sitename>.template.sh`
   when you generate the job array.

## SLURM template tokens

`run_batch.py --slurm` substitutes the following `%%KEY%%` tokens in
the template (or the default one in `_DEFAULT_SLURM_TEMPLATE`).
Unknown bash `$VAR` references pass through untouched.

**Standard tokens** (always available):

| Token | What it becomes |
|---|---|
| `%%JOB_NAME%%` | `AortaCFD-batch` (default; configurable in code) |
| `%%ARRAY_MAX%%` | `N_cases - 1` (used in `#SBATCH --array=0-...`) |
| `%%N_CASES%%` | Number of cases in this batch |
| `%%PARTITION%%` | From `--partition` |
| `%%TIME_LIMIT%%` | From `--time-limit` |
| `%%CPUS_PER_TASK%%` | From `--cpus-per-task` |
| `%%MEM_PER_CPU%%` | From `--mem-per-cpu` |
| `%%CASES%%` | Bash-array literal: `"case_001" "case_002" ...` |
| `%%STEPS%%` | Workflow steps for `run_patient.py` |
| `%%CONFIG_FLAG%%` | Empty or ` --config <path>` |
| `%%GENERATED_AT%%` | ISO timestamp of generation |
| `%%CLUSTER_ENV_SETUP%%` | Auto-built `module load`/`source $foamDotFile` block from the conf — drop this token wherever you want the OpenFOAM env loaded |

**Cluster-conf tokens** — *every* key in your `<sitename>.conf` is
exposed as a token with the same name. So if your conf has
`HPC_ACCOUNT=myproject` then `%%HPC_ACCOUNT%%` substitutes to
`myproject`. Standard ones: `HPC_HOST`, `HPC_USER`, `HPC_SCRATCH`,
`HPC_PARTITION`, `HPC_NCORES`, `HPC_WALLTIME`, `HPC_OF_MODULE`,
`HPC_SOLVER`, `HPC_SOLVER_ARGS`. Add your own (`HPC_ACCOUNT`,
`HPC_QOS`, `HPC_RESERVATION`, ...) and reference them in your template.

## Pre-existing cluster confs in this repo

| Conf | Cluster | Notes |
|---|---|---|
| `hpc.conf` | csf3 (Manchester CSF3) | Default fallback |
| `hpc_G1.conf` ... `hpc_G6.conf` | csf3 | Per-case overrides for the G-series benchmark runs |

These are kept as references — feel free to use them as starting points
for your own conf, but do not assume their settings will work on your
cluster.
