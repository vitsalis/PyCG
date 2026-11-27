import argparse
import json
import os
import sys
from pathlib import Path

import pytest

DESCRIPTION = """\
Writes the vectors of the import manager that the Rust tests replay
(crates/analysis/tests/vectors/imports.json, docs/rust/PLAN.md, section 5):
runs tests/unit/test_imports.py under the oracle and records, for each
ImportManager that a test makes, the files of the test's directory and
every call of the manager's methods that Rust has, with its arguments and
what it gave. A path under the test's directory is written {root}/<path>.

    python3 tools/parity/import_vectors.py

A test whose manager raises (a misuse of the API, which Rust asserts
against), calls a method that Rust does not have, or reads a path outside
the test's directory is listed, not recorded.
"""

ROOT = Path(__file__).resolve().parents[2]
TESTS = ROOT / "tests" / "unit" / "test_imports.py"
OUT = ROOT / "crates" / "analysis" / "tests" / "vectors" / "imports.json"
ROOT_IN_PATHS = "{root}"
RECORDED = (
    "set_pkg",
    "create_node",
    "set_filepath",
    "set_current_mod",
    "handle_import",
    "get_imports",
    "get_filepath",
    "module_files",
    "locate",
    "packages",
    "get_node",
    "get_import_graph",
)
SETTERS = ("set_pkg", "create_node", "set_filepath", "set_current_mod")
UNPORTED = ("create_edge", "is_internal", "get_mod_dir")
SKIPPED_FILES = ("__pycache__",)


class Outside(Exception):
    pass


def spelled(value, root):
    if isinstance(value, str) and os.path.isabs(value):
        path = Path(value)
        if root is None or not path.is_relative_to(root):
            raise Outside(value)
        return f"{ROOT_IN_PATHS}/{path.relative_to(root).as_posix()}".removesuffix("/.")
    if isinstance(value, (list, tuple)):
        return [spelled(item, root) for item in value]
    if isinstance(value, set):
        return sorted(spelled(item, root) for item in value)
    if isinstance(value, dict):
        return {key: spelled(item, root) for key, item in value.items()}
    return value


def comparable(name, result):
    if name in SETTERS:
        return None
    if name == "get_node":
        return result is not None
    if name == "get_import_graph":
        return {
            module: {"filename": node["filename"], "imports": sorted(node["imports"])}
            for module, node in result.items()
        }
    if isinstance(result, set):
        return sorted(result)
    if isinstance(result, list):
        return list(result)
    return result


class Session:
    def __init__(self):
        self.operations = []
        self.problem = None
        self.depth = 0


class Recorder:
    def __init__(self):
        self.vectors = []
        self.listed = []
        self.failed = []

    @pytest.hookimpl(wrapper=True)
    def pytest_runtest_call(self, item):
        from pycg.analysis.imports import ImportManager
        from pycg.analysis.program import Program

        tmp_path = item.funcargs.get("tmp_path")
        sessions = {}
        engine = []
        originals = {
            name: getattr(ImportManager, name) for name in (*RECORDED, *UNPORTED)
        }
        made = ImportManager.__init__
        program = Program.__init__

        def making(manager, *args, **keywords):
            made(manager, *args, **keywords)
            if not engine:
                sessions[id(manager)] = (manager, Session())

        def building(built, *args, **keywords):
            engine.append(built)
            try:
                program(built, *args, **keywords)
            finally:
                engine.pop()

        def session_of(manager):
            return sessions.get(id(manager), (None, None))[1]

        def recorded(name):
            original = originals[name]

            def call(manager, *args, **keywords):
                session = session_of(manager)
                if session is None or session.depth:
                    return original(manager, *args, **keywords)
                session.depth += 1
                try:
                    result = original(manager, *args, **keywords)
                except Exception as error:
                    session.problem = session.problem or f"{name} raises {error!r}"
                    raise
                finally:
                    session.depth -= 1
                session.operations.append(
                    {
                        "call": name,
                        "args": [*args, *keywords.values()],
                        "result": comparable(name, result),
                    }
                )
                return result

            return call

        def unported(name):
            original = originals[name]

            def call(manager, *args, **keywords):
                session = session_of(manager)
                if session is not None and not session.depth:
                    session.problem = (
                        session.problem or f"{name} has no Rust counterpart"
                    )
                return original(manager, *args, **keywords)

            return call

        for name in RECORDED:
            setattr(ImportManager, name, recorded(name))
        for name in UNPORTED:
            setattr(ImportManager, name, unported(name))
        ImportManager.__init__ = making
        Program.__init__ = building
        try:
            result = yield
        finally:
            for name, original in originals.items():
                setattr(ImportManager, name, original)
            ImportManager.__init__ = made
            Program.__init__ = program
        for index, (_, session) in enumerate(sessions.values()):
            self.write(item.name, index, session, tmp_path)
        if not sessions:
            self.listed.append(f"{item.name}: makes no import manager of its own")
        return result

    def pytest_runtest_logreport(self, report):
        if report.when == "call" and report.failed:
            self.failed.append(report.nodeid)

    def write(self, name, index, session, tmp_path):
        if session.problem is not None:
            self.listed.append(f"{name}: {session.problem}")
            return
        root = Path(tmp_path).resolve() if tmp_path is not None else None
        try:
            operations = [
                {
                    "call": operation["call"],
                    "args": spelled(operation["args"], root),
                    "result": spelled(operation["result"], root),
                }
                for operation in session.operations
            ]
        except Outside as path:
            self.listed.append(f"{name}: reads {path}, outside its directory")
            return
        files = {}
        for path in sorted(root.rglob("*")) if root is not None else ():
            relative = path.relative_to(root)
            if set(relative.parts) & set(SKIPPED_FILES):
                continue
            if path.is_dir() and not any(path.iterdir()):
                files[relative.as_posix() + "/"] = None
            elif path.is_file():
                files[relative.as_posix()] = path.read_text(encoding="utf-8")
        self.vectors.append(
            {
                "test": name if index == 0 else f"{name}-{index + 1}",
                "files": files,
                "operations": operations,
            }
        )


def record(tests):
    recorder = Recorder()
    status = pytest.main(
        ["-q", "-p", "no:cacheprovider", str(tests)], plugins=[recorder]
    )
    return recorder, status == 0 and not recorder.failed


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=DESCRIPTION, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.parse_args(argv)
    recorder, passed = record(TESTS)
    for line in recorder.listed:
        print(f"not recorded: {line}")
    if not passed:
        print(f"the tests of {TESTS} did not pass under the oracle", file=sys.stderr)
        return 1
    lines = ",\n".join(
        json.dumps(vector, sort_keys=True) for vector in recorder.vectors
    )
    OUT.write_text(f"[\n{lines}\n]\n", encoding="utf-8")
    print(f"{len(recorder.vectors)} sessions written to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
