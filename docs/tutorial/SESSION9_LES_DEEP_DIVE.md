# Session 9: LES Deep Dive — Theory, Problems, and Practical Implementation

**Duration:** 2 hours (can extend to 2 sessions for detailed coverage)
**Goal:** Understand LES from first principles, know its problems, run it correctly in OpenFOAM

**Core references from Chalmers:**
- [Davidson L. "Fluid mechanics, turbulent flow and turbulence modeling"](https://www.tfd.chalmers.se/~lada/postscript_files/solids-and-fluids_turbulent-flow_turbulence-modelling.pdf) — Chapters 18-22 (the LES bible)
- [Davidson L. "How to estimate the resolution of an LES of recirculating flow"](https://www.cfd-sweden.se/lada/postscript_files/paper-resolution-IJHFF.pdf) — LES quality assessment
- [Salehi S. "PIMPLE algorithm" (Chalmers OS CFD 2022)](https://www.tfd.chalmers.se/~hani/kurser/OS_CFD_2022/lectureNotes/PIMPLE.pdf) — Solver settings for LES
- [Nilsson H. "CFD with OpenSource Software" course](https://www.tfd.chalmers.se/~hani/kurser/OS_CFD/) — OpenFOAM LES tutorials
- [MTF271 Turbulence Modeling course](https://www.tfd.chalmers.se/~lada/comp_turb_model/course_plan.html) — Full theory

---

## Part 1: What LES Actually Is (and Isn't)

### 1.1 The Turbulence Modelling Spectrum

```
DNS    →    LES    →    RANS    →    Laminar
────────────────────────────────────────────
resolve   resolve     model        ignore
  ALL      LARGE      ALL          ALL
 scales    scales    scales       scales
           model
           SMALL
           scales
```

**DNS** (Direct Numerical Simulation): Resolves every eddy down to the Kolmogorov scale η.
Grid requirement: N ~ Re^(9/4). For aortic Re=3000: N ~ 10^8 cells. Feasible only for simple geometries.

**LES**: Resolves eddies larger than the grid filter Δ. Models the subgrid scales (SGS).
Grid requirement: N ~ Re^(6/5) (much less than DNS). For aorta: ~5-20M cells.

**RANS**: Models ALL turbulent scales. Solves for mean quantities only.
Grid requirement: N ~ independent of Re. For aorta: ~1-2M cells.

**Reference:** Davidson Ch. 18.1-18.2 — "The drawback with LES is that it requires much finer mesh than RANS... the advantage is that it captures the large-scale unsteady turbulent motion"

### 1.2 The Filtering Operation

In LES, the Navier-Stokes equations are filtered over a volume (typically the computational cell):

```
ū(x) = ∫ G(x - x') u(x') dx'
```

Where G is the filter function with width Δ (≈ cell size).

The velocity decomposes:
```
u = ū + u'
    ↑     ↑
 resolved  subgrid
 (computed) (modelled)
```

**Critical difference from RANS:** In RANS, ū is the TIME average (deterministic). In LES, ū is the SPATIAL filter (still time-dependent, still turbulent).

**Reference:** Davidson Ch. 18.3-18.6 — Filtering, the filtered equations

### 1.3 The Filtered Momentum Equation

```
∂ūᵢ/∂t + ∂(ūᵢūⱼ)/∂xⱼ = -∂p̄/∂xᵢ + ν ∂²ūᵢ/∂xⱼ² - ∂τᵢⱼ/∂xⱼ
```

Where the **subgrid stress tensor** is:

```
τᵢⱼ = ūᵢuⱼ̄  - ūᵢūⱼ    (Leonard stress + cross stress + Reynolds SGS stress)
```

This term represents the effect of unresolved eddies on the resolved field. It must be modelled.

---

## Part 2: Subgrid Models — What They Do and Their Problems

### 2.1 The Smagorinsky Model (1963) — Simplest, Most Problems

```
τᵢⱼ - (1/3)τₖₖδᵢⱼ = -2νₛₘₐₓ S̄ᵢⱼ

νₛₘₐₓ = (Cₛ Δ)² |S̄|
```

Where Cₛ ≈ 0.1-0.2 and |S̄| = √(2S̄ᵢⱼS̄ᵢⱼ)

**Problems with Smagorinsky:**

1. **Non-zero at walls:** νₛₘₐₓ → Cₛ²Δ²|S̄| ≠ 0 at wall even though true SGS stress → 0.
   Requires van Driest damping function: fᵥᴅ = 1 - exp(-y⁺/A⁺)
   *Reference: Davidson Ch. 18.14-18.15*

2. **Non-zero in laminar flow:** If there's any velocity gradient (e.g., Poiseuille flow),
   Smagorinsky produces νₛₘₐₓ > 0 even though the flow is perfectly laminar.
   This adds artificial dissipation to laminar regions.

3. **Fixed constant Cₛ:** The "correct" value depends on the flow. Cₛ = 0.1 works for
   channels but is wrong for jets, wakes, and transitional flows.
   *Reference: Davidson Ch. 18.10*

4. **No backscatter:** Energy always flows from resolved → subgrid (dissipative only).
   In reality, small eddies can feed energy back to large eddies.

### 2.2 The Dynamic Model (Germano 1991) — Fixes the Constant

```
Cₛ is computed dynamically from the resolved field at each point and time

Apply a test filter (wider than grid filter):
  Δ̂ = 2Δ (typically)

Compare stresses at two filter levels to determine Cₛ locally
```

**Advantages:** Cₛ adapts to the flow — goes to zero at walls, in laminar regions, near boundaries. No van Driest damping needed.

**Problems:**
1. Cₛ can become negative (backscatter) → numerically unstable
2. Requires averaging (plane averaging, Lagrangian, clipping) to stabilise
3. More expensive: needs test filtering operation at every timestep

*Reference: Davidson Ch. 18.18-18.24 — Dynamic models, test filtering*

### 2.3 The WALE Model (Nicoud & Ducros 1999) — Best for Cardiovascular

```
νₛₘₐₓ = (Cᵤ Δ)² × (SᵈᵢⱼSᵈᵢⱼ)^(3/2) / ((S̄ᵢⱼS̄ᵢⱼ)^(5/2) + (SᵈᵢⱼSᵈᵢⱼ)^(5/4))
```

Where Sᵈ is the traceless symmetric part of the squared velocity gradient tensor.

**Why WALE is better for aortic flows:**

1. **Goes to zero at walls automatically** — no damping function needed (correct y³ behaviour)
2. **Goes to zero in pure shear** — no spurious SGS viscosity in laminar regions
3. **Handles laminar-turbulent transition** — only activates where there's actually rotation AND strain
4. **Single constant** Cᵤ = 0.325 — works well across flow types without tuning

**Reference:** Davidson Ch. 18.26 — "The advantage with the WALE model is that it gives the correct near-wall behaviour"

### 2.4 How To Choose: Decision Tree

```
Is your flow fully turbulent everywhere?
  YES → Smagorinsky is OK (simplest, cheapest)
  NO →
    Is there laminar-turbulent transition?
      YES → WALE (handles transition automatically)
      NO →
        Do you need adaptive constant?
          YES → Dynamic model (most sophisticated)
          NO → WALE (good default)
```

**For aortic CFD: always use WALE.** The flow is transitional (Re 2000-4500), has laminar regions during diastole, and has complex geometry where Smagorinsky's fixed constant fails.

---

## Part 3: The Five Critical Problems of LES

### Problem 1: Numerical Diffusion vs Subgrid Dissipation

**The fundamental LES dilemma:** The numerical scheme adds artificial dissipation. If this numerical diffusion is larger than the physical SGS dissipation, you're not doing LES — you're doing "implicitly filtered" simulation where the numerics control the cascade, not the physics.

```
Total dissipation = Physical SGS dissipation + Numerical diffusion

If numerical >> physical:  numerics control the cascade (NOT real LES)
If physical >> numerical:  SGS model controls the cascade (real LES)
```

**How to check:** Compare the SGS viscosity (νₛₘₐₓ) with the numerical diffusion estimate.
For upwind: numerical viscosity ≈ |u|Δ/2. For LUST: ≈ |u|Δ/8.

**Practical test:**
```
In ParaView: plot nut (SGS viscosity) field
Compare with: ν_numerical ≈ 0.25 × U_mean × cell_size (for LUST)
If nut << ν_numerical: your LES is dominated by numerics
```

**Reference:** Montecchia et al. (2019) showed that Rhie-Chow interpolation is the dominant dissipation source in OpenFOAM LES, even with central differencing.

**Scheme requirements:**
| Scheme | Numerical viscosity | LES quality |
|--------|-------------------|-------------|
| Upwind (1st order) | ~|u|Δ/2 | **TERRIBLE** — worse than no SGS model |
| LinearUpwind (2nd) | ~|u|Δ²/6 × ∂u/∂x | Acceptable if mesh is fine |
| LimitedLinearV | Between linearUpwind and linear | Acceptable |
| LUST (75% central) | ~|u|Δ/8 | **Recommended** |
| Linear (central) | 0 (but unstable) | Best accuracy, worst stability |

### Problem 2: Resolution — How Fine Is Fine Enough?

**Pope's 80% criterion:** At least 80% of the turbulent kinetic energy should be resolved (not modelled).

```
k_resolved / k_total > 0.8
```

Where k_total = k_resolved + k_SGS (from the SGS model).

**How to check in OpenFOAM:**
```
k_resolved = 0.5 × (⟨u'²⟩ + ⟨v'²⟩ + ⟨w'²⟩)    ← from time/phase averaging
k_SGS = ν_sgs / (Ck × Δ)                          ← from the SGS model
ratio = k_resolved / (k_resolved + k_SGS)
```

If ratio < 0.8 anywhere important, your mesh is too coarse there.

**Reference:** Davidson "How to estimate the resolution of an LES of recirculating flow" — proposes using two-point correlations as additional quality indicator.

**Two-point correlations:** For proper LES, the correlation function R(r) should show:
- A peak at r=0 (trivially 1.0)
- Decay to ~0 within a few cell widths
- If R(r) is still ~1 at r = Δ, the flow is under-resolved

**Energy spectra:** Plot E(k) vs wavenumber k:
- Should show -5/3 inertial range (Kolmogorov cascade)
- Should NOT pile up at the grid cutoff frequency (aliasing)
- If spectrum flattens or rises at high k, you have insufficient resolution

### Problem 3: Commutation Error

The filtering operation and spatial differentiation do NOT commute when the filter width varies:

```
∂ū/∂x ≠ ∂u/∂x̄
```

Error = O(Δ² ∂²Δ/∂x²) — proportional to the gradient of filter width.

**When this matters:**
- Near mesh refinement boundaries (Δ changes abruptly)
- At wall-normal stretching (boundary layers with high expansion ratio)
- At snappyHexMesh refinement level transitions

**For aortic CFD:** surfaceRefinementLevels [1,2] creates an 8:1 volume jump — massive commutation error at the refinement boundary. Use [n,n] (uniform) for LES.

**Reference:** Davidson Ch. 18.7 — "the commutation error... is usually neglected"

### Problem 4: Inlet Boundary Conditions

LES needs **turbulent inlet conditions** — not just a mean velocity profile. Without inlet turbulence, the LES develops its own turbulence structure from scratch, which takes many diameters (10-50D) of development length.

**Methods for generating inlet turbulence:**

1. **Precursor simulation:** Run a periodic channel/pipe simulation separately, feed its outlet as inlet to the main simulation. Most accurate, most expensive.

2. **Synthetic turbulence (DFSEM, Vortex Method):** Generate random fluctuations that satisfy specified Reynolds stress tensor and length scales. Faster than precursor, but turbulence "adjusts" over 3-5D.

3. **Recycling:** Take velocity from a plane downstream and feed it back to inlet with rescaling. Only works for flows with a homogeneous direction.

4. **4D flow MRI:** For cardiovascular — directly map measured velocity (contains real turbulence). Best if available.

5. **No inlet turbulence (just mean profile):** Acceptable if the inlet is far from the region of interest (>10D upstream). The flow will develop its own turbulence.

**For aortic CFD with AortaCFD:**
- MRI inlet: already contains measured turbulence (best option)
- CSV inlet: no turbulence — acceptable if inlet is >5D from region of interest
- The ascending aorta is typically long enough that inlet effects wash out before the arch

**Reference:** Davidson Ch. 18.27 — "Generating inlet turbulence is a major challenge in LES"

### Problem 5: Statistical Convergence — How Many Samples?

LES produces stochastic data — each timestep and each cycle is different. To extract meaningful statistics, you need MANY samples.

**Mean velocity:** Converges relatively fast (~5-10 cycles for aortic flow)

**Reynolds stresses ⟨u'u'⟩:** Converges slowly (~20-50 cycles)

**Higher-order statistics:** May never converge practically

**Phase averaging for pulsatile flow:**
```
⟨u⟩(t_phase) = (1/N) Σᵢ u(t_phase + i×T)
```
Where N = number of cycles averaged. Statistical error ~ 1/√N.

For 10% error in mean velocity: need N > 100/(0.1²) × σ²/μ² samples
For typical aortic flow: N ~ 10-20 for mean, N ~ 50-100 for stresses

**Reference:** Davidson Ch. 18.28 — "The time-averaging must be made over a sufficiently long time"

---

## Part 4: LES in OpenFOAM — Practical Implementation

### 4.1 The Complete OpenFOAM LES Setup

**constant/momentumTransport:**
```
simulationType  LES;

LES
{
    LESModel        WALE;
    turbulence      on;
    printCoeffs     on;
    delta           cubeRootVol;     // Filter width = (cell volume)^(1/3)

    WALECoeffs
    {
        Ck          0.094;           // Don't change unless you know why
        Cw          0.325;           // WALE constant
    }
}
```

**system/fvSchemes for LES:**
```
ddtSchemes
{
    default         backward;            // 2nd order (or CrankNicolson 0.9)
}

gradSchemes
{
    default         cellLimited Gauss linear 1;  // Full gradient limiting
}

divSchemes
{
    default         none;
    div(phi,U)      Gauss LUST grad(U);  // 75% central + 25% upwind
    div(phi,k)      Gauss upwind;         // SGS k (if used)
    div((nuEff*dev2(T(grad(U))))) Gauss linear;
}

laplacianSchemes
{
    default         Gauss linear limited 0.5;
}

snGradSchemes
{
    default         limited 0.5;
}
```

**system/fvSolution for LES:**
```
PIMPLE
{
    nOuterCorrectors    10;     // Same as laminar — don't increase for LES
    nCorrectors         2;
    nNonOrthogonalCorrectors 0;
    pRefCell            0;
    pRefValue           0;

    outerCorrectorResidualControl
    {
        p { tolerance 1e-3; relTol 0; }
        U { tolerance 1e-4; relTol 0; }
    }
}

relaxationFactors
{
    fields    { p 0.5; pFinal 1; }
    equations { "U.*" 0.8; "k.*" 1; }
}
```

**system/controlDict for LES:**
```
maxCo           0.5;          // CRITICAL: CFL < 0.5 for temporal accuracy
// OR for strict LES:
maxCo           0.3;          // Better temporal accuracy

adjustTimeStep  yes;
maxDeltaT       0.0001;       // Limit max timestep
```

### 4.2 Mesh Requirements

| Parameter | Laminar | RANS | LES |
|-----------|---------|------|-----|
| cells_per_diameter | 12-15 | 12-15 | **20-30** |
| y⁺ at wall | N/A | < 30 | **< 1** |
| Boundary layers | 3-5 | 5-10 | **10-15** |
| Expansion ratio | 1.2 | 1.1-1.3 | **< 1.1** |
| Cell aspect ratio | < 100 | < 100 | **< 5** (near-isotropic) |
| Refinement levels | [1,1] | [1,1]-[2,3] | **[n,n] uniform only** |

### 4.3 How to Check Your LES Quality

**Step 1: Check ν_SGS / ν ratio**
```python
# In ParaView or Python:
# nut = SGS viscosity (from simulation)
# nu = 3.7736e-6 (kinematic)
# If nut/nu > 1 in most of the domain: mesh is too coarse
# Ideal: nut/nu ~ 0.1-0.5 in the bulk
```

**Step 2: Check energy spectra at probe locations**
Place probes in the aorta (ascending, arch, descending) and record velocity time series. Compute spectra:
```python
import numpy as np
from scipy.signal import welch
f, Pxx = welch(u_timeseries, fs=1/dt, nperseg=1024)
plt.loglog(f, Pxx)
# Should show -5/3 slope in inertial range
```

**Step 3: Two-point correlations**
Extract velocity along a line. Compute:
```python
R(r) = ⟨u'(x) u'(x+r)⟩ / ⟨u'²⟩
# R should decay to ~0 within a few cell widths
# If R(Δ) > 0.5: under-resolved
```

**Step 4: Pope's criterion**
```
k_resolved = 0.5 * (UPrime2Mean_xx + UPrime2Mean_yy + UPrime2Mean_zz)
k_SGS ≈ nut² / (Ck × Δ)²
ratio = k_resolved / (k_resolved + k_SGS)
# If ratio > 0.8: good LES
# If ratio < 0.8: mesh too coarse for LES
```

---

## Part 5: LES for Aortic CFD — Specific Considerations

### 5.1 Why Aortic LES Is Especially Difficult

1. **Transitional flow:** Re 2000-4500 — turbulence is intermittent, not sustained
2. **Pulsatile:** Turbulence appears during systolic deceleration, disappears during diastole
3. **Complex geometry:** No homogeneous direction for averaging
4. **Small Re:** Inertial range is very short — subgrid model has little to do
5. **Long integration time:** Need 10-30 cardiac cycles for converged statistics
6. **Windkessel BCs:** Add complexity at outlets (backflow stabilisation issues)

### 5.2 What AortaCFD Does Automatically for LES

When `"model": "les"` is selected:
1. Generates WALE subgrid model configuration
2. Sets precise profile (CrankNicolson 0.9 + LUST)
3. Sets maxCo = 0.5
4. **Auto-disables hard backflow stabilisation** (Heaviside creates ν_SGS spikes)
5. Uses `pressureInletOutletVelocity` at outlets instead
6. Generates nut (eddy viscosity) initial field

### 5.3 Cost Estimation

For a 2M cell aortic mesh, 3 cardiac cycles at 0.81s:

| Factor | Laminar | LES |
|--------|---------|-----|
| Mesh | 2M | 10M (need finer for y⁺<1) |
| CFL | 1.0 | 0.3 |
| Steps/cycle | 30k | 300k |
| Cycles | 3 | 15 |
| Cost/step | 1× | 5× (5× more cells) |
| **Total** | **1×** | **~750×** |
| 32 cores | 1 day | 2 years |
| 200 cores | 4 hours | 5 months |
| 1000 cores | 1 hour | 1 month |

**Conclusion:** Aortic LES requires HPC with hundreds of cores and weeks of wall time.

### 5.4 When LES Is and Isn't Worth It

**USE LES when:**
- You need time-resolved vortex dynamics (e.g., studying vortex ring breakdown post-stenosis)
- You need turbulence statistics (Reynolds stresses, TKE budgets)
- You're validating against turbulence-resolved 4D flow MRI
- You're studying the effect of turbulence on near-wall transport

**DO NOT USE LES when:**
- You only need TAWSS and pressure drop (laminar gives these within 10-20%)
- Your mesh is too coarse (you'll get expensive laminar, not LES)
- You can't afford 10+ cardiac cycles
- You're doing clinical screening (too slow for routine use)
- You're comparing surgical options (relative differences captured by laminar)

---

## Exercise

Using the pre-computed BPM120 results:

```bash
# Compare Laminar vs RANS vs LES hemodynamics
for MODEL in robust rans les; do
  echo "=== $(echo $MODEL | tr '[:lower:]' '[:upper:]') ==="
  grep "TAWSS Mean\|OSI Mean\|TAWSS Max" \
    docs/tutorial/precomputed_results/BPM120_${MODEL}_hemodynamics.txt
  echo ""
done
```

**Questions to answer:**
1. How does TAWSS differ between laminar and LES? Why?
2. Is OSI higher or lower with LES? What does this mean physically?
3. Given the cost difference (1× vs 750×), when would you justify LES for your research?
4. What mesh resolution would you need for proper LES of your anatomy?

---

## Homework

1. Read Davidson Ch. 18 (sections 18.1-18.15 minimum)
2. Calculate: what y⁺ would your current mesh give for LES? (Use y⁺ ≈ uτ×y₁/ν)
3. If you have access to HPC: try running BPM120 with LES for 1 cardiac cycle
   - Compare nut field with laminar ν — is the ratio > 1?
   - Does the velocity field look different from laminar at peak systole?
4. Read Montecchia et al. (2019) — what did they find about numerical dissipation in OpenFOAM LES?

---

## Key References

### From Chalmers (tfd.chalmers.se)
- [Davidson L. "Fluid mechanics, turbulent flow and turbulence modeling"](https://www.tfd.chalmers.se/~lada/postscript_files/solids-and-fluids_turbulent-flow_turbulence-modelling.pdf) — Ch. 18-22 cover LES comprehensively
- [Davidson L. "How to estimate LES resolution"](https://www.cfd-sweden.se/lada/postscript_files/paper-resolution-IJHFF.pdf) — Quality criteria for LES
- [Davidson L. pyCALC-LES](https://www.tfd.chalmers.se/~lada/postscript_files/py-calc-les.pdf) — Python LES code with Smagorinsky and WALE
- [Salehi S. "PIMPLE algorithm" (2022)](https://www.tfd.chalmers.se/~hani/kurser/OS_CFD_2022/lectureNotes/PIMPLE.pdf) — Solver settings
- [MTF271 Turbulence Modeling course](https://www.tfd.chalmers.se/~lada/comp_turb_model/course_plan.html) — Full course on turbulence modelling
- [El-Alti M. LES tutorial (2007)](https://www.tfd.chalmers.se/~hani/kurser/OS_CFD_2007/MohammadElAlti/tutorial_elalti.pdf) — OpenFOAM LES tutorial
- [Penttinen O. pimpleFoam channel flow (2011)](https://www.tfd.chalmers.se/~hani/kurser/OS_CFD_2011/OlofPenttinen/projectReport.pdf) — LES model comparison

### Other Key Papers
- Nicoud F, Ducros F (1999) "Subgrid-scale stress modelling based on the square of the velocity gradient tensor" Flow Turbul Combust 62:183-200 — WALE model original paper
- Montecchia M et al (2019) "Improving LES with OpenFOAM by minimising numerical dissipation" J Turbulence 20:697-722 — Rhie-Chow dissipation problem
- Pope SB (2000) "Turbulent Flows" Cambridge University Press — Ch. 13: LES theory
- Cheng Z et al (2025) "Characteristics of transition to turbulence in a healthy thoracic aorta using LES" Sci Rep — Aortic LES application
