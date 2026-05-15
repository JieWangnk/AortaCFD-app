# Session 8: Advanced Topics + Student Project

**Duration:** 2 hours
**Goal:** Research-ready — RANS, batch processing, verification, independent project

---

## Hour 1: Advanced Features (60 min)

### 1.1 Turbulence Models: RANS and LES (20 min)

#### RANS k-omega SST

When to use RANS instead of laminar:
- Peak Re > 5000 (severe stenosis, mechanical valve)
- You need turbulent kinetic energy or Reynolds stresses
- Comparing with LES as a cheaper alternative

```json
"physics": {
    "model": "rans_komegasst",
    "simulation_type": "RAS"
}
```

What changes:
- Additional fields: `k` (turbulent kinetic energy), `omega` (specific dissipation)
- Additional BCs: wall functions for k and omega
- `constant/momentumTransport` switches to `RAS` with `kOmegaSST`
- Slightly more expensive per timestep (~1.2x laminar)

**Important caveat:** At aortic Reynolds numbers (Re 500-4000), the flow is transitional. k-omega SST may over-predict eddy viscosity in predominantly laminar regions, artificially increasing dissipation. Laminar simulation is scientifically defensible for most aortic cases.

#### LES (WALE model)

For research requiring time-resolved turbulent structures:

```json
"physics": {
    "model": "les",
    "simulation_type": "LES",
    "les_model": "WALE"
}
```

LES requirements:
- **Mesh:** y+ < 1, 15+ cells across diameter
- **CFL:** maxCo = 0.3-0.5 (must be low for temporal accuracy)
- **Profile:** precise (CrankNicolson + LUST preserves resolved scales)
- **Cost:** 50-100× laminar for same mesh (smaller timestep + more cycles needed)
- **Duration:** 10-30 cardiac cycles for converged turbulence statistics

AortaCFD auto-disables hard backflow stabilisation for LES (the Heaviside step function creates velocity gradient discontinuities that corrupt the subgrid model).

**When to use LES:**
- Studying jet breakdown (severe coarctation)
- Resolving vortex dynamics in dilated aorta
- Comparing with turbulence-resolved 4D flow MRI
- **NOT** for routine clinical hemodynamics — cost is prohibitive

| | Laminar | RANS | LES |
|---|---|---|---|
| Cost | 1× | 1.2× | 50-100× |
| Re < 4000 | Recommended | Acceptable | Research only |
| Re > 5000 | Not appropriate | Recommended | Best (if affordable) |
| WSS accuracy | Good | Good (may over-predict) | Best |

### 1.2 Batch Processing (10 min)

Run multiple cases in parallel:

```bash
# Run all discovered cases
python run_batch.py

# Specific cases
python run_batch.py --cases BPM120 PAT002 --workers 2

# Mesh convergence study (same patient, different configs)
python run_batch.py \
  --config-list BPM120:config_coarse.json BPM120:config_medium.json BPM120:config_fine.json \
  --workers 2
```

After batch completion: `output/cohort_comparison.csv` aggregates QoIs.

For an end-to-end walkthrough of parametric studies at scale —
synthetic-geometry generation, packaging, local batch, HPC submission,
and cohort analysis — see the [**workshop guide**](../workshop/README.md)
(six lessons over the four composable blocks A→B→C→D).

### 1.3 Mesh Convergence and GCI (20 min)

The Grid Convergence Index (GCI) quantifies mesh independence:

1. Run 3 mesh levels (e.g., cpd = 10, 15, 22)
2. Compute a metric on each (e.g., pressure drop)
3. GCI estimates the error from extrapolation to infinite refinement

```
GCI_fine = Fs × |ε| / (r^p - 1)
```
Where:
- `ε` = relative change between fine and medium
- `r` = refinement ratio (cell size ratio)
- `p` = observed order of convergence
- `Fs` = safety factor (1.25 for 3+ grids)

**Practical guidance:**
- GCI < 5% for pressure → mesh is adequate for pressure
- GCI < 10% for TAWSS → mesh is adequate for WSS (hard to achieve)
- Non-monotonic convergence for WSS → report the range, not GCI

### 1.4 Reporting Standards (15 min)

What to include in a paper using AortaCFD:

**Minimum reporting:**
- Mesh: cell count, cells_per_diameter, boundary layers, checkMesh quality
- Profile: which one (robust/standard/precise), justify the choice
- BCs: inlet type, blood pressure, Windkessel parameters (auto or manual)
- Simulation: number of cycles, which cycle(s) analysed
- Post-processing: which metrics, percentile descriptors, masking thresholds

**Best practice:**
- Include `merged_config.json` as supplementary material
- Report GCI for at least pressure drop
- State the profile sensitivity range from appendix
- Acknowledge limitations: rigid walls, Newtonian, inlet assumptions

**Example methods paragraph:**
> "Simulations were performed using AortaCFD v1.0 with OpenFOAM 12. The mesh comprised 1.95M cells (15 cells per inlet diameter, 5 boundary layers, max non-orthogonality 62°). The standard profile (backward temporal, linearUpwind spatial) was used with adaptive time-stepping (maxCo = 0.8). Three-element Windkessel outlets were calibrated from measured blood pressure (120/80 mmHg) using Murray's law for flow distribution. Three cardiac cycles were simulated; hemodynamic metrics were averaged over the final cycle. Complete configuration is provided in Supplementary Material."

---

### 1.5 Clinical Applications of Aortic CFD (10 min)

| Application | Key metric | Clinical threshold |
|-------------|-----------|-------------------|
| **Coarctation severity** | Pressure drop | > 20 mmHg at rest = significant |
| **Atherosclerosis risk** | Low TAWSS + high OSI | TAWSS < 0.4-0.5 Pa, OSI > 0.15 |
| **Aneurysm rupture risk** | Peak WSS, RRT | High WSS on dome, elevated RRT |
| **Surgical planning** | Flow distribution | Murray's law deviation post-surgery |
| **Valve assessment** | Jet velocity, turbulence | Peak velocity > 4 m/s = severe stenosis |

**Where does plaque form?**
- Outer curvature of aortic arch (low WSS, disturbed flow)
- Branch ostia (flow separation, oscillatory WSS)
- Post-stenotic regions (recirculation zones)
- NOT where WSS is highest — plaque forms where WSS is LOW

### 1.6 Modelling Assumptions and Their Impact (5 min)

| Assumption | Impact on results | When it matters |
|-----------|-------------------|-----------------|
| Rigid walls | WSS over-predicted by 10-20% | Compliant aorta, aneurysm |
| Newtonian blood | OK at high shear rates (> 100 s⁻¹) | Low-shear recirculation zones |
| No FSI | Pressure waveform not fully physiological | Compliant vessels, pulse wave |
| Prescribed inlet | No upstream feedback | If studying arch haemodynamics |

For a PhD student's first study, these assumptions are standard and acceptable. State them explicitly in your paper.

---

## Hour 2: Student Project (60 min)

### 2.1 Student Presents Their Case (20 min)

Student shows:
- Their geometry (ParaView)
- Their config.json choices and reasoning
- Mesh quality (checkMesh results)
- Any solver issues encountered and how they were resolved
- Preliminary results (if solver has completed)

### 2.2 Review Together (20 min)

Check:
- Is the mesh resolution appropriate? (cpd, boundary layers)
- Are the BCs reasonable? (inlet type, blood pressure, flow rate)
- Is the profile choice justified? (robust for first run, standard for production)
- Are there any red flags in the solver log?
- Are the hemodynamic results physiologically reasonable?

### 2.3 Plan Next Steps (20 min)

Depending on the student's research:
- **Need mesh independence?** → Set up 3-level convergence study
- **Need turbulence?** → Switch to RANS, discuss limitations
- **Multiple patients?** → Set up batch processing
- **Comparing with MRI?** → Set up 4D flow inlet, discuss validation
- **Writing a paper?** → Discuss reporting standards, figure preparation

---

## What You Can Now Do Independently

After 8 sessions, you should be able to:

- [x] Install and configure AortaCFD + OpenFOAM 12
- [x] Understand every file in an OpenFOAM cardiovascular case
- [x] Control mesh resolution and assess mesh quality
- [x] Choose the right numerical profile for your application
- [x] Set up inlet BCs from different types of clinical data
- [x] Run simulations and diagnose common failures
- [x] Extract and interpret TAWSS, OSI, RRT, pressure drop
- [x] Create publication-quality figures in ParaView
- [x] Set up a new patient case from scratch
- [x] Run on HPC for large meshes
- [x] Report results to publication standards

---

## Further Resources

- `README.md` — Quick start and configuration reference
- `examples/README_CONFIG.md` — Full configuration documentation
- `docs/_internal/PIMPLE_SOLVER_SETTINGS.md` — Solver settings deep dive
- `docs/_internal/PROFILE_SETTINGS_EVIDENCE.md` — Why profiles are set as they are
- `docs/_internal/BACKFLOW_STABILIZATION_ANALYSIS.md` — Stabilisation details
- OpenFOAM User Guide: https://doc.cfd.direct/openfoam/user-guide-v12/
- CFD Direct notes on PIMPLE: https://doc.cfd.direct/notes/cfd-general-principles/the-pimple-algorithm
