#!/usr/bin/env python3
import argparse
import importlib.util
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

CONTAINER_DIRECTORY = Path(__file__).resolve().parent
REPOSITORY = CONTAINER_DIRECTORY.parents[1]
BENCHMARK = REPOSITORY / "evaluation" / "macro-benchmark"
PROJECT_NAME_PATTERN = re.compile(r"[A-Za-z0-9_.-]+")
WORK_DIRECTORY = Path("/tmp/work")
OUTPUT_DIRECTORY = Path("/tmp/out")
RESULTS_DIRECTORY = Path("/results")
PROJECTS_READER = BENCHMARK / "projects.py"
DESCRIPTION = """Records the trace of one macro-benchmark project inside the `trace`
service of evaluation/compose.yaml, writes it to /results/trace/NAME.json
and, with --compare, compares it with the committed trace
(evaluation/macro-benchmark/README.md, "Re-recording a trace").

    NAME=jmespath docker compose -f evaluation/compose.yaml \\
        run --rm trace [--compare]"""


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


helper = _load("trace_helper", CONTAINER_DIRECTORY / "trace_helper.py")


def lay_out_benchmark_directory(benchmark, project, work):
    name = project.name
    shutil.copytree(
        project.directory,
        work / "projects" / name,
        symlinks=True,
        ignore=shutil.ignore_patterns(".git"),
    )
    shutil.copy(benchmark / "projects.toml", work / "projects.toml")
    for plugin in helper.plugins(benchmark, name):
        (work / plugin).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(benchmark / plugin, work / plugin)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=DESCRIPTION, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("name", help="a project of macro-benchmark/projects.toml")
    parser.add_argument("--compare", action="store_true")
    args = parser.parse_args(argv)
    if not PROJECT_NAME_PATTERN.fullmatch(args.name) or args.name in (".", ".."):
        parser.error(f"not one path component: {args.name!r}")
    benchmark = BENCHMARK
    projects = _load("macro_projects", PROJECTS_READER)
    found = projects.load_projects(benchmark / "projects.toml")
    if args.name not in found:
        parser.error(f"{args.name} is no project of the macro-benchmark")
    source = found[args.name].directory
    if not source.is_dir():
        print(f"trace_entry.py: {args.name}: no source at {source}", file=sys.stderr)
        return 1
    python = sys.executable
    trace = REPOSITORY / "evaluation" / "macro-benchmark" / "trace.py"
    try:
        lay_out_benchmark_directory(benchmark, found[args.name], WORK_DIRECTORY)
        subprocess.run(
            [
                python,
                "-I",
                "-B",
                str(trace),
                args.name,
                "--benchmark-dir",
                str(WORK_DIRECTORY),
            ]
            + ["--locate"],
            check=True,
        )
        OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [python, "-I", "-B", str(trace), args.name, "--python", python]
            + ["--benchmark-dir", str(WORK_DIRECTORY)]
            + ["--output", str(OUTPUT_DIRECTORY / "trace.json")],
            check=True,
        )
        destination = RESULTS_DIRECTORY / "trace"
        image = os.environ.get("PYTHON_IMAGE", "")
        print(
            helper.check_trace(
                OUTPUT_DIRECTORY / "trace.json",
                benchmark,
                args.name,
                image,
                destination,
            )
        )
    except (helper.HelperError, OSError, subprocess.CalledProcessError) as error:
        print(f"trace_entry.py: {args.name}: {error}", file=sys.stderr)
        return 1
    committed = benchmark / "dynamic" / f"{args.name}.json"
    if args.compare:
        if not committed.is_file():
            print(f"trace_entry.py: no committed {committed}", file=sys.stderr)
            return 1
        lines, equal = helper.compare(committed, destination / f"{args.name}.json")
        print("\n".join(lines))
        return 0 if equal else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
