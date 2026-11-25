import os
import re
import tomllib
from pathlib import Path
from typing import NamedTuple

BENCHMARK_DIR = Path(__file__).resolve().parent
MICRO_BENCHMARK = BENCHMARK_DIR.parent / "micro-benchmark"
_PROJECT_NAME_PATTERN = re.compile(r"[A-Za-z0-9_.-]+")
CONFIG_PATH = BENCHMARK_DIR / "projects.toml"
SOURCES = Path("/inputs/macro-benchmark/projects")
_GIT_KEYS = ("repository", "tag", "commit")
_SDIST_KEYS = ("sdist", "sdist_url", "sdist_sha256")
_SDIST_FILE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]*\.tar\.gz")
_SHA256 = re.compile(r"[0-9a-f]{64}")
BATCHES = (1, 2, 3, 4, 5, 6, 7, 8, "icse-2021")


class Sdist(NamedTuple):
    file: str
    url: str
    sha256: str


class Project(NamedTuple):
    name: str
    batch: int | str | None
    directory: Path
    root: Path
    packages: tuple
    exclude: tuple
    dependencies: frozenset
    pytest_args: tuple
    config: Path | None
    deselect: tuple
    plugins: tuple
    also_installed: frozenset
    not_importable: frozenset
    requirements: tuple
    repository: str | None
    commit: str | None
    sdist: Sdist | None
    environment: tuple = ()

    @property
    def pin(self):
        if self.sdist is not None:
            return f"sha256:{self.sdist.sha256}"
        return self.commit

    def pytest_command(self):
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
        return tuple(
            self.module_name(package)
            if package.suffix == ".py"
            else ".".join(package.relative_to(self.root).parts)
            for package in self.packages
        )

    def in_scope(self, filename):
        path = os.path.realpath(filename)
        if not path.endswith(".py"):
            return False
        return any(is_under(path, p) for p in self.packages) and not any(
            is_under(path, e) for e in self.exclude
        )

    def module_name(self, path):
        parts = list(Path(path).resolve().relative_to(self.root).with_suffix("").parts)
        if parts[-1] == "__init__" and len(parts) > 1:
            parts.pop()
        return ".".join(parts)

    def source_files(self):
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
    config_path = Path(config_path).resolve()
    if config_path == CONFIG_PATH and SOURCES.is_dir():
        return SOURCES
    return config_path.parent / "projects"


def load_projects(config_path=CONFIG_PATH):
    config_path = Path(config_path).resolve()
    source_dir = sources(config_path)
    with config_path.open("rb") as f:
        data = tomllib.load(f)
    projects = {}
    for name, entry in data.items():
        if not _PROJECT_NAME_PATTERN.fullmatch(name) or name in (".", ".."):
            raise ValueError(
                f"{config_path}: [{name}]: a project name is one path component "
                "of letters, digits, _, - and ."
            )
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
            environment=_environment(config_path, name, entry),
        )
        if not project.also_installed <= set(project.package_names):
            raise ValueError(
                f"{config_path}: [{name}]: also_installed names a package of "
                f"the project: {sorted(project.also_installed)}"
            )
        if not project.not_importable <= set(project.package_names):
            raise ValueError(
                f"{config_path}: [{name}]: not_importable names a package of "
                f"the project: {sorted(project.not_importable)}"
            )
        projects[name] = project
    return projects


_TRACER_VARIABLES = frozenset(
    {"PATH", "HOME", "TMPDIR", "LANG", "NO_PROXY", "PYTHONHASHSEED"}
)
_RESERVED_VARIABLE_PREFIXES = ("PYTHON", "PYTEST", "LD_", "LC_")
_VARIABLE_NAME_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def reserved_variable(name):
    upper = name.upper()
    return upper in _TRACER_VARIABLES or upper.startswith(_RESERVED_VARIABLE_PREFIXES)


def _environment(config_path, name, entry):
    table = entry.get("environment", {})
    where = f"{config_path}: [{name}]: environment"
    if not isinstance(table, dict) or not all(
        isinstance(key, str)
        and _VARIABLE_NAME_PATTERN.fullmatch(key)
        and isinstance(value, str)
        for key, value in table.items()
    ):
        raise ValueError(f"{where}: a table of variable names and strings")
    for key in table:
        if reserved_variable(key):
            raise ValueError(
                f"{where}: {key} is not an entry's to set (trace.py sets it, or "
                "it configures the interpreter, pytest, the loader or the locale)"
            )
    return tuple(sorted(table.items()))


def _sdist(config_path, name, entry):
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
