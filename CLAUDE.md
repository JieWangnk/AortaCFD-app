# CLAUDE.md

Instructions for Claude Code (AI assistant) when working with this repository.

## Quick Reference

**Main commands:**
```bash
source venv/bin/activate
python run_patient.py patient1
./venv/bin/pytest tests/
```

**Core architecture:** Task-based workflow (`src/workflow/manager.py`) orchestrates tasks (`src/workflow/tasks/`) using config (`src/config/`) and domain logic (`src/aortacfd_lib/`).

**Config system:** 3-layer merge: base → profile → case config

**Key implementations:**
- Inlet BC: `src/aortacfd_lib/inlet_mapping.py` + `src/templates/U.tpl`
- Windkessel BC: `src/aortacfd_lib/wk_setup.py` + `src/templates/` (requires custom OpenFOAM BC)
- Mesh: `src/aortacfd_lib/mesh_setup.py`
- Workflow: `src/workflow/manager.py`

**Testing:** 362 tests (302 unit, 42 integration, 18 e2e). Always run tests after changes.

**Important constraints:**
- Use inlet type checks (TIMEVARYING needs CSV, CONSTANT doesn't)
- Config merge order must be preserved
- Windkessel flow splits must sum to 1.0
- Always use venv (`source venv/bin/activate`)

**For full details, see README.md**
