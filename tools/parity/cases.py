import argparse
import ast
import json
import logging
import re
import sys
import tempfile
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TESTS = ROOT / "tests"
CASES = ROOT / "tests" / "cases"
DESIGN = ROOT / "docs" / "design.md"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(TESTS))

import programs  # noqa: E402
import pytest  # noqa: E402

from pycg.formats import edges as edges_of  # noqa: E402
from pycg.pycg import CallGraphGenerator  # noqa: E402

DESCRIPTION = """Turn the tests of one Python test file into Rust cases
(docs/rust/PLAN.md, section 5, "Cases"): every program that a test analyses
through tests/programs.py becomes tests/cases/FAMILY/<test>/, with its files,
case.toml and expected.json, the oracle's edges and unresolved sites.

    python -I tools/parity/cases.py tests/test_super.py super "`super()`"

The edges that a test asserts present or absent go to case.toml; the
assertions that it cannot read, and the tests that analyse no program or
more than one, are printed for a hand conversion."""

PROGRAM_LOGGER = "pycg.analysis.program"
CASE_NAME = re.compile(r"[a-z0-9_]+")


class Program:
    def __init__(self, files, entry_points, package, options):
        self.files = files
        self.entry_points = entry_points
        self.package = package
        self.options = options


class Recorder:
    def __init__(self):
        self.programs = {}
        self.current = None

    @pytest.hookimpl(wrapper=True)
    def pytest_runtest_call(self, item):
        self.current = item
        original = programs.analysed

        def analysed(root, files, entry_points=("main.py",), package=True, **options):
            texts = {
                path: source if isinstance(source, bytes) else textwrap.dedent(source)
                for path, source in files.items()
            }
            program = Program(texts, list(entry_points), package, options)
            self.programs.setdefault(item, []).append(program)
            return original(root, files, entry_points, package, **options)

        programs.analysed = analysed
        for module in list(sys.modules.values()):
            if getattr(module, "analysed", None) is original:
                module.analysed = analysed
        try:
            return (yield)
        finally:
            programs.analysed = original
            for module in list(sys.modules.values()):
                if getattr(module, "analysed", None) is analysed:
                    module.analysed = original


class Oracle:
    def __init__(self, document, warnings):
        self.document = document
        self.warnings = warnings
        self.edges = edges_of(document)
        self.unresolved = _unresolved(document)


class _Warnings(logging.Handler):
    def __init__(self, root):
        super().__init__(logging.WARNING)
        self.prefixes = sorted({f"{root}/", f"{root.resolve()}/"}, key=len)[::-1]
        self.lines = []

    def emit(self, record):
        line = record.getMessage()
        for prefix in self.prefixes:
            line = line.replace(prefix, "")
        self.lines.append(line)


def oracle(program):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        programs.write(root, program.files)
        generator = CallGraphGenerator(
            [str(root / entry) for entry in program.entry_points],
            str(root) if program.package else None,
            **program.options,
        )
        handler = _Warnings(root)
        logger = logging.getLogger(PROGRAM_LOGGER)
        logger.addHandler(handler)
        try:
            generator.analyze()
        finally:
            logger.removeHandler(handler)
        return Oracle(generator.document(), handler.lines)


def _unresolved(document):
    unresolved = {}
    for caller, sites in sorted(document["calls"].items()):
        causes = {
            f"{site['line']}:{site['col']}": site["unresolved"]
            for site in sites
            if "unresolved" in site
        }
        if causes:
            unresolved[caller] = causes
    return unresolved


def _caller_of(node):
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "callees"
        and len(node.args) == 2
        and isinstance(node.args[1], ast.Constant)
    ):
        return node.args[1].value
    if (
        isinstance(node, ast.Subscript)
        and isinstance(node.slice, ast.Constant)
        and isinstance(node.value, ast.Name)
        and node.value.id == "graph"
    ):
        return node.slice.value
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in ("set", "sorted")
        and len(node.args) == 1
    ):
        return _caller_of(node.args[0])
    return None


def _strings(node):
    if isinstance(node, (ast.List, ast.Set, ast.Tuple)):
        values = [
            element.value for element in node.elts if isinstance(element, ast.Constant)
        ]
        if len(values) == len(node.elts) and all(isinstance(v, str) for v in values):
            return values
    return None


def _translate(test):
    present, absent, unread = [], [], []
    for node in ast.walk(test):
        if not isinstance(node, ast.Assert):
            continue
        check = node.test
        edges = None
        if isinstance(check, ast.Compare) and len(check.ops) == 1:
            left, op, right = check.left, check.ops[0], check.comparators[0]
            caller = _caller_of(right)
            if (
                isinstance(op, (ast.In, ast.NotIn))
                and isinstance(left, ast.Constant)
                and caller is not None
            ):
                edges = (op, [(caller, left.value)])
            caller = _caller_of(right)
            if isinstance(op, ast.LtE) and caller is not None:
                callees = _strings(left)
                if callees is not None:
                    edges = (ast.In(), [(caller, callee) for callee in callees])
            caller = _caller_of(left)
            if isinstance(op, (ast.Eq, ast.GtE)) and caller is not None:
                callees = _strings(right)
                if callees is not None:
                    edges = (ast.In(), [(caller, callee) for callee in callees])
        if edges is None:
            unread.append(ast.unparse(node))
        elif isinstance(edges[0], ast.NotIn):
            absent += edges[1]
        else:
            present += edges[1]
    return present, absent, unread


def _test_functions(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    }


def _headings():
    return {
        line.lstrip("#").strip()
        for line in DESIGN.read_text(encoding="utf-8").splitlines()
        if line.startswith("#")
    }


def _toml_string(value):
    return json.dumps(value, ensure_ascii=True)


def _toml_pairs(pairs):
    if not pairs:
        return "[]"
    lines = [f"    [{_toml_string(a)}, {_toml_string(b)}]," for a, b in pairs]
    return "[\n" + "\n".join(lines) + "\n]"


def case_toml(statement, design, program, warnings, present, absent):
    lines = [
        f"statement = {_toml_string(statement)}",
        f"design = {_toml_string(design)}",
        "entry_points = ["
        + ", ".join(_toml_string(entry) for entry in program.entry_points)
        + "]",
        f"package = {'true' if program.package else 'false'}",
    ]
    if "cap" in program.options:
        cap = program.options["cap"]
        lines.append(f"cap = {_toml_string('none') if cap is None else cap}")
    assert set(program.options) <= {"cap"}, program.options
    lines.append(
        "warnings = [" + ", ".join(_toml_string(warning) for warning in warnings) + "]"
    )
    lines.append(f"present = {_toml_pairs(present)}")
    lines.append(f"absent = {_toml_pairs(absent)}")
    return "\n".join(lines) + "\n"


def _json_map(name, items):
    if not items:
        return f" {json.dumps(name)}: {{}}"
    lines = [
        f"  {json.dumps(key)}: {json.dumps(value, sort_keys=True)}"
        for key, value in items
    ]
    return f" {json.dumps(name)}: {{\n" + ",\n".join(lines) + "\n }"


def expected_json(edges, unresolved):
    parts = [
        _json_map("edges", edges.items()),
        _json_map("unresolved", unresolved.items()),
    ]
    return "{\n" + ",\n".join(parts) + "\n}\n"


def write_case(directory, statement, design, program, present, absent):
    found = oracle(program)
    edges = found.edges
    missing = [pair for pair in present if pair[1] not in edges.get(pair[0], [])]
    unexpected = [pair for pair in absent if pair[1] in edges.get(pair[0], [])]
    assert not missing and not unexpected, (directory, missing, unexpected)
    directory.mkdir(parents=True)
    for path, source in program.files.items():
        file = directory / path
        file.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(source, bytes):
            file.write_bytes(source)
        else:
            file.write_text(source, encoding="utf-8", newline="\n")
    (directory / "case.toml").write_text(
        case_toml(statement, design, program, found.warnings, present, absent),
        encoding="utf-8",
        newline="\n",
    )
    (directory / "expected.json").write_text(
        expected_json(edges, found.unresolved), encoding="utf-8", newline="\n"
    )


def main(argv):
    parser = argparse.ArgumentParser(
        description=DESCRIPTION, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("test_file", type=Path)
    parser.add_argument("family")
    parser.add_argument("design")
    args = parser.parse_args(argv)
    assert CASE_NAME.fullmatch(args.family), args.family
    if args.design not in _headings():
        parser.error(f"{args.design!r} is not a heading of {DESIGN}")
    family = CASES / args.family
    if family.exists():
        parser.error(f"{family} exists")
    recorder = Recorder()
    status = pytest.main(
        ["-q", "-p", "no:cacheprovider", str(args.test_file)], plugins=[recorder]
    )
    if status != 0:
        parser.error(f"the tests of {args.test_file} do not pass")
    functions = _test_functions(args.test_file)
    by_name = {}
    for item, recorded in recorder.programs.items():
        by_name.setdefault(item.originalname, []).extend(recorded)
    report = []
    for name, function in functions.items():
        recorded = by_name.get(name, [])
        if any(argument.arg == "monkeypatch" for argument in function.args.args):
            report.append(f"{name}: monkeypatches; no case is written")
            continue
        if not recorded:
            report.append(f"{name}: analyses no program through tests/programs.py")
            continue
        present, absent, unread = (
            _translate(function) if len(recorded) == 1 else ([], [], [])
        )
        if len(recorded) > 1:
            report.append(
                f"{name}: analyses {len(recorded)} programs; no assertion is read"
            )
        report += [f"{name}: not read: {line}" for line in unread]
        statement = name.removeprefix("test_").replace("_", " ")
        for index, program in enumerate(recorded, 1):
            case = name.removeprefix("test_") + ("" if index == 1 else f"_{index}")
            write_case(family / case, statement, args.design, program, present, absent)
    for line in report:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
