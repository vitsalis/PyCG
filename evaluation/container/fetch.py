#!/usr/bin/env python3
"""The downloads of the macro-benchmark's projects: a step of the build of
the inputs image (evaluation/container/Dockerfile.inputs), the only place
where git runs on third-party content.

    python3 -I fetch.py macro DESTINATION   # each project of projects.toml

Each source goes to DESTINATION/<name>.

A git source is fetched at its one pinned commit (a bare repository, `git
fetch --depth 1 URL COMMIT`, https only, no hooks, no submodules, every
object checked by git) and written as the plain files of the commit's tree,
without .git: the bytes and modes of its blobs, a link as a link, a nested
submodule not fetched. No checkout runs, so no attribute, filter or hook of
the fetched repository applies. An sdist is downloaded, checked against its
SHA-256 and unpacked with tarfile's "data" filter; the archive is not kept.
Nothing fetched is run. A source that is not its pin is not written, and
the command fails, so the build fails.
"""

import hashlib
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

EVALUATION = Path(__file__).resolve().parents[1]
COMMIT = re.compile(r"[0-9a-f]{40}")
PROTOCOLS = ("https",)  # the tests add "file"
SUBMODULE = "160000"  # the mode of a nested submodule in a tree


def _load(name, path):
    import importlib.util

    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FetchError(Exception):
    """A source that was not fetched or is not its pin."""


def git(*args):
    """Run git with no configuration of the user or the system, no hooks,
    only the protocols of PROTOCOLS, and every received object checked;
    return its output."""
    settings = [
        "core.hooksPath=/dev/null",
        "protocol.allow=never",
        *(f"protocol.{name}.allow=always" for name in PROTOCOLS),
        "transfer.fsckObjects=true",
        "fetch.recurseSubmodules=false",
    ]
    environment = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": tempfile.gettempdir(),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
    }
    command = ["git", *(part for s in settings for part in ("-c", s)), *args]
    done = subprocess.run(command, env=environment, capture_output=True)
    if done.returncode:
        message = done.stderr.decode("utf-8", "replace").strip()[-2000:]
        raise FetchError(f"git failed: {message}")
    return done.stdout


def fetch_commit(url, commit):
    """Fetch `commit` of `url` into a new bare repository; return the
    repository. The caller removes the repository's parent."""
    if not url.startswith(tuple(f"{name}://" for name in PROTOCOLS)):
        raise FetchError(f"{url}: not a URL of {', '.join(PROTOCOLS)}")
    if not COMMIT.fullmatch(commit):
        raise FetchError(f"{commit}: not a full commit id")
    repository = Path(tempfile.mkdtemp(prefix="fetch-")) / "repo.git"
    try:
        git("init", "--quiet", "--bare", "--template=", str(repository))
        git(
            *("-C", str(repository), "fetch", "--quiet", "--depth=1", "--no-tags"),
            *("--no-recurse-submodules", "--", url, commit),
        )
        fetched = git("-C", str(repository), "rev-parse", "FETCH_HEAD^{commit}")
    except FetchError:
        shutil.rmtree(repository.parent, ignore_errors=True)
        raise
    fetched = fetched.decode().strip()
    if fetched != commit:
        shutil.rmtree(repository.parent, ignore_errors=True)
        raise FetchError(f"{url}: fetched {fetched}, not the commit {commit}")
    return repository


def write_tree(repository, commit, directory):
    """Write the files of the tree of `commit` into the new `directory`."""
    listing = git("-C", str(repository), "ls-tree", "-r", "-z", "--full-tree", commit)
    directory.mkdir()
    for item in filter(None, listing.split(b"\0")):
        meta, _, name = item.partition(b"\t")
        mode, _, oid = meta.decode().split()
        if mode == SUBMODULE:
            continue
        data = git("-C", str(repository), "cat-file", "blob", oid)
        target = directory / os.fsdecode(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        if mode == "120000":
            os.symlink(data, target)
        else:
            target.write_bytes(data)
            target.chmod(0o755 if mode == "100755" else 0o644)


def fetch_tree(url, commit, destination):
    """Fetch the tree of `commit` of `url` into the new directory
    `destination`; return what was done. FetchError, and nothing written,
    if the commit cannot be fetched."""
    destination = Path(destination)
    if destination.exists():
        raise FetchError(f"{destination} is there already")
    repository = fetch_commit(url, commit)
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        scratch = Path(
            tempfile.mkdtemp(prefix=f".{destination.name}-", dir=destination.parent)
        )
        try:
            write_tree(repository, commit, scratch / "tree")
            os.rename(scratch / "tree", destination)
        finally:
            shutil.rmtree(scratch, ignore_errors=True)
    finally:
        shutil.rmtree(repository.parent, ignore_errors=True)
    return f"fetched at {commit}"


def download(url):
    """The bytes at an https URL."""
    if not url.startswith("https://"):
        raise FetchError(f"{url}: not https")
    with urllib.request.urlopen(url, timeout=60) as response:
        return response.read()


def unpack_sdist(archive, destination):
    """Unpack the sdist `archive` into `destination` (made if missing)
    without its top directory, with tarfile's "data" filter (no absolute
    path, no `..`, no link out, no device); every member must be under the
    top directory that the file name names."""
    archive, destination = Path(archive), Path(destination)
    top = archive.name.removesuffix(".tar.gz")

    def strip(member, path):
        name = member.name.rstrip("/")
        if name == top:
            return None
        if not name.startswith(top + "/"):
            raise ValueError(f"{archive.name}: {member.name} is not under {top}/")
        return tarfile.data_filter(member.replace(name=name[len(top) + 1 :]), path)

    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:gz") as tar:
        tar.extractall(destination, filter=strip)


def fetch_sdist(sdist, destination):
    """Download `sdist` (projects.Sdist), check its SHA-256 and unpack it
    into the new directory `destination`; return what was done. The
    archive is not kept."""
    destination = Path(destination)
    if destination.exists():
        raise FetchError(f"{destination} is there already")
    data = download(sdist.url)
    digest = hashlib.sha256(data).hexdigest()
    if digest != sdist.sha256:
        raise FetchError(f"{sdist.url} has the SHA-256 {digest}, not {sdist.sha256}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    scratch = Path(
        tempfile.mkdtemp(prefix=f".{destination.name}-", dir=destination.parent)
    )
    try:
        (scratch / sdist.file).write_bytes(data)
        unpack_sdist(scratch / sdist.file, scratch / "tree")
        os.rename(scratch / "tree", destination)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    return f"fetched {sdist.file} at sha256:{sdist.sha256}"


def fetch_macro(destination, config=None):
    """Fetch each project of projects.toml into DESTINATION/<name>; return
    the number refused."""
    projects = _load("macro_projects", EVALUATION / "macro-benchmark" / "projects.py")
    found = projects.load_projects(config or projects.CONFIG_PATH)
    refused = 0
    for name, project in sorted(found.items()):
        try:
            if project.sdist is not None:
                done = fetch_sdist(project.sdist, Path(destination) / name)
            elif project.repository and project.commit:
                done = fetch_tree(
                    project.repository, project.commit, Path(destination) / name
                )
            else:
                raise FetchError("projects.toml gives no repository and commit")
        except (FetchError, ValueError, OSError, tarfile.TarError) as error:
            print(f"{name}: refused: {error}", file=sys.stderr)
            refused += 1
            continue
        print(f"{name}: {done}")
    return refused


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    commands = {"macro": fetch_macro}
    if len(argv) != 2 or argv[0] not in commands:
        print(__doc__, file=sys.stderr)
        return 2
    command, destination = argv
    try:
        return 1 if commands[command](destination) else 0
    except (FetchError, ValueError, OSError) as error:
        print(f"fetch.py {command}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
