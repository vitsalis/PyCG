import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest

pytestmark = pytest.mark.slow

if sys.version_info < (3, 14):
    pytest.skip(
        "trace.py loads evaluation/micro-benchmark/validate.py, "
        "which needs Python 3.14",
        allow_module_level=True,
    )

TRACE = Path(__file__).resolve().parents[1] / "macro-benchmark" / "trace.py"


def benchmark_with_project_demo(root, entry, files):
    for relative in files:
        path = root / "projects" / "demo" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("")
    config = "[demo]\nexclude = []\ndependencies = []\n" + dedent(entry)
    (root / "projects.toml").write_text(config)
    return root


def locate_without_site_packages(benchmark_dir, only_other_directory=None):
    env = {"PATH": "/usr/bin:/bin"}
    if only_other_directory is not None:
        env["PYTHONPATH"] = str(only_other_directory)
    return subprocess.run(
        [sys.executable, "-S", "-P", "-B", str(TRACE), "demo"]
        + ["--benchmark-dir", str(benchmark_dir), "--locate"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


ONE_PART_SHAPES = [
    ('root = "."\npackages = ["demo_pkg"]', ["demo_pkg/__init__.py"], "demo_pkg"),
    ('root = "src"\npackages = ["demo_pkg"]', ["src/demo_pkg/__init__.py"], "demo_pkg"),
    ('root = "."\npackages = ["demo_mod.py"]', ["demo_mod.py"], "demo_mod"),
]
INSTALLED_FILE_BY_NAME = {"demo_pkg": "demo_pkg/__init__.py", "demo_mod": "demo_mod.py"}


@pytest.mark.parametrize(("entry", "files", "name"), ONE_PART_SHAPES)
def test_a_one_part_package_is_found_in_the_root(tmp_path, entry, files, name):
    done = locate_without_site_packages(
        benchmark_with_project_demo(tmp_path, entry, files)
    )
    origin = tmp_path / "projects" / "demo" / files[0]
    assert (done.returncode, done.stderr) == (0, "")
    assert done.stdout == f"{name}: {origin.resolve()}\n"


@pytest.mark.parametrize(("entry", "files", "name"), ONE_PART_SHAPES)
def test_a_one_part_package_found_elsewhere_too_is_refused(
    tmp_path, entry, files, name
):
    elsewhere = tmp_path / "elsewhere"
    copy = elsewhere / INSTALLED_FILE_BY_NAME[name]
    copy.parent.mkdir(parents=True)
    copy.write_text("")
    done = locate_without_site_packages(
        benchmark_with_project_demo(tmp_path, entry, files), elsewhere
    )
    assert done.returncode == 1
    assert f"demo: {name} is also found outside the checkout" in done.stderr


def test_a_missing_package_is_not_found(tmp_path):
    project = benchmark_with_project_demo(
        tmp_path, 'root = "."\npackages = ["demo_pkg"]', []
    )
    done = locate_without_site_packages(project)
    assert done.returncode == 1
    assert "demo: demo_pkg is not found in the checkout" in done.stderr


BELOW_SRC = 'root = "."\npackages = ["src/demo_pkg"]'
SHAPES_BELOW_A_DIRECTORY = [
    (BELOW_SRC, ["src/demo_pkg/__init__.py"], "src.demo_pkg"),
    (
        'root = "."\npackages = ["src/ns/demo_pkg"]',
        ["src/ns/demo_pkg/__init__.py"],
        "src.ns.demo_pkg",
    ),
    (BELOW_SRC, ["src/__init__.py", "src/demo_pkg/__init__.py"], "src.demo_pkg"),
]


@pytest.mark.parametrize(("entry", "files", "name"), SHAPES_BELOW_A_DIRECTORY)
def test_a_package_below_a_directory_is_found_part_by_part_without_imports(
    tmp_path, entry, files, name
):
    done = locate_without_site_packages(
        benchmark_with_project_demo(tmp_path, entry, files)
    )
    origin = tmp_path / "projects" / "demo" / files[-1]
    assert (done.returncode, done.stderr) == (0, "")
    assert done.stdout == f"{name}: {origin.resolve()}\n"


def test_a_module_that_hides_a_namespace_directory_hides_the_package(tmp_path):
    files = ["src.py", "src/demo_pkg/__init__.py"]
    done = locate_without_site_packages(
        benchmark_with_project_demo(tmp_path, BELOW_SRC, files)
    )
    assert done.returncode == 1
    assert "demo: src.demo_pkg is not found in the checkout" in done.stderr


def test_a_first_part_found_elsewhere_too_is_refused(tmp_path):
    elsewhere = tmp_path / "elsewhere"
    (elsewhere / "src" / "demo_pkg").mkdir(parents=True)
    (elsewhere / "src" / "demo_pkg" / "__init__.py").write_text("")
    project = benchmark_with_project_demo(
        tmp_path, BELOW_SRC, ["src/demo_pkg/__init__.py"]
    )
    done = locate_without_site_packages(project, elsewhere)
    assert done.returncode == 1
    assert "demo: src is also found outside the checkout" in done.stderr


def test_a_namespace_without_the_package_is_not_found(tmp_path):
    project = benchmark_with_project_demo(
        tmp_path, BELOW_SRC, ["src/other/__init__.py"]
    )
    done = locate_without_site_packages(project)
    assert done.returncode == 1
    assert "demo: src.demo_pkg is not found in the checkout" in done.stderr
