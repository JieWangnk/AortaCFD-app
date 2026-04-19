# Session 2: Understanding the OpenFOAM Case

**Duration:** 2 hours
**Goal:** Understand what every generated file does

**Pre-requisite:** Session 1 completed, BPM120 case generated in `output/BPM120/run_xxx/openfoam/`

---

## Hour 1: Case Anatomy (60 min)

### 1.1 The Three Directories (10 min)

```bash
cd output/BPM120/run_xxx/openfoam/
ls
```

| Directory | Purpose | When it changes |
|-----------|---------|-----------------|
| `0/` | Initial + boundary conditions | Once at setup |
| `constant/` | Mesh + physical properties | Once at setup |
| `system/` | Solver controls + schemes | Once at setup (or regenerate) |
| `0.01/`, `0.02/`, ... | Solution at each saved time | During simulation |

### 1.2 system/controlDict (15 min)

```bash
cat system/controlDict
```

Key parameters to understand:
```
application     foamRun;            // OF12 modular solver
solver          incompressibleFluid; // Navier-Stokes for blood
startFrom       startTime;          // Start from t=0
endTime         1.5;                // 3 cardiac cycles × 0.5s
deltaT          1e-06;              // Initial timestep (adaptive)
adjustTimeStep  yes;                // Adaptive time stepping
maxCo           0.8;                // Max Courant number
writeInterval   0.01;               // Save every 0.01s
```

**Exercise:** What happens if you change `maxCo` from 0.8 to 2.0? (Larger timesteps, faster but riskier)

### 1.3 system/fvSchemes (15 min)

```bash
cat system/fvSchemes
```

This file controls HOW the equations are discretised:

| Block | What it controls | Example |
|-------|-----------------|---------|
| `ddtSchemes` | Time derivative | `Euler` (1st order), `backward` (2nd order) |
| `gradSchemes` | Gradient calculation | `cellLimited Gauss linear 1` |
| `divSchemes` | Convection term | `Gauss linearUpwind` (2nd order, stable) |
| `laplacianSchemes` | Diffusion term | `Gauss linear limited 0.5` |

**Key concept:** Higher order = more accurate but less stable. The profile system automates this choice.

**Exercise:** Open fvSchemes from a robust vs standard run. What's different?

### 1.4 system/fvSolution (20 min)

```bash
cat system/fvSolution
```

This file controls HOW the equations are solved:

**Linear solvers** (how each equation is solved per iteration):
```
p:    GAMG (geometric agglomeration multigrid) — fast for pressure
U:    smoothSolver with symGaussSeidel — standard for velocity
```

**PIMPLE algorithm** (how pressure-velocity coupling works):
```
nOuterCorrectors  10;   // Max outer loops per timestep
nCorrectors       2;    // Pressure corrections per outer loop
```

**Under-relaxation** (damping to prevent oscillation):
```
fields:    p = 0.5, pFinal = 1.0    // Pressure: partial correction, full on final
equations: U = 0.8, UFinal = 1.0    // Velocity: same idea
```

**Why pFinal = 1.0?** The Windkessel BC needs the true pressure to compute the outlet flow. Under-relaxing the final iteration would corrupt the pressure-flow coupling.

**outerCorrectorResidualControl** (early exit criteria):
```
p:  tolerance 1e-3;    // Stop PIMPLE if p residual < 0.001
U:  tolerance 1e-4;    // Stop if U residual < 0.0001
```

**Exercise:** Check the solver log — how many PIMPLE iterations does each timestep actually take?
```bash
grep "PIMPLE: Iteration\|PIMPLE: Converged" logs/log.solver | tail -20
```

---

## Hour 2: Boundary Conditions Deep Dive (60 min)

### 2.1 Velocity BC: 0/U (15 min)

```bash
cat 0/U
```

**Inlet:** `timeVaryingMappedFixedValue` — reads velocity data from `constant/boundaryData/inlet/`
- Each time directory contains a `U` file with velocity vectors for every inlet face
- AortaCFD generates this automatically from your CSV flowrate + profile choice

**Outlets:** `pressureInletOutletVelocity` or `stabilizedWindkesselVelocity`
- Forward flow: zero gradient (flow exits freely)
- Backflow: damped (prevents instability during diastole)

**Wall:** `fixedValue` with `uniform (0 0 0)` — no-slip condition

### 2.2 Pressure BC: 0/p (20 min)

```bash
cat 0/p
```

**The Windkessel boundary condition** (most important to understand):
```
type            modularWKPressure;
R               966320.75;     // Peripheral resistance (s/m in kinematic units)
C               1.777e-06;     // Arterial compliance (m in kinematic units)
Z               113924.53;     // Characteristic impedance (s/m)
p0              11.739;        // Initial pressure (m²/s² kinematic)
```

**What do R, C, Z mean physically?**
- **Z** (impedance): resistance to pressure waves → from vessel size + pulse wave velocity
- **R** (resistance): downstream vascular resistance → controls mean pressure
- **C** (compliance): how much the artery stretches → controls pulse pressure

**The electrical analogy:**
```
inlet → [Z] → [C] → [R] → venous pressure
         ↑      ↑      ↑
      wave    vessel   tissue
      speed   stretch  resistance
```

### 2.3 How AortaCFD Calculates R, C, Z (15 min)

From your config:
```json
"systolic_pressure": 120,    // mmHg
"diastolic_pressure": 80     // mmHg
```

The pipeline computes:
1. **MAP** = 80 + (120-80)/3 = 93.3 mmHg
2. **Total R** = (MAP - P_venous) / Q_mean
3. **Flow split** via Murray's law: Q_i ∝ r_i^2.6
4. **Individual R_i** = R_total × (Q_total / Q_i)
5. **Z_i** = ρ × PWV / A_i (from Olufsen formula)
6. **C_i** = τ / R_i (from diastolic decay time)

**Exercise:** Change blood pressure in config.json and re-run boundary step:
```bash
# Edit config: change systolic to 140, diastolic to 90
python run_patient.py BPM120 --update output/BPM120/run_xxx --steps boundary
# Compare R, C, Z values in the new 0/p file — they should change!
```

### 2.4 Physical Properties (10 min)

```bash
cat constant/transportProperties
cat constant/momentumTransport
```

`transportProperties`:
```
nu    3.7736e-06;    // Kinematic viscosity (m²/s) = μ/ρ = 0.004/1060
```

`momentumTransport`:
```
simulationType  laminar;    // No turbulence model
```

For RANS, this would be `RAS` with k-ω SST specified.

**Why kinematic units?** OpenFOAM's incompressible solver divides everything by density. Pressure is in m²/s² (not Pa), viscosity is kinematic (not dynamic). To convert back: multiply by ρ = 1060.

---

### 2.5 Provenance Tracking (bonus, 10 min)

AortaCFD records everything about every run:

```bash
# The merged config — records EXACTLY what was used
cat reports/merged_config.json

# The simulation setup report — human-readable summary
cat reports/simulation_setup_report.txt
```

**Why this matters:** In a paper you need to state exactly what settings you used. The `merged_config.json` is your audit trail — it captures the base profile + your overrides, so the simulation can be reproduced exactly.

### 2.6 The --update Workflow (bonus, 5 min)

Change boundary conditions without re-meshing:

```bash
# Edit your config (e.g., change blood pressure)
# Then re-run ONLY the boundary step on the existing mesh:
python run_patient.py BPM120 --update output/BPM120/run_xxx --steps boundary

# Or re-run boundary + solver:
python run_patient.py BPM120 --update output/BPM120/run_xxx --steps boundary,solver
```

This is much faster than starting from scratch — the mesh (which takes minutes) is preserved.

---

## Homework

1. Open `reports/merged_config.json` — find: what profile was used? What p relaxation?
2. Change `diastolic_pressure` from 80 to 90 in your config
3. Re-run: `python run_patient.py BPM120 --update <your_run> --steps boundary`
4. Compare `0/p` before and after — how did R, C, Z change? Why?
5. Read `docs/PIMPLE_SOLVER_SETTINGS.md` for background on solver settings
