# Reproducibility Checklist

This document ensures computational reproducibility of AortaCFD simulations for research publications, clinical validation, and collaborative studies.

## 📋 Quick Checklist

- [ ] Software versions documented
- [ ] Hardware specifications recorded
- [ ] Input data location specified
- [ ] Configuration files version-controlled
- [ ] Random seeds fixed (if applicable)
- [ ] Expected outputs documented
- [ ] Execution logs preserved
- [ ] Mesh quality metrics validated

---

## 1. Software Environment

### Required Software Versions

Document exact versions used for your simulation:

```bash
# Check versions
python --version
foamRun -help | head -n 1
pvbatch --version
git --version
```

**Minimum Requirements:**
- **Python:** 3.12+ (tested: 3.12.3)
- **OpenFOAM:** 12 (ESI version)
- **ParaView:** 5.11+ (for post-processing)
- **Operating System:** Ubuntu 22.04 LTS or compatible Linux distribution

**Python Package Versions:**
```bash
# Export exact package versions
pip freeze > requirements.lock

# Key packages to document:
# - numpy==1.26.4
# - trimesh==4.3.2
# - jinja2==3.1.4
# - pytest==8.2.2
```

### OpenFOAM Installation

```bash
# Verify OpenFOAM installation path
echo $WM_PROJECT_DIR

# Expected: /opt/openfoam12 (or custom path)
# Document exact installation method:
# - Package manager (apt, yum)
# - Source compilation
# - Docker container
```

### Custom Boundary Conditions

**3-Element Windkessel BC Installation:**
```bash
# Check if custom BC library exists
ls -lh $FOAM_USER_LIBBIN/libstabilizedWindkesselVelocity.so

# If using custom BCs, document:
# 1. Source location: scripts/windkessel_of12/
# 2. Compilation method: ./scripts/install_windkessel_of12.sh
# 3. Library hash: sha256sum $FOAM_USER_LIBBIN/libstabilizedWindkesselVelocity.so
```

---

## 2. Hardware Specifications

Document computational resources used:

```bash
# CPU information
lscpu | grep -E "Model name|CPU\(s\)|Thread|Core"

# Memory
free -h | grep Mem

# Disk space
df -h $PWD
```

**Example Documentation:**
```yaml
hardware:
  processor: Intel Xeon Gold 6248R @ 3.0 GHz
  cores: 48 (24 physical, 2 threads per core)
  memory: 192 GB DDR4
  storage: 2 TB NVMe SSD
  gpu: Not used (CPU-only simulation)
```

**Parallelization Settings:**
- Number of processors used: (document from config.json)
- Decomposition method: scotch / simple / hierarchical
- MPI version: `mpirun --version`

---

## 3. Input Data Specification

### Geometry Files

**STL File Requirements:**
```bash
# Document STL file metadata
cd cases_input/patient1/
for file in *.stl; do
  echo "=== $file ==="
  echo "Size: $(stat -c%s $file) bytes"
  echo "Hash: $(sha256sum $file | awk '{print $1}')"
  echo "Triangles: $(grep -c 'facet normal' $file)"
done
```

**Required STL Files:**
- `inlet.stl` - Inlet patch geometry
- `wall_aorta.stl` - Vessel wall geometry
- `outlet1.stl, outlet2.stl, ...` - Outlet patch geometries

**Geometry Source:**
- [ ] Medical imaging modality (CT/MRI/Ultrasound)
- [ ] Imaging resolution: ___ mm
- [ ] Reconstruction software: (e.g., 3D Slicer, ITK-SNAP, VMTK)
- [ ] Segmentation method: (manual/semi-automatic/AI-assisted)
- [ ] Smoothing applied: Yes/No (method: ___)

### Flow Data

**Inlet Boundary Condition Data:**
```bash
# Document CSV file
cd cases_input/patient1/
echo "Flow data file: $(ls *.csv)"
echo "Hash: $(sha256sum *.csv | awk '{print $1}')"
echo "Data points: $(wc -l < *.csv)"
echo "Time range: $(head -n 2 *.csv | tail -n 1 | awk -F, '{print $1}') to $(tail -n 1 *.csv | awk -F, '{print $1}') seconds"
```

**Flow Data Source:**
- [ ] Patient-specific measurement (Phase-Contrast MRI / Doppler Ultrasound)
- [ ] Population-averaged template (reference: ___)
- [ ] Synthetic waveform (model: ___)

### Configuration File

**Version Control:**
```bash
# Track configuration in git
git add cases_input/patient1/config.json
git commit -m "Add patient1 config for study XYZ"

# Document configuration hash
sha256sum cases_input/patient1/config.json
```

**Key Configuration Parameters to Document:**
- Simulation profile: `sim_laminar_medium` / `sim_rans_fine` / etc.
- Blood properties:
  - Density: 1060 kg/m³
  - Viscosity: 0.004 Pa·s
- Mesh resolution: cells_per_diameter = ___
- Time stepping: adjustable / fixed (Δt = ___ s)
- Total simulation time: ___ cardiac cycles

---

## 4. Execution Procedure

### Exact Command Used

```bash
# Document the exact command
python run_patient.py patient1 --profile sim_laminar_medium

# Or with custom config
python run_patient.py patient1 --config /path/to/config.json

# Document date and time
date -Iseconds > simulation_start_timestamp.txt
```

### Workflow Steps

**If running partial workflow:**
```bash
# Document which steps were executed
python run_patient.py patient1 --step case
python run_patient.py patient1 --step mesh
python run_patient.py patient1 --step boundary
python run_patient.py patient1 --step solver
python run_patient.py patient1 --step post
```

### Random Seeds

**For stochastic simulations (LES):**
```bash
# Document random seed if applicable
# (Currently not used, but add if future LES synthetic turbulence is enabled)
```

---

## 5. Expected Outputs

### Output Directory Structure

```
output/patient1/run_YYYYMMDD_HHMMSS/
├── openfoam/                 # Complete OpenFOAM case
│   ├── 0/                    # Initial conditions
│   ├── constant/             # Mesh and properties
│   ├── system/               # Solver settings
│   ├── 0.1, 0.2, ..., 2.0/   # Time directories
│   └── logs/                 # Execution logs
├── reports/                  # Simulation documentation
│   ├── simulation_setup_report.md
│   ├── simulation_setup_report.json
│   └── simulation_summary.txt
├── logs/                     # Workflow logs
└── summary.json              # Analysis summary
```

### Expected Result Files

**Minimum Output for Reproducibility:**
- [ ] `constant/polyMesh/` - Mesh files (points, faces, cells)
- [ ] `log.blockMesh` - Background mesh log
- [ ] `log.snappyHexMesh` - Refinement log
- [ ] `log.foamRun` - Solver log
- [ ] Time directories (0.1, 0.2, ...) - Solution fields (U, p, wallShearStress)

**Quality Assurance Files:**
- [ ] `reports/simulation_setup_report.json` - Complete parameter documentation
- [ ] `checkMesh` output (orthogonality, skewness, aspect ratio)

### Mesh Quality Metrics

**Run checkMesh and document:**
```bash
cd output/patient1/run_*/openfoam
checkMesh > checkMesh_report.txt

# Key metrics to record:
# - Total cells: ___
# - Min/max cell volume: ___
# - Non-orthogonality max: ___ (should be < 70)
# - Max skewness: ___ (should be < 4)
# - Aspect ratio max: ___ (should be < 100)
```

**Reference Values (from validation/):**
- **Coarse mesh:** ~100K-300K cells
- **Medium mesh:** ~500K-1.5M cells
- **Fine mesh:** ~2M-5M cells

### Solver Convergence

**Document residuals:**
```bash
# Extract final residuals from log
grep "Final residual" output/patient1/run_*/openfoam/log.foamRun | tail -n 20
```

**Expected Convergence:**
- Pressure residual: < 1e-4 (laminar) / < 1e-5 (RANS)
- Velocity residual: < 1e-5 (laminar) / < 1e-6 (RANS)

---

## 6. Result Validation

### Physical Plausibility Checks

**Velocity Magnitude:**
```python
# Check peak velocities are physiologically reasonable
# Adult aorta: 0.5-1.5 m/s (systolic peak)
# Expected range: 0.3-2.0 m/s
```

**Pressure Drop:**
```python
# Aortic pressure drop should be < 20 mmHg (2666 Pa) for healthy vessels
# Significant stenosis: > 50 mmHg pressure drop
```

**Wall Shear Stress:**
```python
# Healthy aorta: 1-3 Pa (mean), up to 10 Pa (peak systole)
# Low WSS regions (< 0.4 Pa): atherosclerosis risk
```

### Mesh Independence Study

**If claiming mesh independence:**
```bash
# Run 3 mesh resolutions
python run_patient.py patient1 --profile sim_laminar_coarse   # ~100K cells
python run_patient.py patient1 --profile sim_laminar_medium  # ~500K cells
python run_patient.py patient1 --profile sim_laminar_fine    # ~2M cells

# Compare key quantities of interest (QoI):
# - Peak velocity difference < 5%
# - Mean WSS difference < 10%
# - Pressure drop difference < 5%
```

### Time Step Independence (if using fixed Δt)

**If claiming time step independence:**
```bash
# Vary time step at fixed mesh resolution
# Δt = 1e-4, 5e-5, 1e-5 seconds
# Compare QoI convergence as above
```

---

## 7. Data Archival and Sharing

### Minimal Reproducibility Package

**For publication supplementary materials:**
```bash
# Create reproducibility archive
tar -czf patient1_reproducibility.tar.gz \
    cases_input/patient1/config.json \
    cases_input/patient1/*.stl \
    cases_input/patient1/*.csv \
    output/patient1/run_YYYYMMDD_HHMMSS/reports/ \
    output/patient1/run_YYYYMMDD_HHMMSS/openfoam/log.* \
    output/patient1/run_YYYYMMDD_HHMMSS/openfoam/constant/polyMesh/boundary \
    requirements.lock \
    REPRODUCIBILITY.md

# Include README with:
# 1. Exact software versions
# 2. Hardware used
# 3. Command executed
# 4. Expected runtime
# 5. Data access restrictions (if any)
```

### Long-Term Storage

**Recommended repositories:**
- [ ] **Code:** GitHub/GitLab (public or private)
- [ ] **Data:** Zenodo / Figshare / Institutional repository
- [ ] **Large files (>100MB):** Git LFS / cloud storage

**Persistent Identifiers:**
- [ ] Code DOI (Zenodo archive)
- [ ] Dataset DOI
- [ ] Publication DOI

### Data Privacy (Clinical Data)

**If using patient data:**
- [ ] De-identification completed (HIPAA/GDPR compliant)
- [ ] IRB approval obtained (if applicable)
- [ ] Data sharing agreement in place
- [ ] Anonymized identifiers used (patient1, patient2, not names)

---

## 8. Troubleshooting and Known Issues

### Common Sources of Non-Reproducibility

1. **OpenFOAM Version Mismatch**
   - Solution: Use Docker container with fixed OpenFOAM 12 installation

2. **Random Mesh Decomposition**
   - `decomposePar` with `scotch` may vary slightly between runs
   - Solution: Use `hierarchical` or `simple` methods for exact reproducibility

3. **Adaptive Time Stepping**
   - Δt varies based on Courant number (maxCo)
   - Solution: Document maxCo, or use fixed time step for exact comparison

4. **Floating-Point Precision**
   - Results may vary slightly across different CPUs/compilers
   - Typical variation: < 0.1% for same hardware family

### Validation Against Known Benchmarks

**Run included validation cases:**
```bash
# Poiseuille flow validation
python run_patient.py validation_poiseuille
# Expected: Analytical vs. numerical error < 1%

# Womersley flow validation
python run_patient.py validation_womersley
# Expected: Phase lag and amplitude match theory
```

---

## 9. Reproducibility Statement Template

**For Methods Section of Manuscript:**

> **Computational Setup:** Simulations were performed using AortaCFD version X.X.X
> (DOI: XXXXX) on OpenFOAM 12 with Python 3.12. Hardware: 48-core Intel Xeon
> with 192 GB RAM. The 3-element Windkessel boundary condition library was
> compiled from source (scripts/install_windkessel_of12.sh). Patient-specific
> geometries were reconstructed from CT angiography (0.5mm resolution) using
> 3D Slicer v5.2. Mesh independence was verified with coarse (100K), medium
> (500K), and fine (2M) meshes, showing <5% variation in peak velocity. Blood
> properties: ρ=1060 kg/m³, μ=0.004 Pa·s (Newtonian). Simulation profile:
> sim_laminar_medium (adjustable time stepping, maxCo=1.0). Complete configuration
> files, input data, and execution logs are available at [repository URL].

---

## 10. Automated Reproducibility Check

**Script to verify reproducibility:**

```bash
#!/bin/bash
# verify_reproducibility.sh

echo "=== AortaCFD Reproducibility Check ==="

# 1. Software versions
echo "Python: $(python --version)"
echo "OpenFOAM: $(foamRun -help | head -n 1)"

# 2. Input files
echo "Config hash: $(sha256sum cases_input/patient1/config.json)"
echo "STL files: $(ls cases_input/patient1/*.stl | wc -l)"

# 3. Run simulation twice
python run_patient.py patient1 --profile sim_laminar_coarse
RUN1=$(find output/patient1 -maxdepth 1 -type d -name "run_*" | sort -r | head -n 1)

python run_patient.py patient1 --profile sim_laminar_coarse
RUN2=$(find output/patient1 -maxdepth 1 -type d -name "run_*" | sort -r | head -n 1)

# 4. Compare key outputs
diff $RUN1/reports/simulation_setup_report.json $RUN2/reports/simulation_setup_report.json
echo "Config files match: $?"

# 5. Compare final velocity field (should be nearly identical)
python -c "
import numpy as np
# Load U field from both runs and compute difference
# (requires PyFoam or manual parsing of OpenFOAM files)
"

echo "=== Reproducibility check complete ==="
```

---

## References

1. **OpenFOAM User Guide:** https://www.openfoam.com/documentation/user-guide
2. **AortaCFD Documentation:** See README.md, USER_GUIDE.md, CLAUDE.md
3. **Good Practices in CFD:** ASME V&V 20-2009 Standard
4. **Research Data Management:** https://www.re3data.org/

---

## Changelog

| Date       | Version | Changes                                       |
|------------|---------|-----------------------------------------------|
| 2025-10-14 | 1.0     | Initial reproducibility checklist created     |

---

**Document maintained by:** AortaCFD Development Team
**Last updated:** 2025-10-14
**Contact:** See CITATION.cff for author information
