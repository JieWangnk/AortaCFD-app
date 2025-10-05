# Quick Start: Realistic BC Validation

## One-Line Commands

### Minimal Test (30 seconds)
```bash
source /opt/openfoam12/etc/bashrc && \
./validation/run_realistic_validation.py patient1 --profile sim_laminar_medium --cycles 0.5
```

### Full Cardiac Cycle (5-10 minutes)
```bash
source /opt/openfoam12/etc/bashrc && \
./validation/run_realistic_validation.py patient1 --profile sim_laminar_medium --cycles 1.0
```

### Research-Grade with WSS (2-4 hours)
```bash
source /opt/openfoam12/etc/bashrc && \
./validation/run_realistic_validation.py patient1 --profile sim_les_fine --cycles 3
```

## What You Get

✅ **Pulsatile Inlet**:
- Velocity: 0-1.156 m/s (realistic cardiac cycle)
- Heart rate: 75 BPM
- Profile: from `test_cardio_profile.csv`

✅ **3-Element Windkessel Outlets**:
- Flow distribution: Murray's Law automatic
- Pressures: 120/80 mmHg
- Physiologically realistic

✅ **Wall Shear Stress**:
- Extracted automatically
- Expected range: 0.5-6.5 Pa
- Available in `<time>/wallShearStress`

## Outputs

📁 **Location**: `validation/output_realistic/patient1/sim_laminar_medium/`

📊 **Key Files**:
- `<time>/U` - Velocity fields
- `<time>/p` - Pressure fields
- `<time>/wallShearStress` - WSS fields ← **Important**
- `constant/windkesselProperties` - 3EWK parameters
- `log.foamRun` - Simulation log

## Validate Results

```bash
# Check WSS statistics
grep wallShearStress validation/output_realistic/patient1/sim_laminar_medium/postProcessing/fieldMinMax/*/fieldMinMax.dat

# Run BC validation
./validation/run_bc_validation.py patient1 --profile sim_laminar_medium --time 0.8

# View in ParaView
paraview --data=validation/output_realistic/patient1/sim_laminar_medium/
```

## Expected Results

| Metric | Value | Range |
|--------|-------|-------|
| Peak Velocity | 1.156 m/s | 1.0-1.5 m/s ✅ |
| Mean Velocity | ~0.4 m/s | 0.3-0.6 m/s ✅ |
| Pressure Drop | 10-30 mmHg | 10-50 mmHg ✅ |
| Peak WSS | 4-8 Pa | 1-10 Pa ✅ |
| Mean WSS | 2-4 Pa | 1-7 Pa ✅ |
| Reynolds Number | 2000-4000 | Transitional ✅ |

## Troubleshooting

❌ **"foamRun not found"**
```bash
source /opt/openfoam12/etc/bashrc
```

❌ **Simulation crashes**
```bash
# Use smaller time step
./validation/run_realistic_validation.py patient1 --profile sim_laminar_medium --cycles 0.5
```

❌ **No WSS field**
```bash
# Check controlDict has wallShearStress function
grep -A5 "wallShearStress" validation/output_realistic/patient1/sim_laminar_medium/system/controlDict
```

## Next Steps

1. ✅ Run realistic validation (above)
2. ✅ Extract WSS statistics
3. 📊 Visualize in ParaView
4. 📈 Compare with literature values
5. 🔬 Time-average over cardiac cycle

📖 **Full Guide**: See `REALISTIC_BC_GUIDE.md`
