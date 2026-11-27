import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pycg import view  # noqa: E402

DESCRIPTION = """\
Renders every document of the oracle with pycg-view and with pycg view and
compares the pages byte for byte (docs/rust/PLAN.md, stage 8): ORACLE is the
oracle's directory of one seed, OUT the directory for the pages of pycg view,
PYCG the Rust program. Prints one line and the first differences, and exits 1
when a page differs or pycg view fails.

    python3 -I tools/parity/view.py ORACLE OUT PYCG
"""
DOCUMENT = "D6.json"
PAGE = "page.html"
SHOWN_DIFFERENCES_MAX = 10


def compare(document, page, program):
    page.parent.mkdir(parents=True, exist_ok=True)
    command = [program, "view", str(document), "-o", str(page)]
    completed = subprocess.run(command, capture_output=True, check=False)
    if completed.returncode != 0:
        return f"pycg view failed: {completed.stderr.decode('utf-8', 'replace')}"
    expected = view.render(view.read(document)).encode("utf-8")
    if page.read_bytes() != expected:
        return "the pages differ"
    return None


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=DESCRIPTION, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("oracle", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("pycg")
    arguments = parser.parse_args(argv)
    documents = sorted(arguments.oracle.rglob(DOCUMENT))
    differences = []
    for document in documents:
        name = document.parent.relative_to(arguments.oracle)
        page = arguments.out / name / PAGE
        difference = compare(document, page, arguments.pycg)
        if difference is not None:
            differences.append(f"{name}: {difference}")
    identical = len(documents) - len(differences)
    print(
        f"view: {len(documents)} documents, {identical} identical, "
        f"{len(differences)} different"
    )
    for line in differences[:SHOWN_DIFFERENCES_MAX]:
        print(f"  {line}")
    return 1 if differences else 0


if __name__ == "__main__":
    sys.exit(main())
