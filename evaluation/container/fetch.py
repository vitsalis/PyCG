#!/usr/bin/env python3
import hashlib
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

EVALUATION = Path(__file__).resolve().parents[1]
COMMIT = re.compile(r"[0-9a-f]{40}")
GIT_PROTOCOLS_ALLOWED = ("https",)
GIT_MODE_SUBMODULE = "160000"
GIT_MODE_SYMBOLIC_LINK = "120000"
GIT_MODE_EXECUTABLE = "100755"
LICENCE_NAME_PREFIXES = ("LICENSE", "LICENCE", "COPYING", "NOTICE")
SOURCE_SUFFIX = ".py"
SOURCE_FILE_MODE = 0o644
USAGE = """usage: python3 -I fetch.py macro DESTINATION
       python3 -I fetch.py scale DESTINATION

Fetches each project of macro-benchmark/projects.toml (macro) or of
scale/projects.toml (scale) into DESTINATION/<name>, checked against its pin
(evaluation/README.md, "The inputs image")."""


def _load(name, path):
    import importlib.util

    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FetchError(Exception):
    pass


def git(*args):
    settings = [
        "core.hooksPath=/dev/null",
        "protocol.allow=never",
        *(f"protocol.{name}.allow=always" for name in GIT_PROTOCOLS_ALLOWED),
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
    if not url.startswith(tuple(f"{name}://" for name in GIT_PROTOCOLS_ALLOWED)):
        raise FetchError(f"{url}: not a URL of {', '.join(GIT_PROTOCOLS_ALLOWED)}")
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
    listing = git("-C", str(repository), "ls-tree", "-r", "-z", "--full-tree", commit)
    directory.mkdir()
    for item in filter(None, listing.split(b"\0")):
        meta, _, name = item.partition(b"\t")
        mode, _, oid = meta.decode().split()
        if mode == GIT_MODE_SUBMODULE:
            continue
        data = git("-C", str(repository), "cat-file", "blob", oid)
        target = directory / os.fsdecode(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        if mode == GIT_MODE_SYMBOLIC_LINK:
            os.symlink(data, target)
        else:
            target.write_bytes(data)
            target.chmod(0o755 if mode == GIT_MODE_EXECUTABLE else 0o644)


def fetch_tree(url, commit, destination):
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


def download_https(url):
    if not url.startswith("https://"):
        raise FetchError(f"{url}: not https")
    with urllib.request.urlopen(url, timeout=60) as response:
        return response.read()


def unpack_sdist(archive, destination):
    archive, destination = Path(archive), Path(destination)
    top_directory = archive.name.removesuffix(".tar.gz")

    def strip_top_directory(member, path):
        name = member.name.rstrip("/")
        if name == top_directory:
            return None
        if not name.startswith(top_directory + "/"):
            raise ValueError(
                f"{archive.name}: {member.name} is not under {top_directory}/"
            )
        relative_name = name[len(top_directory) + 1 :]
        return tarfile.data_filter(member.replace(name=relative_name), path)

    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:gz") as tar:
        tar.extractall(destination, filter=strip_top_directory)


def fetch_archive(url, sha256, file, unpack, destination):
    destination = Path(destination)
    if destination.exists():
        raise FetchError(f"{destination} is there already")
    data = download_https(url)
    digest = hashlib.sha256(data).hexdigest()
    if digest != sha256:
        raise FetchError(f"{url} has the SHA-256 {digest}, not {sha256}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    scratch = Path(
        tempfile.mkdtemp(prefix=f".{destination.name}-", dir=destination.parent)
    )
    try:
        (scratch / file).write_bytes(data)
        unpack(scratch / file, scratch / "tree")
        os.rename(scratch / "tree", destination)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    return f"fetched {file} at sha256:{sha256}"


def fetch_sdist(sdist, destination):
    return fetch_archive(sdist.url, sdist.sha256, sdist.file, unpack_sdist, destination)


def is_kept(parts):
    if parts[-1].endswith(SOURCE_SUFFIX):
        return True
    return any(part.upper().startswith(LICENCE_NAME_PREFIXES) for part in parts)


def member_parts(archive, name):
    path = PurePosixPath(name)
    if path.is_absolute() or "\\" in name or ".." in path.parts or not path.parts:
        raise FetchError(f"{archive.name}: {name} is not a path inside the archive")
    return path.parts


def unpack_wheel(archive, destination):
    archive, destination = Path(archive), Path(destination)
    destination.mkdir(parents=True)
    with zipfile.ZipFile(archive) as wheel:
        for member in wheel.infolist():
            if member.is_dir():
                continue
            parts = member_parts(archive, member.filename)
            if stat.S_ISLNK(member.external_attr >> 16):
                raise FetchError(f"{archive.name}: {member.filename} is a link")
            if not is_kept(parts):
                continue
            target = destination.joinpath(*parts)
            if target.exists():
                raise FetchError(f"{archive.name}: {member.filename} is there twice")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(wheel.read(member))
            target.chmod(SOURCE_FILE_MODE)


def unpack_git_archive(archive, destination):
    archive, destination = Path(archive), Path(destination)
    destination.mkdir(parents=True)
    with tarfile.open(archive, "r:gz") as tar:
        tops = {member_parts(archive, member.name)[0] for member in tar.getmembers()}
        if len(tops) != 1:
            raise FetchError(f"{archive.name}: not one top directory: {sorted(tops)}")
        (top,) = tops

        def keep_sources(member, path):
            parts = member_parts(archive, member.name)[1:]
            if not parts or not member.isfile() or not is_kept(parts):
                return None
            relative = PurePosixPath(*parts).as_posix()
            kept = member.replace(name=relative, mode=SOURCE_FILE_MODE, deep=False)
            return tarfile.data_filter(kept, path)

        tar.extractall(destination, filter=keep_sources)


UNPACK_BY_KIND = {
    "pure wheel": unpack_wheel,
    "platform wheel": unpack_wheel,
    "git archive": unpack_git_archive,
}


def fetch_macro(destination, config=None):
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


def fetch_scale(destination, config=None):
    projects = _load("scale_projects", EVALUATION / "scale" / "projects.py")
    found = projects.load_projects(config or projects.CONFIG_PATH)
    refused = 0
    for name, project in sorted(found.items()):
        try:
            done = fetch_archive(
                project.url,
                project.sha256,
                project.file,
                UNPACK_BY_KIND[project.kind],
                Path(destination) / name,
            )
        except (
            FetchError,
            ValueError,
            OSError,
            tarfile.TarError,
            zipfile.BadZipFile,
        ) as error:
            print(f"{name}: refused: {error}", file=sys.stderr)
            refused += 1
            continue
        print(f"{name}: {done}")
    return refused


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    commands = {"macro": fetch_macro, "scale": fetch_scale}
    if len(argv) != 2 or argv[0] not in commands:
        print(USAGE, file=sys.stderr)
        return 2
    command, destination = argv
    try:
        return 1 if commands[command](destination) else 0
    except (FetchError, ValueError, OSError) as error:
        print(f"fetch.py {command}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
