# Changelog

All notable changes to AortaCFD are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added (v1.2.0 epic D continued — pressure anchor for zeroGradient outlets, steady inlets only)
- **`outlets.pressure_anchor`** config field pins one outlet to a fixed
  pressure while the rest stay `zeroGradient`. Limited to **steady
  inlets** (`CONSTANT` / `PARABOLIC`) — pulsatile + `zeroGradient` is
  rejected by the validator regardless of anchor (see "Changed" below).
  Shape:
  ```json
  "outlets": {
    "type": "zeroGradient",
    "pressure_anchor": {"outlet": "outlet1", "pressure_mmHg": 80}
  }
  ```
  `outlet: "auto"` resolves to the first outlet patch; `pressure_mmHg`
  defaults to 80 (diastolic).
- **Validator** `_validate_outlet_pressure_reference()` rejects
  `outlets.type: zeroGradient` paired with a pulsatile inlet at
  config-build time (not 17 minutes into a doomed solve), with a
  remediation pointer to `3EWINDKESSEL` / `fixedPressure`.
- **Replaces** the previous undocumented `loop.last fixedValue 0`
  fallback in `p.tpl` with the explicit, user-configurable anchor.

### Changed
- **Pulsatile inlet + `zeroGradient` outlets is now hard-rejected** at
  config-build, including when a `pressure_anchor` is set. Initial
  v1.2.0 development assumed one-outlet anchoring would cure the
  pressure-field drift, but empirical testing on BPM120 (severe
  pediatric coarctation) showed the solver still diverges in
  `correctPressure` at t≈0.020s. The textbook "single anchor is
  sufficient" rule of thumb does not survive coarctation-grade pressure
  gradients. For pulsatile arterial flows, use `3EWINDKESSEL`
  (recommended) or `fixedPressure`.

### Added (v1.2.0 epic D — config variability tests + hardening)
- **`inlet.type = "MAPPED_PROFILE"`** as the new name for the pre-mapped
  per-face per-timestep inlet branch (formerly called `MRI`). The path
  is unchanged — the rename reflects that the branch consumes pre-mapped
  `timeVaryingMappedFixedValue` data regardless of source modality
  (4D MRI, Doppler, 1D model output, synthetic, etc.). `MRI` continues
  to work as a deprecated alias and emits a `DeprecationWarning`;
  removal scheduled for v2.0.
- **`InletProfile` schema enum** validates `inlet.profile` at
  config-build time (was a silent string compare). Typos like
  `walldistance` now raise `ValueError` with the allowed list instead
  of falling through to `parabolic`.
- **`physics.rans_model` / `physics.les_model` allow-lists** in
  `src/config/schema.py`. Unknown models (e.g. lowercase `wale`) used
  to surface as a cryptic OpenFOAM error hours into a solver run;
  v1.2.0 catches them at `ConfigBuilder.build()`.
- **`tests/test_config_matrix.py`** — 13 new mock-OpenFOAM integration
  tests rotating one config axis at a time (Epic D: MAPPED_PROFILE
  end-to-end, RAS+zeroGradient, LES auto-stabilization, precise
  numerics, hardening fuzz, flow-split edge cases). Runs in ~0.5s
  alongside the rest of the suite.

### Fixed
- **`WkSetup._parse_custom_flow_split` rejects negative values.**
  Previously, a typo like `{"outlet1": -20, "outlet2": 120}` silently
  produced a negative `R/C/Z` and the solver diverged with no clear
  cause. Now raises `ValueError` at config-build time.

### Added (v1.2.0 epic B + A.3 — UX polish and benchmark scaffold)
- **`--end-time T` CLI flag** on `run_patient.py` / `aortacfd` overrides
  the simulation `endTime` (in seconds) regardless of `cardiac_cycle ×
  number_of_cycles`. Lets a user run a short demo simulation without
  editing config files. Pairs with `--quick` for fast first-time runs.
- **`--max-runs N` CLI flag** prunes the oldest `run_*/` subdirectories
  under `output/<patient>/` so at most `N` remain (excluding the
  current run). Default `0` keeps current behaviour. Each AortaCFD run
  is ~150 MB, so a researcher iterating on configs will fill disk
  quickly without this.
- **`--doctor` CLI subcommand** runs environment diagnostics:
  Python ≥3.10, all declared runtime deps importable, sample STLs
  under `cases_input/*/*.stl` parse cleanly, OpenFOAM 12 sourced (soft
  warning if not), ≥5 GB free in `output/`. Exits 0 (green) / 1 (red).
- **`benchmark` pytest marker** registered in `pyproject.toml` and a
  new `tests/benchmarks/test_bpm120_benchmark.py` that validates a
  produced `qoi_summary.json` against `benchmarks/expected_values.json`
  (published Wang et al. Table 3 values for BPM120). Skipped unless
  `BPM120_QOI=path/to/qoi_summary.json` is set. CI hook target.
- **`benchmarks/expected_values.json`** as the single machine-readable
  source of truth for benchmark expected values + tolerances. Wired
  into the new tests. Placeholders for PAT002 and VOL04 (A.2 milestone).

### Changed
- **Hemodynamics postprocess** emits a clear `UserWarning` (instead of
  silently zeroing `tawss_*`/`osi_*`/`rrt_*`) when the simulation is
  shorter than `skip_cycles × cardiac_cycle`. The message names the
  exact `--end-time` value needed to populate the time-averaged QoIs.
- **`qoi_summary.json` schema** gained a top-level
  `_metadata.tawss_status` field with one of `OK`, `INCOMPLETE_CYCLES`,
  `NO_FIELDS`, `STEADY`. Lets downstream pipelines distinguish "TAWSS
  is genuinely small" from "TAWSS was never computed". Backwards-
  compatible additive change.
- **Hemodynamics report (`hemodynamics_report.txt`)** prints an explicit
  "TIME-AVERAGED METRICS — NOT AVAILABLE" section with a remediation
  hint when `tawss_status == INCOMPLETE_CYCLES`, rather than just
  omitting the block.
- **README install section** now includes platform-specific OpenFOAM 12
  install commands (Ubuntu apt + Foundation repo, macOS Docker, link to
  the official guide). Earlier versions only told users to `source` it
  without saying where to get it.

## [1.1.1] - 2026-05-11

Pre-release hygiene pass: dead code, lint, security, CI gate alignment, and
a robustness fix for the inlet-normal detection introduced in `v1.1.0`.
No behavioural changes for production cases.

### Added
- `psutil` declared as a runtime dependency in `pyproject.toml`. It was
  already imported in `performance_optimizer` and `utils/security`, but
  only pulled in transitively — making it explicit prevents a silent
  break if the transitive ever drops.
- Documentation of `OPENFOAM_ENV_PATH` / `foamDotFile` in `README.md`
  (HPC override path; the env var was added in `v1.1.0` but undocumented).
- `rrt_p95` and `rrt_p99` percentile QoIs listed in `README.md` (already
  emitted by the post-processor but not yet documented).

### Changed
- `[tool.mypy]` config in `pyproject.toml` now disables a small set of
  high-noise codes (`no-any-return`, `assignment`, `attr-defined`) that
  fire predominantly on `numpy`/`scipy` return-types. A focused typing
  pass is planned for v1.2.0; the remaining 72 reports are now genuine
  type concerns rather than baseline noise.
- `compute_inward_normal` now raises a clear `FileNotFoundError` when the
  inlet or wall STL is missing or empty, and the callers
  (`GeometryAnalyzer._get_internal_point_for_snappy` and
  `DistanceWallInletProfile._should_flip_normal`) fall back to the
  legacy wall-centroid / outlet-bearing heuristic. Production runs still
  use the new edge-ring method introduced in `v1.1.0`; tests and partial
  pipelines no longer crash on missing STLs.
- `release.yml` workflow now enforces a coverage gate (≥ 60 %), a flake8
  F-code lint gate, and a Bandit HIGH/HIGH security gate before
  publishing a tag.
- `tests.yml` coverage threshold aligned to `60` (matches
  `pyproject.toml`).
- `pr-checks.yml` no longer references non-existent
  `test_patient1_e2e.py` / `test_multi_patient_e2e.py` and now honours
  the same `not slow and not e2e` marker selection as the main test job.
- `precise` numerics profile documentation corrected to reflect the
  actual rendered scheme (`cellLimited Gauss linear 1` — full limiting).
  No code change; only the docstring and inline `_comment` were
  inaccurate.

### Fixed
- 125 flake8 F-code violations cleared (unused imports, unused
  variables, empty f-strings). No behavioural change.
- 9 Bandit HIGH/HIGH findings suppressed with `# nosec` and a
  per-occurrence justification (Jinja2 renders OpenFOAM dictionaries
  not HTML; the two `shell=True` calls use `shlex.quote`-ed internal
  paths only).
- `boundary_condition_setup` no longer reads `turbulence_viscosity_ratio`
  from physics settings, since the value was never actually applied to
  the omega initialisation formula.
- README/CLI examples and `docs/REGENERATE_NUMERICS_USAGE.md` cleaned up
  of two broken internal links.

### Removed
- 30 one-off mesh-study configs and helper scripts under
  `scripts/hpc/mesh_study/` (paper artefacts; the methodology is
  preserved in the v1.0.0 / v1.1.0 trees).

## [1.1.0] - 2026-04-19

First post-submission bug-fix and cleanup release. Fully additive over
`v1.0.0` (the CMPB paper-submission reference); no behavioural changes
for existing configs.

### Added
- `OPENFOAM_ENV_PATH` environment variable now overrides `openfoam_env_path`
  in the case config, so a single config file works across laptop and HPC
  without editing.
- `[mesh]` optional extra in `pyproject.toml` for `trimesh` (only needed
  for a few advanced STL-processing paths).
- Optional percentile fields `rrt_p95` and `rrt_p99` in hemodynamics output
  (the raw max is dominated by outlier cells near the wall).

### Changed
- `locationInMesh` seed point for `snappyHexMesh` is now derived from the
  inlet → wall-STL centroid direction instead of the inlet normal. On
  aortic-arch geometries the descending-outlet centroid could drag the
  average outlet below the inlet plane, placing the seed outside the tube
  and leaving ~65k faces on the residual `world` patch.
- Numerics profiles aligned with rendered OpenFOAM dicts (deep audit):
  `standard` profile `div(phi,U)` corrected to `limitedLinearV 1`,
  gradient limiter to `0.5`; `precise` profile laplacian corrected to
  `0.5`; `fvSchemes` / `fvSolution` / `controlDict` fallbacks now inherit
  from the profile rather than hard-coded defaults.
- `adaptive_span` no longer unconditionally reduces
  `surfaceRefinementLevels` when `addLayers=True`, restoring layer
  coverage on cases that previously dropped to ~0%.
- Single source of truth for version numbers. `pyproject.toml` holds the
  canonical version; `aortacfd_lib.__version__` is read via
  `importlib.metadata`; `CITATION.cff` is updated per release.

### Fixed
- World-patch detection no longer mis-fires on sweep geometries where
  `snappyHexMesh` leaves a residual `world` patch alongside proper
  `inlet`/`outlet`/`wall` patches. Previously this caused
  `PrepareBoundaryDataTask` to short-circuit and BC templates to omit the
  `world` entry, crashing `foamRun`.
- `FoamFile` header no longer leaks into the non-default patch count in
  `detect_world_patch_mode`. Two tests that relied on the old buggy
  behaviour were rewritten.
- Python 3.9 compatibility restored for CSF3 HPC — removed PEP 604
  `X | None` return annotations.
- 15 additional numerics / mesh / hemodynamics correctness issues found
  in a deep audit (see commit `a28a55cd` for the full list).

### Removed
- Stopped tracking 812 files (~56 MB) of regenerable mapped inlet BC data
  under `cases_input/VOL04/InletData_OF4_BL_95/`. Demo geometry and
  configs for `VOL04` remain; `.gitignore` now excludes
  `cases_input/*/InletData_*/` and `cases_input/*/inlet/` so future
  cases don't accidentally commit mapped data.

### CI / packaging
- All four workflows (`tests.yml`, `ci.yml`, `pr-checks.yml`,
  `release.yml`) now install via `pip install -e ".[dev]"` instead of
  `pip install -r requirements.txt`. This surfaced 42 Pydantic-gated
  tests that were previously silent-skipped in CI — the full suite is
  now 2167 passing / 7 skipped (was 2125 / 49).
- `pyproject.toml` runtime dependencies now include `scikit-learn` and
  `vtk` (both were imported directly in `src/` but only declared in the
  old `requirements.txt`).
- `requirements.txt` retained as a `-e .` shim for users/tools expecting
  it; the single source of dependency truth is `pyproject.toml`.

## [1.0.0] - 2026-04-10

CMPB paper-submission reference release. Preserved unchanged as the
citable version for the paper; do not re-tag.

### Added
- JSON-driven case setup from geometry → hemodynamic outputs.
- Three numerical profiles — `robust` / `standard` / `precise` — with
  documented sensitivity.
- Automated Windkessel boundary conditions via Murray's law and Olufsen
  impedance.
- Backflow stabilisation (default `betaT=0.3`).
- Span-based adaptive meshing with a geometry-aware planner.
- Deterministic post-processing — TAWSS, OSI, RRT, pressure monitoring.
- Benchmark cases `BPM120`, `PAT002`, `VOL04` with expected outputs in
  `benchmarks/README.md`.

### Validation (reference)
- `VOL04`: 4D-flow-MRI comparison, velocity correlation R = 0.75–0.86.
- `0023`: cross-solver comparison vs SimVascular, pressure R > 0.95.
- `BPM120`: mesh / scheme / physics sensitivity (Appendix A of the paper).

### Test baseline
- 2,098 automated tests, 83% code coverage.

[Unreleased]: https://github.com/JieWangnk/AortaCFD-app/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/JieWangnk/AortaCFD-app/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/JieWangnk/AortaCFD-app/releases/tag/v1.0.0
