"""Regression guard against dual-import module duplication.

Historical context (see ARCHITECTURE.md / SECURITY.md): every module under
src/task_manager/ used to carry a `try: from task_manager.X import Y /
except ModuleNotFoundError: from src.task_manager.X import Y` compatibility
shim. Under an installed package (`pip install -e .` / `uv sync`), the bare
`task_manager.*` import succeeds, while tests and alembic/env.py imported
via the `src.task_manager.*` path explicitly -- so the same source file
loaded as two independent module objects, each with its own module-level
state (notably `database.py`'s SQLAlchemy `engine`, bound to its own
`StaticPool` connection to the same SQLite file, and `scheduler.py`'s
`_last_run_info`). Confirmed via `issubclass(User, Base) is False` and a
Windows `PermissionError` proving two live connections to the same file.

This test doesn't check for that specific shim -- it checks the invariant
that must hold regardless of *how* a duplication happens: every physical
source file under task_manager must resolve to exactly one loaded module
identity. Any future accidental duplication (a stray sys.path.insert, a
reintroduced compatibility import, a second package registration) trips
this the same way.
"""

import sys
from collections import defaultdict
from pathlib import Path

import task_manager.main  # noqa: F401 - forces the full app import graph to load


def test_no_task_manager_source_file_loaded_under_two_module_identities() -> None:
    """Every task_manager source file must map to exactly one sys.modules
    entry, no matter which import spelling was used to reach it."""
    modules_by_file: dict[Path, set[str]] = defaultdict(set)

    for name, module in list(sys.modules.items()):
        if "task_manager" not in name:
            continue
        file_path = getattr(module, "__file__", None)
        if file_path is None:
            continue
        modules_by_file[Path(file_path).resolve()].add(name)

    duplicates = {
        str(file_path): sorted(names)
        for file_path, names in modules_by_file.items()
        if len(names) > 1
    }

    assert not duplicates, (
        "The same source file is loaded under more than one module name. "
        "This means module-level state (e.g. a SQLAlchemy engine, a "
        "rate limiter, an in-memory scheduler cache) exists as two "
        "independent, silently-diverging copies for what should be a "
        f"single instance. Duplicated files -> module names: {duplicates}"
    )
