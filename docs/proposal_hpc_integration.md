# Proposal: Native HPC Integration for AortaCFD

**Status:** Proposed
**Branch:** `feature/hpc-integration`
**Target Version:** v2.x

---

## Motivation

Currently, running AortaCFD on HPC requires manual steps: generating setup locally, copying files to HPC, writing a SLURM job script, submitting, and copying results back. This proposal adds native HPC support to `run_patient.py` so users can generate solver-ready job scripts directly.

---

## Proposed Changes

### 1. `--submit-hpc` Flag for `run_patient.py`

Add a new flag that, instead of running the solver locally, generates a SLURM job script:

```bash
# Setup + generate job script (solver NOT executed)
python run_patient.py PAT002 \
  --config config_repeatability.json \
  --output-id repeatability_demo \
  --step case --step mesh --step boundary \
  --submit-hpc
```

**Output:**
```
...
WORKFLOW COMPLETED SUCCESSFULLY!
Results: output/PAT002/repeatability_demo

HPC Job Script Generated:
  output/PAT002/repeatability_demo/job_solver.sh

Submit with:
  sbatch output/PAT002/repeatability_demo/job_solver.sh
```

### 2. HPC Configuration Section in `config.json`

```json
{
  "hpc": {
    "scheduler": "slurm",
    "partition": "multicore",
    "time_limit": "24:00:00",
    "ntasks": 8,
    "modules": [
      "openfoam/12-foss-2023a"
    ],
    "scratch_dir": "$SCRATCH",
    "account": null,
    "extra_sbatch": []
  }
}
```

### 3. Generated SLURM Job Script

The generated `job_solver.sh` would contain:

```bash
#!/bin/bash
#SBATCH --job-name=AortaCFD-PAT002-repeatability_demo
#SBATCH --partition=multicore
#SBATCH --ntasks=8
#SBATCH --cpus-per-task=1
#SBATCH --time=24:00:00
#SBATCH --output=output/PAT002/repeatability_demo/openfoam/logs/slurm_%j.log

# Load modules
module load openfoam/12-foss-2023a
source $FOAM_BASH

# Case directory
CASE_DIR=$(pwd)/output/PAT002/repeatability_demo/openfoam

echo "================================================"
echo "AortaCFD Solver Job"
echo "Case: $CASE_DIR"
echo "Processors: $SLURM_NTASKS"
echo "Started: $(date)"
echo "================================================"

# Decompose
decomposePar -force -case $CASE_DIR > $CASE_DIR/logs/log.decomposePar 2>&1

# Run solver
mpirun -np $SLURM_NTASKS foamRun -parallel -case $CASE_DIR > $CASE_DIR/logs/log.solver 2>&1

echo "================================================"
echo "Solver completed: $(date)"
echo "Reconstruct with:"
echo "  python run_patient.py PAT002 \\"
echo "    --case-dir $CASE_DIR \\"
echo "    --step reconstruct --step hemodynamics"
echo "================================================"
```

### 4. HPC Profile Presets

Support named HPC profiles for common clusters:

```json
{
  "hpc": {
    "profile": "csf4"
  }
}
```

Built-in profiles:
| Profile | Partition | Modules | Notes |
|---------|-----------|---------|-------|
| `csf4` | `multicore` | `openfoam/12-foss-2023a` | UoM CSF4 |
| `csf4-multi` | `multinode` | `openfoam/12-foss-2023a` | CSF4 multi-node (80+ cores) |
| `generic` | `compute` | (user-specified) | Generic SLURM cluster |

### 5. Optional: Auto-Submit

```bash
# Generate AND submit in one command
python run_patient.py PAT002 --submit-hpc --auto-submit
# Equivalent to: ... && sbatch job_solver.sh
```

---

## Implementation Plan

### Phase 1: Job Script Generation
- [ ] Add `--submit-hpc` flag to `cli.py`
- [ ] Add `hpc` section to config schema
- [ ] Create `src/aortacfd_lib/hpc_job_generator.py`
- [ ] Generate SLURM job script from config + case directory
- [ ] Add HPC profile presets (CSF4, generic)

### Phase 2: Workflow Integration
- [ ] When `--submit-hpc` is used, skip solver step automatically
- [ ] Generate reconstruction command in job script output
- [ ] Add `--auto-submit` flag for direct `sbatch` submission

### Phase 3: Multi-Node Support
- [ ] Support `multinode` partition (80+ cores on CSF4)
- [ ] Hostfile generation for multi-node MPI
- [ ] Decomposition method selection (scotch vs hierarchical)

### Phase 4: Job Monitoring (Optional)
- [ ] `python run_patient.py PAT002 --check-job` to poll SLURM status
- [ ] Auto-trigger reconstruct when job completes

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `src/aortacfd_lib/hpc_job_generator.py` | **Create** | SLURM script generator |
| `src/patient_runner/cli.py` | Modify | Add `--submit-hpc`, `--auto-submit` flags |
| `src/patient_runner/core.py` | Modify | HPC config handling, skip solver when HPC |
| `src/config/schema.py` | Modify | Add `hpc` section validation |
| `src/config/hpc_profiles.py` | **Create** | Built-in HPC cluster profiles |
| `tests/test_hpc_job_generator.py` | **Create** | Unit tests |

---

## Not In Scope (Future Work)

- Container-based execution (Singularity/Apptainer)
- Cloud HPC (AWS, Azure)
- Job dependency chains (mesh job -> solver job -> post job)
- Real-time log streaming from compute nodes
