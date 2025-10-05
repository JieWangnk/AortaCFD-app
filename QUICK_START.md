# AortaCFD Quick Start Guide

## 🚀 Run Your First Simulation

### 1. Simple Test (Recommended First Run)
```bash
# Quick RANS coarse test - completes in ~5 minutes
python run_patient.py patient1 --config config_simple_rans_coarse.json
```

### 2. Default Simulation
```bash
# Uses config.json in patient directory
python run_patient.py patient1
```

### 3. Custom Configuration
```bash
# Any of these work:
python run_patient.py patient1 --config my_config.json
python run_patient.py patient1 --config cases_input/patient1/my_config.json
python run_patient.py patient1 --config /full/path/to/config.json
```

## 📋 Configuration Files

| File | Purpose | Use Case |
|------|---------|----------|
| `config_simple_rans_coarse.json` | Minimal RANS test | Quick validation, learning |
| `config_comprehensive.json` | Complete reference | Template, documentation |
| `config.json` | Production settings | Realistic simulations |

## 🔧 Common Commands

### List Available Steps
```bash
python run_patient.py patient1 --list-steps
```

### Run Specific Steps
```bash
# Only mesh
python run_patient.py patient1 --steps mesh

# Mesh + boundary conditions
python run_patient.py patient1 --steps mesh,boundary

# Full workflow
python run_patient.py patient1 --steps all
```

### List Patients
```bash
python run_patient.py --list
```

## ⚙️ Quick Config Examples

### Fastest Test (30 seconds)
```json
{
  "simulation_settings": {"analysis_type": "coarse", "solver_type": "laminar"},
  "boundary_conditions": {
    "inlet": {"type": "CONSTANT", "velocity_magnitude": 0.5},
    "outlets": {"type": "ZEROGRADIENT"}
  },
  "simulation_control": {"end_time": 0.1}
}
```

### Realistic Cardiac (30 minutes)
```json
{
  "simulation_settings": {"analysis_type": "medium", "solver_type": "laminar"},
  "boundary_conditions": {
    "inlet": {"type": "TIMEVARYING", "csv_file": "flow.csv", "profile": "womersley"},
    "outlets": {
      "type": "3EWINDKESSEL",
      "windkessel_settings": {
        "systolic_pressure": 120,
        "diastolic_pressure": 80,
        "methodology": "murray_law_automatic"
      }
    }
  },
  "simulation_control": {"number_of_cycles": 3}
}
```

## 📊 Analysis Types

| Type | Cell Size | Cells | Time | Use Case |
|------|-----------|-------|------|----------|
| `coarse` | 1.8 mm | 1.5M | Fast | Testing, debugging |
| `medium` | 1.0 mm | 3.5M | Moderate | Production, validation |
| `fine` | 0.6 mm | 7M | Slow | High accuracy, publication |

## 🔬 Solver Types

| Type | Model | Best For | Speed |
|------|-------|----------|-------|
| `laminar` | None | Most aortic flows | Fast |
| `RANS` | k-ω SST | Turbulent regions | Medium |
| `LES` | WALE/Smagorinsky | Complex turbulence | Slow |

## 🌊 Boundary Conditions

### Inlet Types
- `TIMEVARYING`: Cardiac waveform from CSV (realistic)
- `CONSTANT`: Fixed velocity (simple testing)
- `WOMERSLEY`: Analytical pulsatile (validation)

### Outlet Types
- `3EWINDKESSEL`: Physiological RCR model (recommended)
- `ZEROGRADIENT`: Simple outlet (quick tests)
- `FLOWSPLIT`: Manual flow distribution

## 📁 File Structure

```
cases_input/patient1/
├── config.json                          # Default config
├── config_simple_rans_coarse.json      # Quick test config
├── config_comprehensive.json           # Reference
├── inlet.stl                           # Geometry files
├── outlet1.stl, outlet2.stl, ...
├── wall_aorta.stl
└── flow.csv                            # Boundary data

output/patient1/
└── run_YYYYMMDD_HHMMSS/
    └── openfoam/                       # OpenFOAM case
        ├── 0/                          # Initial conditions
        ├── constant/                    # Properties, mesh
        ├── system/                      # Solvers, schemes
        └── [time directories]/          # Results
```

## 🐛 Troubleshooting

### Config Not Found
```bash
# ❌ This fails if not in patient directory:
python run_patient.py patient1 --config my_config.json

# ✅ Use full path or put in patient directory:
python run_patient.py patient1 --config cases_input/patient1/my_config.json
```

### Mesh Quality Warning
```json
// Increase mesh quality settings:
{
  "mesh": {
    "mesh_resolution": {"target_cell_size_mm": 1.0},  // Smaller = better
    "SNAPPY_SETTINGS": {
      "nSolveIter": 700,        // More iterations
      "tolerance": 3.0          // More relaxed
    }
  }
}
```

### Solver Crashes (NaN/Divergence)
```json
// Use safer time stepping:
{
  "simulation_control": {
    "controlDict": {
      "maxCo": 0.5,             // Lower Courant number
      "deltaT": 1e-6,           // Smaller initial step
      "maxDeltaT": 1e-4
    }
  }
}
```

### Slow Simulation
```json
// Use parallel execution:
{
  "run_settings": {
    "solution_type": "parallel",
    "subdomains": 8,                    // Match CPU cores
    "decomposition_method": "scotch"
  },
  "mesh": {
    "SNAPPY_SETTINGS": {
      "parallel": true,
      "nProcessors": 8
    }
  }
}
```

## 📚 Documentation

- **[CONFIG_GUIDE.md](CONFIG_GUIDE.md)** - Complete configuration reference
- **[config_comprehensive.json](cases_input/patient1/config_comprehensive.json)** - All options with docs
- **[README.md](README.md)** - Project overview and setup

## 🎯 Next Steps

1. **Start Simple:**
   ```bash
   python run_patient.py patient1 --config config_simple_rans_coarse.json
   ```

2. **Review Results:**
   - Check `output/patient1/run_*/openfoam/` for OpenFOAM case
   - Use ParaView to visualize: `paraview output/patient1/run_*/openfoam/openfoam.foam`

3. **Customize:**
   - Copy `config_simple_rans_coarse.json` to `my_config.json`
   - Modify settings based on your needs
   - Reference `config_comprehensive.json` for all options

4. **Scale Up:**
   - Increase analysis_type: `coarse` → `medium` → `fine`
   - Add realistic BCs: `ZEROGRADIENT` → `3EWINDKESSEL`
   - Enable parallel execution for speed

## 💡 Pro Tips

1. **Always test with coarse first** - Validates setup quickly
2. **Use patient directory** - Keep configs organized per patient
3. **Start serial, scale parallel** - Debug in serial, run in parallel
4. **Monitor logs** - Check `output/*/openfoam/log.*` for issues
5. **Visualize early** - Open in ParaView after mesh generation

---

**Ready to start? Run this:**
```bash
python run_patient.py patient1 --config config_simple_rans_coarse.json
```

**Need help?** Check [CONFIG_GUIDE.md](CONFIG_GUIDE.md) for details.
