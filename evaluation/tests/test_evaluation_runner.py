import importlib.util
import json
import sys
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "evaluation_fakes", Path(__file__).resolve().parent / "evaluation_fakes.py"
)
fakes = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fakes)


process_ends_within_five_seconds = fakes.process_ends_within_five_seconds
run, project, tool, fake_checkout = (
    fakes.run,
    fakes.project,
    fakes.tool,
    fakes.fake_checkout,
)


def test_a_crash_is_recorded_with_the_last_error_line_and_the_exit_status(tmp_path):
    job = project(tmp_path, "crash")
    graph_path = tmp_path / "graph.json"
    graph_of_earlier_run = "{}"
    graph_path.write_text(graph_of_earlier_run)
    record = run.run_job(tool(tmp_path), job, graph_path, timeout_seconds=60)
    assert record["status"] == "crash"
    assert record["error"] == "pycg: internal error at crates/a.rs:1:2: a message"
    assert record["where"] == "target/release/pycg (exit 101)"
    assert record["exit_status"] == 101
    assert not graph_path.exists()


def test_the_program_of_the_checkout_runs_isolated_and_its_document_is_read(tmp_path):
    job, fake = project(tmp_path, "ok"), tool(tmp_path)
    graph_path = tmp_path / "out" / "graph.json"

    record = run.run_job(fake, job, graph_path, timeout_seconds=60)

    assert record["status"] == "ok"
    assert record["files"] == 1 and record["peak_rss_mib"] > 0
    assert json.loads(graph_path.read_text()) == {
        "main": ["main.a", "main.b", "os.getcwd"],
        "main.a": [],
        "main.b": [],
        "os.getcwd": [],
    }
    seen = json.loads((job.package / "seen.json").read_text())
    assert seen["arguments"][:2] == ["--package", str(job.package.resolve())]
    assert seen["arguments"][2:-2] == [str(job.entry_points[0].resolve())]
    assert seen["arguments"][-2] == "-o"
    assert seen["found"] == [True]
    assert set(seen["environment"]) - {"LC_CTYPE"} == set()
    assert Path(seen["cwd"]).name.startswith("pycg-run-")
    assert not (job.package / "main.py.ran").exists()


def test_a_part_that_is_not_ported_is_recorded_as_a_crash(tmp_path):
    job, fake = project(tmp_path, "not ported"), tool(tmp_path)
    graph_path = tmp_path / "graph.json"

    record = run.run_job(fake, job, graph_path, timeout_seconds=60)

    assert record["status"] == "crash"
    assert record["error"] == "pycg: not ported: outside attributes"
    assert record["where"] == "target/release/pycg (exit 3)"
    assert record["exit_status"] == 3
    assert not graph_path.exists()


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="VmHWM is Linux")
def test_a_child_of_a_large_parent_reports_its_own_peak_memory(tmp_path):
    ballast = b"x" * (400 << 20)
    record = run.run_job(
        tool(tmp_path), project(tmp_path, "ok"), tmp_path / "g.json", timeout_seconds=60
    )
    assert len(ballast) == 400 << 20
    assert record["status"] == "ok"
    assert 0 < record["peak_rss_mib"] < 200


def test_a_run_past_its_time_limit_is_killed(tmp_path):
    job = project(tmp_path, "hang")
    record = run.run_job(
        tool(tmp_path), job, tmp_path / "graph.json", timeout_seconds=1
    )
    assert record == {"status": "timeout", "wall_seconds": 1}
    assert process_ends_within_five_seconds(
        int((job.package / "child.pid").read_text())
    )
    assert not (tmp_path / "graph.json").exists()


def test_a_run_over_its_memory_limit_is_killed_with_its_workers(tmp_path):
    job = project(tmp_path, "fork-eat")
    record = run.run_job(
        tool(tmp_path),
        job,
        tmp_path / "graph.json",
        timeout_seconds=60,
        memory_limit_mib=200,
    )
    assert record["status"] == "memory"
    assert record["peak_rss_mib"] > 200
    assert record["wall_seconds"] < 60
    assert process_ends_within_five_seconds(
        int((job.package / "worker.pid").read_text())
    )


def test_a_child_that_dies_without_a_result_is_a_crash(tmp_path):
    job = project(tmp_path, "die")
    record = run.run_job(
        tool(tmp_path), job, tmp_path / "graph.json", timeout_seconds=60
    )
    assert record["status"] == "crash"
    assert record["error"].startswith("exit status 1: json.decoder.JSONDecodeError")
    assert record["exit_status"] == 1


def test_the_jobs_of_a_benchmark_run_k_at_a_time_each_with_its_limits(tmp_path):
    behaviours = ("hang", "ok", "die", "crash")
    jobs = [project(tmp_path, behaviour) for behaviour in behaviours]
    data = run.run(
        tool(tmp_path),
        "micro",
        jobs,
        tmp_path / "out",
        2,
        progress=None,
        allow_dirty=True,
        workers=4,
    )
    statuses = {key: record["status"] for key, record in data["runs"].items()}
    assert statuses == {
        "micro/demo/crash": "crash",
        "micro/demo/die": "crash",
        "micro/demo/hang": "timeout",
        "micro/demo/ok": "ok",
    }
    assert data["workers"] == 4


def test_the_first_error_of_a_task_stops_the_tasks():
    def task(number):
        if number == 1:
            raise ValueError("task 1")
        return number

    with pytest.raises(ValueError, match="task 1"):
        run.run_tasks([0, 1, 2], task, 2)
    assert run.run_tasks([0, 2, 3], task, 2) == [0, 2, 3]


def test_micro_cases_that_need_a_newer_python_are_skipped(tmp_path):
    for case, version in (
        ("a/old", None),
        ("a/new", "3.99"),
        ("b/same", "3.12"),
        ("b/patch", "3.12.0"),
        ("b/later", "3.12.1"),
    ):
        directory = tmp_path / case
        directory.mkdir(parents=True)
        (directory / "main.py").write_text("")
        if version:
            (directory / "requires-python").write_text(version + "\n")
    jobs, skipped = run.micro_jobs(tmp_path, version=(3, 12, 0))
    assert [job.key for job in jobs] == ["micro/a/old", "micro/b/patch", "micro/b/same"]
    assert skipped == ["micro/a/new", "micro/b/later"]
    assert jobs[0].entry_points == (tmp_path / "a" / "old" / "main.py",)
    assert jobs[0].package == tmp_path / "a" / "old"


def test_the_runner_runs_the_projects_of_the_macro_benchmark(tmp_path, monkeypatch):
    config = tmp_path / "bench" / "projects.toml"
    monkeypatch.setattr(run.projects, "CONFIG_PATH", config)
    project = tmp_path / "bench" / "projects" / "demo"
    (project / "pkg").mkdir(parents=True)
    (project / "pkg" / "__init__.py").write_text("")
    (project / "BEHAVIOUR").write_text("ok")
    (tmp_path / "bench" / "projects.toml").write_text(
        '[demo]\nroot = "."\npackages = ["pkg"]\nexclude = []\n'
        "dependencies = []\npytest_args = []\ntest_requirements = []\n"
    )
    checkout = fake_checkout(tmp_path)
    out = tmp_path / "out"
    argv = ["--checkout", str(checkout), "--name", "t"]
    argv += ["--benchmark", "macro", "--allow-dirty", "--out", str(out)]
    assert run.main(argv) == 0
    runs = json.loads((out / "t" / "macro" / "runs.json").read_text())
    assert runs["runs"]["macro/demo"]["status"] == "ok"


def test_a_checkout_without_its_program_is_refused(tmp_path):
    with pytest.raises(SystemExit):
        run.main(["--checkout", str(tmp_path), "--name", "t", "--allow-dirty"])
