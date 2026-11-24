"""Tests of the fetch program (evaluation/container/fetch.py, a step of the
build of the inputs image) in-process on local git repositories that the
tests make (our own data, never third-party code), and of where the
sources of the projects are read (macro-benchmark/projects.py sources).
Nothing here needs Docker or the network."""

import hashlib
import importlib.util
import io
import os
import shutil
import subprocess
import tarfile
from pathlib import Path
from textwrap import dedent

import pytest

EVALUATION = Path(__file__).resolve().parents[1]
CONTAINER = EVALUATION / "container"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fetch = load("evaluation_fetch", CONTAINER / "fetch.py")
projects = load("macro_projects", EVALUATION / "macro-benchmark" / "projects.py")
needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="needs git")
SUBMODULE = "5" * 40
FILES = {
    # The blobs as committed: no attribute, filter or line-ending conversion.
    "pkg/__init__.py": b"x = 'released'\n",
    "pkg/run.sh": ("exec", b"#!/bin/sh\n"),
    "pkg/link.py": ("link", "__init__.py"),
    "café/über.py": b"accents = 1\n",
    ".gitattributes": b"*.py text eol=crlf filter=upper\n",
}


def git(directory, *args):
    """Run git in `directory` with no configuration of the user or system."""
    environment = {
        "PATH": os.environ["PATH"],
        "HOME": str(directory),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_AUTHOR_NAME": "A",
        "GIT_AUTHOR_EMAIL": "a@example.org",
        "GIT_COMMITTER_NAME": "C",
        "GIT_COMMITTER_EMAIL": "c@example.org",
        "GIT_AUTHOR_DATE": "2026-11-14T00:00:00Z",
        "GIT_COMMITTER_DATE": "2026-11-14T00:00:00Z",
    }
    done = subprocess.run(
        ["git", *args], cwd=directory, env=environment, check=True, capture_output=True
    )
    return done.stdout.decode().strip()


def make_repository(root, files, submodules=()):
    """A git repository at `root` with one commit of `files` ({path: bytes,
    or ("exec", bytes), or ("link", target)}) and of nested submodule
    entries `submodules` ({path: commit id}); return (file URL, commit)."""
    root.mkdir(parents=True)
    git(root, "init", "--quiet", "--initial-branch=main")
    for path, content in files.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        kind, data = content if isinstance(content, tuple) else ("file", content)
        if kind == "link":
            target.symlink_to(data)
        else:
            target.write_bytes(data)
            target.chmod(0o755 if kind == "exec" else 0o644)
    git(root, "add", "--all")
    for path, oid in dict(submodules).items():
        git(root, "update-index", "--add", "--cacheinfo", f"160000,{oid},{path}")
    git(root, "commit", "--quiet", "--no-gpg-sign", "--allow-empty", "-m", "c")
    return f"file://{root}", git(root, "rev-parse", "HEAD")


@pytest.fixture
def source(tmp_path, monkeypatch):
    """A local repository with FILES and a nested submodule; (url, commit).
    The fetch program may read file:// URLs (and no other non-https one)."""
    monkeypatch.setattr(fetch, "PROTOCOLS", ("file",))
    return make_repository(tmp_path / "source", FILES, {"vendor/sub": SUBMODULE})


def benchmark(root, entry):
    """A benchmark directory whose projects.toml has the project demo."""
    root.mkdir(parents=True)
    (root / "projects.toml").write_text(
        "[demo]\n" + dedent(entry) + 'exclude = []\ndependencies = []\nroot = "."\n'
    )
    return root / "projects.toml"


@needs_git
def test_a_commit_that_the_repository_lacks_is_not_fetched(tmp_path, source):
    url, _ = source
    with pytest.raises(fetch.FetchError, match="git failed"):
        fetch.fetch_tree(url, "0" * 40, tmp_path / "demo")
    assert not (tmp_path / "demo").exists()


def test_only_a_full_commit_id_is_fetched(tmp_path):
    with pytest.raises(fetch.FetchError, match="not a full commit id"):
        fetch.fetch_tree("https://x/y", "8871b86", tmp_path / "demo")


@needs_git
def test_the_projects_are_fetched_into_the_destination(tmp_path, source, capsys):
    url, commit = source
    config = benchmark(
        tmp_path / "bench",
        f'repository = "{url}"\ncommit = "{commit}"\npackages = ["pkg"]\n',
    )
    out = tmp_path / "inputs"
    assert fetch.fetch_macro(out, config) == 0
    assert f"demo: fetched at {commit}" in capsys.readouterr().out
    assert (out / "demo" / "pkg" / "__init__.py").is_file()
    assert not (tmp_path / "bench" / "projects").exists()


SDIST = {
    "demo-1.0/PKG-INFO": b"Name: demo\n",
    "demo-1.0/demo/__init__.py": b"def f():\n    return 1\n",
}
SDIST_URL = "https://files.pythonhosted.org/packages/ab/demo-1.0.tar.gz"


def make_tar(members):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for name, payload in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            tar.addfile(info, io.BytesIO(payload))
    return buffer.getvalue()


def sdist_config(root, data):
    return benchmark(
        root,
        f"""
        sdist = "demo-1.0.tar.gz"
        sdist_url = "{SDIST_URL}"
        sdist_sha256 = "{hashlib.sha256(data).hexdigest()}"
        packages = ["demo"]
        """,
    )


@pytest.fixture
def served(monkeypatch):
    """The program's downloads: {url: body}."""
    bodies = {}

    def urlopen(url, timeout):
        return io.BytesIO(bodies[url])

    monkeypatch.setattr(fetch.urllib.request, "urlopen", urlopen)
    return bodies


def test_an_sdist_of_another_hash_is_not_written_and_the_command_fails(
    tmp_path, served, capsys, monkeypatch
):
    data = make_tar(SDIST)
    served[SDIST_URL] = data + b"\0"
    config = sdist_config(tmp_path / "bench", data)
    monkeypatch.setattr(projects, "CONFIG_PATH", config)
    monkeypatch.setattr(fetch, "_load", lambda name, path: projects)
    out = tmp_path / "inputs"
    assert fetch.main(["macro", str(out)]) == 1
    assert "demo: refused: " in capsys.readouterr().err
    assert not (out / "demo").exists()


# Where the sources are read


def test_the_benchmark_reads_the_sources_of_the_image_where_it_has_them(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(projects, "SOURCES", tmp_path / "inputs" / "projects")
    found = projects.load_projects()
    beside = projects.BENCHMARK_DIR / "projects"
    assert {p.directory.parent for p in found.values()} == {beside.resolve()}
    projects.SOURCES.mkdir(parents=True)
    found = projects.load_projects()
    assert {p.directory.parent for p in found.values()} == {projects.SOURCES.resolve()}
    # Any other projects.toml has its sources beside it.
    config = benchmark(tmp_path / "bench", 'packages = ["pkg"]\n')
    other = projects.load_projects(config)["demo"]
    assert other.directory == (tmp_path / "bench" / "projects" / "demo").resolve()
