"""Behaviour tests for evaluation/common/run.py and evaluation/common/analyse.py.

They run fake PyCG checkouts, written to tmp_path, in child processes. They
need neither the network nor the sources of the benchmark, and run on every
supported Python version.
"""

import importlib.util
import json
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "evaluation_fakes", Path(__file__).resolve().parent / "evaluation_fakes.py"
)
fakes = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fakes)


gone = fakes.gone
run, project, tool, fake_checkout = (
    fakes.run,
    fakes.project,
    fakes.tool,
    fakes.fake_checkout,
)


def test_a_crash_is_recorded_with_the_error_and_where_it_happened(tmp_path):
    job = project(tmp_path, "crash")
    graph_path = tmp_path / "graph.json"
    graph_path.write_text("{}")  # a graph of an earlier run
    record = run.run_job(tool(tmp_path), job, graph_path, timeout=60)
    assert record["status"] == "crash"
    assert record["error"].startswith("JSONDecodeError: Expecting property name")
    assert record["where"].startswith("pycg/pycg.py:")
    assert record["where"].endswith(" in analyze")
    assert not graph_path.exists()


@pytest.mark.parametrize("flavour", ["new", "original"])
def test_an_analysis_runs_isolated_and_never_runs_the_analysed_source(
    tmp_path, flavour
):
    job, fake = project(tmp_path, "ok"), tool(tmp_path, flavour)
    graph_path = tmp_path / "out" / "graph.json"
    record = run.run_job(fake, job, graph_path, timeout=60)
    assert record["status"] == "ok"
    assert record["files"] == 1 and record["peak_rss_mib"] > 0
    graph = json.loads(graph_path.read_text())
    assert graph["main"] == ["main.a", "main.b"]
    assert graph["rest"] == (["-1", "call-graph"] if flavour == "original" else [])
    assert set(graph["environment"]) - {"LC_CTYPE"} == {"PYTHONHASHSEED"}
    assert graph["found"] == ["True"]
    assert str((tmp_path / "fake-pycg").resolve()) in graph["path"]
    assert str(job.package.resolve()) not in graph["path"]
    assert Path(graph["cwd"][0]).name.startswith("pycg-run-")
    assert not (job.package / "main.py.ran").exists()
    again = tmp_path / "again.json"
    run.run_job(fake, job, again, timeout=60)
    assert json.loads(again.read_text())["hash"] == graph["hash"]


def test_a_run_past_its_time_limit_is_killed(tmp_path):
    job = project(tmp_path, "hang")
    record = run.run_job(tool(tmp_path), job, tmp_path / "graph.json", timeout=1)
    assert record == {"status": "timeout", "wall_seconds": 1}
    assert gone(int((job.package / "child.pid").read_text()))
    assert not (tmp_path / "graph.json").exists()


def test_a_run_over_its_memory_limit_is_killed_with_its_workers(tmp_path):
    job = project(tmp_path, "fork-eat")
    record = run.run_job(
        tool(tmp_path), job, tmp_path / "graph.json", timeout=60, memory_limit_mib=200
    )
    assert record["status"] == "memory"
    assert record["peak_rss_mib"] > 200
    assert record["wall_seconds"] < 60
    assert gone(int((job.package / "worker.pid").read_text()))


def test_a_child_that_dies_without_a_result_is_a_crash(tmp_path):
    job = project(tmp_path, "die")
    record = run.run_job(tool(tmp_path), job, tmp_path / "graph.json", timeout=60)
    assert record["status"] == "crash"
    assert record["error"].startswith("exit status 3")


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
    argv = ["--flavour", "new", "--checkout", str(checkout), "--name", "t"]
    argv += ["--benchmark", "macro", "--allow-dirty", "--out", str(out)]
    assert run.main(argv) == 0
    runs = json.loads((out / "t" / "macro" / "runs.json").read_text())
    assert runs["runs"]["macro/demo"]["status"] == "ok"
