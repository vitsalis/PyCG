#!/usr/bin/env python3
import argparse
import hashlib
import json
import sys
import tomllib
from pathlib import Path

MACRO = Path("evaluation/macro-benchmark")
SAME_FUNCTION = Path("evaluation/common/same_function.json")
SNIPPETS = Path("evaluation/micro-benchmark/snippets")
SNIPPET_FILES = ("callgraph.json", "requires-python")
DESCRIPTION = """The gate of the evaluation (AGENTS.md, "Evaluation"). A RESULT
is a directory that `make` measures into: the result.json of `loop.py run`
and the benchmark_sha256 of the checkout measured. BASE_METRICS is the
evaluation/metrics.json of the base, METRICS that of this checkout.

    python -I evaluation/common/gate.py check RESULT BASE_RESULT BASE_METRICS
    python -I evaluation/common/gate.py summary RESULT BASE_RESULT BASE_METRICS \\
        --changes FILE
    python -I evaluation/common/gate.py report RESULT METRICS
    python -I evaluation/common/gate.py record RESULT METRICS
    python -I evaluation/common/gate.py digest ROOT"""
DIGEST_FILE = "benchmark_sha256"
DIGEST_CHARACTERS = frozenset("0123456789abcdef")
DIGEST_LENGTH = 64

VALUES = {
    "micro P": ("micro", "all", "precision"),
    "micro R": ("micro", "all", "recall"),
    "macro inside P": ("macro", "inside", "precision"),
    "macro inside R": ("macro", "inside", "recall"),
    "macro outside P": ("macro", "outside", "precision"),
    "macro outside R": ("macro", "outside", "recall"),
}


class GateError(Exception):
    pass


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def measurement(directory):
    path = Path(directory) / DIGEST_FILE
    if not path.is_file():
        raise GateError(f"{path}: no digest of the benchmark measured; measure again")
    digest = path.read_text(encoding="utf-8").strip()
    if len(digest) != DIGEST_LENGTH or not set(digest) <= DIGEST_CHARACTERS:
        raise GateError(f"{path}: {digest!r} is not a SHA-256 digest")
    return load(Path(directory) / "result.json"), digest


def base_margin(path):
    text = Path(path).read_text(encoding="utf-8")
    if not text.strip():
        raise GateError(f"the base has no metrics.json, so no margin: {path} is empty")
    return json.loads(text)["margin"]


def measured(result):
    values = {}
    for name, (benchmark, edge_set, field) in VALUES.items():
        if benchmark == "micro":
            counts = result["micro"]["total"]["raw"][edge_set]
        else:
            counts = result["macro"]["summed"]["raw"][edge_set]
        if counts[field] is None:
            raise GateError(f"{name}: no edges to compute it from: {counts}")
        values[name] = counts[field]
    return values


def benchmark_files(root):
    macro = root / MACRO
    config = macro / "projects.toml"
    files = [config, root / SAME_FUNCTION]
    for name in tomllib.loads(config.read_text(encoding="utf-8")):
        for directory in ("ground-truth", "dynamic"):
            path = macro / directory / f"{name}.json"
            if path.is_file():
                files.append(path)
    for case in (root / SNIPPETS).glob("*/*"):
        if case.is_dir():
            files += [
                path
                for path in case.rglob("*")
                if path.is_file()
                and (path.suffix == ".py" or path.name in SNIPPET_FILES)
            ]
    return sorted(path.relative_to(root).as_posix() for path in files)


def benchmark_digest(root):
    listing = "".join(
        f"{hashlib.sha256((root / path).read_bytes()).hexdigest()}  {path}\n"
        for path in benchmark_files(root)
    )
    return hashlib.sha256(listing.encode("utf-8")).hexdigest()


def floors(base_values, margin, digest, base_digest):
    if digest != base_digest:
        return None
    return {name: round(base_values[name] - margin, 4) for name in VALUES}


def benchmark_line(found):
    if found is None:
        return "benchmark changed: floors re-based"
    return "benchmark unchanged: each floor is the base's value minus the margin"


def best_floor(metrics, name):
    return round(metrics["best"][name] - metrics["margin"], 4)


def recorded(metrics, values, digest):
    assert "benchmark_sha256" in metrics, metrics
    if set(metrics["best"]) != set(VALUES):
        raise GateError(f"the values of the metrics are not {sorted(VALUES)}")
    if metrics["benchmark_sha256"] != digest:
        best = {name: values[name] for name in VALUES}
    else:
        best = {name: max(metrics["best"][name], values[name]) for name in VALUES}
    return {"margin": metrics["margin"], "benchmark_sha256": digest, "best": best}


def dumps(metrics):
    return json.dumps(metrics, indent=1) + "\n"


def run_failures(result):
    return [f"the run {run['run']} failed: {run['status']}" for run in result["failed"]]


def check(pr, base, margin):
    (result, digest), (base_result, base_digest) = pr, base
    values, base_values = measured(result), measured(base_result)
    found = floors(base_values, margin, digest, base_digest)
    lines = [f"{'value':16} {'measured':>8} {'base':>8} {'floor':>8}"]
    failures = []
    for name, value in values.items():
        start = f"{name:16} {value:8.4f} {base_values[name]:8.4f}"
        if found is None:
            lines.append(f"{start} {'-':>8}  re-based")
            continue
        low = found[name]
        ok = value >= low
        lines.append(f"{start} {low:8.4f}  {'ok' if ok else 'FAIL'}")
        if not ok:
            failures.append(f"{name} is {value:.4f}, below its floor {low:.4f}")
    lines.append(benchmark_line(found))
    return lines, failures + run_failures(result)


def summary(pr, base, margin, changes):
    (result, digest), (base_result, base_digest) = pr, base
    values, base_values = measured(result), measured(base_result)
    found = floors(base_values, margin, digest, base_digest)
    lines = [
        "### PyCG evaluation",
        "",
        "| Value | Base | PR | Floor | |",
        "|---|---|---|---|---|",
    ]
    for name, value in values.items():
        if found is None:
            low, verdict = "-", "re-based"
        else:
            low = f"{found[name]:.4f}"
            verdict = "pass" if value >= found[name] else "**fail**"
        lines.append(
            f"| {name} | {base_values[name]:.4f} | {value:.4f} | {low} | {verdict} |"
        )
    lines += ["", benchmark_line(found)]
    lines += ["", f"Failed runs: {len(result['failed'])}"]
    lines += [f"- {run['run']}: {run['status']}" for run in result["failed"]]
    lines += [
        "",
        "<details><summary>Changes from the base (loop.py compare)</summary>",
        "",
        "```",
        Path(changes).read_text(encoding="utf-8").rstrip("\n"),
        "```",
        "",
        "</details>",
        "",
        "### Macro packages: analysis time and peak memory (not gated)",
        "",
        "| Package | Base s | PR s | Base MiB | PR MiB |",
        "|---|---|---|---|---|",
    ]
    runs = result["macro_runs"]["runs"]
    base_runs = base_result["macro_runs"]["runs"]
    for key in sorted(runs):
        now, before = runs[key], base_runs.get(key, {})
        lines.append(
            f"| {key.removeprefix('macro/')} | {before.get('seconds', '-')} "
            f"| {now.get('seconds', '-')} | {before.get('peak_rss_mib', '-')} "
            f"| {now.get('peak_rss_mib', '-')} |"
        )
    total = {
        side: (
            round(sum(r.get("seconds", 0) for r in found_runs.values()), 3),
            max((r.get("peak_rss_mib", 0) for r in found_runs.values()), default=0),
        )
        for side, found_runs in (("base", base_runs), ("pr", runs))
    }
    lines.append(
        f"| total time, largest peak | {total['base'][0]} | {total['pr'][0]} "
        f"| {total['base'][1]} | {total['pr'][1]} |"
    )
    return lines


def report(measured_commit, metrics):
    result, digest = measured_commit
    values = measured(result)
    expected = recorded(metrics, values, digest)
    same_benchmark = metrics["benchmark_sha256"] == digest
    lines = [
        "### PyCG against evaluation/metrics.json",
        "",
        "| Value | Best | Measured | |",
        "|---|---|---|---|",
    ]
    failures = []
    for name, value in values.items():
        best, low = metrics["best"][name], best_floor(metrics, name)
        if not same_benchmark:
            verdict = "re-based"
        elif value > best:
            verdict = "rose"
        elif value >= low:
            verdict = "kept"
        else:
            verdict = f"**below its floor {low:.4f}**"
            failures.append(f"{name} is {value:.4f}, below its floor {low:.4f}")
        lines.append(f"| {name} | {best:.4f} | {value:.4f} | {verdict} |")
    lines.append("")
    if not same_benchmark:
        lines.append(
            "benchmark changed: make eval-record takes the measured values as the bests"
        )
    elif expected == metrics:
        lines.append("No value rose: evaluation/metrics.json is up to date.")
    else:
        lines.append(
            "A value rose: record it with a pull request that commits only "
            "the evaluation/metrics.json that make eval-record writes on this "
            "commit."
        )
    failures += run_failures(result)
    lines += ["", f"Failed runs: {len(result['failed'])}"]
    lines += [f"- {run['run']}: {run['status']}" for run in result["failed"]]
    lines += [
        "",
        "make eval-record on this commit writes:",
        "",
        "```json",
        dumps(expected).rstrip("\n"),
        "```",
    ]
    return lines, failures


def finish(lines, failures):
    print("\n".join(lines))
    if failures:
        print("\n".join(["gate failed:", *(f"  {f}" for f in failures)]))
        return 1
    print("gate passed")
    return 0


def arguments(argv):
    parser = argparse.ArgumentParser(
        description=DESCRIPTION, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("check", "summary"):
        command = commands.add_parser(name)
        command.add_argument("result", type=Path)
        command.add_argument("base_result", type=Path)
        command.add_argument("base_metrics", type=Path)
        if name == "summary":
            command.add_argument("--changes", type=Path, required=True)
    for name in ("report", "record"):
        command = commands.add_parser(name)
        command.add_argument("result", type=Path)
        command.add_argument("metrics", type=Path)
    commands.add_parser("digest").add_argument("root", type=Path)
    return parser.parse_args(argv)


def main(argv=None):
    args = arguments(argv)
    try:
        if args.command == "digest":
            print(benchmark_digest(args.root.resolve()))
            return 0
        pr = measurement(args.result)
        if args.command == "record":
            print(dumps(recorded(load(args.metrics), measured(pr[0]), pr[1])), end="")
            return 0
        if args.command == "report":
            return finish(*report(pr, load(args.metrics)))
        base = measurement(args.base_result)
        margin = base_margin(args.base_metrics)
        if args.command == "summary":
            print("\n".join(summary(pr, base, margin, args.changes)))
            return 0
        return finish(*check(pr, base, margin))
    except (GateError, OSError) as error:
        print(f"gate: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
