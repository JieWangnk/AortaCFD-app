# Command Reference

| Command         | Description                                      |
|-----------------|--------------------------------------------------|
| setup:dict      | Generate all dictionary files (pre-mesh)         |
| setup:bc        | Prepare and update boundary condition files       |
| run:mesh        | Run OpenFOAM meshing utilities                   |
| run:solver      | Run the OpenFOAM solver (or pimpleFOAM_WK)       |
| createCase      | Full setup (structure, mesh, properties, BCs)    |
| runAll          | Complete end-to-end workflow                     |

**Example:**
```bash
python app.py runAll --case PAT1_2024 --profile sim_laminar_fine --clean
``` 