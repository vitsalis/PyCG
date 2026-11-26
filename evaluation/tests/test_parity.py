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
DUMPS = ("D1.jsonl", "D2.jsonl", "D3.jsonl", "D4.jsonl", "D5.jsonl", "D6.json")


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


compare = load("parity_compare", PARITY / "compare.py")
diff = load("parity_diff", PARITY / "diff.py")

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


def dump(tmp_path, name, seed):
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
    assert {"module", "function", "new_class", "add_call"} <= {r["call"] for r in calls}
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


def copy_as_input(source, root, key):
    target = root / key
    shutil.copytree(source, target)
    return target


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


def test_the_required_dumps_start_empty():
    assert compare.required_dumps(PARITY / "required.txt") == []
