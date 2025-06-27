# Pipeline Architecture

AortaCFD is built around a modular, task-based pipeline managed by the `WorkflowManager`. Each workflow command triggers a sequence of tasks, ensuring reproducibility and clarity.

## Pipeline Overview

```mermaid
graph TD
    A[Start: User Command] --> B[ConfigBuilder: Load Config]
    B --> C[WorkflowManager: Select Recipe]
    C --> D[Task 1: Create Case Structure]
    D --> E[Task 2: Generate Mesh Files]
    E --> F[Task 3: Generate Physical Properties]
    F --> G[Task 4: Generate Numerical Schemes]
    G --> H[Task 5: Generate Solver Settings]
    H --> I[Task 6: Generate DecomposeParDict]
    I --> J[Task 7: Generate ControlDict]
    J --> K[Task 8: Execute Meshing]
    K --> L[Task 9: Prepare Boundary Data]
    L --> M[Task 10: Generate BC Files]
    M --> N[Task 11: Update ControlDict]
    N --> O[Task 12: Execute Solver]
    O --> P[Task 13: Execute Post-Processing]
    P --> Q[End: Results & Logs]
```

## Key Pipeline Commands
- `setup:dict`: Generate all non-mesh-dependent dictionary files.
- `setup:bc`: Prepare and update boundary condition files after meshing.
- `run:mesh`: Execute OpenFOAM meshing utilities.
- `run:solver`: Run the OpenFOAM solver (or `pimpleFOAM_WK` for 3EWK cases).
- `createCase`: Full setup (structure, mesh, properties, BCs).
- `runAll`: Complete end-to-end workflow (setup, mesh, BCs, solve, post-process). 