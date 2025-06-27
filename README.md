# AortaCFD: Patient-Specific Aortic Blood Flow Simulation

AortaCFD is an intelligent, Python-driven workflow for simulating blood flow in patient-specific aortic geometries using OpenFOAM. Inspired by the clarity and structure of SimVascular and VMTK, AortaCFD streamlines the process from geometry preparation to simulation and post-processing, making advanced hemodynamic analysis accessible to researchers and clinicians.

---

## Table of Contents
- [Features](#features)
- [Installation](#installation)
- [Requirements](#requirements)
- [Quick Start](#quick-start)
- [Input Data Structure](#input-data-structure)
- [Simulation Profiles](#simulation-profiles)
- [Workflow & Usage](#workflow--usage)
- [Configuration](#configuration)
- [Post-Processing](#post-processing)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [Contact](#contact)

---

## Features
- **Automated Workflow:** End-to-end automation from geometry import to simulation and post-processing.
- **Patient-Specific Modeling:** Uses STL geometry and physiological boundary conditions from CSV/JSON.
- **Flexible Meshing:** Robust mesh generation with OpenFOAM's snappyHexMesh, supporting coarse to fine resolutions.
- **Advanced Boundary Conditions:** Supports time-varying inlet profiles and 3-element Windkessel outlet models.
- **Batch Processing:** Easily run multiple cases with different profiles.
- **Integrated Post-Processing:** Automated ParaView/PyVista-based visualization and result extraction.
- **Extensible Python Codebase:** Modular design for easy customization and extension.

---

## Installation

1. **Clone the repository:**
   ```bash
   git clone <your-repo-url>
   cd AortaCFD-app
   ```
2. **Install Python dependencies:**
   > **Note:** `requirement.txt` is currently empty. Install the following manually (Python 3.8+ recommended):
   ```bash
   pip install numpy scipy scikit-learn jinja2 matplotlib pyvista
   ```
   - For post-processing: [ParaView](https://www.paraview.org/download/) (5.11+ recommended)
   - For CFD: [OpenFOAM](https://openfoam.org/download/) (version 8 recommended)

3. **Set up OpenFOAM and ParaView environment variables as needed.**

---

## Requirements
- **Python:** 3.8 or higher
- **OpenFOAM:** Version 8 (or compatible)
- **ParaView:** 5.11+ (for automated post-processing)
- **Linux OS** (tested on Ubuntu 20.04+)
- **Additional Python packages:** numpy, scipy, scikit-learn, jinja2, matplotlib, pyvista

---

## Quick Start

1. **Prepare your input data:**
   - Place your STL geometry and boundary condition files in a subdirectory under `CAD/` (see [Input Data Structure](#input-data-structure)).
2. **Choose a simulation profile:**
   - Use one of the provided profiles in `config/profiles/` (e.g., `laminar_medium`, `sim_laminar_coarse`, `sim_laminar_fine`).
3. **Run the workflow:**
   ```bash
   python app.py runAll --case <case_folder> --profile <profile_name>
   # Example:
   python app.py runAll --case PAT1_2024 --profile laminar_medium
   ```
   - Use `--clean` to delete and recreate the case directory for a fresh run.

---

## Input Data Structure

Each case should be organized as a subfolder in `CAD/`, e.g.:

```
CAD/PAT1_2024/
  ├── inlet.stl
  ├── outlet1.stl
  ├── outlet2.stl
  ├── outlet3.stl
  ├── outlet4.stl
  ├── wall_aorta.stl
  ├── boundary_conditions.json
  ├── BPM75.csv
  └── inletFlowRate.csv
```
- **STL files:** Define the geometry (inlet, outlets, wall).
- **CSV files:** Provide time-varying inlet flow/velocity data.
- **JSON files:** Specify boundary conditions and Windkessel parameters.

---

## Simulation Profiles

Profiles define mesh, physics, and solver settings. Example profiles:
- `laminar_medium.py`: Medium-fidelity, parallel run, moderate mesh.
- `sim_laminar_coarse.py`: Fast, coarse mesh, serial run.
- `sim_laminar_fine.py`: High-fidelity, fine mesh, advanced numerics.

Customize or create new profiles in `config/profiles/` as needed.

---

## Workflow & Usage

### Main Workflow Commands
- `runAll`: Full pipeline (setup, mesh, BCs, solve, post-process)
- `createCase`: Setup, mesh, and BCs (no solve)
- `run:mesh`: Only mesh generation
- `run:solver`: Only run the solver
- `setup:dict`: Generate all dictionary files (no mesh)
- `setup:bc`: Update boundary conditions after meshing

### Example Usage
```bash
python app.py runAll --case PAT1_2024 --profile laminar_medium
python app.py createCase --case VOL04 --profile sim_laminar_coarse
```

### Command-line Flags
- `--case`: Name of the case directory in `CAD/`
- `--profile`: Name of the simulation profile in `config/profiles/`
- `--clean`: (Optional) Delete and recreate the case directory

---

## Configuration

- **Global settings:** `config/base.py` (OpenFOAM version, physical properties, post-processing paths)
- **Simulation profiles:** `config/profiles/`
- **Templates:** `templates/` (Jinja2 templates for OpenFOAM dictionaries)

---

## Post-Processing

- **Automated screenshots and animations** using ParaView or PyVista
- **Output images and videos** are saved in the case's `Images/` directory
- **Customizable fields:** Velocity, Pressure, Wall Shear Stress, Kinetic Energy

---

## Troubleshooting
- Ensure all dependencies are installed and environment variables are set for OpenFOAM and ParaView.
- Check log files (e.g., `AortaCFD.log`, `log.blockMesh`, `log.solver`) for error messages.
- For missing or malformed input files, verify your `CAD/<case>/` directory structure.

---

## Contributing
Contributions are welcome! Please open issues or pull requests for bug fixes, new features, or documentation improvements.

---

## Contact
- **Project Lead:** (Add your name/email here)
- **GitHub:** (Add your GitHub link here)
- **Support:** (Add support email or forum link here)

---

## License
*Please add a LICENSE file to specify the project license (e.g., MIT, GPL, etc.).*

---

## Acknowledgments
- Inspired by [SimVascular](https://simvascular.github.io/) and [VMTK](http://www.vmtk.org/)
- Built on [OpenFOAM](https://openfoam.org/) and [ParaView](https://www.paraview.org/)
