import hashlib
import os
from pathlib import Path

import pytest

OUTPUT_DIRECTORY_RELATIVE_TO_ROOTDIR = "tests/test_outputs"
_SNAPSHOT_AT_SESSION_START = pytest.StashKey[dict]()


class OutputsChanged(Exception):
    pass


def snapshot(root):
    found = {}
    for path in sorted(Path(root).rglob("*")):
        key = path.relative_to(root).as_posix()
        if path.is_symlink():
            found[key] = f"-> {os.readlink(path)}"
        elif path.is_dir():
            found[key] = "dir"
        else:
            found[key] = hashlib.sha256(path.read_bytes()).hexdigest()
    return found


def differences_as_git_status(before, after):
    lines = []
    for key in sorted(before.keys() | after.keys()):
        if key not in before:
            lines.append(f"?? {key}")
        elif key not in after:
            lines.append(f" D {key}")
        elif before[key] != after[key]:
            lines.append(f" M {key}")
    return lines


def remove_new_outputs(root, before):
    root = Path(root)
    after = snapshot(root)
    new = sorted(
        key
        for key in after.keys() - before.keys()
        if key.startswith(OUTPUT_DIRECTORY_RELATIVE_TO_ROOTDIR + "/")
    )
    for key in reversed(new):
        path = root / key
        if after[key] == "dir":
            path.rmdir()
        else:
            path.unlink()
    left = differences_as_git_status(before, snapshot(root))
    if left:
        raise OutputsChanged(
            f"the tests changed the checkout {root} outside what "
            "outputs_cleanup.py removes (new entries of "
            f"{OUTPUT_DIRECTORY_RELATIVE_TO_ROOTDIR}/):\n" + "\n".join(left)
        )
    return new


def pytest_sessionstart(session):
    session.stash[_SNAPSHOT_AT_SESSION_START] = snapshot(session.config.rootpath)


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session):
    before = session.stash.get(_SNAPSHOT_AT_SESSION_START, None)
    if before is not None:
        remove_new_outputs(session.config.rootpath, before)
