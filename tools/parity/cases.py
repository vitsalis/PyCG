import argparse
import json
import logging
import os
import re
import shutil
import sys
from pathlib import Path

import pytest

DESCRIPTION = """\
Turns the Python tests of one file into the cases of tests/cases/ that the
Rust harness runs (docs/rust/PLAN.md, section 5, Testing).

    python3 tools/parity/cases.py tests/test_super.py

Runs the file's tests under the oracle. Every program that a test analyses
becomes a case directory, tests/cases/<family>/<test name>[-<n>]/:
program/ holds the files of the program; case.json the entry points, the
package root, the cap, the section of docs/design.md that the family pins,
a one-line statement and the callers and named nodes that the test read;
expected.json the oracle's edges, unresolved sites, the points-to sets of
the named nodes that the test read, the warnings of the analysis, with
{root} for the directory of the program, and each document that the test
read, with the package name and version it was asked with.
A test that monkeypatches an attribute (of the engine: its solver's
order, a rule) is not converted: it is listed, since it states an
invariant for the simulation tests, not a program's output. A test that
only changes the directory or the environment is converted, its paths
taken from the root of its program.
A test that analyses no program in its own process (one that runs the
command line) is listed too, and so is a test that analyses micro cases,
which the harness runs already: it states a property of every case. A
hypothesis property runs with seed 0, so its examples, each a case, are
the same on every run. The cases of the file are written again from
scratch.
"""

ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / "tests" / "cases"
CASE = "case.json"
EXPECTED = "expected.json"
PROGRAM = "program"
SKIPPED_FILES = ("__pycache__",)
SNIPPETS = ROOT / "evaluation" / "micro-benchmark" / "snippets"
FAMILIES = {
    "tests/test_abstract_classes.py": (
        "classes",
        "Classes that Python does not instantiate",
    ),
    "tests/test_arguments.py": (
        "calls",
        "Arguments",
    ),
    "tests/test_call_arity.py": (
        "calls",
        "Calls",
    ),
    "tests/test_callbacks.py": (
        "calls",
        "Call backs",
    ),
    "tests/test_class_rule_limits.py": (
        "classes",
        "Classes and hierarchies",
    ),
    "tests/test_class_tests.py": (
        "classes",
        "Class tests",
    ),
    "tests/test_decorators_and_descriptors.py": (
        "calls",
        "Decorators and functions that return a parameter",
    ),
    "tests/test_defaults_and_receivers.py": (
        "calls",
        "Arguments",
    ),
    "tests/test_descriptors.py": (
        "classes",
        "Descriptors",
    ),
    "tests/test_document.py": (
        "document",
        "What is reported as an edge",
    ),
    "tests/test_flow.py": (
        "flow",
        "Paths, joins and loops",
    ),
    "tests/test_generator.py": (
        "language",
        "The assignment graph (idea 1)",
    ),
    "tests/test_language_items.py": (
        "language",
        "Language features",
    ),
    "tests/test_library_iteration.py": (
        "outside",
        "Selected standard-library operations",
    ),
    "tests/test_literal_imports.py": (
        "language",
        "Imports",
    ),
    "tests/test_match.py": (
        "language",
        "`match`",
    ),
    "tests/test_metaclasses.py": (
        "classes",
        "Metaclasses",
    ),
    "tests/test_object_hooks.py": (
        "classes",
        "Attribute hooks",
    ),
    "tests/test_outside_call_results.py": (
        "outside",
        "Typed outside values",
    ),
    "tests/test_outside_callbacks.py": (
        "outside",
        "Call backs",
    ),
    "tests/test_outside_types.py": (
        "outside",
        "Typed outside values",
    ),
    "tests/test_own_stubs.py": (
        "outside",
        "Declared types (idea 4)",
    ),
    "tests/test_patterns.py": (
        "language",
        "Computed attribute names",
    ),
    "tests/test_slots.py": (
        "classes",
        "The class statement",
    ),
    "tests/test_super.py": (
        "classes",
        "`super()`",
    ),
    "tests/test_third_party_stubs.py": (
        "outside",
        "Stub data",
    ),
    "tests/test_type_three_arguments.py": (
        "classes",
        "The class statement",
    ),
    "tests/test_with_and_exceptions.py": (
        "language",
        "Exceptions, `finally` and `with`",
    ),
    "tests/unit/test_imports.py": (
        "imports",
        "Imports",
    ),
    "tests/unit/test_type_only_names.py": (
        "imports",
        "Imports",
    ),
}
ENGINE_LOGGER = "pycg"
ROOT_IN_WARNINGS = "{root}"
NAME_CHARACTERS = frozenset("abcdefghijklmnopqrstuvwxyz0123456789_")


class Read(dict):
    def __init__(self, values, keys):
        super().__init__(values)
        self.keys_read = keys

    def __getitem__(self, key):
        self.keys_read.add(key)
        return super().__getitem__(key)

    def get(self, key, default=None):
        self.keys_read.add(key)
        return super().get(key, default)

    def __contains__(self, key):
        self.keys_read.add(key)
        return super().__contains__(key)


class Warnings(logging.Handler):
    def __init__(self):
        super().__init__(logging.WARNING)
        self.lines = []

    def emit(self, record):
        self.lines.append(record.getMessage())


class Run:
    def __init__(self, generator, copy_root, entry_points, package):
        self.generator = generator
        self.copy_root = copy_root
        self.entry_points = entry_points
        self.package = package
        self.callers = set()
        self.labels = set()
        self.documents = set()
        self.warnings = []
        self.files = {}


def snapshot(root):
    files = {}
    for path in sorted(Path(root).rglob("*")):
        relative = path.relative_to(root)
        if path.is_file() and not set(relative.parts) & set(SKIPPED_FILES):
            files[relative.as_posix()] = path.read_bytes()
    return files


def statement(name):
    words = re.sub(r"\[.*\]$", "", name).removeprefix("test_").replace("_", " ")
    return words[:1].upper() + words[1:]


def case_name(name, index):
    function, _, parameters = name.removeprefix("test_").partition("[")
    base = function
    if parameters:
        spelled = "".join(
            character if character in NAME_CHARACTERS else f"-{ord(character):x}"
            for character in parameters.removesuffix("]")
        )
        base = f"{base}-{spelled}"
    return base if index == 0 else f"{base}-{index + 1}"


def relative(path, root):
    return Path(os.path.relpath(path, root)).as_posix()


class Recorder:
    def __init__(self, cases, source, family, design):
        self.cases = cases
        self.source = source
        self.family = family
        self.design = design
        self.written = []
        self.skipped = []
        self.unanalysed = []
        self.micro = []
        self.failed = []

    @pytest.hookimpl(wrapper=True)
    def pytest_runtest_call(self, item):
        from pycg.pycg import CallGraphGenerator

        runs = []
        tmp_path = item.funcargs.get("tmp_path")
        analyze = CallGraphGenerator.analyze
        output = CallGraphGenerator.output
        output_points_to = CallGraphGenerator.output_points_to
        document = CallGraphGenerator.document
        outputs = []

        def recorded_analyze(generator):
            entry_points = [os.path.abspath(entry) for entry in generator.entry_points]
            package = generator.package
            package = None if package is None else os.path.abspath(package)
            paths = [*entry_points, *([] if package is None else [package])]
            copy_root = tmp_path or os.path.commonpath(paths)
            run = Run(generator, copy_root, entry_points, package)
            run.files = snapshot(copy_root)
            handler = Warnings()
            logger = logging.getLogger(ENGINE_LOGGER)
            logger.addHandler(handler)
            try:
                analyze(generator)
            finally:
                logger.removeHandler(handler)
            run.warnings = handler.lines
            runs.append(run)

        def recorded_output(generator):
            run = next(run for run in runs if run.generator is generator)
            outputs.append(generator)
            try:
                return Read(output(generator), run.callers)
            finally:
                outputs.pop()

        def recorded_document(generator, package_name=None, package_version=None):
            run = next(run for run in runs if run.generator is generator)
            if generator not in outputs:
                run.documents.add((package_name, package_version))
            return document(generator, package_name, package_version)

        def recorded_output_points_to(generator):
            run = next(run for run in runs if run.generator is generator)
            return Read(output_points_to(generator), run.labels)

        CallGraphGenerator.analyze = recorded_analyze
        CallGraphGenerator.output = recorded_output
        CallGraphGenerator.output_points_to = recorded_output_points_to
        CallGraphGenerator.document = recorded_document
        try:
            result = yield
        finally:
            CallGraphGenerator.analyze = analyze
            CallGraphGenerator.output = output
            CallGraphGenerator.output_points_to = output_points_to
            CallGraphGenerator.document = document
        monkeypatch = item.funcargs.get("monkeypatch")
        if monkeypatch is not None and monkeypatch._setattr:
            self.skipped.append(item.name)
            return result
        if not runs:
            self.unanalysed.append(item.name)
        if any(Path(run.copy_root).is_relative_to(SNIPPETS) for run in runs):
            self.micro.append(item.name)
            return result
        for index, run in enumerate(runs):
            self.write(item.name, index, run, output, output_points_to, document)
        return result

    def pytest_runtest_logreport(self, report):
        if report.when == "call" and report.failed:
            self.failed.append(report.nodeid)

    def write(self, name, index, run, output, output_points_to, document):
        generator = run.generator
        directory = self.cases / self.family / case_name(name, index)
        assert not directory.exists(), f"{directory} is written twice"
        directory.mkdir(parents=True)
        program = directory / PROGRAM
        for path, data in run.files.items():
            target = program / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        root = run.copy_root
        package = run.package
        case = {
            "source": f"{self.source}::{name}",
            "statement": statement(name),
            "design": self.design,
            "entry_points": [relative(entry, root) for entry in run.entry_points],
            "package": None if package is None else relative(package, root),
            "cap": generator.cap,
            "focus": sorted(run.callers),
        }
        edges = output(generator)
        unresolved = generator.program.analysis.unresolved_calls()
        points_to = output_points_to(generator)
        expected = {
            "edges": edges,
            "unresolved": sorted(
                [caller, site, cause] for (caller, site), cause in unresolved.items()
            ),
            "points_to": {
                label: points_to.get(label, []) for label in sorted(run.labels)
            },
            "warnings": [
                warning.replace(str(Path(root).resolve()), ROOT_IN_WARNINGS)
                for warning in run.warnings
            ],
            "documents": [
                {
                    "package_name": package_name,
                    "package_version": package_version,
                    "document": document(generator, package_name, package_version),
                }
                for package_name, package_version in sorted(run.documents, key=repr)
            ],
        }
        (directory / CASE).write_text(json.dumps(case, indent=1, sort_keys=True) + "\n")
        (directory / EXPECTED).write_text(
            json.dumps(expected, indent=1, sort_keys=True) + "\n"
        )
        self.written.append(directory)


def remove_cases_of(cases, source, family):
    for case in sorted((cases / family).glob(f"*/{CASE}")):
        if json.loads(case.read_text())["source"].split("::")[0] == source:
            shutil.rmtree(case.parent)


def convert(cases, test_file, source, family, design):
    remove_cases_of(cases, source, family)
    recorder = Recorder(cases, source, family, design)
    status = pytest.main(
        ["-q", "-p", "no:cacheprovider", "--hypothesis-seed=0", str(test_file)],
        plugins=[recorder],
    )
    return recorder, status == 0 and not recorder.failed


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=DESCRIPTION, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "test_file", help="a test file of FAMILIES, relative to the root"
    )
    args = parser.parse_args(argv)
    source = Path(args.test_file).as_posix()
    if source not in FAMILIES:
        parser.error(f"{source} has no family in FAMILIES")
    family, design = FAMILIES[source]
    recorder, passed = convert(CASES, ROOT / source, source, family, design)
    for name in recorder.skipped:
        print(f"not converted (monkeypatches an attribute): {source}::{name}")
    for name in recorder.micro:
        print(f"not converted (a property of the micro cases): {source}::{name}")
    for name in recorder.unanalysed:
        print(f"not converted (analyses no program in process): {source}::{name}")
    print(f"{len(recorder.written)} cases written to {CASES / family}")
    if not passed:
        print(f"the tests of {source} did not pass under the oracle", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
