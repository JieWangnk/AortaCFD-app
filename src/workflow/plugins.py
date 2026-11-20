"""
Plug-in discovery for the open core.

AortaCFD is an open core: the aortic pipeline is released here, and modules
that are not released (a moving left-ventricle wall, coronary trees, GPU
pressure solves) live in separate packages that register themselves at
start-up. The public repository never has to contain them.

A plug-in is a Python package with a ``register(registry)`` function. It is
found in one of two ways:

1. An entry point in the plug-in's ``pyproject.toml`` (the normal way for an
   installed package)::

       [project.entry-points."aortacfd.plugins"]
       lv_motion = "aortacfd_lv.plugin:register"

2. A module name in the environment, for a checkout that is not installed::

       export AORTACFD_PLUGINS=aortacfd_lv.plugin,another.plugin

``register`` receives a :class:`PluginRegistry` and adds tasks (``Task``
subclasses), recipes (named lists of task names, what ``WorkflowManager``
runs) and CLI steps (what ``--steps`` accepts). A plug-in cannot replace a
built-in task, recipe or step unless it passes ``replace=True``, so a stale
plug-in cannot silently change what the open pipeline does.

Failures are loud: a plug-in that cannot be imported, has no ``register``
function, or registers a recipe that names an unknown task stops the run
with a :class:`PluginError` that names the plug-in. A plug-in is something
the user installed on purpose, so a broken one should not be skipped
quietly.
"""

from __future__ import annotations

import importlib
import os
from dataclasses import dataclass, field
from importlib import metadata
from typing import Callable, Dict, Iterable, List, Optional, Tuple, Type

try:
    from .base_task import AortaCFDError, Task
except ImportError:  # pragma: no cover - direct import from src/
    from workflow.base_task import AortaCFDError, Task

ENTRY_POINT_GROUP = "aortacfd.plugins"
ENV_VAR = "AORTACFD_PLUGINS"


class PluginError(AortaCFDError):
    """A plug-in could not be loaded or registered something invalid."""


@dataclass
class PluginRegistry:
    """
    What plug-ins have added, kept apart from the built-ins.

    The built-in names are passed in so a plug-in cannot overwrite them by
    accident. ``WorkflowManager`` and the CLI merge ``tasks``, ``recipes``
    and ``steps`` into their own tables after :func:`load_plugins` returns.
    """

    builtin_tasks: frozenset = frozenset()
    builtin_recipes: frozenset = frozenset()
    builtin_steps: frozenset = frozenset()
    tasks: Dict[str, Type[Task]] = field(default_factory=dict)
    recipes: Dict[str, List[str]] = field(default_factory=dict)
    steps: Dict[str, str] = field(default_factory=dict)
    step_help: Dict[str, str] = field(default_factory=dict)
    loaded: List[str] = field(default_factory=list)
    _current: str = "plugin"

    # -- what a plug-in calls -------------------------------------------------

    def add_task(self, name: str, task_class: Type[Task], *, replace: bool = False) -> None:
        """Register a ``Task`` subclass under ``name``."""
        if not (isinstance(task_class, type) and issubclass(task_class, Task)):
            raise PluginError(f"{self._current}: task '{name}' is not a Task subclass: {task_class!r}")
        self._check_name("task", name, self.builtin_tasks, self.tasks, replace)
        self.tasks[name] = task_class

    def add_recipe(self, command: str, task_names: Iterable[str], *, replace: bool = False) -> None:
        """Register a workflow command as an ordered list of task names."""
        names = list(task_names)
        if not names or not all(isinstance(n, str) and n for n in names):
            raise PluginError(f"{self._current}: recipe '{command}' must be a non-empty list of task names")
        self._check_name("recipe", command, self.builtin_recipes, self.recipes, replace)
        self.recipes[command] = names

    def add_step(self, step: str, command: str, help: str = "", *, replace: bool = False) -> None:
        """Register a CLI step name (``--steps <step>``) that runs ``command``."""
        self._check_name("step", step, self.builtin_steps, self.steps, replace)
        self.steps[step] = command
        self.step_help[step] = help

    # -- internals ------------------------------------------------------------

    def _check_name(self, kind: str, name: str, builtin: frozenset, mine: Dict, replace: bool) -> None:
        if not isinstance(name, str) or not name:
            raise PluginError(f"{self._current}: {kind} name must be a non-empty string, got {name!r}")
        if name in builtin and not replace:
            raise PluginError(
                f"{self._current}: {kind} '{name}' is built in; pass replace=True to override it on purpose"
            )
        if name in mine and not replace:
            raise PluginError(f"{self._current}: {kind} '{name}' was already registered by another plug-in")

    def validate(self) -> None:
        """Every plug-in recipe and step must resolve to something runnable."""
        known_tasks = set(self.builtin_tasks) | set(self.tasks)
        for command, names in self.recipes.items():
            missing = [n for n in names if n not in known_tasks]
            if missing:
                raise PluginError(f"recipe '{command}' names unknown task(s): {', '.join(missing)}")
        known_recipes = set(self.builtin_recipes) | set(self.recipes)
        for step, command in self.steps.items():
            if command not in known_recipes:
                raise PluginError(f"step '{step}' points at unknown workflow command '{command}'")


def plugin_sources() -> List[Tuple[str, Callable[[], Callable[[PluginRegistry], None]]]]:
    """
    Where plug-ins come from: ``(name, loader)`` pairs, entry points first,
    then the modules named in ``AORTACFD_PLUGINS``. ``loader()`` returns the
    plug-in's ``register`` function.
    """
    sources: List[Tuple[str, Callable[[], Callable[[PluginRegistry], None]]]] = []

    try:
        eps = metadata.entry_points(group=ENTRY_POINT_GROUP)
    except TypeError:  # pragma: no cover - Python < 3.10 API
        eps = metadata.entry_points().get(ENTRY_POINT_GROUP, [])
    for ep in eps:
        sources.append((f"{ep.name} ({ep.value})", ep.load))

    for mod_name in [m.strip() for m in os.environ.get(ENV_VAR, "").split(",") if m.strip()]:

        def _load(mod_name: str = mod_name) -> Callable[[PluginRegistry], None]:
            module = importlib.import_module(mod_name)
            register = getattr(module, "register", None)
            if not callable(register):
                raise PluginError(f"{mod_name}: module has no register(registry) function")
            return register

        sources.append((mod_name, _load))

    return sources


def load_plugins(
    builtin_tasks: Optional[Iterable[str]] = None,
    builtin_recipes: Optional[Iterable[str]] = None,
    builtin_steps: Optional[Iterable[str]] = None,
    validate: bool = True,
) -> PluginRegistry:
    """
    Import every plug-in, call its ``register``, check the result.

    Returns a :class:`PluginRegistry`; the caller merges it into its own
    tables. With no plug-ins installed this is a no-op that returns an empty
    registry. ``validate=False`` skips the cross-checks for callers that only
    need the names (the CLI building its ``--steps`` choices); the
    ``WorkflowManager`` always validates.
    """
    registry = PluginRegistry(
        builtin_tasks=frozenset(builtin_tasks or ()),
        builtin_recipes=frozenset(builtin_recipes or ()),
        builtin_steps=frozenset(builtin_steps or ()),
    )
    for name, loader in plugin_sources():
        registry._current = name
        try:
            register = loader()
        except PluginError:
            raise
        except Exception as exc:  # import errors, bad entry point values
            raise PluginError(f"{name}: could not load plug-in: {exc}") from exc
        if not callable(register):
            raise PluginError(f"{name}: entry point does not resolve to a callable register(registry)")
        try:
            register(registry)
        except PluginError:
            raise
        except Exception as exc:
            raise PluginError(f"{name}: register() raised {type(exc).__name__}: {exc}") from exc
        registry.loaded.append(name)
    registry._current = "plugin"
    if validate:
        registry.validate()
    return registry
