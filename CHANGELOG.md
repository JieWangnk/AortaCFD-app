# Changelog

All notable changes to AortaCFD are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
