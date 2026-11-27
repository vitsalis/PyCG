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


def test_a_package_without_a_licence_file_is_refused(
    tmp_path, served_body_by_url, capsys
):
    data = make_wheel({"demo/__init__.py": b""})
    config = pinned(
        tmp_path, served_body_by_url, data, {"file": "demo-1.0-py3-none-any.whl"}
    )
    out = tmp_path / "inputs"
    assert fetch.fetch_scale(out, config) == 1
    assert "demo: refused: no licence file" in capsys.readouterr().err
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


EVENTS = {"low": 0, "high": 0, "max": 3, "oom": 1, "oom_kill": 1}
KILLED = {"status": "crash", "exit_status": -signal.SIGKILL}


NOT_PORTED = {"status": "crash", "exit_status": 3}


@pytest.mark.parametrize(
    ("record", "flavour", "after", "outcome"),
    [
        ({"status": "ok"}, "new", EVENTS, "finished"),
        ({"status": "memory"}, "new", EVENTS, "killed by the cap"),
        (
            KILLED,
            "new",
            EVENTS | {"oom": 2, "oom_kill": 2},
            "killed: the container ran out of memory",
        ),
        (
            KILLED,
            "new",
            EVENTS | {"oom_kill": 2},
            "killed: the machine ran out of memory",
        ),
        (KILLED, "new", EVENTS, "killed by SIGKILL"),
        (KILLED, "rust", None, "killed by SIGKILL"),
        ({"status": "crash", "exit_status": 1}, "new", EVENTS, "crash"),
        ({"status": "timeout"}, "new", EVENTS, "timeout"),
        (NOT_PORTED, "rust", EVENTS, "not ported"),
        (NOT_PORTED, "new", EVENTS, "crash"),
        ({"status": "crash", "exit_status": 101}, "rust", EVENTS, "crash"),
    ],
)
def test_the_outcome_of_a_run(record, flavour, after, outcome):
    before = None if after is None else EVENTS
    assert measure.outcome_of(record, flavour, before, after) == outcome


def test_the_memory_events_of_the_container_are_read(tmp_path):
    path = tmp_path / "memory.events"
    path.write_text("low 0\nhigh 0\nmax 3\noom 1\noom_kill 1\noom_group_kill 0\n")
    assert measure.memory_events(path) == EVENTS | {"oom_group_kill": 0}
    assert measure.memory_events(tmp_path / "absent") is None


def committed_checkout(tmp_path, rust=False):
    checkout = fakes.fake_checkout(tmp_path, rust=rust)
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
    result = measure.measure(
        checkout, "this", project, out, 1024, 60, sys.executable, "new"
    )
    graph = out / "this" / "scale" / "demo.json"
    assert result["outcome"] == "finished"
    assert result["graph_sha256"] == hashlib.sha256(graph.read_bytes()).hexdigest()
    assert result["files"] == 1
    assert result["flavour"] == "new"
    record = measure.record_path(out, "this", "demo")
    assert json.loads(record.read_text()) == result
    text = measure.comparison(result, result)
    assert "the call graphs are byte-identical" in text
    assert "| outcome | finished | finished |" in text


def test_the_rust_flavour_measures_the_program_of_the_checkout(tmp_path):
    checkout = committed_checkout(tmp_path, rust=True)
    project = demo_project(tmp_path)
    out = tmp_path / "out"
    result = measure.measure(
        checkout, "rust", project, out, 1024, 60, sys.executable, "rust"
    )
    graph = out / "rust" / "scale" / "demo.json"
    assert result["outcome"] == "finished"
    assert result["flavour"] == "rust"
    assert result["graph_sha256"] == hashlib.sha256(graph.read_bytes()).hexdigest()
    seen = json.loads((project.directory / "seen.json").read_text())
    assert seen["arguments"][:2] == ["--package", str(project.root)]
    assert "flavour rust" in measure.report(result)


def test_a_rust_stop_keeps_its_error_line_in_the_record(tmp_path):
    checkout = committed_checkout(tmp_path, rust=True)
    project = demo_project(tmp_path)
    (project.directory / "BEHAVIOUR").write_text("not ported")
    result = measure.measure(
        checkout, "rust", project, tmp_path / "out", 1024, 60, sys.executable, "rust"
    )
    assert result["outcome"] == "not ported"
    assert result["graph_sha256"] is None
    assert result["run"]["error"] == "pycg: not ported: outside attributes"


def cgroup_limit(tmp_path, text):
    path = tmp_path / "memory.max"
    path.write_text(text + "\n")
    return path


def test_a_run_over_the_cap_is_recorded_as_killed_by_the_cap(tmp_path):
    checkout = committed_checkout(tmp_path)
    project = demo_project(tmp_path)
    (project.directory / "BEHAVIOUR").write_text("eat")
    container = cgroup_limit(tmp_path, str((200 + measure.RUNNER_HEADROOM_MIB) << 20))
    out = tmp_path / "out"

    result = measure.measure(
        checkout, "this", project, out, 200, 60, sys.executable, "new", container
    )

    assert result["outcome"] == "killed by the cap"
    assert result["run"]["status"] == "memory"
    assert result["graph_sha256"] is None
    record = measure.record_path(out, "this", "demo")
    assert json.loads(record.read_text()) == result


def test_a_run_that_the_machine_kills_is_not_killed_by_the_cap(tmp_path):
    checkout = committed_checkout(tmp_path)
    project = demo_project(tmp_path)
    (project.directory / "BEHAVIOUR").write_text("killed-by-the-machine")
    events = project.directory / "memory.events"
    events.write_text("low 0\nhigh 0\nmax 0\noom 0\noom_kill 0\n")
    meminfo = tmp_path / "meminfo"
    meminfo.write_text("MemTotal: 8104408 kB\nMemAvailable: 4723208 kB\n")
    out = tmp_path / "out"

    result = measure.measure(
        checkout,
        "this",
        project,
        out,
        1024,
        60,
        sys.executable,
        "new",
        tmp_path / "no-limit",
        events,
        meminfo,
    )

    assert result["outcome"] == "killed: the machine ran out of memory"
    assert result["run"]["exit_status"] == -signal.SIGKILL
    assert result["peak_rss_mib"] is not None
    assert result["graph_sha256"] is None
    assert result["memory_available_mib"] == 4612


@pytest.mark.parametrize("outcome", measure.OUTCOMES_KILLED_FROM_OUTSIDE)
@pytest.mark.parametrize("side", ["base", "this"])
def test_a_run_killed_from_outside_its_cap_is_not_compared(
    outcome, side, capsys, tmp_path
):
    finished = result_of("finished", "1" * 64, 2.0)
    killed = result_of(outcome, None, None)
    base, now = (killed, finished) if side == "base" else (finished, killed)
    with pytest.raises(
        measure.MeasureError, match=f"the {side} run .* is not a measurement"
    ):
        measure.comparison(base, now)
    paths = []
    for name, result in (("base", base), ("this", now)):
        paths.append(tmp_path / f"{name}.json")
        paths[-1].write_text(json.dumps(result))
    assert measure.main(["compare", *map(str, paths)]) == 1
    assert (
        f"the {side} run was killed ({outcome}) and is not a measurement"
        in capsys.readouterr().err
    )


def test_the_memory_that_the_machine_has_available_is_read(tmp_path):
    meminfo = tmp_path / "meminfo"
    meminfo.write_text(
        "MemTotal: 8104408 kB\nMemFree: 1 kB\nMemAvailable: 4723208 kB\n"
        "HugePages_Total: 0\n"
    )
    assert measure.memory_available_mib(meminfo) == 4612
    assert measure.memory_available_mib(tmp_path / "absent") is None


@pytest.mark.parametrize("limit_mib", [1024, 1024 + measure.RUNNER_HEADROOM_MIB - 1])
def test_a_container_without_headroom_above_the_cap_is_refused(tmp_path, limit_mib):
    container = cgroup_limit(tmp_path, str(limit_mib << 20))
    with pytest.raises(
        measure.MeasureError, match=f"needs {measure.RUNNER_HEADROOM_MIB} MiB"
    ):
        measure.measure(
            tmp_path, "this", None, tmp_path, 1024, 60, "python3", "new", container
        )


@pytest.mark.parametrize("text", ["max", None])
def test_a_container_without_a_memory_limit_needs_no_headroom(tmp_path, text):
    container = (
        tmp_path / "memory.max" if text is None else cgroup_limit(tmp_path, text)
    )
    measure.check_headroom(1024, container)


def test_the_container_has_the_cap_and_the_headroom_of_the_runner(capsys):
    assert measure.main(["container-mib", "4096"]) == 0
    assert capsys.readouterr().out == f"{4096 + measure.RUNNER_HEADROOM_MIB}\n"


def test_a_checkout_with_changes_is_not_measured(tmp_path):
    checkout = committed_checkout(tmp_path)
    (checkout / "pycg" / "new.py").write_text("")
    with pytest.raises(measure.MeasureError, match="has changes"):
        measure.measure(
            checkout,
            "this",
            demo_project(tmp_path),
            tmp_path,
            1024,
            60,
            "python3",
            "new",
        )


def result_of(outcome, graph_sha256, seconds):
    return {
        "package": "demo",
        "version": "1.0",
        "archive_sha256": "0" * 64,
        "tool": {"commit": "a" * 40},
        "flavour": "new",
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


def write_result(directory, results):
    for result in results:
        path = measure.record_path(directory, "", result["package"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result))
    return directory


def test_a_summary_has_one_row_per_package_against_the_oracle(tmp_path, capsys):
    finished = result_of("finished", "1" * 64, 1.0) | {"package": "fast"}
    stopped = result_of("crash", None, 0.5) | {
        "package": "stopped",
        "run": {"error": "pycg: not ported: outside attributes"},
    }
    alone = result_of("finished", "2" * 64, 3.0) | {"package": "alone"}
    rust = write_result(tmp_path / "rust", [finished, stopped, alone])
    oracle_fast = result_of("finished", "1" * 64, 4.0) | {
        "package": "fast",
        "peak_rss_mib": 400.0,
    }
    oracle_stopped = result_of("finished", "3" * 64, 2.0) | {"package": "stopped"}
    oracle = write_result(tmp_path / "oracle", [oracle_fast, oracle_stopped])

    assert measure.main(["summary", str(rust), "--oracle", str(oracle)]) == 0

    assert capsys.readouterr().out.splitlines() == [
        "| package | outcome | seconds | peak MiB | oracle outcome | oracle seconds"
        " | time ratio | oracle peak MiB | memory ratio | graphs | error |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
        "| alone | finished | 3.0 | 100.0 | not measured | - | - | - | - | - |  |",
        "| fast | finished | 1.0 | 100.0 | finished | 4.0 | 0.250 | 400.0 | 0.250"
        " | identical |  |",
        "| stopped | crash | 0.5 | 100.0 | finished | 2.0 | 0.250 | 100.0 | 1.000"
        " | - | pycg: not ported: outside attributes |",
    ]


def test_a_summary_without_an_oracle_lists_the_runs(tmp_path):
    rust = write_result(
        tmp_path / "rust", [result_of("timeout", None, None) | {"package": "slow"}]
    )
    assert measure.summary(rust).splitlines() == [
        "| package | outcome | seconds | peak MiB | error |",
        "|---|---|---|---|---|",
        "| slow | timeout | - | 100.0 |  |",
    ]


def test_a_summary_of_a_result_without_records_is_refused(tmp_path):
    with pytest.raises(measure.MeasureError, match="no records"):
        measure.summary(tmp_path)
