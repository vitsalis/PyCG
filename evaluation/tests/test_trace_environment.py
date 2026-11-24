"""Two settings of a trace's test run: the environment variables of an entry
(projects.toml `environment`), which macro-benchmark/trace.py passes into
its minimal environment and records in the trace; and the pytest plugin
plugins/hypothesis_profile.py, which keeps Hypothesis from writing into the
source copy and from timing out under the tracer. The runs are of small
projects written to tmp_path, with this interpreter's pytest."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest

pytestmark = pytest.mark.slow

if sys.version_info < (3, 14):
    pytest.skip(
        "trace.py loads micro-benchmark/validate.py, which needs Python 3.14",
        allow_module_level=True,
    )

EVALUATION = Path(__file__).resolve().parents[1]
BENCHMARK = EVALUATION / "macro-benchmark"
PLUGIN = BENCHMARK / "plugins" / "hypothesis_profile.py"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


projects = load("macro_projects", BENCHMARK / "projects.py")
trace = load("macro_trace", BENCHMARK / "trace.py")
helper = load("trace_helper", EVALUATION / "container" / "trace_helper.py")

ENTRY = """
    [demo]
    root = "."
    packages = ["demo"]
    exclude = []
    dependencies = []
    pytest_args = ["tests"]
    test_requirements = ["pytest"]
"""


def benchmark(root, entry=ENTRY, files=None, plugins=()):
    """A benchmark directory with the project demo: its package, its tests
    (`files`: {path: text}) and the plugins it names (copied in)."""
    files = {"demo/__init__.py": "def f():\n    return 1\n", **(files or {})}
    for relative, text in files.items():
        path = root / "projects" / "demo" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(dedent(text))
    for plugin in plugins:
        (root / "plugins").mkdir(exist_ok=True)
        (root / "plugins" / plugin.name).write_text(plugin.read_text())
    (root / "projects.toml").write_text(dedent(entry))
    return root


def run(root):
    """The trace of demo, as trace.py records it."""
    project = projects.load_projects(root / "projects.toml")["demo"]
    return trace.trace(project, sys.executable, root, timeout=120)


def test_the_trace_records_the_ids_of_failed_and_errored_tests(tmp_path):
    test = """
        import pytest
        import demo

        @pytest.fixture
        def broken():
            raise RuntimeError("set-up fails")

        def test_passes():
            assert demo.f() == 1

        def test_fails():
            assert demo.f() == 2

        def test_errors(broken):
            pass
    """
    data = run(benchmark(tmp_path, files={"tests/test_demo.py": test}))
    assert (data["tests"]["passed"], data["tests"]["failed"]) == (1, 1)
    assert data["tests"]["errors"] == 1
    assert data["failures"] == {
        "errors": ["tests/test_demo.py::test_errors"],
        "failed": ["tests/test_demo.py::test_fails"],
    }


def test_a_run_without_failures_records_empty_lists(tmp_path):
    test = "import demo\n\ndef test_passes():\n    assert demo.f() == 1\n"
    data = run(benchmark(tmp_path, files={"tests/test_demo.py": test}))
    assert data["failures"] == {"errors": [], "failed": []}


def test_an_entry_names_variables_that_the_test_run_gets_and_the_trace_records(
    tmp_path,
):
    entry = ENTRY + 'environment = { DEMO_BACKENDS = "numpy", DEMO_EMPTY = "" }\n'
    test = """
        import os
        import demo

        def test_the_variables_are_there():
            assert os.environ["DEMO_BACKENDS"] == "numpy"
            assert os.environ["DEMO_EMPTY"] == ""
            assert demo.f() == 1
    """
    data = run(benchmark(tmp_path, entry, {"tests/test_demo.py": test}))
    assert (data["tests"]["passed"], data["tests"]["failed"]) == (1, 0)
    assert data["environment"] == {"DEMO_BACKENDS": "numpy", "DEMO_EMPTY": ""}


def test_without_variables_the_trace_has_no_environment(tmp_path):
    test = """
        import os
        import demo

        def test_none():
            assert "DEMO_BACKENDS" not in os.environ and demo.f() == 1
    """
    data = run(benchmark(tmp_path, files={"tests/test_demo.py": test}))
    assert data["tests"]["passed"] == 1
    assert "environment" not in data


@pytest.mark.parametrize(
    "name",
    [
        "PATH",
        "HOME",
        "TMPDIR",
        "LANG",
        "NO_PROXY",
        "no_proxy",
        "PYTHONHASHSEED",
        "PYTHONPATH",
        "PYTHONSTARTUP",
        "pythonpath",
        "PYTEST_ADDOPTS",
        "PYTEST_PLUGINS",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD",
        "LD_PRELOAD",
        "LC_ALL",
    ],
)
def test_a_variable_of_the_tracer_or_of_the_interpreter_is_refused(tmp_path, name):
    entry = ENTRY + f'environment = {{ {name} = "x" }}\n'
    with pytest.raises(ValueError, match=f"environment: {name} is not an entry's"):
        projects.load_projects(benchmark(tmp_path, entry) / "projects.toml")


@pytest.mark.parametrize(
    "value",
    [
        '"numpy"',
        "{ DEMO = 1 }",
        '{ DEMO = ["a"] }',
        '{ "1DEMO" = "a" }',
        '{ "A-B" = "a" }',
    ],
)
def test_the_environment_is_a_table_of_names_and_strings(tmp_path, value):
    entry = ENTRY + f"environment = {value}\n"
    with pytest.raises(ValueError, match="environment: a table of variable names"):
        projects.load_projects(benchmark(tmp_path, entry) / "projects.toml")


def test_every_variable_of_the_tracer_s_environment_is_refused_in_an_entry(tmp_path):
    for name in trace._environment(sys.executable, tmp_path):
        assert projects.reserved_variable(name), name


def test_the_check_of_a_trace_wants_the_environment_of_its_entry():
    data = {key: kind() for key, kind in helper.TRACE_KEYS.items()}
    data |= {"project": "demo", "commit": "c", "tests": {"exit_status": 0}}
    data["tests"] |= dict.fromkeys((*helper.OUTCOMES, "deselected"), 0)
    expected = {"DEMO_BACKENDS": "numpy"}
    assert helper._check_shape(data, "demo", "c") == []
    assert helper._check_shape(data, "demo", "c", expected) == [
        "the trace has the environment {}, its entry {'DEMO_BACKENDS': 'numpy'}"
    ]
    data["environment"] = dict(expected)
    assert helper._check_shape(data, "demo", "c", expected) == []
    assert helper._check_shape(data, "demo", "c") == [
        "the trace has the environment {'DEMO_BACKENDS': 'numpy'}, its entry {}"
    ]
    data["environment"] = {"DEMO_BACKENDS": 1}
    assert "'environment' is not a mapping of names to strings" in helper._check_shape(
        data, "demo", "c", expected
    )


HYPOTHESIS_TEST = """
    from hypothesis import HealthCheck, given, settings, strategies as st
    import demo

    @given(st.text())
    def test_text(value):
        assert demo.f() == 1

    @given(st.integers(0, 10**6).filter(lambda x: x % 1000 == 7))
    def test_a_rare_example(value):
        assert demo.f() == 1

    def test_the_profile():
        current = settings()
        assert current.deadline is None
        assert current.database is None
        assert current.derandomize is True
        assert set(current.suppress_health_check) == set(HealthCheck)
"""
WITH_PLUGIN = ENTRY + 'plugins = ["plugins/hypothesis_profile.py"]\n'
WITH_PLUGIN = WITH_PLUGIN.replace('["pytest"]', '["pytest", "hypothesis"]')


def test_the_hypothesis_profile_writes_nothing_into_the_source_copy(tmp_path):
    root = benchmark(
        tmp_path, WITH_PLUGIN, {"tests/test_demo.py": HYPOTHESIS_TEST}, [PLUGIN]
    )
    data = run(root)
    assert (data["tests"]["passed"], data["tests"]["failed"]) == (3, 0)
    assert data["plugins"] == ["plugins/hypothesis_profile.py"]
    assert not (root / "projects" / "demo" / ".hypothesis").exists()


def test_without_the_profile_hypothesis_writes_into_the_source_copy(tmp_path):
    entry = ENTRY.replace('["pytest"]', '["pytest", "hypothesis"]')
    test = HYPOTHESIS_TEST.split("    def test_the_profile")[0]
    root = benchmark(tmp_path, entry, {"tests/test_demo.py": test})
    with pytest.raises(trace.TraceError, match=r"changes in the checkout"):
        run(root)


def test_two_runs_with_the_profile_draw_the_same_examples(tmp_path):
    test = """
        import json
        from hypothesis import given, strategies as st

        def test_draws():
            seen = []

            @given(st.integers())
            def inner(value):
                seen.append(value)

            inner()
            print("SEEN", json.dumps(seen))
    """
    code = dedent(f"""
        import importlib.util, sys
        spec = importlib.util.spec_from_file_location("profile", {str(PLUGIN)!r})
        spec.loader.exec_module(importlib.util.module_from_spec(spec))
        import pytest
        sys.exit(pytest.main([sys.argv[1], "-q", "-s", "-p", "no:cacheprovider"]))
    """)
    (tmp_path / "test_draws.py").write_text(dedent(test))
    seen = []
    for _ in range(2):
        done = subprocess.run(
            [sys.executable, "-c", code, str(tmp_path / "test_draws.py")],
            cwd=tmp_path,
            capture_output=True,
            text=True,
        )
        assert done.returncode == 0, done.stdout + done.stderr
        (line,) = [x for x in done.stdout.splitlines() if x.startswith("SEEN ")]
        seen.append(json.loads(line.removeprefix("SEEN ")))
    assert seen[0] == seen[1] and len(seen[0]) > 1
    assert not (tmp_path / ".hypothesis").exists()
