import ast
import shutil
import subprocess
from pathlib import Path

import pytest

EVALUATION = Path(__file__).resolve().parents[1]
REPOSITORY = EVALUATION.parent
NOT_SCANNED = (
    EVALUATION / "tests",
    EVALUATION / "macro-benchmark" / "projects",
    EVALUATION / "micro-benchmark" / "snippets",
)
OWN = "our own checkout"
FETCH = "runs in the build of the inputs image"
MAINTAIN = "runs in the maintenance image"
NETWORK = {"urllib.request", "http.client", "socket", "requests", "urllib3", "httpx"}

REASON_BY_STATED_PLACE = {
    ("evaluation/common/run.py", "git_version.git", "git"): OWN,
    ("evaluation/container/fetch.py", "git", "git"): FETCH,
    ("evaluation/container/fetch.py", "<module>", "network"): FETCH,
    ("evaluation/macro-benchmark/draw.py", "<module>", "network"): MAINTAIN,
    ("evaluation/macro-benchmark/draw.py", "Internet.clone", "git"): MAINTAIN,
    ("evaluation/macro-benchmark/draw.py", "_git", "git"): MAINTAIN,
}


def places_writing_git_command_or_importing_network_client(source, name):
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
        if not any(path.is_relative_to(skipped) for skipped in NOT_SCANNED)
    ]


def test_every_place_that_runs_git_or_reaches_the_network_is_stated():
    found = set()
    for path in scanned("*.py"):
        relative = path.relative_to(REPOSITORY).as_posix()
        found |= places_writing_git_command_or_importing_network_client(
            path.read_text(encoding="utf-8"), relative
        )
    assert found - set(REASON_BY_STATED_PLACE) == set(), (
        "a new place: state it, or remove it"
    )
    assert set(REASON_BY_STATED_PLACE) - found == set(), (
        "a stated place is gone: remove it"
    )


def test_no_shell_script_runs_git():
    for path in scanned("*.sh"):
        for line in path.read_text().splitlines():
            code = line.split("#", 1)[0]
            assert "git " not in code, (path, line)


def test_the_repository_has_no_submodule():
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
