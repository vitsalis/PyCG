import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PARITY = Path(__file__).resolve().parent

DESCRIPTION = """\
Runs the Rust program pycg on every input of the oracle that DIFFERENCES
does not list for the engine run, with the package root and entry points of
the oracle's run.json, and compares the document it writes with the oracle's
D6 byte for byte (docs/rust/PLAN.md, stage 7): ORACLE is the oracle's
directory of one seed, OUT the directory for the documents of pycg, PYCG the
Rust program. pycg runs in the checkout, as the oracle did. Prints one line
and every difference, and exits 1 when a document differs or pycg fails.

    python3 -I tools/parity/program.py ORACLE OUT PYCG [--differences FILE]
"""
RUN = "run.json"
DOCUMENT = "D6.json"
WRITTEN = "document.json"
ENGINE_RUN = "engine"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


compare_dumps = load("parity_compare", PARITY / "compare.py")


def agreeing_inputs(oracle, differences):
    known = compare_dumps.known_differences(differences, ENGINE_RUN)
    found = sorted(
        path.parent.relative_to(oracle).as_posix() for path in oracle.rglob(RUN)
    )
    return [name for name in found if name not in known]


def compare(oracle, written, program, checkout):
    run = json.loads((oracle / RUN).read_text(encoding="utf-8"))
    written.parent.mkdir(parents=True, exist_ok=True)
    command = [program, "--package", run["package"], *run["entry_points"]]
    command += ["-o", str(written)]
    completed = subprocess.run(command, cwd=checkout, capture_output=True, check=False)
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", "replace").strip()
        return f"pycg exited with {completed.returncode}: {stderr}"
    if not (oracle / DOCUMENT).is_file():
        return "the oracle wrote no D6"
    expected = (oracle / DOCUMENT).read_bytes() + b"\n"
    if written.read_bytes() != expected:
        return "the documents differ"
    return None


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=DESCRIPTION, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("oracle", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("pycg")
    parser.add_argument(
        "--differences", type=Path, default=compare_dumps.DIFFERENCES_DEFAULT
    )
    parser.add_argument("--checkout", type=Path, default=ROOT)
    arguments = parser.parse_args(argv)
    inputs = agreeing_inputs(arguments.oracle, arguments.differences)
    differences = []
    for name in inputs:
        written = arguments.out / name / WRITTEN
        difference = compare(
            arguments.oracle / name, written, arguments.pycg, arguments.checkout
        )
        if difference is not None:
            differences.append(f"{name}: {difference}")
    identical = len(inputs) - len(differences)
    print(
        f"program: {len(inputs)} inputs, {identical} identical, "
        f"{len(differences)} different"
    )
    for line in differences:
        print(f"  {line}")
    return 1 if differences else 0


if __name__ == "__main__":
    sys.exit(main())
