# Session 6: Post-Processing + Hemodynamics

**Duration:** 2 hours
**Goal:** Extract and interpret hemodynamic results, create publication figures

---

## Hour 1: Hemodynamic Metrics (60 min)

### 1.1 Running Post-Processing (10 min)

```bash
# On a completed run:
python run_patient.py --postprocess output/BPM120/run_xxx

# Or as part of the workflow:
python run_patient.py BPM120 --steps postprocess
```

Real output from the SESSION1 validation run (BPM120, 25 k cells,
4 CPU, 10-min wall budget):

```text
Post-processing: output/BPM120/validation_lesson01
  Computing hemodynamic metrics...

Results:
  Pressure drop (mean): 10.79 mmHg
  WSS p99 (peak systole): 58.11 Pa
```

That **10.79 mmHg** mean pressure drop is within 4.2 % of the Wang
et al. paper reference (11.26 mmHg ± 5 %) — expected agreement for
a coarse 1-cycle laptop run; the paper result comes from a ~1 M-cell
mesh on HPC. The `qoi_summary.json` produced here is what the
`compare_cohort` Block-D aggregator ingests in workshop lesson 5.

Outputs:
```
reports/hemodynamics_report.txt    # Human-readable summary
results/qoi_summary.json          # Machine-readable metrics
results/qoi_summary.csv           # Spreadsheet format
```

### 1.2 TAWSS — Time-Averaged Wall Shear Stress (15 min)

**Formula:**
```
TAWSS = (1/T) ∫₀ᵀ |τ_w(t)| dt
```

**Clinical meaning:**
- Measures the average mechanical force on the blood vessel wall
- Low TAWSS (< 0.4-0.5 Pa) → atherogenic: promotes plaque formation
- High TAWSS (> 40 Pa) → endothelial injury risk
- Normal range: 1-5 Pa for healthy aorta

**In the report:**
```
TAWSS Mean:    4.50 Pa       ← average over entire wall
TAWSS P95:     8.20 Pa       ← 95th percentile (robust descriptor)
TAWSS P99:     15.6 Pa       ← 99th percentile
TAWSS Maximum: 145 Pa        ← single cell peak (often mesh artifact)
```

**Why percentiles, not maximum?** The maximum WSS is often at a single cell near a refinement boundary or sharp geometric feature — it's a mesh artifact, not physics. P95 and P99 are robust descriptors that converge with mesh refinement.

### 1.3 OSI — Oscillatory Shear Index (15 min)

**Formula:**
```
OSI = 0.5 × (1 - |∫τ_w dt| / ∫|τ_w| dt)
```

**Clinical meaning:**
- Measures how much the WSS direction changes during the cardiac cycle
- OSI = 0: unidirectional flow (healthy)
- OSI = 0.5: fully oscillatory (disturbed flow)
- High OSI regions correlate with disturbed flow and adverse remodelling

**Masked OSI:** AortaCFD reports OSI only where TAWSS > 0.5 Pa (Les et al. 2010). This filters out low-shear regions where OSI is numerically noisy.

### 1.4 RRT — Relative Residence Time (10 min)

**Formula:**
```
RRT = 1 / ((1 - 2×OSI) × TAWSS)
```

**Clinical meaning:**
- Combines low shear + oscillatory effects
- High RRT → particles stay near the wall longer → thrombosis risk
- RRT > 10 Pa⁻¹ is considered elevated

### 1.5 Pressure Drop (10 min)

```
ΔP = P_inlet - P_outlet (cycle-averaged)
```

- Reported per outlet in mmHg
- Clinically significant: ΔP > 20 mmHg at rest suggests coarctation
- Most robust metric — converges quickly with mesh and scheme

---

## Hour 2: ParaView Visualisation (60 min)

### 2.1 Loading Results (10 min)

```bash
paraview output/BPM120/run_xxx/openfoam/BPM120.foam &
```

1. Click **Apply** to load
2. Set time to peak systole (check `reports/` for peak time)
3. **Properties panel:** select fields to display

### 2.2 Velocity Streamlines (10 min)

1. Apply **Stream Tracer** filter
2. Seed type: **Point Cloud** at the inlet
3. Number of seeds: 200
4. Color by velocity magnitude
5. Set color range: 0 to 1.5 m/s

**What to observe:**
- Helical flow in the arch
- Flow separation at branches
- Recirculation zones in descending aorta

### 2.3 Wall Shear Stress Maps (10 min)

1. Apply **Extract Surface** filter
2. Select only `wall_aorta` patch
3. Color by `wallShearStress` (magnitude)
4. Set color range: 0 to 10 Pa (or use P99 as max)

**What to observe:**
- High WSS at branch ostia
- Low WSS on outer curve of arch
- WSS pattern follows flow features

### 2.4 Cross-Sectional Slices (10 min)

1. Apply **Slice** filter
2. Normal: Y-axis (axial)
3. Move slice through ascending → arch → descending
4. Color by velocity magnitude
5. Observe: velocity profile shape changes along the aorta

### 2.5 Publication Figure: 4-Panel Layout (20 min)

Create a figure with:
1. **Top-left:** Velocity streamlines (lateral view)
2. **Top-right:** Pressure on wall (anterior view)
3. **Bottom-left:** TAWSS on wall (anterior view)
4. **Bottom-right:** OSI on wall (anterior view)

In ParaView:
- Use **View → Side by Side** for layout
- Set background to white: Edit → Settings → General → Background Color
- Use consistent color maps: `jet` for WSS, `RdYlBu_r` for pressure
- Export: File → Save Screenshot (300 DPI for publication)

---

## Homework

1. Run post-processing on your completed BPM120 case
2. Read the hemodynamics report — are the values physiologically reasonable?
3. Create a 4-panel publication figure in ParaView
4. Write a 1-page analysis:
   - What is the mean TAWSS? Is it in the healthy range?
   - Where is TAWSS highest? Why? (relate to flow features)
   - What is the pressure drop? Is it clinically significant?
   - What is the mean OSI? Where are the high-OSI regions?
