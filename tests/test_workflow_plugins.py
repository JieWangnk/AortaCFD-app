"""
Plug-in interface (workflow/plugins.py): discovery, registration rules, and
the merge into WorkflowManager and the CLI step table.
"""

import sys
import types

import pytest

from workflow.base_task import ExecutionContext, Task, TaskMetadata
from workflow.plugins import ENTRY_POINT_GROUP, ENV_VAR, PluginError, PluginRegistry, load_plugins

FAKE_MODULE = "fake_aortacfd_plugin_for_tests"


class NoopTask(Task):
    """A task that does nothing and reports success."""

    metadata = TaskMetadata(name="Noop", description="test task")
    calls = 0

    def execute(self, context: ExecutionContext) -> bool:
        NoopTask.calls += 1
        return True


def _register(registry: PluginRegistry) -> None:
    registry.add_task("noop_task", NoopTask)
    registry.add_recipe("run:noop", ["noop_task"])
    registry.add_step("noop", "run:noop", help="do nothing (test plug-in)")


@pytest.fixture
def fake_plugin(monkeypatch):
    """A plug-in module reachable through AORTACFD_PLUGINS, with no entry points."""
    module = types.ModuleType(FAKE_MODULE)
    module.register = _register
    monkeypatch.setitem(sys.modules, FAKE_MODULE, module)
    monkeypatch.setenv(ENV_VAR, FAKE_MODULE)
    monkeypatch.setattr("workflow.plugins.metadata.entry_points", lambda **kw: [])
    NoopTask.calls = 0
    return module


@pytest.fixture
def no_plugins(monkeypatch):
    monkeypatch.delenv(ENV_VAR, raising=False)
    monkeypatch.setattr("workflow.plugins.metadata.entry_points", lambda **kw: [])


def test_no_plugins_is_a_noop(no_plugins):
    reg = load_plugins(["a"], ["b"], ["c"])
    assert reg.tasks == {} and reg.recipes == {} and reg.steps == {} and reg.loaded == []


def test_env_var_plugin_registers_task_recipe_and_step(fake_plugin):
    reg = load_plugins(["create_case_structure"], ["runAll"], ["case"])
    assert reg.tasks == {"noop_task": NoopTask}
    assert reg.recipes == {"run:noop": ["noop_task"]}
    assert reg.steps == {"noop": "run:noop"}
    assert reg.step_help["noop"] == "do nothing (test plug-in)"
    assert reg.loaded == [FAKE_MODULE]


def test_entry_point_plugin_is_loaded(monkeypatch):
    monkeypatch.delenv(ENV_VAR, raising=False)

    class FakeEntryPoint:
        name = "fake"
        value = "fake.module:register"

        @staticmethod
        def load():
            return _register

    seen = {}

    def fake_entry_points(**kw):
        seen.update(kw)
        return [FakeEntryPoint()]

    monkeypatch.setattr("workflow.plugins.metadata.entry_points", fake_entry_points)
    reg = load_plugins()
    assert seen == {"group": ENTRY_POINT_GROUP}
    assert "noop_task" in reg.tasks and reg.loaded == ["fake (fake.module:register)"]


def test_builtin_task_cannot_be_replaced_by_accident(fake_plugin):
    fake_plugin.register = lambda reg: reg.add_task("execute_solver", NoopTask)
    with pytest.raises(PluginError, match="execute_solver.*built in"):
        load_plugins(["execute_solver"])


def test_builtin_task_can_be_replaced_on_purpose(fake_plugin):
    fake_plugin.register = lambda reg: reg.add_task("execute_solver", NoopTask, replace=True)
    reg = load_plugins(["execute_solver"])
    assert reg.tasks["execute_solver"] is NoopTask


def test_recipe_with_unknown_task_is_rejected(fake_plugin):
    fake_plugin.register = lambda reg: reg.add_recipe("run:bad", ["no_such_task"])
    with pytest.raises(PluginError, match="no_such_task"):
        load_plugins(["execute_solver"])


def test_recipe_may_reuse_builtin_tasks(fake_plugin):
    fake_plugin.register = lambda reg: reg.add_recipe("run:solve-twice", ["execute_solver", "execute_solver"])
    reg = load_plugins(["execute_solver"])
    assert reg.recipes["run:solve-twice"] == ["execute_solver", "execute_solver"]


def test_non_task_class_is_rejected(fake_plugin):
    fake_plugin.register = lambda reg: reg.add_task("thing", dict)
    with pytest.raises(PluginError, match="not a Task subclass"):
        load_plugins()


def test_module_without_register_is_rejected(fake_plugin):
    del fake_plugin.register
    with pytest.raises(PluginError, match="no register"):
        load_plugins()


def test_missing_module_names_the_plugin(monkeypatch, no_plugins):
    monkeypatch.setenv(ENV_VAR, "no_such_module_xyz")
    with pytest.raises(PluginError, match="no_such_module_xyz"):
        load_plugins()


def test_manager_runs_a_plugin_recipe(fake_plugin, tmp_path, monkeypatch):
    from workflow.manager import WorkflowManager

    monkeypatch.chdir(tmp_path)
    manager = WorkflowManager({"geometry": {"case_name": "plugin_case"}})
    assert manager.available_tasks["noop_task"] is NoopTask
    assert manager.recipes["run:noop"] == ["noop_task"]
    assert "runAll" in manager.recipes  # built-ins untouched
    assert manager.plugins.loaded == [FAKE_MODULE]
    manager.run_workflow("run:noop")
    assert NoopTask.calls == 1


def test_manager_without_plugins_keeps_builtin_recipes(no_plugins):
    from workflow.manager import WorkflowManager

    manager = WorkflowManager({"geometry": {"case_name": "plain"}})
    assert manager.plugins.loaded == []
    assert manager.recipes["run:solver"] == ["execute_solver"]
    assert manager.recipes["runAll"][0] == "create_case_structure"


def test_cli_accepts_plugin_step(fake_plugin):
    from patient_runner import cli

    cli._plugin_registry.cache_clear()
    try:
        assert cli.all_steps()["noop"] == "run:noop"
        assert cli.all_steps()["solver"] == "run:solver"
        args = cli.create_parser().parse_args(["CASE", "--step", "noop"])
        assert args.step_list == ["noop"]
    finally:
        cli._plugin_registry.cache_clear()


def test_cli_without_plugins_has_only_builtin_steps(no_plugins):
    from patient_runner import cli

    cli._plugin_registry.cache_clear()
    try:
        assert cli.all_steps() == cli.STEP_MAPPING
    finally:
        cli._plugin_registry.cache_clear()


def test_plugins_block_survives_the_config_merge():
    from config.builder import ConfigBuilder

    case = {"geometry": {"case_name": "ubend"}, "plugins": {"example": {"text": "hi", "n": 3}}}
    merged = ConfigBuilder().build_with_case_config("ubend", "standard", case)
    assert merged["plugins"] == {"example": {"text": "hi", "n": 3}}
    assert merged["plugins"] is not case["plugins"]  # a copy, not the caller's dict
