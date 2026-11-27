import argparse
import json
import sys
from pathlib import Path

DESCRIPTION = """\
Explains a difference that compare.py found in one dump of one input.
EXPECTED and ACTUAL are the roots that compare.py took, INPUT the input
(micro/<category>/<case>, macro/<project>), DUMP one of D1 to D6.

    python3 -I tools/parity/diff.py EXPECTED ACTUAL INPUT DUMP

D1 to D4 are compared in order, D3 against the partial trace
D3.partial.jsonl when ACTUAL has no D3: the first differing record, with the records
around it on both sides. D5 by node: the nodes that one side has, and the
objects that one side holds. D6 by its parts: the edges, the call sites, the
causes of unresolved sites, the definitions, modules, exports and outside
names that one side has and the other lacks, in the document's own names.
"""

CONTEXT = 3
PARTIAL = "D3.partial.jsonl"
LISTED_MAX = 20


def records(path):
    return Path(path).read_text(encoding="utf-8").splitlines()


def explain_ordered(expected, actual):
    first = next(
        (
            index
            for index, (left, right) in enumerate(zip(expected, actual))
            if left != right
        ),
        min(len(expected), len(actual)),
    )
    if first == len(expected) == len(actual):
        return ["the records are identical"]
    lines = [
        f"first difference at record {first + 1} "
        f"(expected {len(expected)} records, actual {len(actual)})"
    ]
    start = max(0, first - CONTEXT)
    for side, found in (("expected", expected), ("actual", actual)):
        lines.append(f"{side}:")
        for index in range(start, min(len(found), first + CONTEXT + 1)):
            mark = ">" if index == first else " "
            lines.append(f"{mark} {index + 1}: {found[index]}")
    return lines


def explain_points_to(expected, actual):
    left = {r["node"]: set(r["objects"]) for r in map(json.loads, expected)}
    right = {r["node"]: set(r["objects"]) for r in map(json.loads, actual)}
    lines = []
    for side, mine, theirs in (("expected", left, right), ("actual", right, left)):
        only = sorted(set(mine) - set(theirs))
        lines += [f"node only in {side}: {node}" for node in only[:LISTED_MAX]]
    for node in sorted(set(left) & set(right)):
        if left[node] != right[node]:
            lost = sorted(left[node] - right[node])[:LISTED_MAX]
            gained = sorted(right[node] - left[node])[:LISTED_MAX]
            lines.append(f"{node}: expected only {lost}, actual only {gained}")
            if len(lines) >= LISTED_MAX * 3:
                break
    return lines or ["the points-to sets are identical"]


def document_parts(document):
    edges = set()
    sites = {}
    for caller, found in document["calls"].items():
        for site in found:
            where = (
                caller,
                site.get("module", ""),
                site["line"],
                site["col"],
                tuple(site["end"]),
                site.get("implicit", ""),
            )
            sites[where] = (tuple(site["callees"]), site.get("unresolved"))
            edges.update((caller, callee) for callee in site["callees"])
    return {
        "edge": edges,
        "site": set(sites),
        "unresolved": {(w, cause) for w, (_, cause) in sites.items() if cause},
        "site callees": {(w, c) for w, (callees, _) in sites.items() for c in callees},
        "definition": {
            (name, json.dumps(value, sort_keys=True))
            for name, value in document["definitions"].items()
        },
        "module": {
            (name, json.dumps(value, sort_keys=True))
            for name, value in document["modules"].items()
        },
        "export": {
            (name, json.dumps(value, sort_keys=True))
            for name, value in document["exports"].items()
        },
        "outside": {
            (name, json.dumps(value, sort_keys=True))
            for name, value in document["outside"].items()
        },
        "tool": {json.dumps(document["tool"], sort_keys=True)},
    }


def explain_document(expected_path, actual_path):
    expected = json.loads(Path(expected_path).read_text(encoding="utf-8"))
    actual = json.loads(Path(actual_path).read_text(encoding="utf-8"))
    left, right = document_parts(expected), document_parts(actual)
    lines = []
    for part in left:
        for side, mine, theirs in (
            ("expected", left[part], right[part]),
            ("actual", right[part], left[part]),
        ):
            only = sorted(mine - theirs, key=repr)
            if only:
                lines.append(f"{part}: {len(only)} only in {side}")
                lines += [f"  {item}" for item in only[:LISTED_MAX]]
    if not lines and Path(expected_path).read_bytes() != Path(actual_path).read_bytes():
        lines.append("same content, different bytes (encoding or key order)")
    return lines or ["the documents are identical"]


def explain(expected_root, actual_root, key, dump):
    expected_dir = Path(expected_root) / key
    actual_dir = Path(actual_root) / key
    if dump == "D6":
        return explain_document(expected_dir / "D6.json", actual_dir / "D6.json")
    expected = records(expected_dir / f"{dump}.jsonl")
    actual_path = actual_dir / f"{dump}.jsonl"
    if dump == "D3" and not actual_path.exists():
        actual_path = actual_dir / PARTIAL
    actual = records(actual_path)
    if dump == "D5":
        return explain_points_to(expected, actual)
    return explain_ordered(expected, actual)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=DESCRIPTION, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("expected", type=Path)
    parser.add_argument("actual", type=Path)
    parser.add_argument("input")
    parser.add_argument("dump", choices=["D1", "D2", "D3", "D4", "D5", "D6"])
    args = parser.parse_args(argv)
    for line in explain(args.expected, args.actual, args.input, args.dump):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
