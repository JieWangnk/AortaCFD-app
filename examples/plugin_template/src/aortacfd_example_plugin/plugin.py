"""
One task, one workflow command, one CLI step.

After ``pip install -e .`` (or ``export AORTACFD_PLUGINS=aortacfd_example_plugin.plugin``):

    python run_patient.py MY_CASE --list-steps        # shows "example-note"
    python run_patient.py MY_CASE --steps case,example-note
"""

from pathlib import Path

from workflow.base_task import ExecutionContext, Task, TaskMetadata


class WriteNoteTask(Task):
    """Write a small text file into the case folder. Replace with your own work."""

    metadata = TaskMetadata(name="Write example note", description="writes example_plugin.txt into the case")

    def execute(self, context: ExecutionContext) -> bool:
        settings = self.config.get("plugins", {}).get("example", {})  # "plugins": {"example": {...}} in the case JSON
        text = settings.get("text", "written by the example plug-in")
        case_dir = Path(context.case_directory or ".")
        case_dir.mkdir(parents=True, exist_ok=True)
        (case_dir / "example_plugin.txt").write_text(text + "\n")
        self.log.info(f"example plug-in wrote {case_dir / 'example_plugin.txt'}")
        return True


def register(registry) -> None:
    """Called by AortaCFD at start-up. Names must not clash with the built-ins."""
    registry.add_task("example_write_note", WriteNoteTask)
    registry.add_recipe("example:note", ["example_write_note"])
    registry.add_step("example-note", "example:note", help="write example_plugin.txt into the case folder")
