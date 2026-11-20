# AortaCFD plug-in template

A complete, installable plug-in with one task, one workflow command and one
CLI step. Copy the folder, rename `aortacfd_example_plugin`, replace the task.

```bash
cp -r examples/plugin_template ~/my-plugin && cd ~/my-plugin
# rename the package and the entry point in pyproject.toml, then:
pip install -e .                      # into the environment that runs AortaCFD
cd /path/to/AortaCFD-app
python run_patient.py ubend --list-steps        # "example-note" is listed
python run_patient.py ubend --steps case,example-note
```

Without installing, point AortaCFD at the module instead:

```bash
export PYTHONPATH=~/my-plugin/src
export AORTACFD_PLUGINS=aortacfd_example_plugin.plugin
```

The plug-in's own settings live under the reserved `plugins` block of the case
JSON, here `"plugins": {"example": {"text": "..."}}`. Tests: `pytest tests/` with AortaCFD's
`src/` importable.

The guide, with the rules the registry enforces and what stays in which
repository, is `docs/user-guide/plugins.md`.
