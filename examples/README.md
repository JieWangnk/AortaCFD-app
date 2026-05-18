# AortaCFD Examples

This directory contains working **config-JSON templates** and supporting notes
for common AortaCFD usage patterns. The files here are inputs you copy into a
case folder.

If you want learning material instead of templates:

- **`docs/tutorial/`** — 8-week PhD course teaching the CFD pipeline using one
  canonical patient case (depth-first).
- **`docs/workshop/`** — 6-lesson parametric-study walkthrough showing the
  four-block geometry → packaging → running → aggregation workflow
  (breadth-first).

## Configuration Tiers

AortaCFD configs follow a "robust by default, accurate by choice" approach:

| Config | Profile | Outlets | Inlet | Purpose |
|--------|---------|---------|-------|---------|
| `config_golden_base.json` | robust (1st order) | zeroGradient | CONSTANT | Prove geometry + mesh work. Will always converge. |
| `config_standard.json` | standard (2nd order) | 3EWINDKESSEL | TIMEVARYING | Production hemodynamics with pulsatile flow. |
| `config_full.json` | any | any | any | Reference showing all available parameters. |
| `config_minimal.json` | standard | zeroGradient | CONSTANT | Smallest working config (for testing). |

**Recommended workflow for a new case:**
1. Start with `config_golden_base.json` -- verify mesh and geometry
2. Once that runs, switch to `config_standard.json` -- add Windkessel, pulsatile flow, hemodynamics
3. Consult `config_full.json` only when you need a specific advanced setting

## Included Files

- `config_golden_base.json`: guaranteed-to-converge first run (robust profile, simple BCs)
- `config_minimal.json`: smallest working configuration
- `config_standard.json`: practical pulsatile aortic case with Windkessel outlets
- `config_full.json`: broad configuration reference
- `README_CONFIG.md`: field-by-field configuration guide
- `post_processing_example.ipynb`: notebook example for inspecting outputs

Additional markdown files in this directory document specific topics such as boundary layers, function objects, and numerics regeneration.

## Fastest Way to Start a New Case

Create a new case folder:

```bash
mkdir -p cases_input/MY_CASE
```

Add the required geometry files:

```text
cases_input/MY_CASE/
├── inlet.stl
├── outlet1.stl
├── outlet2.stl
├── ...
└── wall_aorta.stl
```

Copy a starter config:

```bash
cp examples/config_minimal.json cases_input/MY_CASE/config.json
```

Then update at least these fields in `cases_input/MY_CASE/config.json`:

- `case_info.patient_id`
- `geometry.inlet_keywords_ordered`
- `geometry.outlet_keywords_ordered`
- `geometry.wall_keywords_ordered`
- `boundary_conditions.inlet`
- `boundary_conditions.outlets`
- `simulation_control`

## Which Example to Use

### `config_golden_base.json` (start here)

Use this for the first run of any new geometry. It uses robust (1st-order) numerics and simple outlet BCs. The simulation will converge even with poor mesh quality.

Best for:

- first run of a new case (prove geometry works)
- verifying STL naming and scale factor
- debugging mesh problems
- cases where you need a result, not accuracy

Run it with:

```bash
cp examples/config_golden_base.json cases_input/MY_CASE/config.json
# Edit: patient_id, patch names, scale_factor
python run_patient.py MY_CASE --steps case,mesh,boundary,solver --run-name first_test
```

### `config_standard.json` (production)

Use this once the golden base runs successfully. Adds 2nd-order numerics, Windkessel outlets, pulsatile flow, and hemodynamics post-processing.

Best for:

- production hemodynamic studies
- time-varying inlet waveforms from CSV
- Windkessel outlet studies
- TAWSS/OSI/RRT computation and QoI export

Expected inputs beyond STL files:

- a waveform CSV referenced by `boundary_conditions.inlet.csv_file`

Run it with:

```bash
python run_patient.py MY_CASE --run-name standard_run
```

### `config_minimal.json`

Smallest config that exercises the pipeline. Useful for testing and CI.

### `config_full.json`

Use this as a reference when you need to discover available options or build a more specialized config.

Best for:

- advanced inlet definitions
- mesh tuning
- turbulence or numerics overrides
- documenting a study-specific setup

It is not the best first file to edit for a new user because it intentionally exposes many optional fields.

## Example Workflows

### 1. Prepare a case without running the solver

```bash
python run_patient.py MY_CASE --steps case,mesh,boundary --run-name prep
```

Use this when you want to inspect the generated case before spending solver time.

### 2. Run the solver after reviewing setup

```bash
python run_patient.py MY_CASE --update output/MY_CASE/prep --steps solver
```

### 3. Re-run post-processing only

```bash
python run_patient.py --postprocess output/MY_CASE/prep
```

### 4. Compare multiple config variants for one case

Store multiple configs such as:

```text
cases_input/MY_CASE/
├── config_mesh10.json
├── config_mesh12.json
└── config_mesh14.json
```

Then run:

```bash
python run_batch.py \
  --config-list MY_CASE:config_mesh10.json MY_CASE:config_mesh12.json MY_CASE:config_mesh14.json \
  --workers 2
```

This creates output folders such as `output/MY_CASE_mesh10/` and writes a current-batch cohort table to `output/cohort_comparison.csv` when QoI summaries exist.

## Outputs to Check

After a run, review:

- `reports/merged_config.json`
- `reports/inlet_audit.json`
- `reports/simulation_setup_report.txt`
- `results/qoi_summary.json`

These files are the most useful first-line artifacts for confirming that the geometry, inlet handling, numerics, and exported metrics match what you intended.

## Common Editing Tips

- Keep STL patch naming consistent with the `geometry` section
- Start with `config_golden_base.json` (robust profile) for any new geometry
- Switch to `config_standard.json` once mesh quality is verified and golden base converges
- Prefer `--update` when changing boundary conditions or solver settings on an existing mesh
- If solver diverges, check mesh quality first (`checkMesh` in openfoam/logs/), then try robust profile

## Related Notes

- Boundary layer guidance: `BOUNDARY_LAYER_GUIDE.md`
- Function objects: `FUNCTION_OBJECTS_GUIDE.md`
- Regenerate numerics example: `REGENERATE_NUMERICS_EXAMPLE.md`
- Full config reference: `README_CONFIG.md`