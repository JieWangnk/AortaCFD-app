# Session 5: Inlet Boundary Conditions

**Duration:** 2 hours
**Goal:** Map clinical data to inlet BCs for different imaging modalities

---

## Hour 1: Inlet Types (60 min)

### 1.1 Overview: From Clinical Data to OpenFOAM BC (10 min)

| Clinical data available | AortaCFD inlet type | Profile shape |
|------------------------|--------------------|----|
| Cardiac output only (L/min) | `CONSTANT` | Plug or parabolic |
| Doppler flow waveform | `TIMEVARYING` + CSV | Plug, parabolic, or wall-distance |
| Phase-contrast MRI waveform | `TIMEVARYING` + CSV | Parabolic or Womersley |
| 4D flow MRI velocity field | `MRI` | Measured (spatially resolved) |

**Key principle:** Use the most detailed data you have. But even "cardiac output only" produces reasonable results for pressure-based metrics.

### 1.2 CONSTANT Inlet (10 min)

Simplest case — steady flow from cardiac output:

```json
"inlet": {
    "type": "CONSTANT",
    "cardiac_output": 5.0,
    "profile": "parabolic"
}
```

- `cardiac_output`: L/min → converted to velocity via inlet area
- `profile`: `plug` (uniform) or `parabolic` (zero at walls)
- Good for: quick tests, pressure-drop estimation
- Not good for: WSS accuracy (no pulsatility)

### 1.3 TIMEVARYING Inlet (15 min)

Pulsatile flow from a CSV file:

```json
"inlet": {
    "type": "TIMEVARYING",
    "csv_file": "flowrate.csv",
    "data_type": "flowrate",
    "profile": "parabolic"
}
```

CSV format:
```csv
Time,Flowrate
0.0000,1.50
0.0100,2.30
0.0200,4.50
...
```

- Units: time in seconds, flowrate in L/min (auto-detected) or m³/s
- The pipeline maps this waveform onto every face of the inlet patch
- Profile options: `plug`, `parabolic`, `wall_distance`, `womersley`

**Unit auto-detection:** AortaCFD automatically detects whether your CSV is in L/min (values > 1) or m³/s (values ~1e-5). No manual conversion needed.

**Exercise:** Open `cases_input/BPM120/flowrate.csv` and plot it:
```python
import numpy as np, matplotlib.pyplot as plt
data = np.loadtxt('cases_input/BPM120/flowrate.csv', delimiter=',', skiprows=1)
plt.plot(data[:,0], data[:,1])
plt.xlabel('Time (s)'); plt.ylabel('Flow rate (L/min)')
plt.title('BPM120 Inlet Waveform'); plt.savefig('waveform.png')
```

### 1.4 Wall-Distance Profile (15 min)

The novel AortaCFD approach for irregular (non-circular) inlets:

```
u(x, t) = u_max(t) × [1 - (1 - d(x)/d_max)^n]
```

Where:
- `d(x)` = distance from face centre to nearest wall point
- `d_max` = maximum distance (at geometric centre)
- `n = 2` gives parabolic-like profile
- Flow rate is enforced by adjusting `u_max`

**Why this matters:** Real aortic inlets are elliptical or D-shaped, not circular. Standard parabolic profiles assume circular geometry.

### 1.5 MRI Inlet (10 min)

For 4D flow MRI data:

```json
"inlet": {
    "type": "MRI",
    "file": "./inlet/"
}
```

The `inlet/` directory contains pre-processed OpenFOAM boundaryData:
```
inlet/
├── points           # Face centre coordinates
├── 0.000000/U       # Velocity vectors at t=0
├── 0.012000/U       # Velocity vectors at t=0.012
└── ...
```

This is the most accurate but requires MRI post-processing beforehand.

**Validation note:** the `inlet/` directory for VOL04 in this repo
contains 811 time snapshots (~58 MB) at 1 ms resolution covering
one cycle. The pipeline reads each, interpolates onto the mesh's
inlet face centroids, and writes OpenFOAM-format `boundaryData`.
On this laptop with a 4-CPU 10-min wall budget, the per-face
interpolation step alone (`Prepare Boundary Data...`) does not
finish — VOL04 with the full MRI dataset wants more like 30-60 min
of wall time before the solver starts. The workflow IS wired and
the config validates; just plan for a longer budget when running
MRI-mapped cases. For laptop demos, the `inflow.csv` TIMEVARYING
flow on the same VOL04 geometry (see workshop lesson 4 for the
analogous BPM120 setup) is the practical substitute.

---

## Hour 2: Inlet Quality and Comparison (60 min)

### 2.1 The Inlet Audit Report (15 min)

After running `--steps boundary`, check:
```bash
cat reports/inlet_audit.json
```

This reports:
- Inlet area (mm²)
- Mean flow rate (mL/s)
- Mean velocity (m/s)
- Womersley number (α)
- Reynolds number (Re)
- Profile recommendation

**Womersley number** α = R × √(2πf/ν):
- α < 5: quasi-steady (parabolic OK)
- α = 5-15: pulsatile effects moderate
- α > 15: flat profile during systole (plug may be appropriate)

**For aortic flows:** typically α ≈ 15-20, meaning the profile is relatively flat during peak systole.

### 2.2 Exercise: Compare Inlet Profiles (25 min)

Run the same case with different profiles:

```bash
# 1. Plug profile
# Edit config: "profile": "plug"
python run_patient.py BPM120 --config config_plug.json --run-name plug_test --steps case,mesh,boundary

# 2. Parabolic profile
# Edit config: "profile": "parabolic"
python run_patient.py BPM120 --config config_para.json --run-name para_test --steps case,mesh,boundary

# 3. Wall-distance profile
# Edit config: "profile": "wall_distance"
python run_patient.py BPM120 --config config_wd.json --run-name wd_test --steps case,mesh,boundary
```

In ParaView: slice the inlet patch, compare velocity distributions.

### 2.3 How Far Downstream Does the Profile Matter? (10 min)

Literature shows (Morbiducci et al. 2013, Pirola et al. 2017):
- Beyond 3-5 inlet diameters, the flow "forgets" the inlet profile
- Geometric features (curvature, branches) dominate
- For pressure-based metrics: inlet profile barely matters
- For WSS near the inlet: profile matters significantly

### 2.4 Creating Your Own Inlet Waveform (10 min)

If you have published data (from a paper or Doppler measurement):

1. Digitise the waveform (use WebPlotDigitizer or similar)
2. Save as CSV: `time,flowrate` in L/min
3. Place in your case folder
4. Reference in config: `"csv_file": "my_waveform.csv"`

```python
# Example: create a simple sinusoidal waveform
import numpy as np
t = np.linspace(0, 0.8, 100)  # 0.8s cardiac cycle
Q = 5.0 + 10.0 * np.sin(2 * np.pi * t / 0.8)  # L/min, mean=5, peak=15
Q[Q < 0] = 0  # no negative flow
np.savetxt('my_waveform.csv', np.column_stack([t, Q]),
           delimiter=',', header='Time,Flowrate', comments='')
```

---

## Homework

1. Find a published aortic flow waveform from any paper
2. Digitise it and create a CSV file
3. Run BPM120 with your custom waveform
4. Compare pressure waveform at an outlet with the original BPM120 waveform
5. Write down: what Womersley number does your case have? What does it mean?
