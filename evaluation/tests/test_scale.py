import hashlib
import importlib.util
import io
import json
import re
import signal
import stat
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

EVALUATION = Path(__file__).resolve().parents[1]
ROOT = EVALUATION.parent
SCALE = EVALUATION / "scale"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


projects = load("scale_projects", SCALE / "projects.py")
fetch = load("evaluation_fetch", EVALUATION / "container" / "fetch.py")
inputs_key = load("tools_inputs_key", ROOT / "tools" / "inputs_key.py")
measure = load("scale_measure", SCALE / "measure.py")
fakes = load("evaluation_fakes", EVALUATION / "tests" / "evaluation_fakes.py")
PINS = "evaluation/scale/projects.toml"
SHA256 = re.compile(r"[0-9a-f]{64}")
SCALE_SET_SIZE = 20


def test_the_pins_parse_and_every_archive_has_a_sha256():
    found = projects.load_projects()
    assert len(found) == SCALE_SET_SIZE
    for name, project in found.items():
        assert SHA256.fullmatch(project.sha256), name
        assert project.url.startswith("https://"), name
        assert project.kind in projects.KINDS, name
        assert project.licence, name
        assert project.packages, name


def test_the_inputs_key_covers_the_pins_and_their_loader():
    assert PINS in inputs_key.BUILD_FILES
    assert "evaluation/scale/projects.py" in inputs_key.BUILD_FILES


def test_the_inputs_key_changes_with_the_pins(tmp_path):
    for path in (*inputs_key.BUILD_FILES, inputs_key.COMPOSE):
        (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / path).write_bytes((ROOT / path).read_bytes())
    key = inputs_key.inputs_key(tmp_path)
    pins = tmp_path / PINS
    pins.write_text(pins.read_text().replace('version = "15.0.0"', 'version = "15"'))
    assert inputs_key.inputs_key(tmp_path) != key


def write_pins(directory, entry):
    directory.mkdir(parents=True, exist_ok=True)
    fields = {
        "version": "1.0",
        "kind": "pure wheel",
        "file": "demo-1.0-py3-none-any.whl",
        "url": "https://files.pythonhosted.org/packages/ab/demo-1.0-py3-none-any.whl",
        "sha256": "0" * 64,
        "licence": "MIT",
        "root": ".",
        "packages": ["demo"],
    } | entry
    lines = ["[demo]"]
    for key, value in fields.items():
        lines.append(f"{key} = {json.dumps(value)}")
    config = directory / "projects.toml"
    config.write_text("\n".join(lines) + "\n")
    return config


@pytest.mark.parametrize(
    ("entry", "message"),
    [
        ({"sha256": "ab" * 31}, "sha256 is not 64"),
        ({"sha256": "AB" * 32}, "sha256 is not 64"),
        ({"url": "http://example.org/demo.whl"}, "url is not https"),
        ({"kind": "sdist"}, "kind is one of"),
        ({"file": "demo-1.0.tar.gz"}, "ends with .whl"),
        ({"kind": "git archive", "file": "demo.tar.gz"}, "full commit id"),
        ({"root": ".."}, "is not inside"),
        ({"packages": []}, "packages is empty"),
        ({"extra": 1}, "the keys are"),
    ],
)
def test_a_pin_that_is_not_well_formed_is_refused(tmp_path, entry, message):
    config = write_pins(tmp_path, entry)
    with pytest.raises(ValueError, match=message):
        projects.load_projects(config)


WHEEL = {
    "demo/__init__.py": b"def f():\n    return 1\n",
    "demo/_speedups.so": b"\x7fELF",
    "demo/data.json": b"{}",
    "demo-1.0.dist-info/METADATA": b"Name: demo\n",
    "demo-1.0.dist-info/licenses/LICENSE": b"MIT\n",
    "demo-1.0.dist-info/licenses/vendored/NOTICE.txt": b"notice\n",
}
KEPT_OF_WHEEL = {
    "demo/__init__.py",
    "demo-1.0.dist-info/licenses/LICENSE",
    "demo-1.0.dist-info/licenses/vendored/NOTICE.txt",
}
COMMIT = "1" * 40
GIT_ARCHIVE = {
    f"demo-{COMMIT}/demo/__init__.py": b"x = 1\n",
    f"demo-{COMMIT}/demo/core.c": b"int x;\n",
    f"demo-{COMMIT}/LICENSE.txt": b"BSD\n",
    f"demo-{COMMIT}/COPYING": b"BSD\n",
    f"demo-{COMMIT}/README.md": b"demo\n",
    f"demo-{COMMIT}/docs/conf.py": b"project = 'demo'\n",
}
KEPT_OF_GIT_ARCHIVE = {"demo/__init__.py", "LICENSE.txt", "COPYING", "docs/conf.py"}


def make_wheel(members, links=()):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as wheel:
        for name, payload in members.items():
            wheel.writestr(name, payload)
        for name, target in links:
            info = zipfile.ZipInfo(name)
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            wheel.writestr(info, target)
    return buffer.getvalue()


def make_tar(members, links=()):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for name, payload in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            info.mode = 0o755
            tar.addfile(info, io.BytesIO(payload))
        for name, target in links:
            info = tarfile.TarInfo(name)
            info.type = tarfile.SYMTYPE
            info.linkname = target
            tar.addfile(info)
    return buffer.getvalue()


def files_under(directory):
    return {
        path.relative_to(directory).as_posix()
        for path in directory.rglob("*")
        if path.is_file() or path.is_symlink()
    }


@pytest.fixture
def served_body_by_url(monkeypatch):
    bodies = {}

    def urlopen(url, timeout):
        return io.BytesIO(bodies[url])

    monkeypatch.setattr(fetch.urllib.request, "urlopen", urlopen)
    return bodies


def pinned(tmp_path, served_body_by_url, data, entry):
    url = f"https://example.org/{entry['file']}"
    served_body_by_url[url] = data
    entry = {"url": url, "sha256": hashlib.sha256(data).hexdigest()} | entry
    return write_pins(tmp_path / "scale", entry)


def test_a_wheel_is_unpacked_to_its_python_sources_and_licences(
    tmp_path, served_body_by_url, capsys
):
    data = make_wheel(WHEEL)
    config = pinned(
        tmp_path, served_body_by_url, data, {"file": "demo-1.0-py3-none-any.whl"}
    )
    out = tmp_path / "inputs"
    assert fetch.fetch_scale(out, config) == 0
    assert (
        "demo: fetched demo-1.0-py3-none-any.whl at sha256:" in capsys.readouterr().out
    )
    assert files_under(out / "demo") == KEPT_OF_WHEEL
    assert (out / "demo" / "demo" / "__init__.py").read_bytes() == WHEEL[
        "demo/__init__.py"
    ]


def test_a_git_archive_is_unpacked_without_its_top_directory(
    tmp_path, served_body_by_url
):
    data = make_tar(GIT_ARCHIVE, links=[(f"demo-{COMMIT}/demo/link.py", "x.py")])
    config = pinned(
        tmp_path,
        served_body_by_url,
        data,
        {"kind": "git archive", "version": COMMIT, "file": f"demo-{COMMIT}.tar.gz"},
    )
    out = tmp_path / "inputs"
    assert fetch.fetch_scale(out, config) == 0
    assert files_under(out / "demo") == KEPT_OF_GIT_ARCHIVE
    mode = (out / "demo" / "demo" / "__init__.py").stat().st_mode
    assert stat.S_IMODE(mode) == fetch.SOURCE_FILE_MODE


@pytest.mark.parametrize(
    ("kind", "data", "message"),
    [
        ("pure wheel", make_wheel({"../evil.py": b""}), "not a path inside"),
        ("pure wheel", make_wheel({"/evil.py": b""}), "not a path inside"),
        ("pure wheel", make_wheel({}, links=[("demo/a.py", "/etc")]), "is a link"),
        ("pure wheel", b"not a zip", "File is not a zip file"),
        ("git archive", make_tar({"a/x.py": b"", "b/y.py": b""}), "not one top"),
        ("git archive", make_tar({"a/../../x.py": b""}), "not a path inside"),
    ],
)
def test_an_archive_that_is_not_well_formed_is_refused(
    tmp_path, served_body_by_url, capsys, kind, data, message
):
    file = "demo.tar.gz" if kind == "git archive" else "demo-1.0-py3-none-any.whl"
    entry = {"kind": kind, "file": file}
    if kind == "git archive":
        entry["version"] = COMMIT
    config = pinned(tmp_path, served_body_by_url, data, entry)
    out = tmp_path / "inputs"
    assert fetch.fetch_scale(out, config) == 1
    error = capsys.readouterr().err
    assert "demo: refused: " in error
    assert message in error
    assert not (out / "demo").exists()


def test_an_archive_of_another_hash_is_not_written(
    tmp_path, served_body_by_url, capsys
):
    data = make_wheel(WHEEL)
    config = pinned(
        tmp_path, served_body_by_url, data, {"file": "demo-1.0-py3-none-any.whl"}
    )
    served_body_by_url["https://example.org/demo-1.0-py3-none-any.whl"] = data + b"\0"
    out = tmp_path / "inputs"
    assert fetch.fetch_scale(out, config) == 1
    assert "has the SHA-256" in capsys.readouterr().err
    assert not (out / "demo").exists()


@pytest.mark.parametrize(
    ("record", "outcome"),
    [
        ({"status": "ok"}, "finished"),
        ({"status": "memory"}, "killed by the cap"),
        ({"status": "crash", "exit_status": -signal.SIGKILL}, "killed by the cap"),
        ({"status": "crash", "exit_status": 1}, "crash"),
        ({"status": "timeout"}, "timeout"),
    ],
)
def test_the_outcome_of_a_run(record, outcome):
    assert measure.outcome_of(record) == outcome


def committed_checkout(tmp_path):
    checkout = fakes.fake_checkout(tmp_path)
    fakes_git = load("evaluation_test_fetch", EVALUATION / "tests" / "test_fetch.py")
    git = fakes_git.git_without_user_configuration
    git(checkout, "init", "--quiet")
    git(checkout, "add", "--all")
    git(checkout, "commit", "--quiet", "--no-gpg-sign", "-m", "c")
    return checkout


def demo_project(tmp_path):
    config = write_pins(tmp_path / "scale", {})
    package = tmp_path / "scale" / "projects" / "demo" / "demo"
    package.mkdir(parents=True)
    (package.parent / "BEHAVIOUR").write_text("ok")
    (package / "__init__.py").write_text("x = 1\n")
    return projects.load_projects(config)["demo"]


def test_a_measurement_records_the_outcome_and_the_sha256_of_the_graph(tmp_path):
    checkout = committed_checkout(tmp_path)
    project = demo_project(tmp_path)
    out = tmp_path / "out"
    result = measure.measure(checkout, "this", project, out, 1024, 60, sys.executable)
    graph = out / "this" / "scale" / "demo.json"
    assert result["outcome"] == "finished"
    assert result["graph_sha256"] == hashlib.sha256(graph.read_bytes()).hexdigest()
    assert result["files"] == 1
    record = measure.record_path(out, "this", "demo")
    assert json.loads(record.read_text()) == result
    text = measure.comparison(result, result)
    assert "the call graphs are byte-identical" in text
    assert "| outcome | finished | finished |" in text


def test_a_checkout_with_changes_is_not_measured(tmp_path):
    checkout = committed_checkout(tmp_path)
    (checkout / "pycg" / "new.py").write_text("")
    with pytest.raises(measure.MeasureError, match="has changes"):
        measure.measure(
            checkout, "this", demo_project(tmp_path), tmp_path, 1024, 60, "python3"
        )


def result_of(outcome, graph_sha256, seconds):
    return {
        "package": "demo",
        "version": "1.0",
        "archive_sha256": "0" * 64,
        "tool": {"commit": "a" * 40},
        "python": "3.14.0",
        "memory_cap_mib": 4096,
        "files": 3,
        "outcome": outcome,
        "seconds": seconds,
        "wall_seconds": seconds,
        "peak_rss_mib": 100.0,
        "graph_sha256": graph_sha256,
        "run": {},
    }


def test_a_comparison_says_when_the_graphs_differ_or_a_run_did_not_finish():
    base = result_of("finished", "1" * 64, 2.0)
    assert "the call graphs differ" in measure.comparison(
        base, result_of("finished", "2" * 64, 1.0)
    )
    killed = measure.comparison(base, result_of("killed by the cap", None, None))
    assert "a run did not finish" in killed
    assert "| seconds | 2.0 | - | - |" in killed
    faster = measure.comparison(base, result_of("finished", "1" * 64, 1.0))
    assert "| seconds | 2.0 | 1.0 | -50.0% |" in faster


def test_records_of_two_packages_are_not_compared():
    other = result_of("finished", None, 1.0) | {"package": "other"}
    with pytest.raises(measure.MeasureError, match="different packages"):
        measure.comparison(result_of("finished", None, 1.0), other)
