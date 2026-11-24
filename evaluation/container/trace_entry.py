#!/usr/bin/env python3
"""Re-trace one macro-benchmark project inside the `trace` service.

    NAME=jmespath docker compose -f evaluation/compose.yaml run --rm trace [--compare]

The service (evaluation/compose.yaml) builds the image of the project from
container/Dockerfile.trace: macro-benchmark/test-environments/NAME.txt
(hash-pinned wheels) and the project's source from the inputs image
(container/Dockerfile.inputs, whose build checked it against its pin). It
runs, without network, with a read-only root, no capability and a
non-root user:

    python3 -I -B /repo/evaluation/container/trace_entry.py NAME

/repo is this repository, read-only; /results/trace
(evaluation/results/trace/) the only writable host mount, so the test suite
of a project writes nowhere else on the host; /tmp a tmpfs. This entry:

1. copies the project's source from the image (projects.SOURCES/NAME) to
   /tmp/work/projects/NAME;
2. copies projects.toml and the project's pytest plugins beside it;
3. runs macro-benchmark/trace.py: --locate, then the tests under the tracer;
4. checks the trace (trace_helper.check_trace: the format of trace.py, this
   project and pin, exactly the distributions of the requirements file) and
   writes it, with the distributions, to /results/trace/NAME.json and
   NAME.installed.txt: the committed macro-benchmark/dynamic/NAME.json is
   not changed;
5. with --compare, prints the differences from the committed trace
   (trace_helper.compare) and exits with 0 only if the edges are equal.

Like trace.sh, it runs only our own code and the project's tests; the trace
image holds CPython, the pinned test requirements and the project's source,
neither PyCG nor git.
"""

import argparse
import importlib.util
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPOSITORY = HERE.parents[1]
BENCHMARK = REPOSITORY / "evaluation" / "macro-benchmark"
NAME = re.compile(r"[A-Za-z0-9_.-]+")
WORK = Path("/tmp/work")
OUT = Path("/tmp/out")
RESULTS = Path("/results")
PROJECTS_READER = BENCHMARK / "projects.py"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


helper = _load("trace_helper", HERE / "trace_helper.py")


def prepare(benchmark, project, work):
    """Lay out the project's source, projects.toml and plugins under `work`
    as trace.py reads a benchmark directory."""
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
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("name", help="a project of macro-benchmark/projects.toml")
    parser.add_argument("--compare", action="store_true")
    args = parser.parse_args(argv)
    if not NAME.fullmatch(args.name) or args.name in (".", ".."):
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
        prepare(benchmark, found[args.name], WORK)
        subprocess.run(
            [python, "-I", "-B", str(trace), args.name, "--benchmark-dir", str(WORK)]
            + ["--locate"],
            check=True,
        )
        OUT.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [python, "-I", "-B", str(trace), args.name, "--python", python]
            + ["--benchmark-dir", str(WORK)]
            + ["--output", str(OUT / "trace.json")],
            check=True,
        )
        destination = RESULTS / "trace"
        image = os.environ.get("PYTHON_IMAGE", "")
        print(
            helper.check_trace(
                OUT / "trace.json", benchmark, args.name, image, destination
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
