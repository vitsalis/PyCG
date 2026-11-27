import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

DESCRIPTION = """\
Writes the licences of everything that the pycg program of one target is
built from: the licence files of every crate in its dependency graph (normal
and build dependencies, not dev ones) and that of the typeshed stub data
that pycg-stubs embeds. A crate whose package has no licence file takes it
from NOT_IN_PACKAGE, the licence of its repository at the commit that its
.cargo_vcs_info.json names; a crate with neither fails the run.

    python3 tools/release/licences.py TARGET > THIRD_PARTY_LICENCES
"""

ROOT = Path(__file__).resolve().parents[2]
PROGRAM = "pycg"
STUBS = "pycg-stubs"
STUB_LICENCE = Path("stub_data") / "LICENSE"
LICENCE_FILE = re.compile(r"^(licen[cs]e|copying|notice|unlicense)([-._].*)?$", re.I)
RUFF = Path(__file__).with_name("licences") / (
    "ruff-c91de8a012cb87efe279b762020a0d28dd75ddb5.txt"
)
NOT_IN_PACKAGE = {
    ("ruff_python_ast", "0.0.22"): RUFF,
    ("ruff_python_parser", "0.0.22"): RUFF,
    ("ruff_python_trivia", "0.0.22"): RUFF,
    ("ruff_source_file", "0.0.22"): RUFF,
    ("ruff_text_size", "0.0.22"): RUFF,
}
BUILT_FROM = (None, "build")
RULE = "=" * 79


def metadata(target):
    command = [
        "cargo",
        "metadata",
        "--format-version",
        "1",
        "--locked",
        "--filter-platform",
        target,
    ]
    completed = subprocess.run(
        command, cwd=ROOT, capture_output=True, check=True, text=True
    )
    return json.loads(completed.stdout)


def dependencies(data):
    packages = {package["id"]: package for package in data["packages"]}
    nodes = {node["id"]: node for node in data["resolve"]["nodes"]}
    [root] = [id for id, package in packages.items() if package["name"] == PROGRAM]
    seen = {root}
    pending = [root]
    while pending:
        node = nodes[pending.pop()]
        for dependency in node["deps"]:
            kinds = {kind["kind"] for kind in dependency["dep_kinds"]}
            if kinds.isdisjoint(BUILT_FROM) or dependency["pkg"] in seen:
                continue
            seen.add(dependency["pkg"])
            pending.append(dependency["pkg"])
    return sorted(
        (packages[id] for id in seen),
        key=lambda found: (found["name"], found["version"]),
    )


def licence_files(package):
    directory = Path(package["manifest_path"]).parent
    found = sorted(
        path
        for path in directory.iterdir()
        if path.is_file() and LICENCE_FILE.match(path.name)
    )
    if found:
        return found
    key = (package["name"], package["version"])
    assert key in NOT_IN_PACKAGE, f"{key} has no licence file"
    return [NOT_IN_PACKAGE[key]]


def section(title, paths):
    parts = [RULE, title, RULE, ""]
    for path in paths:
        parts.append(f"--- {path.name}")
        parts.append("")
        parts.append(path.read_text(encoding="utf-8").rstrip("\n"))
        parts.append("")
    return "\n".join(parts)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=DESCRIPTION, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("target")
    arguments = parser.parse_args(argv)
    sections = []
    for package in dependencies(metadata(arguments.target)):
        if package["source"] is not None:
            title = f"{package['name']} {package['version']} ({package['license']})"
            sections.append(section(title, licence_files(package)))
        elif package["name"] == STUBS:
            directory = Path(package["manifest_path"]).parent
            title = "typeshed, the stub data of pycg-stubs"
            sections.append(section(title, [directory / STUB_LICENCE]))
    sys.stdout.write("\n".join(sections))


if __name__ == "__main__":
    main()
