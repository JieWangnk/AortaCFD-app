# Session 7: Setting Up a New Patient Case

**Duration:** 2 hours
**Goal:** Full independence — set up a case from scratch

---

## Hour 1: Case Setup from Scratch (60 min)

### 1.1 What You Need (5 min)

To run AortaCFD on a new patient, you need:

1. **STL geometry files** — separate patches for inlet, outlets, wall
2. **Clinical data** — at minimum: blood pressure (systolic/diastolic)
3. **Flow data** — cardiac output (L/min) or a flow waveform CSV

### 1.2 STL File Naming Convention (10 min)

```
cases_input/MY_CASE/
├── inlet.stl           # Must contain "inlet" in filename
├── outlet1.stl         # Must contain "outlet" + number
├── outlet2.stl
├── outlet3.stl
├── wall_aorta.stl      # Must contain "wall" in filename
├── config.json         # Your configuration
└── flowrate.csv        # (optional) pulsatile flow waveform
```

**Rules:**
- STL files should be in millimetres (scale_factor: 0.001 converts to metres)
- Or centimetres for SimVascular geometry (scale_factor: 0.01)
- Patch names in config must match STL filenames (without .stl)
- Outlets must be numbered sequentially

### 1.3 Writing config.json from Scratch (20 min)

Start from the minimal template:

```bash
cp examples/config_minimal.json cases_input/MY_CASE/config.json
```

Edit the essential fields:

```json
{
  "case_info": {
    "patient_id": "MY_CASE",
    "description": "My first patient case"
  },
  "physics": {
    "model": "laminar",
    "transport_properties": { "rho": 1060, "nu": 3.7736e-6 }
  },
  "numerics": { "profile": "robust" },
  "mesh": { "cells_per_diameter": 12 },
  "geometry": {
    "inlet_keywords_ordered": "inlet",
    "outlet_keywords_ordered": ["outlet1", "outlet2", "outlet3"],
    "wall_keywords_ordered": "wall_aorta",
    "scale_factor": 0.001
  },
  "boundary_conditions": {
    "inlet": {
      "type": "CONSTANT",
      "cardiac_output": 5.0,
      "profile": "parabolic"
    },
    "outlets": {
      "type": "3EWINDKESSEL",
      "windkessel_settings": {
        "systolic_pressure": 120,
        "diastolic_pressure": 80
      }
    },
    "walls": { "type": "no_slip" }
  },
  "simulation_control": { "end_time": 1.0, "writeInterval": 0.1 },
  "run_settings": { "solution_type": "serial" }
}
```

**Decision guide:**

| What you know | Config setting |
|---------------|---------------|
| Just cardiac output | `"type": "CONSTANT", "cardiac_output": 5.0` |
| Have a flow waveform | `"type": "TIMEVARYING", "csv_file": "flowrate.csv"` |
| Have 4D flow MRI data | `"type": "MRI", "file": "./inlet/"` |
| Blood pressure measured | `"systolic_pressure": 120, "diastolic_pressure": 80` |
| No blood pressure | Use defaults (120/80) or literature values |
| Small anatomy (pediatric) | Lower cardiac_output, different BP |

### 1.4 Exercise: Set Up a VMR Case (25 min)

Using the 0023 (Marfan) or 0014 (coarctation) STL files already in `cases_input/`:

1. Create a NEW config (don't copy the existing one)
2. Start with `config_minimal.json` as template
3. Fill in: patient ID, outlet names, scale factor
4. Choose: inlet type based on what data is available
5. Set mesh resolution: start with cpd=10 for quick test
6. Run: `python run_patient.py 0023_H_AO_MFS --config my_config.json --steps case,mesh`
7. Check: does it mesh successfully? What does checkMesh say?

---

## Hour 2: Troubleshooting (60 min)

### 2.1 Common Mesh Failures (15 min)

**"No cells in mesh"**
- Wrong `scale_factor` — geometry is too big or too small
- Fix: check STL units. mm → 0.001, cm → 0.01, m → 1.0

**"locationInMesh outside domain"**
- The internal point is outside your geometry
- Fix: will be auto-computed, but check the geometry is watertight

**"Boundary layer failure"**
- Layers can't fit on small outlet patches
- Fix: reduce `num_layers` to 3, increase `min_thickness` to 0.2
- AortaCFD auto-retries with relaxed settings

### 2.2 Common Solver Failures (15 min)

**"PIMPLE: Not converged" every timestep**
- Targets too tight for the relaxation factor
- Fix: use robust profile, or reduce nOuterCorrectors

**"deltaT collapsed to 1e-100"**
- PIMPLE outer loop diverging during diastole
- Fix: use robust profile, enable backflow stabilisation

**"Floating point exception"**
- NaN in the solution — mesh too coarse, or bad BCs
- Fix: check mesh quality, try coarser/finer mesh, check inlet data

**"FOAM FATAL ERROR: cannot find file"**
- Missing dictionary or field file
- Fix: re-run `--steps case` to regenerate

### 2.3 Restarting from a Saved Timestep (10 min)

If the solver crashes after running for a while:

```bash
# Check what time directories exist
ls output/MY_CASE/run_xxx/openfoam/ | grep "^0\." | sort -g | tail -5

# Edit controlDict: change startFrom
# startFrom    latestTime;    ← restart from last saved time

# Re-run solver only
python run_patient.py MY_CASE --update output/MY_CASE/run_xxx --steps solver
```

### 2.4 Running on HPC (10 min)

For large meshes or long runs:

```bash
# 1. Set parallel in config
"run_settings": {
    "solution_type": "parallel",
    "subdomains": 32
}

# 2. Run case + mesh + boundary locally
python run_patient.py MY_CASE --steps case,mesh,boundary

# 3. Upload to HPC
bash scripts/hpc/upload.sh scripts/hpc/hpc.conf

# 4. Submit on HPC
ssh csf3
cd ~/scratch/MY_CASE/run_name
sbatch run_MY_CASE.slurm

# 5. Download results
bash scripts/hpc/download.sh scripts/hpc/hpc.conf
```

### 2.5 Exercise: Break and Fix (10 min)

1. Set `scale_factor` to 1.0 (wrong — geometry in mm treated as metres)
2. Run `--steps case,mesh` — what happens?
3. Fix it back to 0.001 and re-run
4. Set `cells_per_diameter` to 3 (too coarse) — what does checkMesh say?
5. Set it to 50 (too fine for serial) — how long does meshing take?

---

## Homework

1. If you have your own patient STL geometry:
   - Set up a case folder with STL files
   - Write config.json from scratch
   - Run case + mesh + boundary
   - Check mesh quality and fix any issues
2. If you don't have geometry yet:
   - Use the 0023 VMR case
   - Write a completely new config (don't copy the existing one)
   - Run through to solver completion (coarse mesh, robust profile)
3. Prepare a 5-minute presentation for next week showing your case
