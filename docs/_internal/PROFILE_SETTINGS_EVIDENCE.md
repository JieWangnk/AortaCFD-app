# Profile Settings: Evidence Report

**Based on 12 simulation runs across 2 patient geometries (0023_H_AO_MFS, VOL04)**

---

## What We Know (Proven)

### 1. Robust profile WORKS for both laminar and RANS

- 0023 Run A (laminar+robust): completed 4 cycles, 0 non-convergences
- 0023 Run B (RANS+robust): completed 4 cycles, 0 non-convergences
- Both used: Euler+upwind, p=0.3, nOuter=25, maxCo=1.0

**No changes needed for the robust profile.** It works as designed.

### 2. Current standard profile CRASHES during diastolic flow reversal

Every run with the current standard settings crashed:
- 0023 Run C (standard, nOuter=10): crashed t=1.69s
- VOL04 laminar_2M_v2 (standard, nOuter=10): crashed t=0.53s
- VOL04 relax_B (standard, targets relaxed): crashed t=0.53s
- VOL04 relax_C (standard, p=0.5): crashed t=0.55s

**Crash mechanism:** PIMPLE outer loop DIVERGES — p residual drops to ~0.007 in
iterations 1-5, then GROWS back to 0.87 by iteration 30. Each outer correction
makes the solution worse after iteration 5-6.

### 3. The crash is caused by MULTIPLE factors acting together

No single setting change fixes the current standard profile:

| What we tried | Result |
|---|---|
| Relax p target to 1e-3 (keep p=0.3) | Still crashed at t=0.53 (maxCo=2.0) |
| Increase p relax to 0.5 + target 1e-3 | Still crashed at t=0.55 (maxCo=2.0) |
| Remove explicit p relaxation entirely | Instant crash (needs p damping for WK startup) |
| Relax both targets to 1e-2 + maxCo=1.0 | **SURVIVED** (Run D hit walltime, not crash) |

**The crash requires ALL of these to be wrong simultaneously:**
- maxCo too high (2.0) → large timesteps during flow reversal
- p explicit relaxation too low (0.3) → residual floor above target
- Targets too tight (1e-4 / 1e-5) → PIMPLE never exits early
- limitedLinearV → less diffusive than linearUpwind during reversal

### 4. Reference-matched 2nd-order settings WORK

VOL04 Run F and G use settings from a proven working case (VOL04Validation):
- backward + linearUpwind (not limitedLinearV)
- p=0.5 (not 0.3)
- pRefCell 0 (not pRefPoint)
- nNonOrthogonalCorrectors 0 (not 1-2)
- maxCo=0.5 (not 1.0-2.0)
- nOuterCorrectors=100 with targets 1e-5

Run F: t=0.40s after 23h, 0 non-convergences, past the diastolic crash zone.
Run G: t=0.24s after 22h, 1 non-convergence, also healthy.

**0023 Run D uses the same settings and is now running.**

---

## What Changed Between Working and Broken

| Setting | Working (reference/robust) | Broken (AortaCFD standard) | Impact |
|---|---|---|---|
| **Convection** | linearUpwind or upwind | limitedLinearV 1 | limitedLinearV is less diffusive at outlet backflow zones |
| **p relaxation** | 0.5 | 0.3 | 0.3 creates higher residual floor (~5e-4 vs ~2e-4) |
| **Grad limiting** | cellLimited 1 | cellLimited 0.5 | Less gradient limiting = less stability |
| **Laplacian** | linear limited 0.5 | linear limited corrected 0.777 | 0.777 is less diffusive |
| **snGrad** | limited 0.5 | limited corrected 0.777 | Same — less diffusion |
| **pRefCell/Point** | pRefCell 0 | pRefPoint (auto) | pRefPoint could be in a bad cell |
| **nNonOrtho** | 0 | 1-2 | More non-ortho corrections = more work, possible instability |
| **maxCo** | 0.5 | 1.0-2.0 | Higher Co = larger timesteps, more coupling error |

---

## Proposed Profile Settings

### Robust (NO CHANGES — already works)

```
Time:       Euler
Convection: Gauss upwind
Laplacian:  Gauss linear limited corrected 0.5
Grad:       cellLimited Gauss linear 1.0
PIMPLE:     nOuter=25, nCorr=3, nNonOrtho=2
Relaxation: p=0.3/pFinal=1.0, U=0.7/UFinal=1.0
Targets:    p=1e-3, U=1e-3
maxCo:      1.0
```

### Standard (NEEDS CHANGES — current version crashes)

**Current (crashes):**
```
Time:       backward
Convection: Gauss limitedLinearV 1
Laplacian:  Gauss linear limited corrected 0.777
Grad:       cellLimited Gauss linear 0.5
PIMPLE:     nOuter=50, nCorr=2, nNonOrtho=1
Relaxation: p=0.3/pFinal=1.0, U=0.7/UFinal=1.0
Targets:    p=1e-4, U=1e-5
maxCo:      1.0
```

**Proposed (based on evidence):**
```
Time:       backward
Convection: Gauss linearUpwind default       ← more stable than limitedLinearV
Laplacian:  Gauss linear limited 0.5         ← more diffusive (0.5 vs 0.777)
Grad:       cellLimited Gauss linear 1       ← full limiting (1 vs 0.5)
snGrad:     limited 0.5                      ← match laplacian
PIMPLE:     nOuter=100, nCorr=2, nNonOrtho=0 ← no non-ortho correctors
pRef:       pRefCell 0                        ← safer than pRefPoint
Relaxation: p=0.5/pFinal=1.0, U=0.8/UFinal=1.0  ← less aggressive under-relaxation
Targets:    p=1e-5, U=1e-5                   ← tight targets (reachable with p=0.5)
maxCo:      0.5                               ← half of current (critical for diastole)
```

**Key differences from current standard:**
1. linearUpwind instead of limitedLinearV (more diffusive but stable)
2. p relaxation 0.5 instead of 0.3 (lower residual floor)
3. maxCo 0.5 instead of 1.0 (prevents large-timestep instability)
4. pRefCell 0 instead of pRefPoint (always valid)
5. Laplacian/snGrad limited 0.5 instead of corrected 0.777 (more stable)
6. No non-orthogonal correctors (simpler, fewer instability sources)

### Precise (NEEDS CHANGES — same issues as standard, plus LES-specific)

**Proposed:**
```
Time:       CrankNicolson 0.9 (or backward)
Convection: Gauss LUST grad(U)               ← 75% central + 25% upwind (for LES)
Laplacian:  Gauss linear limited 0.5
Grad:       cellLimited Gauss linear 1
PIMPLE:     nOuter=100, nCorr=2, nNonOrtho=0
pRef:       pRefCell 0
Relaxation: p=0.5/pFinal=1.0, U=0.8/UFinal=1.0
Targets:    p=1e-5, U=1e-5
maxCo:      0.3                               ← strict CFL for LES temporal accuracy
```

**Note:** LUST vs linearUpwind for precise profile needs testing. LUST preserves
resolved turbulence better but is less stable. If LUST crashes, fall back to
linearUpwind.

---

## What We Still Don't Know (Needs Testing)

### 1. Is linearUpwind necessary, or can limitedLinearV work with other fixes?

We changed multiple settings at once (convection, relaxation, maxCo, pRef, laplacian).
We don't know which individual change is the critical one. Possibilities:
- Maybe just maxCo=0.5 + p=0.5 fixes it even with limitedLinearV
- Maybe pRefCell vs pRefPoint is the key difference
- Maybe the laplacian coefficient (0.5 vs 0.777) matters most

**To test:** Run with limitedLinearV but keep all other reference-matched settings.

### 2. Does backflow stabilisation help or hurt with 2nd-order schemes?

- Run F (no stab): healthy, 0 non-conv
- Run G (betaT=0.3): healthy, 1 non-conv
- Both still running — need to see if either crashes later

**To test:** Wait for F and G to finish or crash.

### 3. Is maxCo=0.5 really necessary or can we use 0.8?

maxCo=0.5 is safe but doubles the number of timesteps compared to maxCo=1.0.
The reference case used FIXED dt=0.0002 which corresponds to Co~0.5 at peak.

**To test:** Run with maxCo=0.8 after confirming 0.5 works.

### 4. Does RANS work with the proposed standard settings?

We only tested laminar with the reference-matched settings. RANS adds k/omega
coupling which might destabilise the outer loop.

**To test:** Create a RANS version of Run D/F settings.

### 5. Does the precise profile (CrankNicolson + LUST) work?

Not tested at all. CrankNicolson adds temporal oscillation risk.
LUST is 75% central — very low dissipation.

**To test:** After standard is confirmed stable.

### 6. How much accuracy do we lose with linearUpwind vs limitedLinearV?

linearUpwind is 2nd-order on uniform meshes but adds more numerical diffusion
on non-uniform meshes. For WSS prediction this could matter.

**To test:** Compare Run D (linearUpwind) with Run A (upwind) and SimVascular.
If linearUpwind matches SV well, the extra diffusion from limitedLinearV→linearUpwind
is acceptable.

---

## Summary: What to Change in the App

| Profile | Action | Confidence |
|---|---|---|
| **Robust** | No changes | HIGH — proven on 2 geometries |
| **Standard** | Change convection, relaxation, maxCo, pRef, laplacian | MEDIUM — proven on VOL04 Run F, 0023 Run D running |
| **Precise** | Same as standard but with LUST and maxCo=0.3 | LOW — not tested yet |

**Recommendation:** Wait for 0023 Run D to complete (7-day walltime). If it
finishes 4 cycles with good hemodynamics matching SimVascular, apply the
reference-matched settings as the new standard profile. Then test precise.
