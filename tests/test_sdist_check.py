import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "tools_sdist_check",
    Path(__file__).resolve().parents[1] / "tools" / "sdist_check.py",
)
sdist_check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sdist_check)

PACKAGE = ["pycg-2.0.0/pyproject.toml", "pycg-2.0.0/pycg/__init__.py"]


def test_an_sdist_of_the_python_package_only_passes():
    assert sdist_check.findings_of(["pycg-2.0.0", *PACKAGE]) == []


def test_a_rust_file_in_the_sdist_fails():
    members = [*PACKAGE, "pycg-2.0.0/Cargo.lock", "pycg-2.0.0/crates/pycg/src/main.rs"]

    assert sdist_check.findings_of(members) == [
        "the sdist holds Cargo.lock",
        "the sdist holds crates/pycg/src/main.rs",
    ]


def test_a_file_named_like_a_rust_path_elsewhere_passes():
    members = [*PACKAGE, "pycg-2.0.0/tests/fixtures/Cargo.toml", "pycg-2.0.0/cratesx"]

    assert sdist_check.findings_of(members) == []


def test_an_sdist_without_the_package_fails():
    assert sdist_check.findings_of(["pycg-2.0.0/pyproject.toml"]) == [
        "the sdist lacks pycg/__init__.py"
    ]
