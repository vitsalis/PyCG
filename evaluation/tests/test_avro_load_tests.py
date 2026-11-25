import os
import subprocess
import sys
from pathlib import Path

EVALUATION = Path(__file__).resolve().parents[1]
PLUGINS = EVALUATION / "macro-benchmark" / "plugins"
CLASSES_THAT_ONLY_LOAD_TESTS_CAN_BUILD = {
    "test_io.py": [
        "BinaryEncodingTestCase",
        "DefaultValueTestCase",
        "IoValidateTestCase",
        "RoundTripTestCase",
        "SchemaPromotionTestCase",
    ],
    "test_protocol.py": ["ProtocolParseTestCase"],
    "test_schema.py": ["FingerprintTestCase", "SchemaParseTestCase"],
}
ORDINARY_CLASS = "TestOther"


def module_with_classes_that_need_constructor_arguments(classes):
    lines = ["import unittest", ""]
    for name in classes:
        lines += [
            f"class {name}(unittest.TestCase):",
            "    def __init__(self, schema, datum):",
            "        super().__init__('check')",
            "    def check(self):",
            "        pass",
            "",
        ]
    lines += [f"class {ORDINARY_CLASS}(unittest.TestCase):", "    def test_one(self):"]
    lines += ["        pass", ""]
    return "\n".join(lines)


def collect(root, plugin=True):
    options = ["-p", "avro_load_tests"] if plugin else []
    done = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"]
        + ["-p", "no:cacheprovider", "--rootdir", str(root), *options, "avro/test"],
        cwd=root,
        env={**os.environ, "PYTHONPATH": str(PLUGINS), "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
    )
    ids = [line for line in done.stdout.splitlines() if "::" in line]
    return done.returncode, ids, done.stdout + done.stderr


def tree(tmp_path, modules):
    directory = tmp_path / "avro" / "test"
    directory.mkdir(parents=True)
    for name, classes in modules.items():
        (directory / name).write_text(
            module_with_classes_that_need_constructor_arguments(classes)
        )
    return tmp_path


def collection_errors(output):
    return sorted(
        line.split()[1]
        for line in output.splitlines()
        if line.startswith("ERROR avro/")
    )


def test_the_eight_classes_are_not_collected_and_the_others_are(tmp_path):
    root = tree(tmp_path, CLASSES_THAT_ONLY_LOAD_TESTS_CAN_BUILD)
    status, ids, output = collect(root, plugin=False)
    assert status == 2, output
    assert collection_errors(output) == sorted(
        f"avro/test/{name}::{c}"
        for name, classes in CLASSES_THAT_ONLY_LOAD_TESTS_CAN_BUILD.items()
        for c in classes
    )
    status, ids, output = collect(root)
    assert status == 0 and collection_errors(output) == [], output
    assert sorted(ids) == sorted(
        f"avro/test/{name}::{ORDINARY_CLASS}::test_one"
        for name in CLASSES_THAT_ONLY_LOAD_TESTS_CAN_BUILD
    )


def test_another_class_or_module_is_collected_as_before(tmp_path):
    root = tree(
        tmp_path,
        {
            "test_io.py": ["NameTestCase"],
            "test_datafile.py": ["IoValidateTestCase"],
        },
    )
    status, ids, output = collect(root)
    assert status == 2, output
    assert collection_errors(output) == [
        "avro/test/test_datafile.py::IoValidateTestCase",
        "avro/test/test_io.py::NameTestCase",
    ]
