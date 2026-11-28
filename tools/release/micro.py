import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pycg.formats import edges  # noqa: E402

DESCRIPTION = """\
Runs a release program on every micro-benchmark case and compares its call
graph with the case's callgraph.json, as tests/test_micro_benchmark.py
compares the Python engine's: the program analyses main.py with the case's
directory as the package root, and the edges of its document
(pycg.formats.edges, what CallGraphGenerator.output gives) must equal the
expected graph. A case of tests/known_failures.txt must differ; a case whose
requires-python is newer than the grammar the program parses
(PROGRAM_GRAMMAR, the Rust parser's target version) is skipped and named.
Prints one line per skipped case and per failure, then a summary, and exits
1 when a case that should agree differs, a known failure agrees, or the
program fails on a case.

    python3 tools/release/micro.py PROGRAM
"""

SNIPPETS = ROOT / "evaluation" / "micro-benchmark" / "snippets"
KNOWN_FAILURES = ROOT / "tests" / "known_failures.txt"
PROGRAM_GRAMMAR = (3, 14)


def read_known_failures(path):
    failures = set()
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            failures.add(line.split(": ", 1)[0])
    return failures


def required_python(case):
    path = case / "requires-python"
    if not path.is_file():
        return None
    return tuple(int(part) for part in path.read_text().strip().split("."))


def sorted_edges(graph):
    return {node: sorted(targets) for node, targets in graph.items()}


def program_graph(program, case, document):
    command = [program, "--package", str(case), str(case / "main.py")]
    completed = subprocess.run(
        [*command, "-o", str(document)], capture_output=True, check=False
    )
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", "replace").strip()
        raise RuntimeError(f"exit {completed.returncode}: {stderr}")
    return edges(json.loads(document.read_text(encoding="utf-8")))


def check(program, snippets, known_failures, scratch):
    cases = sorted(path for path in snippets.glob("*/*") if path.is_dir())
    lines, failures, agreed, known, skipped = [], 0, 0, 0, 0
    for case in cases:
        name = f"{case.parent.name}/{case.name}"
        version = required_python(case)
        if version is not None and version > PROGRAM_GRAMMAR:
            skipped += 1
            lines.append(f"skipped {name}: needs Python {'.'.join(map(str, version))}")
            continue
        try:
            found = program_graph(program, case, scratch / "document.json")
        except RuntimeError as error:
            failures += 1
            lines.append(f"FAILED {name}: the program failed: {error}")
            continue
        expected = json.loads((case / "callgraph.json").read_text(encoding="utf-8"))
        same = sorted_edges(found) == sorted_edges(expected)
        if name in known_failures and same:
            failures += 1
            lines.append(f"FAILED {name}: a known failure agrees")
        elif name in known_failures:
            known += 1
        elif same:
            agreed += 1
        else:
            failures += 1
            lines.append(f"FAILED {name}: the call graph differs")
    lines.append(
        f"micro: {len(cases)} cases, {agreed} agree, {known} known failures, "
        f"{skipped} skipped, {failures} failed"
    )
    return lines, failures


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=DESCRIPTION, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("program")
    parser.add_argument("--snippets", type=Path, default=SNIPPETS)
    parser.add_argument("--known-failures", type=Path, default=KNOWN_FAILURES)
    arguments = parser.parse_args(argv)
    known_failures = read_known_failures(arguments.known_failures)
    with tempfile.TemporaryDirectory() as scratch:
        lines, failures = check(
            arguments.program, arguments.snippets, known_failures, Path(scratch)
        )
    print("\n".join(lines))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
