#!/usr/bin/env python3
import argparse
import importlib.util
import sys
from pathlib import Path

COMMON = Path(__file__).resolve().parent
DESCRIPTION = """The two steps of an optimisation iteration (evaluation/README.md,
"Commands"): `run` measures and scores a checkout, `compare` lists what
changed between two results.

    python -I evaluation/common/loop.py run --flavour new --checkout PATH --name NAME
    python -I evaluation/common/loop.py compare OLD_DIR NEW_DIR"""


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


run = _load("evaluation_run", COMMON / "run.py")
score = run.load_sibling("evaluation_score", COMMON / "score.py")

MODE = "raw"
CHANGES = (
    ("became_tp", "+TP", "tp", "new"),
    ("stopped_tp", "-TP", "tp", "old"),
    ("became_fp", "+FP", "fp", "new"),
    ("stopped_fp", "-FP", "fp", "old"),
)


def measure(
    tool,
    out,
    benchmark_dir=score.BENCHMARK,
    timeout_seconds=run.TIMEOUT_SECONDS_DEFAULT,
    allow_dirty=False,
    snippets=score.SNIPPETS,
    progress=None,
    micro_workers=1,
):
    config = Path(benchmark_dir) / "projects.toml"
    macro, macro_skipped = run.macro_jobs(config)
    micro, skipped = run.micro_jobs(snippets, run.python_version(tool.python))
    run.run(
        tool,
        "micro",
        micro,
        out,
        timeout_seconds,
        skipped,
        progress,
        allow_dirty,
        workers=micro_workers,
    )
    run.run(
        tool, "macro", macro, out, timeout_seconds, macro_skipped, progress, allow_dirty
    )
    tool_dir = Path(out) / tool.name
    data = score.tool_results(tool_dir, config, snippets)
    (tool_dir / "result.json").write_text(score.dumps(data) + "\n", encoding="utf-8")
    return data


def summary_lines(data):
    tool = data["tool"]
    if not tool.get("commit"):
        state = "not under git"
    else:
        state = "with changes" if tool.get("dirty") else "clean"
    lines = [f"{tool['name']} at {(tool.get('commit') or '?')[:10]} ({state})"]
    total = data["micro"]["total"][MODE]
    lines.append(
        f"micro: {total['cases']} cases, {total['skipped']} skipped, "
        f"{total['failed']} failed; exact {total['exact']}; edges "
        f"P {_ratio(total['all']['precision'])} R {_ratio(total['all']['recall'])}"
        f" (inside P {_ratio(total['inside']['precision'])}"
        f" R {_ratio(total['inside']['recall'])})"
    )
    for edge_set in ("inside", "outside"):
        lines.append(f"macro, {edge_set}:  P      R      F1     TP/FP/FN")
        rows = [
            (name, project[MODE][edge_set])
            for name, project in data["macro"]["projects"].items()
        ]
        rows.append(("summed", data["macro"]["summed"][MODE][edge_set]))
        for name, c in rows:
            lines.append(
                f"  {name:14} {_ratio(c['precision'])}  {_ratio(c['recall'])}  "
                f"{_ratio(c['f1'])}  {c['tp']}/{c['fp']}/{c['fn']}"
            )
    failed = data["failed"]
    lines.append(f"failed runs: {len(failed)}")
    for run_ in failed:
        where = f" ({run_['where']})" if run_.get("where") else ""
        line = f"  {run_['run']}: {run_['status']} {run_.get('error', '')}{where}"
        lines.append(line.rstrip())
    return lines


def _ratio(x):
    return "  -  " if x is None else f"{x:.3f}"


def compare(old_dir, new_dir, benchmark_dir=score.BENCHMARK, snippets=score.SNIPPETS):
    config = Path(benchmark_dir) / "projects.toml"
    old = score.macro_edges(old_dir, config, MODE)
    new = score.macro_edges(new_dir, config, MODE)
    projects = {}
    for name, now in new.items():
        before = old.get(name, {"status": "not run"})
        both_runs_measured = (before["status"], now["status"]) == ("ok", "ok")
        if not both_runs_measured:
            projects[name] = {
                "measured": False,
                "old": before["status"],
                "new": now["status"],
            }
            continue
        sets = {"old": before, "new": now}
        projects[name] = {
            key: [
                list(edge)
                for edge in sorted(
                    sets[side][kind] - sets["new" if side == "old" else "old"][kind]
                )
            ]
            for key, _, kind, side in CHANGES
        }
        projects[name]["packages"] = list(now["packages"])
        projects[name]["measured"] = True
    cases = {
        side: score.score_micro(directory, snippets)
        for side, directory in (("old", old_dir), ("new", new_dir))
    }
    statuses = {
        key: (cases["old"][key]["status"], cases["new"][key]["status"])
        for key in cases["new"]
    }
    measured = {k for k, s in statuses.items() if s == ("ok", "ok")}
    exact = {
        side: {k for k in measured if cases[side][k][MODE]["exact"]}
        for side in ("old", "new")
    }
    return {
        "scorer": score.scorer(),
        "macro": projects,
        "micro": {
            "became_exact": sorted(exact["new"] - exact["old"]),
            "stopped_exact": sorted(exact["old"] - exact["new"]),
            "not_measured": sorted(
                k
                for k, s in statuses.items()
                if k not in measured and s != ("skipped", "skipped")
            ),
        },
    }


def changes_text(changes):
    table = changes["scorer"]["table"][:10]
    lines = [f"both scored again now, with the table of names of one function {table}"]
    for name, project in changes["macro"].items():
        if not project["measured"]:
            lines.append(
                f"{name}: not measured (old {project['old']}, new {project['new']})"
            )
            continue
        counts = "  ".join(
            f"{label} {len(project[key])}" for key, label, _, _ in CHANGES
        )
        lines.append(f"{name}: {counts}")
        for key, label, _, _ in CHANGES:
            for caller, callee in project[key]:
                inside = score.check.ledger.in_package(callee, project["packages"])
                mark = "[in] " if inside else ""
                lines.append(f"  {label} {mark}{caller} -> {callee}")
    micro = changes["micro"]
    lines.append(
        f"micro: became exact {len(micro['became_exact'])}, "
        f"stopped being exact {len(micro['stopped_exact'])}, "
        f"not measured {len(micro['not_measured'])} (failed on one side)"
    )
    lines += [f"  + {case}" for case in micro["became_exact"]]
    lines += [f"  - {case}" for case in micro["stopped_exact"]]
    lines += [f"  ? {case}" for case in micro["not_measured"]]
    return lines


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=DESCRIPTION, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    commands = parser.add_subparsers(dest="command", required=True)
    measure_parser = commands.add_parser("run", help="run and score a checkout")
    measure_parser.add_argument("--checkout", type=Path, required=True)
    measure_parser.add_argument(
        "--flavour", choices=sorted(run.analyse.GENERATOR_BY_FLAVOUR), required=True
    )
    measure_parser.add_argument("--name", required=True)
    measure_parser.add_argument("--out", type=Path, default=run.OUT_DEFAULT)
    measure_parser.add_argument(
        "--timeout",
        type=float,
        default=run.TIMEOUT_SECONDS_DEFAULT,
        help="seconds per job",
    )
    measure_parser.add_argument("--python", default=sys.executable)
    measure_parser.add_argument("--hash-seed", type=int, default=0)
    measure_parser.add_argument("--allow-dirty", action="store_true")
    measure_parser.add_argument(
        "--micro-jobs", type=int, default=1, help="micro-benchmark cases at a time"
    )
    compare_parser = commands.add_parser("compare", help="compare two results")
    compare_parser.add_argument("old_dir", type=Path)
    compare_parser.add_argument("new_dir", type=Path)
    compare_parser.add_argument("--json", action="store_true", help="print JSON")
    args = parser.parse_args(argv)
    if args.command == "run":
        tool = run.Tool(
            args.name,
            args.flavour,
            args.checkout.resolve(),
            args.python,
            args.hash_seed,
        )
        try:
            data = measure(
                tool,
                args.out,
                timeout_seconds=args.timeout,
                allow_dirty=args.allow_dirty,
                micro_workers=args.micro_jobs,
            )
        except run.DirtyCheckout as error:
            parser.error(f"{error}; commit it, or pass --allow-dirty")
        print("\n".join(summary_lines(data)))
        print(f"result: {args.out / args.name / 'result.json'}")
        return 0
    changes = compare(args.old_dir, args.new_dir)
    if args.json:
        print(score.dumps(changes))
    else:
        print("\n".join(changes_text(changes)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
