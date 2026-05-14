# scripts/

Utility scripts for AortaCFD users and maintainers. Split into two flavours:

## User-facing (top level)

| Script | What it does |
|---|---|
| [`install_windkessel_of12.sh`](install_windkessel_of12.sh) | Builds and installs the custom modularWKPressure boundary condition into `$FOAM_USER_LIBBIN`. Run once after sourcing OpenFOAM 12. |
| [`run_config_matrix.py`](run_config_matrix.py) | Drives a sweep of config variants against a fixed patient case and summarises solver outcomes. Use for validating a new release against a config matrix. Has a `--cool-down N` flag for thermal management on laptops. See `--help` for the full CLI. |

## HPC-only (`hpc/`)

Per-cluster orchestration. Read [`hpc/hpc.conf`](hpc/hpc.conf) first — it defines cluster login and paths.

| Script | What it does |
|---|---|
| [`hpc/upload.sh`](hpc/upload.sh) | Pushes a configured case to the HPC scratch directory. |
| [`hpc/status.sh`](hpc/status.sh) | Reports SLURM queue status for AortaCFD jobs. |
| [`hpc/download.sh`](hpc/download.sh) | Pulls results back from HPC to the local `output/` directory. |

If you don't have HPC access, you don't need any of `hpc/`.
