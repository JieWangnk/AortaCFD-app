# AortaCFD Patient Case Management

## New Refined Structure

The AortaCFD application now uses a clean, template-based patient case management system that makes it easy to run CFD analyses with minimal configuration.

## Directory Structure

```
AortaCFD-app/
├── cases_input/                    # Patient cases directory
│   ├── patient1/                   # Complex aortic geometry
│   │   ├── inlet.stl               # Inlet geometry
│   │   ├── wall_aorta.stl          # Aortic wall geometry
│   │   ├── outlet1.stl             # Branch outlet 1
│   │   ├── outlet2.stl             # Branch outlet 2
│   │   ├── outlet3.stl             # Branch outlet 3
│   │   ├── outlet4.stl             # Branch outlet 4
│   │   ├── BPM75.csv               # Flow data
│   │   └── cfd_template.json       # CFD configuration template
│   ├── patient2/                   # Coarctation case
│   ├── patient3/                   # Simple geometry
│   └── patient4/                   # Publication-quality aneurysm
└── output/                         # Organized output directory
    ├── patient1/                   # Patient 1 results
    │   ├── run_20250817_140530/    # Timestamped run
    │   │   ├── openfoam/           # OpenFOAM case directory
    │   │   ├── results/            # Post-processed results
    │   │   ├── logs/               # All log files
    │   │   ├── patient_report.html # Main report
    │   │   ├── summary.json        # Analysis summary
    │   │   ├── cfd_template.json   # CFD config used
    │   │   └── README.md           # Run documentation
    │   └── run_20250817_150230/    # Another run
    ├── patient2/                   # Patient 2 results
    └── patient3/                   # Patient 3 results
```

## Running Patient Cases

### Using the Patient Case Runner

```bash
# List available patient cases
python3 run_patient.py --list

# Run analysis for a specific patient
python3 run_patient.py patient1

# Run with specific quality settings
python3 run_patient.py patient2 --quality high

# Quick test run
python3 run_patient.py patient3 --quick
```

### Using the Simple Runner

```bash
# Point to any folder with STL files
python3 simple_run.py /path/to/stl/files

# Specify output location
python3 simple_run.py cases_input/patient1 --output results/patient1
```

## Patient Case Templates

Each patient case contains a `cfd_template.json` file that defines:

- **Case Information**: Patient ID, description, imaging modality
- **Simulation Settings**: Analysis type (quick/standard/high_resolution/publication)
- **Physics**: Blood properties, cardiac cycle parameters  
- **Boundary Conditions**: Inlet flow, outlet pressure, wall properties
- **Computational Settings**: Parallel processing, mesh quality, refinement
- **Output Settings**: Variables to save, post-processing options

### Example Template Structure

```json
{
  "case_info": {
    "patient_id": "patient1",
    "description": "Complex aortic geometry with multiple branches",
    "imaging_modality": "CT"
  },
  "simulation_settings": {
    "analysis_type": "standard",
    "mesh_quality": "auto",
    "solver_type": "laminar"
  },
  "physics": {
    "blood_density": 1060,
    "blood_viscosity": 0.004
  },
  "boundary_conditions": {
    "inlet": {
      "type": "time_varying_flow",
      "flow_data_file": "BPM75.csv"
    },
    "outlets": {
      "type": "windkessel",
      "distribution_method": "murray_law"
    }
  }
}
```

## Available Patient Cases

### Patient1: Complex Multi-Branch Aorta
- **Type**: Standard analysis
- **Geometry**: 4 outlet branches
- **Use Case**: General hemodynamic analysis

### Patient2: Coarctation of Aorta  
- **Type**: High-resolution analysis
- **Geometry**: Stenotic region
- **Use Case**: Pressure gradient analysis, jet formation

### Patient3: Simple Ascending Aorta
- **Type**: Quick analysis  
- **Geometry**: Single outlet
- **Use Case**: Fast prototyping, testing

### Patient4: Thoracic Aortic Aneurysm
- **Type**: Publication-quality analysis
- **Geometry**: Aneurysmal dilatation
- **Use Case**: Research, publication figures, hemodynamic indices

## Adding New Patient Cases

1. Create a new directory: `cases_input/patient5/`
2. Add STL files with standard naming:
   - `inlet.stl` - Inlet geometry
   - `wall_aorta.stl` - Aortic wall 
   - `outlet1.stl`, `outlet2.stl`, ... - Outlets
3. Add flow data: `BPM75.csv` or similar
4. Create `cfd_template.json` based on existing examples
5. Run: `python3 run_patient.py patient5`

## Output Structure Benefits

The new organized output structure provides several advantages:

✅ **Patient-Centric Organization**: Each patient has their own dedicated directory  
✅ **Time-Stamped Runs**: Multiple analysis runs are preserved with timestamps  
✅ **Clear Separation**: OpenFOAM case, results, logs, and reports are organized separately  
✅ **Self-Documenting**: Each run includes README.md and summary.json for easy understanding  
✅ **Log Management**: All log files are collected in one location  
✅ **Easy Access**: Main report is at the top level of each run directory  

### Output Directory Contents

Each patient run directory contains:

- **`openfoam/`**: Complete OpenFOAM case directory with all simulation files (STL files in constant/triSurface/)
- **`results/`**: Post-processed results, figures, and analysis data
- **`logs/`**: All log files from the simulation process
- **`patient_report.html`**: Main analysis report (open in web browser)
- **`summary.json`**: Machine-readable analysis summary
- **`cfd_template.json`**: CFD configuration template used for this run
- **`README.md`**: Human-readable documentation for this specific run

**Note**: Original patient case files (STL, flow data, template) remain in `cases_input/patientN/` to avoid duplication.

## Benefits of New Structure

✅ **Simple**: Just specify patient ID to run analysis  
✅ **Organized**: Clean separation of input, processing, results, and logs  
✅ **Consistent**: Standardized naming and organization  
✅ **Flexible**: Template-based configuration  
✅ **Scalable**: Easy to add new cases  
✅ **Reproducible**: All settings and inputs preserved with each run  
✅ **User-Friendly**: No technical knowledge required  
✅ **Archival**: Multiple runs preserved for comparison and reference