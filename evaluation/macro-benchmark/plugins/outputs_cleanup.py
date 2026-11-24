"""A pytest plugin: remove what the tests write into tests/test_outputs/.

19 test items of python-barcode 0.16.1 (21 with Pillow) write barcodes (SVG,
PNG, JPEG files) and an index.html into tests/test_outputs/ of the checkout;
the directory's .gitignore ignores them. trace.py fails a run that leaves a
file in the checkout copy, so these tests could not run.

At the start of the session the plugin records every file of the rootdir
(the checkout). At its end it removes what is new in tests/test_outputs/ and
nothing else: new files and links (never the target of a link), then new
directories. Then the checkout must be as it was at the start. If anything
else changed (a file outside that directory, or one that was in it at the
start), the plugin raises OutputsChanged and the run fails: trace.py reports
the exception. trace.py loads the plugin from `plugins` in projects.toml;
for the tracer it is client code.
"""

import hashlib
import os
from pathlib import Path

import pytest

OUTPUT_DIR = "tests/test_outputs"  # relative to the rootdir
_BEFORE = pytest.StashKey[dict]()


class OutputsChanged(Exception):
    """The tests changed the checkout outside what the plugin removes."""


def snapshot(root):
    """{relative path: content} of everything below `root`: the SHA-256 of a
    file, the target of a symbolic link, or "dir". Links are not followed."""
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


def differences(before, after):
    """The changes from one snapshot to the other, as git status shows them."""
    lines = []
    for key in sorted(before.keys() | after.keys()):
        if key not in before:
            lines.append(f"?? {key}")
        elif key not in after:
            lines.append(f" D {key}")
        elif before[key] != after[key]:
            lines.append(f" M {key}")
    return lines


def clean(root, before):
    """Remove what is new below root/OUTPUT_DIR since the snapshot `before`;
    return the removed paths. Raise OutputsChanged if the checkout then
    differs from `before`."""
    root = Path(root)
    after = snapshot(root)
    new = sorted(
        key for key in after.keys() - before.keys() if key.startswith(OUTPUT_DIR + "/")
    )
    for key in reversed(new):  # the contents of a directory before it
        path = root / key
        if after[key] == "dir":
            path.rmdir()
        else:
            path.unlink()  # a file, or a link (not its target)
    left = differences(before, snapshot(root))
    if left:
        raise OutputsChanged(
            f"the tests changed the checkout {root} outside what "
            f"outputs_cleanup.py removes (new entries of {OUTPUT_DIR}/):\n"
            + "\n".join(left)
        )
    return new


def pytest_sessionstart(session):
    session.stash[_BEFORE] = snapshot(session.config.rootpath)


# Last, so that the other plugins (the tracer's test counts) finish first.
@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session):
    before = session.stash.get(_BEFORE, None)
    if before is not None:
        clean(session.config.rootpath, before)
