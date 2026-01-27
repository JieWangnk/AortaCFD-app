# Quick Start: velocityFieldAverage

**TL;DR**: Add `"velocityFieldAverage": true` to enable turbulence analysis in LES simulations.

---

## For LES Users (Most Common Use Case)

### Step 1: Add to Your Config

Edit your `config.json`:

```json
{
  "physics": {
    "model": "LES"
  },
  "boundary_conditions": {
    "inlet": {
      "type": "TIMEVARYING",
      "csv_file": "inlet_flow.csv"
    }
  },
  "hemodynamics": {
    "runtime_functions": {
      "velocityFieldAverage": true    ← ADD THIS LINE
    }
  }
}
```

### Step 2: Run Your Simulation

```bash
python src/aortacfd.py config.json
cd output/CASE_NAME/openfoam
./run.sh
```

### Step 3: Check Output

After simulation, each time directory (e.g., `1.5/`) will have:

**NEW fields:**
- `UMean` - Time-averaged velocity
- `UPrime2Mean` - Reynolds stresses
- `pMean` - Time-averaged pressure

### Step 4: Calculate Turbulent Kinetic Energy

Open in ParaView:
1. Load `system.foam`
2. **Filters** → **Calculator**
3. Expression: `0.5 * (UPrime2Mean_XX + UPrime2Mean_YY + UPrime2Mean_ZZ)`
4. Result name: `k_resolved`
5. Apply

**Done!** You now have turbulent kinetic energy field.

---

## What This Does

Enables computation of:
- **k** (turbulent kinetic energy) = ½ tr(⟨u'_i u'_j⟩)
- **TI** (turbulence intensity) = √(⅔k) / |⟨U⟩|
- **Reynolds stresses** for flow structure analysis

**Without this**: LES doesn't output k field (it's hidden in resolved velocity fluctuations).

**With this**: You get explicit UMean and UPrime2Mean to calculate k.

---

## One-Line Summary

```json
"velocityFieldAverage": true  // Enables turbulence analysis for LES
```

---

## Example: Full LES Config

```json
{
  "_doc": "LES aorta simulation with turbulence analysis",

  "physics": {
    "model": "LES",
    "les_model": "WALE"
  },

  "mesh": {
    "boundary_layers": {
      "num_layers": 10,
      "expansion_ratio": 1.2
    },
    "SNAPPY_SETTINGS": {
      "cells_across_span": 25
    }
  },

  "boundary_conditions": {
    "inlet": {
      "type": "TIMEVARYING",
      "csv_file": "BPM120.csv",
      "profile": "parabolic"
    },
    "outlets": {
      "type": "3EWINDKESSEL",
      "windkessel_settings": {
        "systolic_pressure": 120,
        "diastolic_pressure": 80
      }
    }
  },

  "hemodynamics": {
    "runtime_functions": {
      "wallShearStress": true,
      "fieldAverage": true,
      "velocityFieldAverage": true,    ← KEY LINE
      "pressureMonitoring": true
    },
    "tawss_settings": {
      "skip_cycles": 2,
      "periodicRestart": true
    }
  },

  "simulation_control": {
    "cardiac_cycle_period": 0.5,
    "number_of_cycles": 3
  }
}
```

---

## When NOT to Use

Don't enable if:
- ❌ Laminar simulation (no turbulence)
- ❌ Only care about WSS (not turbulence)
- ❌ Steady flow (requires pulsatile)
- ❌ File size is critical concern (+30% storage)

---

## Default Behavior

- **Default**: `false` (disabled)
- **Auto-enable**: No (must explicitly set to `true`)
- **Requirements**: Pulsatile flow only

---

## FAQ

**Q: Do I need this for RANS?**
A: No, RANS already outputs `k` field from turbulence model.

**Q: What's the file size impact?**
A: +30% per time directory (3 additional fields).

**Q: Can I post-process existing results?**
A: No, must enable BEFORE running simulation. See `POST_PROCESS_LIMITATION.md`.

**Q: Will old configs still work?**
A: Yes, 100% backward compatible. Option defaults to `false`.

**Q: What if I forget to enable it?**
A: You won't have UPrime2Mean, so can't calculate k. Must re-run simulation.

---

## Expected Output Values (Aorta)

| Metric | Typical Value | Unit |
|--------|---------------|------|
| k_resolved | 1-5 × 10⁻⁵ | m²/s² |
| TI (turbulence intensity) | 3-8 | % |
| UMean (peak systole) | 1-2 | m/s |

---

## More Information

- **Full documentation**: `VELOCITY_FIELD_AVERAGE_FEATURE.md`
- **Implementation details**: `IMPLEMENTATION_SUMMARY.md`
- **Tests**: `tests/README_VELOCITY_FIELD_AVERAGE_TESTS.md`

---

**Bottom Line**: If you're running LES, add `"velocityFieldAverage": true` to your config.
