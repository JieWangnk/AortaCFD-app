# Getting Started

1. **Prepare your case data:**
   - Place STL geometry and inlet flow CSVs in a subfolder under `CAD/`.
   - Prepare a simulation profile in `config/profiles/`.

2. **Run a workflow command:**
   ```bash
   python app.py runAll --case PAT1_2024 --profile sim_laminar_fine
   ```
   - Use `--clean` to remove previous results and start fresh.

3. **For 3EWK (three-element Windkessel) boundary conditions:**
   - Ensure you have compiled and are using the `pimpleFOAM_WK` solver from [OpenFOAM-v8-Windkessel-code](https://github.com/EManchester/OpenFOAM-v8-Windkessel-code).
   - Follow the Windkessel code's instructions for setting up boundary conditions and `windkesselProperties`.

4. **Results and logs will be generated in the `OPENFOAM/` directory.**

See [Command Reference](command_reference.md) for available commands. 