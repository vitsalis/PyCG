"""macro-benchmark/projects.py: the projects of projects.toml, their batches,
their pins and the analysed source."""

import importlib.util
from pathlib import Path
from textwrap import dedent

import pytest

BENCHMARK = Path(__file__).resolve().parents[1] / "macro-benchmark"
_spec = importlib.util.spec_from_file_location(
    "macro_projects", BENCHMARK / "projects.py"
)
projects = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(projects)

CONFIG = """
    [demo]
    root = "."
    packages = ["demo"]
    exclude = ["demo/vendored"]
    dependencies = []
"""
FILES = {
    "demo/__init__.py": "",
    "demo/core.py": "def f():\n    return 1\n",
    "demo/data.txt": "not code\n",
    "demo/vendored/__init__.py": "",
    "tests/test_demo.py": "import demo\n",
}
SDIST_SHA256 = "ab" * 32
SDIST_URL = "https://files.pythonhosted.org/packages/ab/cd/demo-1.0.tar.gz"


def benchmark(root, config=CONFIG):
    """Write projects.toml and the source projects/demo; return the config."""
    for relative, text in FILES.items():
        path = root / "projects" / "demo" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    config_path = root / "projects.toml"
    config_path.write_text(dedent(config))
    return config_path


def test_the_analysed_source_is_the_packages_without_the_exclusions(tmp_path):
    project = projects.load_projects(benchmark(tmp_path))["demo"]
    modules = [project.module_name(path) for path in project.source_files()]
    assert modules == ["demo", "demo.core"]


def test_a_link_that_leaves_the_project_is_refused(tmp_path):
    config_path = benchmark(tmp_path)
    (tmp_path / "outside.py").write_text("")
    link = tmp_path / "projects" / "demo" / "demo" / "out.py"
    link.symlink_to(tmp_path / "outside.py")
    project = projects.load_projects(config_path)["demo"]
    with pytest.raises(ValueError, match="a link leaves the project: demo/out.py"):
        project.source_files()
    config_path.write_text(dedent(CONFIG.replace('root = "."', 'root = "../.."')))
    with pytest.raises(ValueError, match="is not inside"):
        projects.load_projects(config_path)


def test_the_pin_is_the_commit_or_the_sha256_of_the_sdist(tmp_path):
    config_path = benchmark(tmp_path, CONFIG + f'commit = "{"0" * 40}"\n')
    project = projects.load_projects(config_path)["demo"]
    assert (project.sdist, project.pin) == (None, "0" * 40)
    sdist = 'sdist = "demo-1.0.tar.gz"\n'
    sdist += f'sdist_url = "{SDIST_URL}"\nsdist_sha256 = "{SDIST_SHA256}"\n'
    config_path.write_text(dedent(CONFIG) + sdist)
    project = projects.load_projects(config_path)["demo"]
    assert project.sdist == projects.Sdist("demo-1.0.tar.gz", SDIST_URL, SDIST_SHA256)
    assert (project.commit, project.pin) == (None, f"sha256:{SDIST_SHA256}")
    config_path.write_text(dedent(CONFIG) + sdist + f'commit = "{"0" * 40}"\n')
    with pytest.raises(ValueError, match="a git checkout or an sdist, not both"):
        projects.load_projects(config_path)


def test_every_project_of_the_benchmark_has_a_batch():
    """The 30 projects: five per batch, in the order of projects.BATCHES."""
    batches = {}
    for name, project in projects.load_projects().items():
        batches.setdefault(project.batch, []).append(name)
    assert list(batches) == list(projects.BATCHES)
    assert {len(names) for names in batches.values()} == {5}
    assert batches[1] == ["jmespath", "tenacity", "cachetools", "pluggy", "h11"]
    assert batches["icse-2021"] == [
        "autojump",
        "fabric",
        "asciinema",
        "face_classification",
        "Sublist3r",
    ]


@pytest.mark.parametrize("batch", ["0", "6", '"2"', "true"])
def test_a_batch_is_one_of_the_batches(tmp_path, batch):
    config_path = benchmark(tmp_path, CONFIG + f"batch = {batch}\n")
    with pytest.raises(ValueError, match="batch is one of 1, 2, 3, 4, 5, 'icse-2021'"):
        projects.load_projects(config_path)
    config_path.write_text(dedent(CONFIG + "batch = 3\n"))
    assert projects.load_projects(config_path)["demo"].batch == 3
