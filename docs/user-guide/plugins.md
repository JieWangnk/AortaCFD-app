# Plug-ins: add your own steps without touching this repository

AortaCFD is an open core. The aortic pipeline in this repository is released
under the MIT licence. Work that is not released, or not released yet, lives in
separate packages that plug into the pipeline at start-up: a moving
left-ventricle wall, coronary trees, GPU pressure solves, a lab's own
post-processing. The public repository never has to contain that code, and a
plug-in never has to fork this one.

A plug-in can add three things:

| What | Where it shows up | Registered with |
|------|-------------------|-----------------|
| A task (a `Task` subclass) | `WorkflowManager.available_tasks` | `registry.add_task(name, cls)` |
| A workflow command (an ordered list of task names) | `WorkflowManager.recipes`, `run_workflow(command)` | `registry.add_recipe(command, [task names])` |
| A CLI step (`--steps <name>`) | `run_patient.py --steps`, `--list-steps` | `registry.add_step(step, command, help)` |

A recipe may mix the plug-in's own tasks with built-in ones, for example
`["execute_meshing", "my_motion_tables", "execute_solver"]`.

## How a plug-in is found

Either way works; use both if you like.

**1. Entry point** (an installed package). In the plug-in's `pyproject.toml`:

```toml
[project.entry-points."aortacfd.plugins"]
lv_motion = "aortacfd_lv.plugin:register"
```

Then `pip install -e /path/to/the/plugin` into the same environment as
AortaCFD.

**2. Environment variable** (a checkout that is not installed, or a quick
experiment). The value is a comma-separated list of importable module names,
each with a `register` function:

```bash
export AORTACFD_PLUGINS=aortacfd_lv.plugin
python run_patient.py MY_CASE --steps case,mesh,lv-motion,solver
```

`python run_patient.py --list-steps` prints the plug-in steps under the built-in
ones.

## Writing one

The smallest plug-in is one module:

```python
from workflow.base_task import ExecutionContext, Task, TaskMetadata


class WriteMotionTablesTask(Task):
    metadata = TaskMetadata(name="Write motion tables", description="wall displacement per phase")

    def execute(self, context: ExecutionContext) -> bool:
        case_dir = context.case_directory          # the OpenFOAM case folder
        settings = self.config.get("plugins", {}).get("lv_motion", {})  # your block of the case JSON
        ...                                          # write constant/boundaryData, dynamicMeshDict
        return True


def register(registry):
    registry.add_task("lv_write_motion_tables", WriteMotionTablesTask)
    registry.add_recipe("lv:motion", ["lv_write_motion_tables"])
    registry.add_step("lv-motion", "lv:motion", help="write the wall-motion tables from the cine fit")
```

`examples/plugin_template/` is a complete package you can copy: `pyproject.toml`
with the entry point, the module above, a README and a test.

Rules the registry enforces:

- A built-in task, recipe or step name cannot be replaced unless you pass
  `replace=True`. A stale plug-in cannot change what the open pipeline does
  without saying so.
- Two plug-ins cannot register the same name.
- Every recipe must name tasks that exist (built in or registered), and every
  step must point at a recipe that exists.
- A plug-in that cannot be imported, has no `register` function, or breaks one
  of the rules above stops the run with a `PluginError` that names the plug-in.
  Plug-ins are installed on purpose, so a broken one is not skipped quietly.

Your own settings go under the reserved `plugins` block of the case JSON,
keyed by your plug-in's name:

```json
"plugins": {
  "lv_motion": { "phases": 25, "smoothing": "spline" }
}
```

The config builder carries that block through the merge untouched (other
unknown top-level keys are dropped), so a task reads it as
`self.config["plugins"]["lv_motion"]`, next to the built-in sections.

## What stays where

| | Public repository (this one) | Plug-in package (yours) |
|---|---|---|
| Code | aorta pipeline, mesh, boundary conditions, solver driver, hemodynamics | your tasks, recipes, steps, templates |
| Licence | MIT | whatever you choose; it is a separate work |
| Tests | 2,300+ in `tests/` | yours, run against an installed AortaCFD |
| Release | tagged, on GitHub | private, or released when you decide |

One thing to keep in mind if you distribute a plug-in: Python code that writes
OpenFOAM dictionaries and calls the solver is independent of OpenFOAM's licence.
Code compiled against OpenFOAM's libraries (a boundary condition, a function
object, a coded source) is covered by the GPL the moment it is distributed. Keep
compiled extensions in their own repository with their own licence, as
`OpenFOAM-WK` does.
