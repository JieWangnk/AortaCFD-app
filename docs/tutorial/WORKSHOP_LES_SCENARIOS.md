# LES Workshop: Scenario-Based Tutorials with VOL04

**Base case:** `docs/tutorial/VOL04_LES_OF12/` (OF12 converted, 4.5M cell ICEM mesh)
**Student walks through each scenario by modifying ONE thing from the base case.**

---

## Workshop Structure

### Part 0: Walkthrough of the Golden Case (30 min)
Open every file, explain every line. Student understands the complete setup before changing anything.

### Part 1: Boundary Condition Scenarios (60 min)
Each scenario modifies ONLY the boundary conditions. Same mesh, same schemes, same solver.

### Part 2: Solver & Convergence Scenarios (30 min)
Each scenario modifies ONLY the solver settings or simulation duration.

### Part 3: Scheme & Model Scenarios (30 min)
Each scenario modifies the numerical schemes or turbulence model.

---

## Part 1: Boundary Condition Scenarios

### Scenario 1A: Simplest possible — fixedValue everywhere
**Question:** "I just want to see if the mesh works. Simplest BCs."

**Changes to 0/U:**
```
INLET  { type fixedValue; value uniform (0 0 -0.5); }  // plug flow ~0.5 m/s
RCC    { type zeroGradient; }
LCC    { type zeroGradient; }
LSA    { type zeroGradient; }
OUTLET { type zeroGradient; }
WALL   { type fixedValue; value uniform (0 0 0); }      // no-slip
```

**Changes to 0/p:**
```
INLET  { type zeroGradient; }
RCC    { type fixedValue; value uniform 0; }
LCC    { type fixedValue; value uniform 0; }
LSA    { type fixedValue; value uniform 0; }
OUTLET { type fixedValue; value uniform 0; }
WALL   { type zeroGradient; }
```

**What to learn:** This is the cavity-like setup. Zero pressure at outlets, fixed velocity at inlet. No Windkessel complexity. Should run immediately.

**controlDict change:** `endTime 0.01;` (just 50 timesteps to verify it runs)

---

### Scenario 1B: Constant flow + Windkessel outlets
**Question:** "I have cardiac output = 5 L/min. How do I set constant inlet with Windkessel?"

**Changes to 0/U:**
```
INLET  { type fixedValue; value uniform (-0.51 0.08 0.66); }  // from CO=5 L/min ÷ inlet area
// outlets: keep pressureInletOutletVelocity (same as golden case)
```

**Changes to 0/p:**
```
// Keep modularWKPressure on all outlets (same as golden case)
// Keep zeroGradient on inlet and wall
```

**What to learn:** Constant inlet + Windkessel. The WK will develop a pressure waveform even with steady inlet (the RC circuit has its own dynamics). Good for checking WK is working.

**How to calculate inlet velocity from cardiac output:**
```python
CO = 5.0        # L/min
Q = CO / 60000  # m³/s = 8.33e-5
A_inlet = 4.91e-4  # m² (from STL or checkMesh)
U_mean = Q / A      # = 0.17 m/s (plug profile)
# Direction: use inlet normal from STL geometry
```

---

### Scenario 1C: CSV flowrate → plug inlet profile
**Question:** "I have a Doppler flow waveform as CSV. How do I create inlet BC data?"

**Step 1:** Create CSV file `flowrate.csv`:
```csv
# VOL04 example flowrate waveform
# time (s), flowrate (L/min)
0.000,2.5
0.050,5.0
0.100,12.0
0.150,18.0
0.200,15.0
0.250,8.0
0.300,4.0
0.400,2.0
0.500,1.5
0.600,1.8
0.700,2.2
0.809,2.5
```

**Step 2:** Convert CSV to OpenFOAM boundaryData using Python:
```python
import numpy as np
import os

# Read CSV
data = np.loadtxt('flowrate.csv', delimiter=',', skiprows=2)
times = data[:, 0]
Q_lmin = data[:, 1]
Q_m3s = Q_lmin / 60000  # Convert L/min → m³/s

# Read inlet points from the mesh
# (copy from constant/boundaryData/INLET/points)
# Each point gets the same velocity (plug profile)
n_points = 2447  # from the golden case
A_inlet = 4.91e-4  # m² (inlet area)

# Inlet normal direction (from STL geometry)
normal = np.array([-0.61, 0.10, 0.79])  # approximate for VOL04
normal = normal / np.linalg.norm(normal)

# Create boundaryData directories
os.makedirs('constant/boundaryData/INLET', exist_ok=True)

for i, (t, Q) in enumerate(zip(times, Q_m3s)):
    U_mag = Q / A_inlet
    U_vec = U_mag * normal

    dir_name = f'constant/boundaryData/INLET/{t:.6f}'
    os.makedirs(dir_name, exist_ok=True)

    with open(f'{dir_name}/U', 'w') as f:
        f.write(f'{n_points}\n(\n')
        for _ in range(n_points):
            f.write(f'({U_vec[0]:.6e} {U_vec[1]:.6e} {U_vec[2]:.6e})\n')
        f.write(')\n')

print(f'Created {len(times)} inlet timesteps')
```

**Step 3:** Create symlinks for multiple cycles (same as setupScript_0_inletBC)

**0/U stays:** `type timeVaryingMappedFixedValue;`

**What to learn:** The full pipeline from clinical measurement → OpenFOAM BC.

---

### Scenario 1D: CSV flowrate → parabolic inlet profile
**Question:** "Same CSV but I want parabolic profile instead of plug."

**Same as 1C but velocity varies with distance from wall:**
```python
# For each inlet face point:
# 1. Calculate distance to nearest wall point
# 2. d_max = max distance (at centre)
# 3. u(x) = u_max × (1 - (1 - d/d_max)²)
# 4. Scale u_max so that ∫ u dA = Q(t)

# Read wall boundary points
# Calculate distance for each inlet face centre
# Apply profile shape
```

**What to learn:** How inlet profile shape affects the flow. Compare with plug in ParaView.

---

### Scenario 1E: Change flow split ratio at outlets
**Question:** "I want 60% of flow going to descending aorta, 15% to each branch."

**Changes to 0/p (Windkessel R values):**
The flow split is controlled by the ratio of resistances:
```
Q_i / Q_total = R_total / R_i

# To get 60% to OUTLET:  R_OUTLET = R_total / 0.60
# To get 15% to RCC:     R_RCC = R_total / 0.15
# To get 15% to LCC:     R_LCC = R_total / 0.15
# To get 10% to LSA:     R_LSA = R_total / 0.10
```

**Calculate new R values:**
```python
rho = 1060
MAP_Pa = 93.3 * 133.322  # 93.3 mmHg → Pa
Q_total = 5.0 / 60000    # 5 L/min → m³/s
R_total = MAP_Pa / Q_total  # Total resistance

# New individual resistances (dynamic units)
R_OUTLET = R_total / 0.60
R_RCC = R_total / 0.15
R_LCC = R_total / 0.15
R_LSA = R_total / 0.10

# Convert to kinematic
print(f'OUTLET R_kin = {R_OUTLET/rho:.1f}')
print(f'RCC    R_kin = {R_RCC/rho:.1f}')
# ... etc
# Keep C and Z unchanged (or recalculate from new R)
```

**What to learn:** How Windkessel R controls flow distribution. Murray's law gives natural split; you can override.

---

### Scenario 1F: No Windkessel — just fixed pressure outlets
**Question:** "I don't want Windkessel complexity. Just zero pressure at outlets."

**Changes to 0/p:**
```
RCC    { type fixedValue; value uniform 0; }
LCC    { type fixedValue; value uniform 0; }
LSA    { type fixedValue; value uniform 0; }
OUTLET { type fixedValue; value uniform 0; }
```

**Remove** `libs ("libmodularWKPressure.so");` from controlDict (not needed).

**What to learn:** Simpler but less physiological. Pressure waveform won't be realistic. Good for quick tests. Compare pressure waveform with Scenario 1B.

---

## Part 2: Solver & Convergence Scenarios

### Scenario 2A: Run only 1 cardiac cycle
**Question:** "I just want a quick result — 1 cycle."

**Changes to controlDict:**
```
endTime         0.809;    // 1 cycle (was 16.2 = 20 cycles)
```

**What to learn:** 1 cycle is enough for instantaneous WSS but NOT enough for TAWSS/OSI (need time averaging over developed flow).

---

### Scenario 2B: Run 3 cycles, average over the last
**Question:** "I want TAWSS but can't afford 20 cycles."

**Changes to controlDict:**
```
endTime         2.427;    // 3 cycles

// Enable field averaging starting at cycle 2
fieldAverage1
{
    type            fieldAverage;
    libs            ("libfieldFunctionObjects.so");
    writeControl    writeTime;
    timeStart       0.809;    // Start averaging after 1st cycle
    fields
    (
        U { mean on; prime2Mean on; base time; }
        wallShearStress { mean on; prime2Mean on; base time; }
    );
}
```

**What to learn:** Trade-off between cost and statistical convergence. 3 cycles gives approximate TAWSS; 20+ gives converged turbulence statistics.

---

### Scenario 2C: Change PIMPLE convergence
**Question:** "PIMPLE is using too many iterations. How do I speed it up?"

**Changes to fvSolution:**
```
PIMPLE
{
    nOuterCorrectors    10;     // Was 50 — exit early
    nCorrectors         2;
    pRefCell            0;
    pRefValue           0;

    outerCorrectorResidualControl
    {
        p { tolerance 1e-3; relTol 0; }   // Was 1e-5
        U { tolerance 1e-3; relTol 0; }   // Was 1e-5
    }
}
```

**What to learn:** Tighter targets = more iterations but better convergence. Looser targets = fewer iterations, faster, but may miss details. For LES, the pFinal solve with relaxation=1.0 corrects the solution regardless.

---

### Scenario 2D: Use adaptive timestep instead of fixed
**Question:** "The fixed dt=0.0002 is too conservative. Can I use adaptive?"

**Changes to controlDict:**
```
deltaT          1e-5;           // Initial small dt
adjustTimeStep  yes;
maxCo           0.5;            // Keep CFL < 0.5 for LES accuracy
maxDeltaT       0.0005;         // Don't exceed 0.5 ms
```

**What to learn:** Adaptive saves time during diastole (low flow → large dt). Fixed dt is safer and gives uniform temporal resolution for spectral analysis.

---

## Part 3: Scheme & Model Scenarios

### Scenario 3A: Switch from central to LUST convection
**Question:** "Central differencing crashes on my mesh. What's the safe alternative?"

**Changes to fvSchemes:**
```
divSchemes
{
    div(phi,U)    Gauss LUST grad(U);   // Was: Gauss linear
}
```

**What to learn:** LUST = 75% central + 25% upwind. Adds some numerical diffusion but prevents wiggles. Compare velocity field with pure central — should be very similar on good mesh.

---

### Scenario 3B: Switch from LES to laminar
**Question:** "Is LES actually necessary for my case? What if I just run laminar?"

**Changes to constant/momentumTransport:**
```
simulationType  laminar;
```

**Remove** 0/nut (not needed for laminar).

**What to learn:** Compare WSS maps between LES and laminar. At aortic Re ~3000, the differences may be modest. If your research question is about pressure drop, laminar is sufficient.

---

### Scenario 3C: Switch from WALE to Smagorinsky
**Question:** "What happens with a different subgrid model?"

**Changes to constant/momentumTransport:**
```
LES
{
    LESModel        Smagorinsky;
    SmagorinskyCoeffs
    {
        Ck          0.094;
        Ce          1.048;
    }
    delta           cubeRootVol;
}
```

**What to learn:** Smagorinsky over-predicts SGS viscosity near walls and in laminar regions. Compare nut field with WALE — Smagorinsky has non-zero nut at the wall.

---

## Ready Cases to Prepare

For each scenario, create a directory with ONLY the changed files:

```
docs/tutorial/VOL04_scenarios/
├── scenario_1A_simple/          → 0/U, 0/p (fixedValue everywhere)
├── scenario_1B_constant_wk/     → 0/U (fixedValue inlet)
├── scenario_1C_csv_plug/        → flowrate.csv + Python script
├── scenario_1E_flow_split/      → 0/p (modified R values)
├── scenario_1F_no_wk/           → 0/p (fixedValue outlets) + controlDict
├── scenario_2A_1cycle/          → system/controlDict (endTime=0.809)
├── scenario_2B_3cycle_avg/      → system/controlDict (endTime=2.427 + fieldAverage)
├── scenario_2C_fast_pimple/     → system/fvSolution (nOuter=10, targets=1e-3)
├── scenario_2D_adaptive_dt/     → system/controlDict (adjustTimeStep)
├── scenario_3A_lust/            → system/fvSchemes (LUST)
├── scenario_3B_laminar/         → constant/momentumTransport (laminar)
└── scenario_3C_smagorinsky/     → constant/momentumTransport (Smagorinsky)
```

Each scenario directory contains ONLY the files that differ from the golden case.
Student copies the golden case, then overwrites with the scenario files.

## Workflow for Each Scenario

```bash
# 1. Copy golden case
cp -r docs/tutorial/VOL04_LES_OF12 /tmp/my_scenario
# (mesh and boundaryData are symlinks — they share the original data)

# 2. Apply scenario changes
cp docs/tutorial/VOL04_scenarios/scenario_1A_simple/0/* /tmp/my_scenario/0/

# 3. Run (short test)
cd /tmp/my_scenario
foamRun -solver incompressibleFluid    # or with decomposePar + mpirun

# 4. Compare with golden case in ParaView
```
