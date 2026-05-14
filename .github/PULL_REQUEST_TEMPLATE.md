<!--
Thanks for the PR! Please fill in the sections below. Read CONTRIBUTING.md
first if you haven't — it covers code style, test conventions, and the
backwards-compatibility expectations specific to this codebase.
-->

## Summary

<!-- One paragraph: what does this PR change and why? -->

## Type of change

- [ ] Bug fix (non-breaking — fixes an issue)
- [ ] New feature (non-breaking — adds functionality)
- [ ] Breaking change (will affect existing user configs or CLI)
- [ ] Documentation only
- [ ] Internal refactor / test improvement / lint cleanup

## Linked issue

<!-- Closes #123 / Refs #456 -->

## Checklist

- [ ] My change is **backwards-compatible** with existing user configs, OR I have added a deprecation warning that points users at the new form (template: see `pressure_anchor` deprecation in v1.4.0)
- [ ] I have added tests covering the new behaviour in `tests/`
- [ ] `make test` passes locally
- [ ] `make lint` passes locally (`flake8 -F` and Bandit HIGH must both be 0)
- [ ] I have updated `CHANGELOG.md` under `[Unreleased]` if the change is user-visible
- [ ] I have updated relevant documentation (README, docstrings, or `docs/`)
- [ ] If this touches OpenFOAM dictionary rendering: I have verified the rendered `0/U`, `0/p`, `system/fvSchemes`, `constant/momentumTransport` match my intent
- [ ] If this touches Windkessel / boundary conditions / numerics: I have cited the relevant literature in the PR description below

## Test plan

<!--
How did you verify this change works? Be specific.
  - "I ran `pytest tests/test_X.py::TestY::test_Z`"
  - "I ran `python run_patient.py BPM120 --steps case,mesh,boundary` and inspected `0/p`"
  - "I extended the config matrix with a new R-series entry and ran it to completion"
-->

## Notes for reviewer

<!-- Anything specific you want feedback on? Open questions? Trade-offs? -->
