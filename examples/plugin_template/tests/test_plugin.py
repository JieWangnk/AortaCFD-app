"""Run with AortaCFD importable (its src/ on sys.path, or installed)."""

from aortacfd_example_plugin.plugin import WriteNoteTask, register
from workflow.plugins import PluginRegistry


def test_register_adds_task_recipe_and_step():
    reg = PluginRegistry()
    register(reg)
    assert reg.tasks["example_write_note"] is WriteNoteTask
    assert reg.recipes["example:note"] == ["example_write_note"]
    assert reg.steps["example-note"] == "example:note"


def test_task_writes_the_note(tmp_path):
    from workflow.base_task import ExecutionContext

    ctx = ExecutionContext()
    ctx.case_directory = str(tmp_path)
    assert WriteNoteTask({"plugins": {"example": {"text": "hello"}}}).execute(ctx) is True
    assert (tmp_path / "example_plugin.txt").read_text() == "hello\n"
