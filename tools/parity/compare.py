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
names. Every required dump is compared (D5 as sets, the others byte for
byte), and D6 by SHA-256 when ACTUAL wrote it; an input whose required
dumps agree is missing when ACTUAL wrote no D6 and D6 is not required.
An input where ACTUAL wrote error.txt and the partial trace
D3.partial.jsonl is partial when that trace begins the oracle's D3, and
different when it leaves it. --dumps names the required dumps instead of
REQUIRED.

DIFFERENCES lists the inputs of a run that are known not to agree, one per
line: run, dump, input, status (different, partial or failed) and cause,
tab-separated. RUN names the run that ACTUAL holds. An unlisted input must
agree. A listed input must have its listed status and, when different,
differ in exactly its listed dumps; a partial or failed entry names D3 and
covers the input. A listed input that agrees, or that EXPECTED lacks,
fails. Lines starting with # are notes. The list only shrinks: with
--base FILE, the differences of the base, an entry (run, dump, input
and status) that the base does not have fails, so a newly differing
input fails the job instead of being listed. Prints one line per set and
the first failures, and exits 1 when an input fails.

    python3 -I tools/parity/compare.py EXPECTED ACTUAL [--required FILE]
        [--dumps NAME...] [--differences FILE] [--run NAME] [--base FILE]
"""

REQUIRED_DEFAULT = Path(__file__).with_name("required.txt")
DIFFERENCES_DEFAULT = Path(__file__).with_name("differences.txt")
RUN_DEFAULT = "replay"
STATUSES = ("different", "partial", "failed")
INPUT_DUMP = "D3"
DUMPS = ("D1", "D2", "D3", "D4", "D5", "D6", "D6in")
DOCUMENT = "D6.json"
ERROR = "error.txt"
PARTIAL = "D3.partial.jsonl"
SHOWN_DIFFERENCES_MAX = 10


def listed(path):
    names = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        name = line.strip()
        if name:
            names.append(name)
    return names


def entries(path):
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    for number, line in enumerate(lines, start=1):
        if line.strip() and not line.startswith("#"):
            yield number, line


def added_entries(path, base):
    kept = {tuple(line.split("\t")[:4]) for _, line in entries(base)}
    return [
        line for _, line in entries(path) if tuple(line.split("\t")[:4]) not in kept
    ]


def known_differences(path, run):
    found = {}
    for number, line in entries(path):
        fields = line.split("\t")
        assert len(fields) == 5, f"{path}:{number}: run, dump, input, status, cause"
        entry_run, dump, key, status, cause = fields
        assert dump in DUMPS, f"{path}:{number}: no dump {dump}"
        assert status in STATUSES, f"{path}:{number}: no status {status}"
        assert cause.strip(), f"{path}:{number}: an entry gives its cause"
        assert status == "different" or dump == INPUT_DUMP, (
            f"{path}:{number}: a {status} entry covers the input and names {INPUT_DUMP}"
        )
        if entry_run != run:
            continue
        if key in found:
            assert found[key][0] == status == "different", (
                f"{path}:{number}: {key} is listed twice"
            )
            assert dump not in found[key][1], f"{path}:{number}: {key} {dump} twice"
        found.setdefault(key, (status, set()))[1].add(dump)
    return found


def verdict(status, differences, known):
    if known is None:
        if status in STATUSES:
            return differences
        return []
    listed_status, dumps = known
    if status in ("identical", "missing"):
        return [f"listed as {listed_status} but agrees: remove it"]
    if status != listed_status:
        return [f"listed as {listed_status} but {status}", *differences]
    if status != "different":
        return []
    unlisted = [name for name in differences if name not in dumps]
    agreeing = sorted(name for name in dumps if name not in differences)
    return unlisted + [f"{name} agrees: remove it" for name in agreeing]


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
    if name == "D6":
        return DOCUMENT
    if name == "D6in":
        return "D6in.json"
    return f"{name}.jsonl"


def compare_input(expected, actual, required):
    if (expected / ERROR).exists():
        return "failed", ["the oracle failed"]
    if (actual / ERROR).exists():
        if not (actual / PARTIAL).exists():
            return "failed", ["the other tool failed"]
        partial = (actual / PARTIAL).read_bytes()
        if (expected / "D3.jsonl").read_bytes().startswith(partial):
            return "partial", ["the trace stops where the other tool stopped"]
        return "different", ["D3"]
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


def compare(expected_root, actual_root, required, known=None):
    expected_root, actual_root = Path(expected_root), Path(actual_root)
    known = {} if known is None else known
    sets = {}
    shown = []
    keys = input_keys(expected_root)
    for key in sorted(set(keys) | set(known)):
        if key in keys:
            status, differences = compare_input(
                expected_root / key, actual_root / key, required
            )
            failures = verdict(status, differences, known.get(key))
        else:
            status = "failed"
            failures = ["listed, and the oracle has no such input"]
        counts = sets.setdefault(
            key.split("/")[0],
            {
                "inputs": 0,
                "identical": 0,
                "different": 0,
                "failed": 0,
                "missing": 0,
                "partial": 0,
                "listed": 0,
                "failing": 0,
            },
        )
        counts["inputs"] += 1
        counts[status] += 1
        counts["listed"] += key in known
        counts["failing"] += bool(failures)
        if failures and len(shown) < SHOWN_DIFFERENCES_MAX:
            listing = key in known and not set(failures) <= set(DUMPS)
            shown.append((key, "listed" if listing else status, failures))
    return sets, shown


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=DESCRIPTION, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("expected", type=Path)
    parser.add_argument("actual", type=Path)
    parser.add_argument("--required", type=Path, default=REQUIRED_DEFAULT)
    parser.add_argument("--dumps", nargs="+", choices=DUMPS)
    parser.add_argument("--differences", type=Path, default=DIFFERENCES_DEFAULT)
    parser.add_argument("--run", default=RUN_DEFAULT)
    parser.add_argument("--base", type=Path)
    args = parser.parse_args(argv)
    if args.base is not None:
        added = added_entries(args.differences, args.base)
        for line in added:
            print(f"  {args.differences}: an entry the base lacks: {line}")
        if added:
            return 1
    required = listed(args.required) if args.dumps is None else args.dumps
    known = known_differences(args.differences, args.run)
    sets, shown = compare(args.expected, args.actual, required, known)
    if not sets:
        print(f"compare: no inputs in {args.expected}")
        return 1
    for name, counts in sorted(sets.items()):
        print(
            f"{name}: {counts['inputs']} inputs, {counts['identical']} identical, "
            f"{counts['different']} different, {counts['failed']} failed, "
            f"{counts['missing']} missing, {counts['partial']} partial, "
            f"{counts['listed']} listed, {counts['failing']} failing"
        )
    for key, label, failures in shown:
        print(f"  {key}: {label}: {', '.join(failures)}")
    bad = any(counts["failing"] for counts in sets.values())
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
