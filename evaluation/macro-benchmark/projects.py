"""The projects of the macro-benchmark, as projects.toml describes them.

Read by trace.py, check.py and the evaluation scripts. It needs nothing but
the standard library of Python 3.12, so that the runner of evaluation/ can
find the analysed source without loading the tracer (Python 3.14).

The sources of the projects are not in git. The build of the inputs image
(evaluation/container/Dockerfile.inputs) fetches each one by its pin and
fails if one is not its pin; every image of the evaluation holds them at
SOURCES. On the host, projects/ beside projects.toml holds them only if
they were copied out of that image, to be read (see the README).
"""

import os
import re
import tomllib
from pathlib import Path
from typing import NamedTuple

BENCHMARK_DIR = Path(__file__).resolve().parent
# The micro-benchmark is versioned with the tool, at the root of this
# repository. Every script takes its place from here.
MICRO_BENCHMARK = BENCHMARK_DIR.parents[1] / "micro-benchmark"
# A project name names projects/<name> and the files of its results.
_NAME = re.compile(r"[A-Za-z0-9_.-]+")
CONFIG_PATH = BENCHMARK_DIR / "projects.toml"
# Where the images of the evaluation hold the sources of the projects of
# CONFIG_PATH. Any other projects.toml (a test's, the copy of a trace) has
# its sources in projects/ beside it.
SOURCES = Path("/inputs/macro-benchmark/projects")
# The keys of the two forms of a project's source: a git checkout at a
# commit, or a source archive from PyPI.
_GIT_KEYS = ("repository", "tag", "commit")
_SDIST_KEYS = ("sdist", "sdist_url", "sdist_sha256")
_SDIST_FILE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]*\.tar\.gz")
_SHA256 = re.compile(r"[0-9a-f]{64}")
# The batches: the five batches in the order in which they were built,
# then the projects of PyCG's ICSE 2021 evaluation.
BATCHES = (1, 2, 3, 4, 5, "icse-2021")


class Sdist(NamedTuple):
    """A source archive from PyPI, in place of a git checkout."""

    file: str  # the file name of the archive, which names the release
    url: str
    sha256: str


class Project(NamedTuple):
    """A project of the benchmark, as projects.toml describes it."""

    name: str
    batch: int | str | None  # one of BATCHES (None: a project of the tests)
    directory: Path  # the source, sources(projects.toml)/<name>
    root: Path  # the directory on sys.path; module names are relative to it
    packages: tuple  # package directories or module files: the analysed source
    exclude: tuple  # paths in the packages that are not analysed
    dependencies: frozenset  # installed top-level modules that are library code
    pytest_args: tuple  # empty: no test run (a ground truth from reading only)
    config: Path | None  # the project's own pytest configuration file
    deselect: tuple  # ({"test": node id, "reason": why}, ...)
    plugins: tuple  # pytest plugins: .py files of the benchmark, outside projects/
    also_installed: frozenset  # packages that the test environment also installs
    not_importable: frozenset  # packages that the test environment cannot import
    requirements: (
        tuple  # what the test environment has installed: name or name==version
    )
    repository: str | None  # the git repository's URL
    commit: str | None
    sdist: Sdist | None  # in place of a commit; the source is its unpacked copy

    @property
    def pin(self):
        """What the source is pinned at: the commit, or `sha256:` and the hash
        of the sdist (None for an unpinned checkout, as in the tests)."""
        if self.sdist is not None:
            return f"sha256:{self.sdist.sha256}"
        return self.commit

    def pytest_command(self):
        """The arguments of pytest: the checkout is the rootdir and the limit
        for conftest.py files, and only the project's own configuration counts
        (none: os.devnull, so that pytest does not look in parent directories)."""
        return [
            *self.pytest_args,
            "-c",
            str(self.config or os.devnull),
            f"--rootdir={self.directory}",
            f"--confcutdir={self.directory}",
            "-p",
            "no:cacheprovider",
            "--continue-on-collection-errors",
            *(f"--deselect={entry['test']}" for entry in self.deselect),
        ]

    @property
    def package_names(self):
        """The names of the analysed packages (`jmespath`). A module file is
        named as its module, by module_name: `configargparse.py` is
        `configargparse`, `pkg/__init__.py` is `pkg`."""
        return tuple(
            self.module_name(package)
            if package.suffix == ".py"
            else ".".join(package.relative_to(self.root).parts)
            for package in self.packages
        )

    def in_scope(self, filename):
        """Whether `filename` is a module of the analysed source."""
        path = os.path.realpath(filename)
        if not path.endswith(".py"):
            return False
        return any(is_under(path, p) for p in self.packages) and not any(
            is_under(path, e) for e in self.exclude
        )

    def module_name(self, path):
        """The dotted name of a source file; a package __init__.py is the package."""
        parts = list(Path(path).resolve().relative_to(self.root).with_suffix("").parts)
        if parts[-1] == "__init__" and len(parts) > 1:
            parts.pop()
        return ".".join(parts)

    def source_files(self):
        """The modules of the analysed source, sorted by path. A package is a
        directory, or a module file. ValueError if a link of the project's
        directory leaves it: the pin fixes a link's text, not what it reaches
        (escaping_links)."""
        leaving = escaping_links(self.directory)
        if leaving:
            raise ValueError(
                f"{self.directory}: a link leaves the project: {', '.join(leaving)}"
            )
        files = {
            path.resolve()
            for package in self.packages
            for path in ([package] if package.is_file() else package.rglob("*.py"))
            if self.in_scope(path)
        }
        return sorted(files)


def escaping_links(directory):
    """The paths (relative, sorted) of the links below `directory` whose
    target, resolved, is not inside `directory`; no link is followed while
    walking. Every reader of a project's files goes through this check
    (source_files), so a fetched link cannot select a file that the pin
    does not fix."""
    directory = os.path.realpath(directory)
    if not os.path.isdir(directory):
        return []
    found = []
    for top, names, files in os.walk(directory):
        for name in sorted(names + files):
            path = os.path.join(top, name)
            if os.path.islink(path) and not is_under(os.path.realpath(path), directory):
                found.append(os.path.relpath(path, directory))
    return sorted(found)


def is_under(path, directory):
    return path == str(directory) or path.startswith(str(directory) + os.sep)


def sources(config_path):
    """The directory of the sources of the projects of `config_path`:
    SOURCES for the benchmark's own projects.toml in an image of the
    evaluation, else projects/ beside the file."""
    config_path = Path(config_path).resolve()
    if config_path == CONFIG_PATH and SOURCES.is_dir():
        return SOURCES
    return config_path.parent / "projects"


def load_projects(config_path=CONFIG_PATH):
    """Read projects.toml: {name: Project}. The source of a project is
    sources(config_path)/<name>: the files of a git commit, or the unpacked
    copy of an sdist."""
    config_path = Path(config_path).resolve()
    source_dir = sources(config_path)
    with config_path.open("rb") as f:
        data = tomllib.load(f)
    projects = {}
    for name, entry in data.items():
        if not _NAME.fullmatch(name) or name in (".", ".."):
            raise ValueError(
                f"{config_path}: [{name}]: a project name is one path component "
                "of letters, digits, _, - and ."
            )
        # A project without both has no test run: its ground truth comes
        # from reading only, and trace.py refuses it.
        if ("pytest_args" in entry) != ("test_requirements" in entry):
            raise ValueError(
                f"{config_path}: [{name}]: pytest_args and test_requirements go "
                "together (neither: the project has no test run)"
            )
        batch = entry.get("batch")
        if isinstance(batch, bool) or batch not in (None, *BATCHES):
            raise ValueError(
                f"{config_path}: [{name}]: batch is one of "
                f"{', '.join(map(repr, BATCHES))}: {entry['batch']!r}"
            )
        deselect = entry.get("deselect", [])
        if not all(
            isinstance(item, dict) and item.get("test") and item.get("reason")
            for item in deselect
        ):
            raise ValueError(
                f"{config_path}: [{name}]: "
                "every deselect entry needs a test and a reason"
            )
        plugins = tuple(
            _plugin_path(config_path, name, plugin)
            for plugin in entry.get("plugins", [])
        )
        directory = (source_dir / name).resolve()
        root = (directory / entry["root"]).resolve()
        packages = tuple((root / p).resolve() for p in entry["packages"])
        config = (
            directory / entry["pytest_config"] if "pytest_config" in entry else None
        )
        # The root, the packages and the configuration, resolved, must stay
        # in the project's directory: a link of the tree may not lead out.
        for path in (root, *packages, *([config.resolve()] if config else [])):
            if not is_under(str(path), directory):
                raise ValueError(
                    f"{config_path}: [{name}]: {path} is not inside {directory} "
                    "(a link of the project that leaves it?)"
                )
        project = Project(
            name=name,
            batch=entry.get("batch"),
            directory=directory,
            root=root,
            packages=packages,
            exclude=tuple((directory / p).resolve() for p in entry["exclude"]),
            dependencies=frozenset(entry["dependencies"]),
            pytest_args=tuple(entry.get("pytest_args", ())),
            config=config,
            deselect=tuple(deselect),
            plugins=plugins,
            also_installed=frozenset(entry.get("also_installed", ())),
            not_importable=frozenset(entry.get("not_importable", ())),
            requirements=tuple(entry.get("test_requirements", ())),
            repository=entry.get("repository"),
            commit=entry.get("commit"),
            sdist=_sdist(config_path, name, entry),
        )
        # A test requirement can need the package itself (pytest needs
        # pluggy): the environment then has it too. The run checks that the
        # package was imported from the checkout.
        if not project.also_installed <= set(project.package_names):
            raise ValueError(
                f"{config_path}: [{name}]: also_installed names a package of "
                f"the project: {sorted(project.also_installed)}"
            )
        # A package of the analysed source can need a library that the test
        # environment lacks: no test imports it, and the run checks that.
        if not project.not_importable <= set(project.package_names):
            raise ValueError(
                f"{config_path}: [{name}]: not_importable names a package of "
                f"the project: {sorted(project.not_importable)}"
            )
        projects[name] = project
    return projects


def _sdist(config_path, name, entry):
    """The sdist of an entry (None if it names none): a file name ending in
    .tar.gz, an https URL that ends in that name, and the SHA-256 of the
    file."""
    given = [key for key in _SDIST_KEYS if key in entry]
    if not given:
        return None
    where = f"{config_path}: [{name}]"
    if any(key in entry for key in _GIT_KEYS):
        raise ValueError(
            f"{where}: the source is a git checkout or an sdist, not both "
            f"({', '.join(_GIT_KEYS)} or {', '.join(_SDIST_KEYS)})"
        )
    if len(given) != len(_SDIST_KEYS):
        raise ValueError(f"{where}: sdist, sdist_url and sdist_sha256 go together")
    file, url, sha256 = (entry[key] for key in _SDIST_KEYS)
    if not (isinstance(file, str) and _SDIST_FILE.fullmatch(file)):
        raise ValueError(f"{where}: sdist: a file name that ends in .tar.gz: {file!r}")
    if not (
        isinstance(url, str)
        and url.startswith("https://")
        and url.rsplit("/", 1)[-1] == file
    ):
        raise ValueError(f"{where}: sdist_url: an https URL of {file}: {url!r}")
    if not (isinstance(sha256, str) and _SHA256.fullmatch(sha256)):
        raise ValueError(f"{where}: sdist_sha256: 64 lowercase hex digits: {sha256!r}")
    return Sdist(file, url, sha256)


def _plugin_path(config_path, name, plugin):
    """The path of a pytest plugin of projects.toml: a relative path to a .py
    file of the benchmark directory, outside the checkouts, so that the
    tests of a project cannot change it."""
    benchmark = config_path.parent
    if isinstance(plugin, str) and not os.path.isabs(plugin):
        path = (benchmark / plugin).resolve()
        if (
            path.suffix == ".py"
            and is_under(str(path), benchmark)
            and not is_under(str(path), benchmark / "projects")
        ):
            return path
    raise ValueError(
        f"{config_path}: [{name}]: a pytest plugin is a .py file of the benchmark "
        f"directory, outside projects/, given relative to it: {plugin!r}"
    )
