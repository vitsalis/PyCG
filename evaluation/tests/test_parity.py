import importlib.util
import json
import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PARITY = ROOT / "tools" / "parity"
DUMPS = (
    "D1.jsonl",
    "D2.jsonl",
    "D3.jsonl",
    "D4.jsonl",
    "D5.jsonl",
    "D6.json",
    "D6in.json",
)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


compare = load("parity_compare", PARITY / "compare.py")
diff = load("parity_diff", PARITY / "diff.py")
oracle = load("parity_dump", PARITY / "dump.py")

PROGRAMS = {
    "classes": """
        import re
        class Base:
            def __init__(self, value):
                self.value = value
            def __setattr__(self, name, value):
                object.__setattr__(self, name, value)
        class Child(Base):
            @property
            def size(self):
                return len(self.value)
        def make(kind, value):
            return kind(value)
        for kind in (Base, Child):
            made = make(kind, [1, 2])
            made.size
        re.compile("a").sub(lambda m: m.group(0), "b")
        """,
    "containers": """
        def first(*args, **kwargs):
            return args[0], kwargs.get("key")
        values = {"a": first, "b": len}
        pairs = [(k, v) for k, v in values.items()]
        for name, function in pairs:
            function(name)
        merged = {**values, "c": print}
        merged["c"]("x")
        a, *rest = [first, len, print]
        rest[0]("y")
        """,
}


def read(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def dump(tmp_path, name, seed, cap=None):
    program = tmp_path / name / "program"
    if not program.exists():
        program.mkdir(parents=True)
        source = textwrap.dedent(PROGRAMS[name])
        (program / "main.py").write_text(source, encoding="utf-8")
    out = tmp_path / name / f"seed-{seed}"
    done = subprocess.run(
        [
            sys.executable,
            "-I",
            str(PARITY / "dump.py"),
            "input",
            "--checkout",
            str(ROOT),
            "--out",
            str(out),
            "--package",
            str(program),
            *([] if cap is None else ["--cap", str(cap)]),
            str(program / "main.py"),
        ],
        env={"PYTHONHASHSEED": str(seed)},
        capture_output=True,
        text=True,
    )
    assert done.returncode == 0, done.stderr
    return out


@pytest.fixture(scope="module")
def dumped(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("parity")
    return {name: [dump(tmp_path, name, seed) for seed in (0, 1)] for name in PROGRAMS}


@pytest.mark.parametrize("name", sorted(PROGRAMS))
def test_every_dump_is_written_and_is_the_same_for_hash_seeds_0_and_1(dumped, name):
    first, second = dumped[name]
    for file_name in DUMPS:
        assert (first / file_name).stat().st_size > 0, file_name
        assert (first / file_name).read_bytes() == (second / file_name).read_bytes()


@pytest.mark.parametrize("name", sorted(PROGRAMS))
def test_the_document_inputs_hold_what_the_document_names(dumped, name):
    first, _ = dumped[name]
    document = json.loads((first / "D6.json").read_text(encoding="utf-8"))
    inputs = json.loads((first / "D6in.json").read_text(encoding="utf-8"))

    defined = {
        name
        for name, module in document["modules"].items()
        if module["kind"] == "source"
    }
    defined |= {entry["name"] for entry in inputs["functions"]}
    defined |= {entry["name"] for entry in inputs["classes"]}
    assert defined == set(document["definitions"])
    sites = {caller for caller, *_ in inputs["site_edges"]}
    sites |= {caller for caller, *_ in inputs["unresolved"]}
    assert sites == set(document["calls"])
    assert inputs["cap"] == document["tool"]["cap"]


def test_the_run_record_names_the_package_and_entry_points_from_the_checkout(
    dumped, tmp_path
):
    first, _ = dumped["classes"]
    run = json.loads((first / "run.json").read_text(encoding="utf-8"))
    program = first.parent / "program"

    assert (ROOT / run["package"]).resolve() == program.resolve()
    assert [(ROOT / path).resolve() for path in run["entry_points"]] == [
        (program / "main.py").resolve()
    ]


def test_every_record_is_canonical_json_without_addresses(dumped):
    first, _ = dumped["classes"]
    for file_name in DUMPS[:5]:
        for line in (first / file_name).read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            assert line == json.dumps(record, sort_keys=True, separators=(",", ":"))
            assert " at 0x" not in line, line


def test_the_dumps_name_what_the_engine_did(dumped):
    first, _ = dumped["classes"]
    calls = read(first / "D4.jsonl")
    assert {"module", "function", "new_class", "add_call"} <= {
        r["call"] for r in calls if "call" in r
    }
    trace = read(first / "D3.jsonl")
    operations = {record["op"] for record in trace}
    assert {"attach", "apply", "applied", "solve", "fire", "final", "work"} <= (
        operations
    )
    stubs = read(first / "D2.jsonl")
    assert any(record["call"] == "find" for record in stubs)
    points_to = read(first / "D5.jsonl")
    assert any(record["node"] == "main.make.kind" for record in points_to)
    scopes = read(first / "D1.jsonl")
    assert any(record.get("scope", {}).get("name") == "main.Base" for record in scopes)


def test_a_builder_call_names_every_argument_with_its_defaults(dumped):
    first, _ = dumped["classes"]
    calls = [record for record in read(first / "D4.jsonl") if "call" in record]
    (function, *_) = [record for record in calls if record["call"] == "function"]
    assert set(function["arguments"]) == {
        "name",
        "module",
        "signature",
        "defaults",
        "generator",
    }
    assert function["arguments"]["signature"] == {
        "signature": {
            "positional": ["self", "value"],
            "positional_only_count": 0,
            "keyword_only": [],
            "vararg": None,
            "kwarg": None,
        }
    }
    imported = next(r for r in calls if r["call"] == "imports.handle_import")
    assert imported["arguments"] == {"name": "re", "level": 0, "record": True}
    assert imported["answer"] is None
    add_call = next(record for record in calls if record["call"] == "add_call")
    assert add_call["arguments"]["applies"] is False
    assert add_call["arguments"]["star"] == []


def test_the_linking_of_the_program_is_recorded_before_solving(tmp_path):
    program = tmp_path / "linking" / "program"
    for relative, source in {
        "main.py": "import pkg.sub\nfrom pkg import *\n",
        "pkg/__init__.py": "__all__ = ['sub']\n",
        "pkg/sub.py": "",
    }.items():
        (program / relative).parent.mkdir(parents=True, exist_ok=True)
        (program / relative).write_text(source, encoding="utf-8")
    seeds = [read(dump(tmp_path, "linking", seed) / "D4.jsonl") for seed in (0, 1)]
    linked = [r for r in seeds[0] if r["module"] == oracle.PROGRAM]

    assert linked == [r for r in seeds[1] if r["module"] == oracle.PROGRAM]
    calls = [(r["call"], r["arguments"]) for r in linked if "call" in r]
    assert (
        "imports.handle_import",
        {"name": "pkg.sub", "level": 0, "record": True},
    ) in calls
    modules = [arguments["name"] for call, arguments in calls if call == "module"]
    assert modules[:3] == ["main", "pkg", "pkg.sub"]
    assert "add_object" in {call for call, _ in calls}
    assert seeds[0][-1] == {
        "module": oracle.PROGRAM,
        "object": {"object": "Module:pkg"},
        "fields": {"defines": {"set": ["__all__", "sub"]}},
    }


def test_the_fields_that_the_builder_writes_end_each_module_of_the_build(dumped):
    first, _ = dumped["classes"]
    records = read(first / "D4.jsonl")
    fields = {
        record["object"]["object"]: record["fields"]
        for record in records
        if "fields" in record
    }
    assert {"Base", "Child", "make"} <= set(fields["Module:main"]["defines"]["set"])
    size = fields["Function:main.Child.size"]
    assert (size["lineno"], size["end_lineno"], size["decorated"]) == (10, 11, True)
    base = fields["Class:main.Base"]
    assert base["lineno"] == 3
    assert {"__init__", "__setattr__"} <= set(base["defines"]["set"])
    last = max(i for i, record in enumerate(records) if "call" in record)
    assert all({"fields", "tables"} & set(record) for record in records[last + 1 :])
    (tables,) = [record["tables"] for record in records if "tables" in record]
    assert tables["iterated_expressions"]["set"]
    assert tables["read_namespaces"] == {"set": []}
    answered = {
        record["answer"]["object"]
        for record in records
        if "call" in record and isinstance(record["answer"], dict)
        if "object" in record["answer"]
    }
    assert set(fields) - {"Module:main"} <= answered


def test_an_unread_lazy_import_is_written_by_its_position(tmp_path):
    PROGRAMS["lazy"] = """
        __lazy_modules__ = ["audit"]
        import audit
        import report
        report.build()
        """
    try:
        out = dump(tmp_path, "lazy", 0)
    finally:
        del PROGRAMS["lazy"]
    records = read(out / "D1.jsonl")

    assert {"module": "main", "unread_lazy": [["alias", 3, 7, 3, 12]]} in records


@pytest.mark.parametrize("name", sorted(PROGRAMS))
def test_the_trace_declares_every_object_and_constraint_before_it_is_used(dumped, name):
    first, _ = dumped[name]
    objects = {}
    constraints = {}
    nodes = set()
    for record in read(first / "D3.jsonl"):
        operation = record["op"]
        if operation == "object":
            assert record["object"] not in objects
            assert record["types"][-1] == "Object"
            assert record["opacity"] is None or record["opacity"] in (
                {"saturated", record["object"]} | set(objects)
            )
            objects[record["object"]] = record
        elif operation == "constraint":
            assert set(record["captured"]) <= set(objects)
            assert record["mode"] in ("each", "list")
            constraints[record["constraint"]] = record
        elif operation == "node":
            nodes.add(record["node"])
        elif operation in ("constant", "add_object"):
            assert record["args"][-1]["object"] in objects
        elif operation in ("attach", "apply_now"):
            assert next(iter(record["args"][1].values())) in constraints
        elif operation == "apply":
            assert record["constraint"] in constraints
            assert all(o["object"] in objects for o in record["objects"])
        elif operation == "wake":
            assert record["node"] in nodes
    assert any(record["mode"] == "each" for record in constraints.values())


def test_a_class_that_becomes_unknown_is_named_between_rounds(tmp_path):
    PROGRAMS["unknown"] = """
        def b1(): return b2
        def b2(): return (int, str, bytes)
        for base in b1()():
            Holder = base
        class Late(Holder):
            def run(self): pass
        Late().run()
        """
    try:
        out = dump(tmp_path, "unknown", 0, cap=2)
    finally:
        del PROGRAMS["unknown"]
    trace = read(out / "D3.jsonl")
    done = [r for r in trace if r["op"] == "between_rounds_done"]

    assert ["Class:main.Late"] in [r["unknown"] for r in done]
    starts = [i for i, r in enumerate(trace) if r["op"] == "between_rounds"]
    assert len(starts) == len(done)


def copy_as_input(source, root, key):
    target = root / key
    shutil.copytree(source, target)
    return target


def test_the_oracle_finds_every_dump_that_differs_between_the_seeds(dumped, tmp_path):
    first, second = dumped["classes"]
    seed_0 = copy_as_input(first, tmp_path, "seed-0")
    seed_1 = copy_as_input(second, tmp_path, "seed-1")

    assert oracle.differing_dumps(seed_0, seed_1) == []

    with (seed_1 / "D3.jsonl").open("a", encoding="utf-8") as trace:
        trace.write("{}\n")
    (seed_1 / "D5.jsonl").unlink()

    assert oracle.differing_dumps(seed_0, seed_1) == ["D3", "D5"]


def test_the_same_dumps_compare_identical(dumped, tmp_path, capsys):
    first, second = dumped["classes"]
    expected = tmp_path / "expected"
    actual = tmp_path / "actual"
    copy_as_input(first, expected, "micro/a/classes")
    copy_as_input(second, actual, "micro/a/classes")
    required = tmp_path / "required.txt"
    required.write_text("D1\nD2\nD3\nD4\nD5\n", encoding="utf-8")

    status = compare.main([str(expected), str(actual), "--required", str(required)])

    assert status == 0
    assert "1 inputs, 1 identical, 0 different" in capsys.readouterr().out


def test_a_planted_difference_in_the_document_inputs_is_found_and_explained(
    dumped, tmp_path, capsys
):
    first, _ = dumped["classes"]
    expected = tmp_path / "expected"
    actual = tmp_path / "actual"
    copy_as_input(first, expected, "micro/a/classes")
    planted = copy_as_input(first, actual, "micro/a/classes")
    inputs = json.loads((planted / "D6in.json").read_text(encoding="utf-8"))
    inputs["functions"][0]["lineno"] += 1
    (planted / "D6in.json").write_text(
        json.dumps(inputs, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    status = compare.main([str(expected), str(actual), "--dumps", "D6in"])
    found = capsys.readouterr().out
    explained = diff.explain(expected, actual, "micro/a/classes", "D6in")

    assert status == 1
    assert "micro/a/classes: different: D6in" in found
    assert explained[0] == "functions/0/lineno:"


def test_a_planted_difference_in_a_dump_is_found_and_explained(
    dumped, tmp_path, capsys
):
    first, _ = dumped["classes"]
    expected = tmp_path / "expected"
    actual = tmp_path / "actual"
    copy_as_input(first, expected, "micro/a/classes")
    planted = copy_as_input(first, actual, "micro/a/classes")
    lines = (planted / "D4.jsonl").read_text(encoding="utf-8").splitlines()
    changed = len(lines) // 2
    lines[changed] = lines[changed].replace('"call":"', '"call":"planted_', 1)
    (planted / "D4.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    required = tmp_path / "required.txt"
    required.write_text("D4\n", encoding="utf-8")

    status = compare.main([str(expected), str(actual), "--required", str(required)])
    found = capsys.readouterr().out
    explained = diff.explain(expected, actual, "micro/a/classes", "D4")

    assert status == 1
    assert "1 different" in found and "micro/a/classes: different: D4" in found
    assert explained[0].startswith(f"first difference at record {changed + 1} ")
    assert any(line.startswith(">") and "planted_" in line for line in explained)


def test_a_planted_difference_in_a_document_is_found_and_explained(
    dumped, tmp_path, capsys
):
    first, _ = dumped["classes"]
    expected = tmp_path / "expected"
    actual = tmp_path / "actual"
    copy_as_input(first, expected, "micro/a/classes")
    planted = copy_as_input(first, actual, "micro/a/classes")
    document = json.loads((planted / "D6.json").read_text(encoding="utf-8"))
    site = next(s for s in document["calls"]["main.make"] if s["callees"])
    removed = site["callees"].pop(0)
    (planted / "D6.json").write_text(json.dumps(document), encoding="utf-8")
    required = tmp_path / "required.txt"
    required.write_text("", encoding="utf-8")

    status = compare.main([str(expected), str(actual), "--required", str(required)])
    found = capsys.readouterr().out
    explained = diff.explain(expected, actual, "micro/a/classes", "D6")

    assert status == 1
    assert "micro/a/classes: different: D6" in found
    assert "edge: 1 only in expected" in explained
    assert f"  ('main.make', '{removed}')" in explained


def test_an_input_that_the_other_side_has_not_written_is_missing(
    dumped, tmp_path, capsys
):
    first, _ = dumped["classes"]
    expected = tmp_path / "expected"
    actual = tmp_path / "actual"
    copy_as_input(first, expected, "micro/a/classes")
    copy_as_input(first, expected, "macro/b")
    partial = copy_as_input(first, actual, "micro/a/classes")
    for path in partial.iterdir():
        if path.name != "D1.jsonl":
            path.unlink()
    required = tmp_path / "required.txt"
    required.write_text("", encoding="utf-8")

    status = compare.main([str(expected), str(actual), "--required", str(required)])
    found = capsys.readouterr().out

    assert status == 0
    assert "micro: 1 inputs, 0 identical, 0 different, 0 failed, 1 missing" in found
    assert "macro: 1 inputs, 0 identical, 0 different, 0 failed, 1 missing" in found


def test_a_required_dump_is_compared_before_the_other_side_writes_a_document(
    dumped, tmp_path, capsys
):
    first, _ = dumped["classes"]
    expected = tmp_path / "expected"
    actual = tmp_path / "actual"
    copy_as_input(first, expected, "micro/a/classes")
    copy_as_input(first, expected, "micro/a/same")
    planted = copy_as_input(first, actual, "micro/a/classes")
    same = copy_as_input(first, actual, "micro/a/same")
    for partial in (planted, same):
        for path in partial.iterdir():
            if path.name != "D2.jsonl":
                path.unlink()
    lines = (planted / "D2.jsonl").read_text(encoding="utf-8").splitlines()
    lines[0] = lines[0].replace('"call":"', '"call":"planted_', 1)
    (planted / "D2.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    required = tmp_path / "required.txt"
    required.write_text("D2\n", encoding="utf-8")

    status = compare.main([str(expected), str(actual), "--required", str(required)])
    found = capsys.readouterr().out

    assert status == 1
    assert "micro: 2 inputs, 0 identical, 1 different, 0 failed, 1 missing" in found
    assert "micro/a/classes: different: D2" in found


@pytest.mark.parametrize("dump", ["D3", "D6"])
def test_a_required_dump_that_the_other_side_lacks_fails(
    dumped, tmp_path, capsys, dump
):
    first, _ = dumped["classes"]
    expected = tmp_path / "expected"
    actual = tmp_path / "actual"
    copy_as_input(first, expected, "micro/a/classes")
    partial = copy_as_input(first, actual, "micro/a/classes")
    (partial / compare.file_of(dump)).unlink()
    required = tmp_path / "required.txt"
    required.write_text(f"{dump}\n", encoding="utf-8")

    status = compare.main([str(expected), str(actual), "--required", str(required)])

    assert status == 1
    assert f"failed: {dump} is required and absent" in capsys.readouterr().out


def test_only_the_listed_inputs_are_compared_on_the_named_dumps(
    dumped, tmp_path, capsys
):
    first, _ = dumped["classes"]
    expected = tmp_path / "expected"
    actual = tmp_path / "actual"
    copy_as_input(first, expected, "micro/a/classes")
    copy_as_input(first, expected, "micro/a/other")
    agreeing = copy_as_input(first, actual, "micro/a/classes")
    (agreeing / "D4.jsonl").write_text("{}\n", encoding="utf-8")
    (copy_as_input(first, actual, "micro/a/other") / "error.txt").write_text("")
    inputs = tmp_path / "inputs.txt"
    inputs.write_text("micro/a/classes\n", encoding="utf-8")

    status = compare.main(
        [str(expected), str(actual), "--dumps", "D3", "D5", "--inputs", str(inputs)]
    )

    assert status == 0
    assert "micro: 1 inputs, 1 identical, 0 different" in capsys.readouterr().out


def test_a_listed_input_that_the_oracle_lacks_fails(dumped, tmp_path, capsys):
    first, _ = dumped["classes"]
    expected = tmp_path / "expected"
    actual = tmp_path / "actual"
    copy_as_input(first, expected, "micro/a/classes")
    copy_as_input(first, actual, "micro/a/classes")
    inputs = tmp_path / "inputs.txt"
    inputs.write_text("micro/a/classes\nmicro/a/renamed\n", encoding="utf-8")

    status = compare.main(
        [str(expected), str(actual), "--dumps", "D3", "--inputs", str(inputs)]
    )

    assert status == 1
    assert "micro/a/renamed: failed: the oracle has no such input" in (
        capsys.readouterr().out
    )


def stopped_after(source, root, key, records):
    stopped = copy_as_input(source, root, key)
    trace = (stopped / "D3.jsonl").read_text(encoding="utf-8").splitlines()
    (stopped / "D3.jsonl").unlink()
    (stopped / "D5.jsonl").unlink()
    (stopped / "D6.json").unlink()
    partial = "".join(f"{line}\n" for line in trace[:records])
    (stopped / compare.PARTIAL).write_text(partial, encoding="utf-8")
    (stopped / "error.txt").write_text("not ported: a rule\n", encoding="utf-8")
    return stopped


def test_a_trace_that_stops_inside_the_oracles_trace_is_partial(
    dumped, tmp_path, capsys
):
    first, _ = dumped["classes"]
    expected = tmp_path / "expected"
    actual = tmp_path / "actual"
    copy_as_input(first, expected, "micro/a/classes")
    stopped_after(first, actual, "micro/a/classes", 40)
    inputs = tmp_path / "inputs.txt"
    inputs.write_text("micro/a/classes\n", encoding="utf-8")

    status = compare.main([str(expected), str(actual), "--dumps", "D3", "D5"])
    found = capsys.readouterr().out
    listed = compare.main(
        [str(expected), str(actual), "--dumps", "D3", "--inputs", str(inputs)]
    )

    assert status == 0
    assert "0 failed, 0 missing, 1 partial" in found
    assert listed == 1


def test_a_trace_that_leaves_the_oracles_trace_before_it_stops_differs(
    dumped, tmp_path, capsys
):
    first, _ = dumped["classes"]
    expected = tmp_path / "expected"
    actual = tmp_path / "actual"
    copy_as_input(first, expected, "micro/a/classes")
    stopped = stopped_after(first, actual, "micro/a/classes", 40)
    lines = (stopped / compare.PARTIAL).read_text(encoding="utf-8").splitlines()
    lines[30] = lines[30].replace('"op":"', '"op":"planted_', 1)
    (stopped / compare.PARTIAL).write_text("\n".join(lines) + "\n", encoding="utf-8")

    status = compare.main([str(expected), str(actual), "--dumps", "D3", "D5"])
    found = capsys.readouterr().out
    explained = diff.explain(expected, actual, "micro/a/classes", "D3")

    assert status == 1
    assert "micro/a/classes: different: D3" in found
    assert explained[0].startswith("first difference at record 31 ")


def test_the_inputs_of_the_engine_are_inputs_of_the_oracle():
    inputs = compare.listed(PARITY / "engine.txt")
    snippets = ROOT / "evaluation" / "micro-benchmark" / "snippets"

    assert inputs == sorted(set(inputs))
    assert all((snippets / key.removeprefix("micro/")).is_dir() for key in inputs)


KEY_FILES = (
    "tools/inputs_key.py",
    "evaluation/compose.yaml",
    "evaluation/container/Dockerfile.inputs",
    "evaluation/container/Dockerfile.inputs.dockerignore",
    "evaluation/container/fetch.py",
    "evaluation/macro-benchmark/projects.py",
    "evaluation/macro-benchmark/projects.toml",
    "evaluation/scale/projects.py",
    "evaluation/scale/projects.toml",
    "evaluation/common/run.py",
    "tools/parity/dump.py",
    "pycg/__init__.py",
    "evaluation/micro-benchmark/snippets/args/assigned_call/main.py",
)


def git(repository, *args):
    subprocess.run(
        ["git", "-C", str(repository), *args],
        check=True,
        capture_output=True,
        env=dict(
            os.environ,
            GIT_AUTHOR_NAME="parity",
            GIT_AUTHOR_EMAIL="parity@localhost",
            GIT_COMMITTER_NAME="parity",
            GIT_COMMITTER_EMAIL="parity@localhost",
        ),
    )


def oracle_key(repository):
    done = subprocess.run(
        [
            sys.executable,
            "-I",
            str(PARITY / "dump.py"),
            "key",
            "--checkout",
            repository,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return done.stdout.strip()


@pytest.mark.parametrize(
    "changed",
    [
        "pycg/__init__.py",
        "tools/parity/dump.py",
        "evaluation/micro-benchmark/snippets/args/assigned_call/main.py",
        "evaluation/common/run.py",
        "evaluation/macro-benchmark/projects.toml",
    ],
)
def test_the_key_of_an_oracle_run_follows_every_input_of_the_run(tmp_path, changed):
    for name in KEY_FILES:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "inputs")
    before = oracle_key(tmp_path)
    with (tmp_path / changed).open("a", encoding="utf-8") as file:
        file.write("\n")
    git(tmp_path, "commit", "-q", "-a", "-m", "changed")

    assert len(before) == 64 and int(before, 16) >= 0
    assert oracle_key(tmp_path) != before


def test_the_required_dumps_are_dumps_that_the_oracle_writes():
    required = compare.listed(PARITY / "required.txt")

    assert {"D1", "D2"} <= set(required)
    assert set(required) <= {"D1", "D2", "D3", "D4", "D5", "D6"}
