# PIMPLE Solver Settings for AortaCFD

**Status: DRAFT — under review. This document is a working record, not validated guidance.**

---

## 1. Background: How PIMPLE Works

PIMPLE merges PISO (inner corrector) and SIMPLE (outer corrector) loops.
All AortaCFD simulations use PIMPLE — users control behaviour through parameters.

From Chalmers lecture notes (Salehi 2022, slide 8):
> "The main idea behind the PIMPLE loop is to seek a fully converged steady-state
> solution with under-relaxation in each time step and proceed in time."
> "PIMPLE works for Co_max >> 1."
> "Under-relaxations can be used to have a smooth convergence in each time step."

The key parameters:
- `nOuterCorrectors`: number of outer (SIMPLE-like) loops per timestep (default: 1)
- `nCorrectors`: number of inner (PISO-like) pressure corrections per outer loop (default: 1)
- `nNonOrthogonalCorrectors`: additional pressure corrections for non-orthogonal meshes (default: 0)

Setting `nOuterCorrectors = 1` makes PIMPLE behave like PISO. Setting it higher
enables the outer correction loop with under-relaxation.

### PISO limitation (slide 7):
> "The momentum predictor is only solved once at each time step. The linearized momentum
> equation uses fluxes and pressure gradient from the previous time-step. This assumption
> is only acceptable for very small time-steps (Co_max < 1). Under-relaxation cannot be used."

### PIMPLE advantage (slide 8):
With nOuterCorrectors > 1, the momentum equation is re-solved with updated fluxes
and pressure from the current timestep. This allows larger Co and under-relaxation
for stability.

---

## 2. Explicit vs Implicit Relaxation

**This is the most important distinction for understanding our convergence problems.**

OpenFOAM has TWO types of relaxation, applied in different places in fvSolution:

### Implicit relaxation (equations block)

Applied to the **equation matrix** via `UEqn.relax()`. Modifies the matrix diagonal:

```
(aP/α) φP + Σ aN φN = r + ((aP/α) - aP) φ^(n-1)
```

From Chalmers notes (slide 31):
> "Regardless of α value, implicit relaxation guarantees matrix diagonal equality/dominance."

> "Therefore, it is common to have relaxationFactors dictionary as `".*" 1;`"

**Key property:** Even α = 1 does something useful (ensures diagonal dominance).
Values < 1 add extra diagonal weight for stability. This does NOT create a residual floor.

### Explicit relaxation (fields block)

Applied to the **field values** via `p.relax()`. Blends new solution with previous outer iteration:

```
φ_relaxed = φ^(n-1) + α (φ^n - φ^(n-1))
```

From Chalmers notes (slide 34):
> "Unlike implicit relaxations of equations, setting explicit relaxation of fields to
> α = 1 does not have any effects."

> "The explicit relaxation in PIMPLE loop uses contribution from previous outer
> corrector iteration."

**Key property:** α = 1 is a no-op. α < 1 blends with the previous outer iteration,
discarding `(1-α)` of the correction. **This is what creates the residual floor.**

### What AortaCFD currently uses

```
relaxationFactors
{
    fields                              // EXPLICIT relaxation
    {
        p           0.3;               // ← THIS creates the residual floor
        pFinal      1.0;
    }
    equations                           // IMPLICIT relaxation
    {
        U           0.7;               // ← This helps stability, no floor
        UFinal      1.0;
    }
}
```

- **p** uses EXPLICIT relaxation (field blending) with α = 0.3
  → Each outer iteration discards 70% of the pressure correction
  → Creates a residual floor that PIMPLE cannot push below
  → This is why VOL04 standard profile burned all 30 outer iterations

- **U** uses IMPLICIT relaxation (matrix diagonal) with α = 0.7
  → Adds diagonal weight for stability
  → U converges fine (reaches 1e-6 by iteration 3)

- **pFinal / UFinal = 1.0**: on the LAST outer iteration, full correction is applied.
  This is critical for Windkessel coupling (the WK ODE needs the true pressure).

---

## 3. The Residual Floor Problem (Observed)

### VOL04 laminar_2M_v2: standard profile, nOuterCorrectors=30, p relax=0.3

```
PIMPLE iter 1:  p residual = 0.095     (big initial correction)
PIMPLE iter 2:  p residual = 0.006
PIMPLE iter 3:  p residual = 0.002
PIMPLE iter 4:  p residual = 0.0009
PIMPLE iter 5:  p residual = 0.0006
PIMPLE iter 6:  p residual = 0.0005    ← floor reached
...
PIMPLE iter 30: p residual = 0.0005    ← still at floor, target was 1e-4
```

**outerCorrectorResidualControl target: p < 1e-4**
**Actual floor: ~5e-4**
**Result:** 1622 out of 1623 timesteps burned all 30 iterations. 3.8x slower than robust.

### 0023 run_A_laminar_robust: robust profile, nOuterCorrectors=25

With Euler + upwind (robust profile), the system is better conditioned.
p converges below target in 4 iterations, PIMPLE exits early, average 5.5 iters/step.

### Root cause

The explicit relaxation `p 0.3` creates a floor because each outer iteration
blends 70% of the old p field back in. The correction that would push the residual
lower is discarded. The target 1e-4 sits below this floor.

---

## 4. What the Literature Says (and What It Doesn't)

### What IS established:

1. **PIMPLE default is nOuterCorrectors = 1** (Chalmers notes, OpenFOAM docs)
2. **Implicit relaxation α=1 ensures diagonal dominance** (Chalmers notes slide 31)
3. **Explicit relaxation α=1 has no effect** (Chalmers notes slide 34)
4. **PISO requires Co < 1** (Chalmers notes slide 7)
5. **PIMPLE allows Co >> 1 with outer corrections** (Chalmers notes slide 8)

### OpenFOAM LES tutorials:

| Tutorial | nOuter | nCorr | Relaxation | Time scheme |
|---|---|---|---|---|
| channel395 (Foundation OF-7) | 1 | 2 | none | backward |
| channel395DFSEM (ESI) | 3 | 1 | equations ".*" 1 | backward |
| pitzDaily LES (compressible) | 3 | 1 | equations ".*" 1 | backward |

Both nOuter=1 and nOuter=3 are used in official LES tutorials.
When nOuter > 1, relaxation is equations-only at 1.0 (implicit, for diagonal dominance).
No LES tutorial uses explicit field relaxation (α < 1).

### Cardiovascular CFD:

- Raza (Chalmers 2024): nOuter=1, nCorr=2, no relaxation, Euler, constant dt, Windkessel BCs
- Boccadifuoco et al. (2023): pimpleWKFoam, Euler, maxCo=0.8, exact PIMPLE settings not reported
- CoronaryHemodynamics (2025): custom solver, constant dt=1e-4, exact PIMPLE settings not reported

### What is NOT established in any source reviewed:

- How many outer correctors are optimal for any specific physics model
- Whether outer correctors add dissipation to resolved LES scales
- The relationship between CFL and nOuterCorrectors for LES accuracy
- Whether nOuter=5 is "enough" or nOuter=50 is "wasteful"
- Any recommended nOuterCorrectors for RANS vs laminar vs LES

**The claim in a previous version of this document that "Going to 5 gives a safety
margin. Going higher (10, 50) is wasting compute" was fabricated by inference and
has no source. It has been removed.**

---

## 5. Current Profile Settings and Known Issues

### Standard profile (current)
```
nOuterCorrectors: 50
nCorrectors: 2
p relaxation: 0.3 (EXPLICIT)    ← creates residual floor
U relaxation: 0.7 (IMPLICIT)
pFinal/UFinal: 1.0
outerResidualControl p: 1e-4    ← below the floor → never exits early
maxCo: 1.0
Time: backward, Conv: limitedLinearV 1
```
**Known issue:** p explicit relaxation 0.3 creates floor at ~5e-4, above target 1e-4.
Every timestep burns all 50 outer iterations.

### Robust profile (current)
```
nOuterCorrectors: 25
nCorrectors: 3
p relaxation: 0.3 (EXPLICIT)    ← same issue but target is 1e-3
U relaxation: 0.7 (IMPLICIT)
pFinal/UFinal: 1.0
outerResidualControl p: 1e-3    ← above the floor → exits early (~5 iters)
maxCo: 1.0
Time: Euler, Conv: upwind
```
**Works because:** target 1e-3 is above the floor 5e-4, so PIMPLE exits early.
Also, Euler+upwind produces smaller corrections that converge faster.

### Precise profile (current)
```
nOuterCorrectors: 50
nCorrectors: 3
p relaxation: 0.3 (EXPLICIT)    ← same floor problem as standard
U relaxation: 0.7 (IMPLICIT)
pFinal/UFinal: 1.0
outerResidualControl p: 1e-4
maxCo: 0.5
Time: CrankNicolson 0.9, Conv: LUST
```
**Same issue as standard** — p floor above target.

---

## 6. Open Questions for Testing

These need actual simulation testing, not literature inference:

1. **What combination of explicit p relaxation and residual target works?**
   - Option A: Remove explicit p relaxation entirely (set to 1.0 or remove from fields)
     → Will PIMPLE converge without it? May oscillate on poor meshes.
   - Option B: Keep p=0.3 but relax target to 1e-3 (like robust does)
     → Accepts the floor, exits early. But is this accurate enough?
   - Option C: Increase p to 0.5-0.7 with target 1e-3
     → Lower floor, still some damping.

2. **How many nOuterCorrectors are actually needed for Windkessel coupling?**
   The Windkessel BC imposes a pressure-flow ODE that couples nonlinearly to the
   pressure equation. Does this need more outer iterations than a simple outlet?
   → Test nOuter=1 vs 3 vs 10 on 0023 with Windkessel.

3. **Does the physics model (laminar/RANS/LES) change the answer?**
   The Chalmers notes make no distinction. The tutorials show both nOuter=1 and
   nOuter=3 for LES. No source establishes that LES needs different PIMPLE settings.
   → Test on VOL04 or 0014 with RANS and LES.

4. **Is implicit-only relaxation (equations ".*" 1) sufficient for all profiles?**
   The ESI LES tutorials and the OpenFOAM v13 docs both recommend this.
   But cardiovascular meshes (snappyHexMesh, bifurcations, small outlets) may
   need explicit p relaxation for stability.
   → Test on 0023 and VOL04.

5. **What CFL is needed for accurate LES of aortic flow?**
   Montecchia et al. (2019) showed CFL sensitivity for channel flow.
   Aortic flow is different (pulsatile, transitional, complex geometry).
   → Needs CFL sensitivity study.

---

## References

1. Salehi S. "PIMPLE algorithm and pimpleFoam solver" — Chalmers Open-Source CFD
   Course Lecture Notes (September 2022). Based on OpenFOAM v2112.
   https://www.tfd.chalmers.se/~hani/kurser/OS_CFD_2022/lectureNotes/PIMPLE.pdf

2. OpenFOAM v13 User Guide, Section 4.6 "Solution and algorithm control"
   https://doc.cfd.direct/openfoam/user-guide-v13/fvsolution

3. CFD Direct "Notes on CFD: General Principles", Section 5.21 "The PIMPLE algorithm"
   https://doc.cfd.direct/notes/cfd-general-principles/the-pimple-algorithm

4. Raza MA. "Cardiovascular CFD with Windkessel BCs" — Chalmers OS CFD Project (2024)
   https://www.tfd.chalmers.se/~hani/kurser/OS_CFD_2024/MuhammadAhmadRaza/

5. Boccadifuoco A et al. "Blood Flow Simulation of Aneurysmatic and Sane Thoracic
   Aorta Using OpenFOAM CFD Software." Fluids (2023) 8(10):272.

6. OpenFOAM Foundation LES tutorial: channel395 fvSolution
   https://github.com/OpenFOAM/OpenFOAM-7/blob/master/tutorials/incompressible/pimpleFoam/LES/channel395/system/fvSolution

7. OpenFOAM ESI LES tutorial: channel395DFSEM
   https://develop.openfoam.com/Development/OpenFOAM-plus

8. Montecchia M et al. "Improving LES with OpenFOAM by minimising numerical
   dissipation." J Turbulence (2019) 20:697-722.

9. CoronaryHemodynamics automated framework (2025)
   https://arxiv.org/html/2501.08340v1
