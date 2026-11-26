import os
import re
import tomllib
from pathlib import Path
from typing import NamedTuple

SCALE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = SCALE_DIR / "projects.toml"
KINDS = ("pure wheel", "platform wheel", "git archive")
SUFFIX_BY_KIND = {
    "pure wheel": ".whl",
    "platform wheel": ".whl",
    "git archive": ".tar.gz",
}
KEYS = ("version", "kind", "file", "url", "sha256", "licence", "root", "packages")
_NAME = re.compile(r"[A-Za-z0-9_.-]+")
_FILE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.+-]*")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_COMMIT = re.compile(r"[0-9a-f]{40}")


class Project(NamedTuple):
    name: str
    version: str
    kind: str
    file: str
    url: str
    sha256: str
    licence: str
    directory: Path
    root: Path
    packages: tuple

    def source_files(self):
        return sorted(
            path.resolve()
            for package in self.packages
            for path in package.rglob("*.py")
            if path.is_file()
        )


def is_under(path, directory):
    return path == str(directory) or path.startswith(str(directory) + os.sep)


def _check(config_path, name, entry):
    where = f"{config_path}: [{name}]"
    if not _NAME.fullmatch(name) or name in (".", ".."):
        raise ValueError(
            f"{where}: a name is one path component of letters, digits, _, - and ."
        )
    if sorted(entry) != sorted(KEYS):
        raise ValueError(f"{where}: the keys are {', '.join(KEYS)}: {sorted(entry)}")
    if entry["kind"] not in KINDS:
        raise ValueError(f"{where}: kind is one of {', '.join(KINDS)}")
    suffix = SUFFIX_BY_KIND[entry["kind"]]
    if not (_FILE.fullmatch(entry["file"]) and entry["file"].endswith(suffix)):
        raise ValueError(f"{where}: file is a file name that ends with {suffix}")
    if not entry["url"].startswith("https://"):
        raise ValueError(f"{where}: url is not https")
    if not _SHA256.fullmatch(entry["sha256"]):
        raise ValueError(f"{where}: sha256 is not 64 lowercase hex digits")
    if entry["kind"] == "git archive" and not _COMMIT.fullmatch(entry["version"]):
        raise ValueError(f"{where}: the version of a git archive is a full commit id")
    if not entry["packages"]:
        raise ValueError(f"{where}: packages is empty")


def load_projects(config_path=CONFIG_PATH, sources=None):
    config_path = Path(config_path).resolve()
    sources = Path(sources or config_path.parent / "projects")
    with config_path.open("rb") as file:
        data = tomllib.load(file)
    projects = {}
    for name, entry in data.items():
        _check(config_path, name, entry)
        directory = (sources / name).resolve()
        root = (directory / entry["root"]).resolve()
        packages = tuple((root / package).resolve() for package in entry["packages"])
        for path in (root, *packages):
            if not is_under(str(path), directory):
                raise ValueError(
                    f"{config_path}: [{name}]: {path} is not inside {directory}"
                )
        projects[name] = Project(
            name=name,
            version=entry["version"],
            kind=entry["kind"],
            file=entry["file"],
            url=entry["url"],
            sha256=entry["sha256"],
            licence=entry["licence"],
            directory=directory,
            root=root,
            packages=packages,
        )
    return projects
