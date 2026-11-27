import argparse
import hashlib
import json
import sys
from pathlib import Path

DESCRIPTION = """\
Compares the dumps of two runs (docs/rust/PLAN.md, section 3): EXPECTED is
the oracle's directory of one seed, ACTUAL the other tool's. Each holds one
directory per input (micro/<category>/<case>, macro/<project>, ...). An input
fails when either side wrote error.txt or ACTUAL lacks a dump that REQUIRED
names. Every required dump is compared (D5 as sets, the others record by
record), and D6 by SHA-256 when ACTUAL wrote it; an input whose required
dumps agree is missing when ACTUAL wrote no D6 and D6 is not required.
Prints one line per set and the first differences, and exits 1 when an
input differs or failed. --dumps names the required dumps instead of
REQUIRED, and --inputs compares only the inputs that its file lists, one
per line; a listed input that EXPECTED lacks fails.

    python3 -I tools/parity/compare.py EXPECTED ACTUAL [--required FILE]
        [--dumps NAME...] [--inputs FILE]
"""

REQUIRED_DEFAULT = Path(__file__).with_name("required.txt")
DUMPS = ("D1", "D2", "D3", "D4", "D5", "D6")
DOCUMENT = "D6.json"
ERROR = "error.txt"
SHOWN_DIFFERENCES_MAX = 10


def listed(path):
    names = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        name = line.strip()
        if name:
            names.append(name)
    return names


def input_keys(root):
    root = Path(root)
    found = set()
    for marker in (DOCUMENT, ERROR):
        for path in root.rglob(marker):
            found.add(path.parent.relative_to(root).as_posix())
    return sorted(found)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def points_to(path):
    held = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        held[record["node"]] = set(record["objects"])
    return held


def same_dump(name, expected, actual):
    if name == "D5":
        return points_to(expected) == points_to(actual)
    return Path(expected).read_bytes() == Path(actual).read_bytes()


def file_of(name):
    return DOCUMENT if name == "D6" else f"{name}.jsonl"


def compare_input(expected, actual, required):
    if (expected / ERROR).exists():
        return "failed", ["the oracle failed"]
    if (actual / ERROR).exists():
        return "failed", ["the other tool failed"]
    absent = [name for name in required if not (actual / file_of(name)).exists()]
    if absent:
        return "failed", [f"{name} is required and absent" for name in absent]
    differences = [
        name
        for name in required
        if name != "D6"
        and not same_dump(name, expected / file_of(name), actual / file_of(name))
    ]
    if not (actual / DOCUMENT).exists():
        if differences:
            return "different", differences
        return "missing", ["D6 is not written yet"]
    if digest(expected / DOCUMENT) != digest(actual / DOCUMENT):
        differences.insert(0, "D6")
    return ("different" if differences else "identical"), differences


def compare(expected_root, actual_root, required, inputs=None):
    expected_root, actual_root = Path(expected_root), Path(actual_root)
    sets = {}
    shown = []
    keys = input_keys(expected_root)
    for key in keys if inputs is None else inputs:
        if key in keys:
            status, differences = compare_input(
                expected_root / key, actual_root / key, required
            )
        else:
            status, differences = "failed", ["the oracle has no such input"]
        counts = sets.setdefault(
            key.split("/")[0],
            {"inputs": 0, "identical": 0, "different": 0, "failed": 0, "missing": 0},
        )
        counts["inputs"] += 1
        counts[status] += 1
        if (
            status not in ("identical", "missing")
            and len(shown) < SHOWN_DIFFERENCES_MAX
        ):
            shown.append((key, status, differences))
    return sets, shown


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=DESCRIPTION, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("expected", type=Path)
    parser.add_argument("actual", type=Path)
    parser.add_argument("--required", type=Path, default=REQUIRED_DEFAULT)
    parser.add_argument("--dumps", nargs="+", choices=DUMPS)
    parser.add_argument("--inputs", type=Path)
    args = parser.parse_args(argv)
    required = listed(args.required) if args.dumps is None else args.dumps
    inputs = None if args.inputs is None else listed(args.inputs)
    sets, shown = compare(args.expected, args.actual, required, inputs)
    if not sets:
        print(f"compare: no inputs in {args.expected}")
        return 1
    for name, counts in sorted(sets.items()):
        print(
            f"{name}: {counts['inputs']} inputs, {counts['identical']} identical, "
            f"{counts['different']} different, {counts['failed']} failed, "
            f"{counts['missing']} missing"
        )
    for key, status, differences in shown:
        print(f"  {key}: {status}: {', '.join(differences)}")
    bad = any(counts["different"] or counts["failed"] for counts in sets.values())
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
