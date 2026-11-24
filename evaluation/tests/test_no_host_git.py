"""The maintainer's rule of 2026-11-14: git and every download run only in
a container, never on the host; the repository holds no submodule, and
projects.toml is the only lock of every source of the benchmark. The
inputs are fetched in the build of the inputs image
(evaluation/container/Dockerfile.inputs); the maintenance commands that
need the network run in its target `maintain`.

A short inventory: every place in evaluation/ (but its tests) that
writes a command line of git (a list or tuple whose first item is "git")
or imports a network client is stated below, as "our own checkout" (git on
this repository or a PyCG checkout), "runs in the build of the inputs
image" or "runs in the maintenance image". A new place fails the test
until it is stated; a stated place that is gone fails it too. It reads the
syntax trees only: it is a guard, not a proof.
"""

import ast
import shutil
import subprocess
from pathlib import Path

import pytest

EVALUATION = Path(__file__).resolve().parents[1]
REPOSITORY = EVALUATION.parent
# Not scanned: the tests, and a copy of the sources (data).
SKIPPED = (EVALUATION / "tests", EVALUATION / "macro-benchmark" / "projects")
OWN = "our own checkout"
FETCH = "runs in the build of the inputs image"
MAINTAIN = "runs in the maintenance image"
NETWORK = {"urllib.request", "http.client", "socket", "requests", "urllib3", "httpx"}

# (file, the function that holds it, kind): why it may be there.
STATED = {
    ("evaluation/common/run.py", "git_version.git", "git"): OWN,
    ("evaluation/container/fetch.py", "git", "git"): FETCH,
    ("evaluation/container/fetch.py", "<module>", "network"): FETCH,
    ("evaluation/macro-benchmark/draw.py", "<module>", "network"): MAINTAIN,
    ("evaluation/macro-benchmark/draw.py", "Internet.clone", "git"): MAINTAIN,
    ("evaluation/macro-benchmark/draw.py", "_git", "git"): MAINTAIN,
}


def inventory(source, name):
    """{(name, function, kind)} of the places of `source` that write a git
    command line (kind "git") or import a network client ("network")."""
    found = set()

    def visit(node, scope):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            scope = [*scope, node.name]
        where = ".".join(scope) or "<module>"
        if (
            isinstance(node, (ast.List, ast.Tuple))
            and node.elts
            and isinstance(node.elts[0], ast.Constant)
            and node.elts[0].value == "git"
        ):
            found.add((name, where, "git"))
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in node.names]
            if isinstance(node, ast.ImportFrom):
                names = [node.module or ""] + [f"{node.module}.{n}" for n in names]
            if any(n in NETWORK for n in names):
                found.add((name, where, "network"))
        for child in ast.iter_child_nodes(node):
            visit(child, scope)

    visit(ast.parse(source), [])
    return found


def scanned(pattern):
    return [
        path
        for path in sorted(EVALUATION.rglob(pattern))
        if not any(path.is_relative_to(skipped) for skipped in SKIPPED)
    ]


def test_every_place_that_runs_git_or_reaches_the_network_is_stated():
    found = set()
    for path in scanned("*.py"):
        relative = path.relative_to(REPOSITORY).as_posix()
        found |= inventory(path.read_text(encoding="utf-8"), relative)
    assert found - set(STATED) == set(), "a new place: state it, or remove it"
    assert set(STATED) - found == set(), "a stated place is gone: remove it"


def test_no_shell_script_runs_git():
    for path in scanned("*.sh"):
        for line in path.read_text().splitlines():
            code = line.split("#", 1)[0]
            assert "git " not in code, (path, line)


def test_the_repository_has_no_submodule():
    """Every source of the benchmark is a pin that the build of the inputs
    image fetches."""
    assert not (REPOSITORY / ".gitmodules").exists()
    if shutil.which("git") is None or not (REPOSITORY / ".git").exists():
        pytest.skip("not a git checkout")
    done = subprocess.run(
        ["git", "-C", str(REPOSITORY), "ls-files", "--stage"],
        capture_output=True,
        text=True,
        check=True,
    )
    gitlinks = [line for line in done.stdout.splitlines() if line.startswith("160000")]
    assert gitlinks == []
