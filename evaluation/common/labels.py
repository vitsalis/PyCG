#!/usr/bin/env python3
import json
import sys
from pathlib import Path

USAGE = """usage: python -I evaluation/common/labels.py \\
    RESULT BASE_RESULT CHANGED_FILES OUTPUTS

RESULT and BASE_RESULT are the result.json of `loop.py run` for the pull
request and for its base; CHANGED_FILES lists the paths that the pull request
changes, one per line. OUTPUTS gets `<label>=true|false` per label (the format
of $GITHUB_OUTPUT); the Markdown of the decision goes to standard output."""
PROTECTED = (
    "evaluation/macro-benchmark/ground-truth/",
    "evaluation/macro-benchmark/dynamic/",
    "evaluation/macro-benchmark/projects.toml",
    "evaluation/macro-benchmark/test-environments/",
    "evaluation/common/same_function.json",
    "evaluation/micro-benchmark/snippets/**/callgraph.json",
    "tests/known_failures.txt",
    "evaluation/metrics.json",
    ".github/",
)
COUNTS = {
    "micro": ("micro", "all"),
    "macro inside": ("macro", "inside"),
    "macro outside": ("macro", "outside"),
}


def protected(path):
    for pattern in PROTECTED:
        if "/**/" in pattern:
            prefix, suffix = pattern.split("/**/")
            if path.startswith(prefix + "/") and path.endswith("/" + suffix):
                return True
        elif pattern.endswith("/"):
            if path.startswith(pattern):
                return True
        elif path == pattern:
            return True
    return False


def counts(result):
    found = {}
    for name, (benchmark, edge_set) in COUNTS.items():
        if benchmark == "micro":
            data = result["micro"]["total"]["raw"][edge_set]
        else:
            data = result["macro"]["summed"]["raw"][edge_set]
        found[name] = (data["tp"], data["fp"], data["fn"])
    return found


def decide(result, base_result, changed):
    now, before = counts(result), counts(base_result)
    moved = {
        name: (before[name], now[name]) for name in COUNTS if now[name] != before[name]
    }
    touched = sorted(path for path in changed if protected(path))
    return moved, touched


def markdown(moved, touched):
    lines = ["### Labels", ""]
    if moved:
        lines.append("- `metrics-changed`: yes (TP/FP/FN, base -> PR)")
        for name, (before, now) in moved.items():
            old, new = ("/".join(map(str, c)) for c in (before, now))
            lines.append(f"  - {name}: {old} -> {new}")
    else:
        lines.append("- `metrics-changed`: no (every TP/FP/FN count as on the base)")
    if touched:
        lines.append("- `benchmark-changed`: yes (protected files changed)")
        lines += [f"  - `{path}`" for path in touched]
    else:
        lines.append("- `benchmark-changed`: no (no protected file changed)")
    return lines


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 4:
        print(USAGE, file=sys.stderr)
        return 2
    result, base_result, changed_files, outputs = argv
    changed = Path(changed_files).read_text(encoding="utf-8").splitlines()
    moved, touched = decide(
        json.loads(Path(result).read_text(encoding="utf-8")),
        json.loads(Path(base_result).read_text(encoding="utf-8")),
        changed,
    )
    Path(outputs).write_text(
        f"metrics-changed={str(bool(moved)).lower()}\n"
        f"benchmark-changed={str(bool(touched)).lower()}\n",
        encoding="utf-8",
    )
    print("\n".join(markdown(moved, touched)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
