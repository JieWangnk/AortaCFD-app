# Input Data Structure

- `CAD/<case_name>/`
  - `inlet.stl`, `outlet1.stl`, ..., `wall_aorta.stl`
  - `inletFlowRate.csv`
  - `boundary_conditions.json` (optional)
- `config/profiles/<profile_name>.py`
  - Simulation profile (mesh, physics, solver settings)

Example:
```text
CAD/PAT1_2024/
  inlet.stl
  outlet1.stl
  outlet2.stl
  wall_aorta.stl
  inletFlowRate.csv
  boundary_conditions.json
config/profiles/sim_laminar_fine.py
``` 