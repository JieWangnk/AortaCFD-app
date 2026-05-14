# Contributing to AortaCFD

Thanks for considering a contribution. AortaCFD is research-grade cardiovascular CFD software — correctness matters more than ergonomics, and physics matters more than features. Please read this whole document before opening a PR.

## Quick start

```bash
git clone https://github.com/JieWangnk/AortaCFD-app.git
cd AortaCFD-app
make install           # creates ./venv and installs the package + dev deps
source venv/bin/activate
make test              # ~30s, 2210+ tests pass
make lint              # flake8 F-codes + bandit HIGH
```

For tasks that touch OpenFOAM dictionary rendering or hemodynamics, also:
```bash
source /opt/openfoam12/etc/bashrc
make test-all          # full suite minus benchmark fixtures
```

For benchmark validation (you need a real solver output):
```bash
BPM120_TUTORIAL_QOI=output/BPM120/run_XXX/results/qoi_summary.json \
    make test-bench
```

## Reporting bugs

Open an issue using the **Bug report** template. Include:

- AortaCFD version (`python run_patient.py --version`)
- Output of `python run_patient.py --doctor`
- OpenFOAM version (`echo $WM_PROJECT_VERSION`) — most non-trivial bugs are OF-version-specific
- A minimal config that reproduces the issue (we ship 3 sample cases under `cases_input/` — please base your repro on one of those when possible)
- The first 20 lines of `output/<patient>/run_XXX/openfoam/logs/log.solver` (or whichever log is relevant)

If the bug is in mesh quality or convergence on a specific patient geometry, please attach the STLs or a description of the geometry — these issues are usually geometry-specific (e.g. severe coarctation cases behave differently from healthy aortas).

## Requesting features

Open an issue using the **Feature request** template. Describe:

- The cardiovascular CFD problem you're trying to solve
- What you tried with the existing config knobs (we have ~50 user-facing config keys; check `docs/_internal/MESH_SPECIFICATION_GUIDE.md` and the `outlets` / `inlet` sections of [README](README.md) first)
- Alternatives you considered

## Pull requests

### Process

1. Open an issue first if the change is non-trivial. Saves wasted work if the approach needs discussion.
2. Branch from `main`. Name: `feature/<short-name>` or `fix/<short-name>`.
3. Keep commits focused — one logical change per commit. Squash-merge happens at PR-close, but readable commits help review.
4. Each PR must pass `make test` and `make lint` locally before requesting review. CI runs the same gates.
5. Update `CHANGELOG.md` under `[Unreleased]` if your change is user-visible.

### What we look for

- **Tests for new behaviour.** Anything that touches `src/aortacfd_lib/` or `src/config/` should have a test in `tests/test_<module>.py`. New config branches should add a `D.N` test in `tests/test_config_matrix.py` mirroring the existing pattern (validator + resolver + rendering).
- **Backwards compatibility.** Existing configs must continue to render byte-identically unless the change is explicitly behavioural. If you must change behaviour, add a deprecation warning that points users at the new form (see `pressure_anchor` → `per_outlet` for the canonical example).
- **Physics integrity over code elegance.** Cardiovascular CFD has real conventions (Windkessel for arterial flows, etc.). Where in doubt, cite the literature in your PR description.
- **No silent fallbacks.** When a user config is ambiguous or potentially wrong, raise `ValueError` at config-build time. The mid-pipeline failure modes we've found (FPE at hour 17) are user-hostile.
- **No surprise compute.** Don't add tests that hit the OpenFOAM solver. Don't add scripts that launch multi-hour jobs without an explicit flag. Mark slow tests with `@pytest.mark.slow` and `@pytest.mark.e2e` as appropriate.

### Code style

- `black --line-length 120 src/ tests/`
- `isort --profile black src/ tests/`
- `flake8 src/ --select F` must be 0 (other style violations are advisory)
- `bandit -r src/ -ll -ii` must be 0 (HIGH severity, HIGH confidence findings block release)
- New `# nosec` annotations need a one-line justification

## Project conventions worth knowing

- **OpenFOAM 12 Foundation only.** No support for ESI OpenFOAM (different solver names, different patch types).
- **STL files in millimetres** internally scaled to metres via `scale_factor`. Don't pre-scale your STLs.
- **Blood properties**: ρ=1060 kg/m³, μ=0.004 Pa·s for aortic flow; lower viscosity for small vessels (Fahraeus-Lindqvist).
- **Numerics profiles**: `robust` (1st order, debug), `standard` (production default), `precise` (LES / convergence studies). Cite Wang et al. Table 3 for scheme sensitivity.
- **Internal documentation** lives under `docs/_internal/` — read it if you're touching boundary layers, mesh setup, or PIMPLE settings.

## License

By contributing, you agree your contributions are licensed under the [MIT License](LICENSE), the same as the rest of the project.
