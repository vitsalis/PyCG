import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DEVICE_NAMES = frozenset({"con", "prn", "aux", "nul"}) | frozenset(
    f"{device}{number}" for device in ("com", "lpt") for number in "123456789¹²³"
)
FORBIDDEN_CHARACTERS = frozenset('<>:"\\|?*') | frozenset(map(chr, range(32)))


def windows_problems(paths):
    found = set()
    for path in paths:
        for part in path.split("/"):
            if part.split(".", 1)[0].rstrip(" ").lower() in DEVICE_NAMES:
                found.add(f"{path}: {part!r} is a device name")
            if forbidden := "".join(sorted(set(part) & FORBIDDEN_CHARACTERS)):
                found.add(f"{path}: {part!r} holds {forbidden!r}")
            if part.endswith((".", " ")):
                found.add(f"{path}: {part!r} ends in a dot or a space")
    spelled = {}
    for path in paths:
        parts = path.split("/")
        for depth in range(1, len(parts) + 1):
            prefix = "/".join(parts[:depth])
            first = spelled.setdefault(prefix.casefold(), prefix)
            if first != prefix:
                found.add(f"{first} and {prefix} differ only in case")
    return sorted(found)


def tracked_paths():
    done = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-z"],
        capture_output=True,
        check=True,
    )
    return [path.decode("utf-8") for path in done.stdout.split(b"\0") if path]


def test_every_tracked_path_can_be_checked_out_on_windows():
    paths = tracked_paths()
    assert paths
    assert windows_problems(paths) == []


@pytest.mark.parametrize(
    "path",
    [
        "program/nul.py",
        "program/NUL",
        "program/Con.tar.gz",
        "program/aux .py",
        "com1.txt",
        "a/lpt9/b.py",
        "COM¹.py",
        "a/b?.py",
        "a:b.py",
        'a/"b".py',
        "a/b|c.py",
        "a/b*.py",
        "a/b<c>.py",
        "a\\b.py",
        "a/b\tc.py",
        "directory./b.py",
        "a/b.py ",
    ],
)
def test_a_path_that_windows_cannot_check_out_is_found(path):
    assert windows_problems([path]) != []


@pytest.mark.parametrize(
    "path",
    [
        "program/null_byte.py",
        "program/console.py",
        "program/com10.py",
        "program/lpt.py",
        "program/nul_x.py",
        "program/auxiliary/con_figure.py",
        ".hidden/a.b.c",
        "a/b-c_d e.py",
    ],
)
def test_a_path_that_windows_can_check_out_is_not_found(path):
    assert windows_problems([path]) == []


@pytest.mark.parametrize(
    "paths",
    [
        ["a/x.py", "a/X.py"],
        ["A/x.py", "a/y.py"],
        ["tests/Cases/a.py", "tests/cases/b.py"],
    ],
)
def test_paths_that_differ_only_in_case_are_found(paths):
    assert windows_problems(paths) != []


def test_paths_that_differ_in_more_than_case_are_not_found():
    assert windows_problems(["a/x.py", "a/x.pyi", "b/x.py"]) == []
