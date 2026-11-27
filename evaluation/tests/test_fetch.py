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
SUBMODULE_COMMIT = "5" * 40
FILES_AS_COMMITTED = {
    "LICENSE": b"MIT\n",
    "pkg/__init__.py": b"x = 'released'\n",
    "pkg/run.sh": ("exec", b"#!/bin/sh\n"),
    "pkg/link.py": ("link", "__init__.py"),
    "café/über.py": b"accents = 1\n",
    ".gitattributes": b"*.py text eol=crlf filter=upper\n",
}


def git_without_user_configuration(directory, *args):
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


def make_repository(root, content_by_path, submodule_commit_by_path=()):
    root.mkdir(parents=True)
    git_without_user_configuration(root, "init", "--quiet", "--initial-branch=main")
    for path, content in content_by_path.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        kind, data = content if isinstance(content, tuple) else ("file", content)
        if kind == "link":
            target.symlink_to(data)
        else:
            target.write_bytes(data)
            target.chmod(0o755 if kind == "exec" else 0o644)
    git_without_user_configuration(root, "add", "--all")
    for path, oid in dict(submodule_commit_by_path).items():
        git_without_user_configuration(
            root, "update-index", "--add", "--cacheinfo", f"160000,{oid},{path}"
        )
    git_without_user_configuration(
        root, "commit", "--quiet", "--no-gpg-sign", "--allow-empty", "-m", "c"
    )
    return f"file://{root}", git_without_user_configuration(root, "rev-parse", "HEAD")


@pytest.fixture
def source(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch, "GIT_PROTOCOLS_ALLOWED", ("file",))
    return make_repository(
        tmp_path / "source", FILES_AS_COMMITTED, {"vendor/sub": SUBMODULE_COMMIT}
    )


def write_benchmark_with_project_demo(root, entry):
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
    config = write_benchmark_with_project_demo(
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
    return write_benchmark_with_project_demo(
        root,
        f"""
        sdist = "demo-1.0.tar.gz"
        sdist_url = "{SDIST_URL}"
        sdist_sha256 = "{hashlib.sha256(data).hexdigest()}"
        packages = ["demo"]
        """,
    )


@pytest.fixture
def served_body_by_url(monkeypatch):
    bodies = {}

    def urlopen(url, timeout):
        return io.BytesIO(bodies[url])

    monkeypatch.setattr(fetch.urllib.request, "urlopen", urlopen)
    return bodies


def test_an_sdist_of_another_hash_is_not_written_and_the_command_fails(
    tmp_path, served_body_by_url, capsys, monkeypatch
):
    data = make_tar(SDIST)
    served_body_by_url[SDIST_URL] = data + b"\0"
    config = sdist_config(tmp_path / "bench", data)
    monkeypatch.setattr(projects, "CONFIG_PATH", config)
    monkeypatch.setattr(fetch, "_load", lambda name, path: projects)
    out = tmp_path / "inputs"
    assert fetch.main(["macro", str(out)]) == 1
    assert "demo: refused: " in capsys.readouterr().err
    assert not (out / "demo").exists()


def test_the_benchmark_reads_the_sources_of_the_image_where_it_has_them(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(projects, "SOURCES", tmp_path / "inputs" / "projects")
    found = projects.load_projects()
    beside = projects.BENCHMARK_DIR / "projects"
    assert {p.directory for p in found.values()} == {
        (beside / name).resolve() for name in found
    }
    projects.SOURCES.mkdir(parents=True)
    found = projects.load_projects()
    assert {p.directory.parent for p in found.values()} == {projects.SOURCES.resolve()}
    config = write_benchmark_with_project_demo(
        tmp_path / "bench", 'packages = ["pkg"]\n'
    )
    project_of_other_benchmark = projects.load_projects(config)["demo"]
    assert (
        project_of_other_benchmark.directory
        == (tmp_path / "bench" / "projects" / "demo").resolve()
    )


NOTICE_URL = "https://files.pythonhosted.org/packages/cd/demo-1.0.tar.gz"
NOTICE_RELEASE = {
    "demo-1.0/LICENSE": b"MIT License of the release\n",
    "demo-1.0/demo/__init__.py": b"",
}


def notice_of(data, member="demo-1.0/LICENSE"):
    return {
        "url": NOTICE_URL,
        "sha256": hashlib.sha256(data).hexdigest(),
        "member": member,
    }


def source_without_licence(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch, "GIT_PROTOCOLS_ALLOWED", ("file",))
    files = {k: v for k, v in FILES_AS_COMMITTED.items() if k != "LICENSE"}
    url, commit = make_repository(tmp_path / "unlicensed", files)
    return write_benchmark_with_project_demo(
        tmp_path / "bench",
        f'repository = "{url}"\ncommit = "{commit}"\npackages = ["pkg"]\n',
    )


@needs_git
def test_a_source_without_a_licence_file_is_refused(tmp_path, monkeypatch, capsys):
    config = source_without_licence(tmp_path, monkeypatch)
    monkeypatch.setattr(fetch, "LICENCE_NOTICES", {})
    out = tmp_path / "inputs"
    assert fetch.fetch_macro(out, config) == 1
    assert "demo: refused: no licence file" in capsys.readouterr().err
    assert not (out / "demo").exists()


@needs_git
def test_the_licence_file_of_the_release_is_added_beside_the_source(
    tmp_path, monkeypatch, served_body_by_url, capsys
):
    config = source_without_licence(tmp_path, monkeypatch)
    data = make_tar(NOTICE_RELEASE)
    served_body_by_url[NOTICE_URL] = data
    monkeypatch.setattr(fetch, "LICENCE_NOTICES", {"demo": notice_of(data)})
    out = tmp_path / "inputs"
    assert fetch.fetch_macro(out, config) == 0
    assert "; added LICENSE of demo-1.0.tar.gz" in capsys.readouterr().out
    licence = out / "demo" / "LICENSE"
    assert licence.read_bytes() == NOTICE_RELEASE["demo-1.0/LICENSE"]
    assert not (out / "demo" / "demo").exists()


@needs_git
@pytest.mark.parametrize(
    ("served", "member", "message"),
    [
        (b"\0", "demo-1.0/LICENSE", "has the SHA-256"),
        (b"", "demo-1.0/COPYING", "has no demo-1.0/COPYING"),
    ],
)
def test_a_licence_notice_that_is_not_its_pin_is_refused(
    tmp_path, monkeypatch, served_body_by_url, capsys, served, member, message
):
    config = source_without_licence(tmp_path, monkeypatch)
    data = make_tar(NOTICE_RELEASE)
    served_body_by_url[NOTICE_URL] = data + served
    monkeypatch.setattr(fetch, "LICENCE_NOTICES", {"demo": notice_of(data, member)})
    out = tmp_path / "inputs"
    assert fetch.fetch_macro(out, config) == 1
    assert message in capsys.readouterr().err
    assert not (out / "demo").exists()


def test_every_licence_notice_names_a_project_of_the_benchmark():
    assert set(fetch.LICENCE_NOTICES) <= set(projects.load_projects())
