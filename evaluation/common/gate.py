#!/usr/bin/env python3
import argparse
import hashlib
import json
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MACRO = Path("evaluation/macro-benchmark")
SAME_FUNCTION = Path("evaluation/common/same_function.json")
SNIPPETS = Path("micro-benchmark/snippets")
SNIPPET_FILES = ("callgraph.json", "requires-python")
DESCRIPTION = """The gate of the evaluation: the values of a result against their floors
(evaluation/README.md, "The gate"). RESULT is the result.json of `loop.py
run`; METRICS is evaluation/metrics.json.

    python -I evaluation/common/gate.py check RESULT METRICS [--base BASE_METRICS]
    python -I evaluation/common/gate.py record RESULT METRICS [--base BASE_METRICS]
    python -I evaluation/common/gate.py summary RESULT METRICS --base-result RESULT \\
        --changes FILE"""

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


def benchmark_digest(root=ROOT):
    listing = "".join(
        f"{hashlib.sha256((root / path).read_bytes()).hexdigest()}  {path}\n"
        for path in benchmark_files(root)
    )
    return hashlib.sha256(listing.encode("utf-8")).hexdigest()


def rebased(base, digest):
    return base.get("benchmark_sha256", digest) != digest


def floor(metrics, name):
    return round(metrics["best"][name] - metrics["margin"], 4)


def recorded(base, values, digest):
    if set(base["best"]) != set(VALUES):
        raise GateError(f"the values of the metrics are not {sorted(VALUES)}")
    if rebased(base, digest):
        best = {name: values[name] for name in VALUES}
    else:
        best = {name: max(base["best"][name], values[name]) for name in VALUES}
    return {"margin": base["margin"], "benchmark_sha256": digest, "best": best}


def dumps(metrics):
    return json.dumps(metrics, indent=1) + "\n"


def check(result, metrics, digest, base=None):
    values = measured(result)
    lines = [f"{'value':16} {'measured':>8} {'best':>8} {'floor':>8}"]
    failures = []
    if metrics.get("benchmark_sha256") != digest:
        failures.append(
            "evaluation/metrics.json was recorded on another benchmark "
            f"(benchmark_sha256 {metrics.get('benchmark_sha256')}, this "
            f"checkout's {digest}): run make eval-record"
        )
    for name, value in values.items():
        low = floor(metrics, name)
        ok = value >= low
        best = metrics["best"][name]
        lines.append(
            f"{name:16} {value:8.4f} {best:8.4f} {low:8.4f}  {'ok' if ok else 'FAIL'}"
        )
        if not ok:
            failures.append(f"{name} is {value:.4f}, below its floor {low:.4f}")
    for run in result["failed"]:
        failures.append(f"the run {run['run']} failed: {run['status']}")
    if base is not None:
        lines.append(benchmark_line(base, digest))
        expected = recorded(base, values, digest)
        if metrics != expected:
            failures.append(
                "evaluation/metrics.json is not what make eval-record writes from "
                f"the base's and the measured values: it should be "
                f"{json.dumps(expected)}; run make eval-record"
            )
    return lines, failures


def benchmark_line(base, digest):
    if rebased(base, digest):
        return "benchmark changed: floors re-based"
    return "benchmark unchanged: floors only rise"


def summary(result, metrics, base_result, changes, digest, base=None):
    values, base_values = measured(result), measured(base_result)
    lines = [
        "### PyCG evaluation",
        "",
        "| Value | Base | PR | Floor | |",
        "|---|---|---|---|---|",
    ]
    for name, value in values.items():
        low = floor(metrics, name)
        verdict = "pass" if value >= low else "**fail**"
        lines.append(
            f"| {name} | {base_values[name]:.4f} | {value:.4f} | {low:.4f} "
            f"| {verdict} |"
        )
    if base is not None:
        lines += ["", benchmark_line(base, digest)]
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
        pr, before = runs[key], base_runs.get(key, {})
        lines.append(
            f"| {key.removeprefix('macro/')} | {before.get('seconds', '-')} "
            f"| {pr.get('seconds', '-')} | {before.get('peak_rss_mib', '-')} "
            f"| {pr.get('peak_rss_mib', '-')} |"
        )
    total = {
        side: (
            round(sum(r.get("seconds", 0) for r in found.values()), 3),
            max((r.get("peak_rss_mib", 0) for r in found.values()), default=0),
        )
        for side, found in (("base", base_runs), ("pr", runs))
    }
    lines.append(
        f"| total time, largest peak | {total['base'][0]} | {total['pr'][0]} "
        f"| {total['base'][1]} | {total['pr'][1]} |"
    )
    return lines


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=DESCRIPTION, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("command", choices=["check", "record", "summary"])
    parser.add_argument("result", type=Path)
    parser.add_argument("metrics", type=Path)
    parser.add_argument("--base", type=Path)
    parser.add_argument("--base-result", type=Path)
    parser.add_argument("--changes", type=Path)
    args = parser.parse_args(argv)
    try:
        result, metrics = load(args.result), load(args.metrics)
        base = None
        if args.base and args.base.read_text(encoding="utf-8").strip():
            base = load(args.base)
        elif args.base:
            print(f"the base has no metrics: {args.base} is empty", file=sys.stderr)
        digest = benchmark_digest()
        if args.command == "record":
            print(dumps(recorded(base or metrics, measured(result), digest)), end="")
            return 0
        if args.command == "summary":
            if not (args.base_result and args.changes):
                parser.error("summary needs --base-result and --changes")
            lines = summary(
                result, metrics, load(args.base_result), args.changes, digest, base
            )
            print("\n".join(lines))
            return 0
        lines, failures = check(result, metrics, digest, base)
    except GateError as error:
        print(f"gate: {error}", file=sys.stderr)
        return 1
    print("\n".join(lines))
    if base is None:
        print("floors only rise: not checked (no base metrics)")
    if failures:
        print("\n".join(["gate failed:", *(f"  {f}" for f in failures)]))
        return 1
    print("gate passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
