# Session 4: Numerical Profiles + Solver Behaviour

**Duration:** 2 hours
**Goal:** Choose the right profile, read solver logs, diagnose problems

---

## Hour 1: The Three Profiles (60 min)

### 1.1 What Each Scheme Does Physically (20 min)

**Time schemes** — how the time derivative is approximated:
- `Euler`: 1st order. Uses only current + previous timestep. Very stable, very diffusive.
- `backward`: 2nd order. Uses current + 2 previous timesteps. More accurate, less stable.
- `CrankNicolson 0.9`: 2nd order with 90% CN + 10% Euler blending. Minimal diffusion.

**Convection schemes** — how velocity transports quantities:
- `upwind`: 1st order. Always takes the upstream value. Maximum stability, maximum diffusion.
- `linearUpwind`: 2nd order. Uses upstream + gradient correction. Good balance.
- `LUST`: 75% central + 25% upwind. Minimal diffusion, needs good mesh.

**The physical effect of numerical diffusion:**
- High diffusion (robust): smears velocity gradients → WSS is under-predicted
- Low diffusion (precise): preserves gradients → WSS is accurate but solver can crash
- Standard: balanced trade-off

### 1.2 Profile Comparison Table (10 min)

| | Robust | Standard | Precise |
|---|---|---|---|
| Time | Euler | backward | CrankNicolson 0.9 |
| Convection | upwind | linearUpwind | LUST |
| maxCo | 1.0 | 0.8 | 0.5 |
| p relaxation | 0.3 | 0.5 | 0.5 |
| Accuracy | Low | Good | Best |
| Stability | Maximum | Good | Needs good mesh |
| Speed | Fast | Medium | Slowest |

### 1.3 Live Demo: Same Case, Two Profiles (20 min)

```bash
# Already have robust results from Session 1
# Run standard profile
python run_patient.py BPM120 --config config_standard.json --run-name standard_demo --steps case,mesh,boundary,solver

# Compare in ParaView (use pre-computed if solver hasn't finished)
```

Open both in ParaView, compare:
- Velocity streamlines at peak systole — standard shows sharper flow features
- TAWSS on wall — robust is smoother (more diffusion), standard shows more detail
- Pressure — nearly identical (pressure is robust to scheme choice)

### 1.4 Pre-computed Comparison (10 min)

```bash
cat docs/tutorial/precomputed_results/profile_comparison.txt
```

| Metric | Robust | Standard | Precise |
|--------|--------|----------|---------|
| TAWSS Mean (Pa) | 4.28 | 4.50 | 4.47 |
| OSI Mean | 0.18 | 0.21 | 0.11 |
| Inlet P (mmHg) | 115.9 | 114.4 | 119.1 |

**Key takeaway:** Pressure varies by ~4% between profiles. TAWSS varies by ~5%. OSI varies by ~50%. Choice matters most for oscillatory metrics.

---

## Hour 2: Reading Solver Logs (60 min)

### 2.1 Understanding log.solver (20 min)

```bash
# View the last part of the solver log
tail -100 output/BPM120/run_xxx/openfoam/logs/log.solver
```

What each line means:
```
Time = 0.5s                                    ← Current simulation time
Courant Number mean: 0.05 max: 0.98            ← Flow speed × dt / cell size
deltaT = 3.2e-05                               ← Current timestep
PIMPLE: Iteration 1                            ← Outer corrector loop
  smoothSolver: Solving for Ux, Initial residual = 0.001, Final = 1e-7  ← Velocity solve
  GAMG: Solving for p, Initial residual = 0.5, Final = 1e-6             ← Pressure solve
  continuity errors: sum local = 1e-10         ← Mass conservation check
PIMPLE: Converged in 3 iterations              ← Early exit (good!)
ExecutionTime = 1234 s  ClockTime = 1300 s      ← Wall clock time
```

### 2.2 Healthy vs Unhealthy Solver Behaviour (15 min)

**Healthy:**
```
PIMPLE: Converged in 3 iterations    ← exits early, 3 out of 10 max
Courant Number max: 0.98             ← close to maxCo but not over
deltaT = 3.2e-05                     ← stable timestep
```

**Warning signs:**
```
PIMPLE: Not converged within 10 iterations   ← hitting the limit
deltaT = 1.5e-08                              ← timestep getting very small
Courant Number max: 3.5                       ← way above maxCo
```

**Crash imminent:**
```
deltaT = 1e-110                               ← collapsed
FOAM FATAL ERROR                              ← game over
Floating point exception                      ← NaN in the solution
```

### 2.3 Exercise: Plot Residuals (15 min)

```python
# Simple residual plotter (run in Python)
import re, matplotlib.pyplot as plt

with open('output/BPM120/run_xxx/openfoam/logs/log.solver') as f:
    log = f.read()

# Extract p residuals
p_residuals = [float(m) for m in re.findall(r'Solving for p, Initial residual = ([\d.e+-]+)', log)]

plt.semilogy(p_residuals[:500])
plt.xlabel('Solver iteration')
plt.ylabel('p residual')
plt.title('Pressure residual convergence')
plt.savefig('residuals.png')
print(f'Final residual: {p_residuals[-1]:.2e}')
```

### 2.4 Backflow Stabilisation Demo (10 min)

**The diastolic crash problem:**
During diastole, blood flow reverses at outlet patches. Without stabilisation, this creates spurious vortices that crash the solver.

```json
// Config WITH stabilisation (default, works):
"enable_stabilization": true, "betaT": 0.3

// Config WITHOUT stabilisation (may crash):
"enable_stabilization": false
```

**Exercise:** If you have a completed run, check the outlet pressure waveform — you should see systolic peak (~120 mmHg) and diastolic trough (~80 mmHg).

### 2.5 Physics Advisor and Reynolds Number (10 min)

AortaCFD estimates the Reynolds number from your inlet conditions and warns if your physics model choice may be inappropriate:

```
Re = U × D / ν
```

**For the aorta:**
- Typical peak Re: 500-4500 (transitional, not fully turbulent)
- Laminar simulation is scientifically defensible up to Re ~4000
- RANS (k-ω SST) may over-predict eddy viscosity at low Re
- LES is expensive (50-100x RANS cost) and only needed for research

The advisor runs automatically during config build — check the console output when you run `--steps case`.

### 2.6 Key Cardiovascular CFD Limitations (5 min)

Every AortaCFD simulation makes these assumptions:
- **Rigid walls** — real arteries are compliant (can affect WSS by 10-20%)
- **Newtonian blood** — real blood is shear-thinning (matters at low shear rates)
- **No FSI** — no fluid-structure interaction
- **Prescribed inlet** — no feedback from downstream vasculature

These are standard assumptions in published aortic CFD. Know them, state them in papers.

---

## Homework

1. Run BPM120 with `standard` and `precise` profiles (may need to run overnight)
2. Compare TAWSS maps in ParaView between robust and standard
3. Plot the pressure residual from your solver log
4. Check: how many PIMPLE iterations per timestep does your run use on average?
   ```bash
   grep "PIMPLE: Converged in" logs/log.solver | awk '{print $NF}' | sort | uniq -c
   ```
5. Read `docs/_internal/PIMPLE_SOLVER_SETTINGS.md` — focus on explicit vs implicit relaxation
