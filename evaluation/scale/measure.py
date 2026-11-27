#!/usr/bin/env python3
import argparse
import hashlib
import importlib.util
import json
import signal
import sys
from pathlib import Path

SCALE = Path(__file__).resolve().parent
EVALUATION = SCALE.parent
OUTCOME_FINISHED = "finished"
OUTCOME_KILLED_BY_THE_CAP = "killed by the cap"
OUTCOME_CONTAINER_OUT_OF_MEMORY = "killed: the container ran out of memory"
OUTCOME_MACHINE_OUT_OF_MEMORY = "killed: the machine ran out of memory"
OUTCOME_KILLED = "killed by SIGKILL"
OUTCOMES_KILLED_FROM_OUTSIDE = (
    OUTCOME_CONTAINER_OUT_OF_MEMORY,
    OUTCOME_MACHINE_OUT_OF_MEMORY,
    OUTCOME_KILLED,
)
RUNNER_HEADROOM_MIB = 512
CGROUP_MEMORY_MAX = Path("/sys/fs/cgroup/memory.max")
CGROUP_MEMORY_EVENTS = Path("/sys/fs/cgroup/memory.events")
PROC_MEMINFO = Path("/proc/meminfo")
KIB_PER_MIB = 1 << 10
CGROUP_NO_LIMIT = "max"
MIB = 1 << 20
DESCRIPTION = """Measures a PyCG checkout on one package of the scale set
(evaluation/scale/README.md).

    python3 -I evaluation/scale/measure.py run --checkout PATH --name NAME \\
        --flavour new --package rich --out OUT --memory-mib 4096
    python3 -I evaluation/scale/measure.py compare BASE_RECORD RECORD
    python3 -I evaluation/scale/measure.py summary RESULT [--oracle ORACLE]
    python3 -I evaluation/scale/measure.py container-mib 4096

The container needs RUNNER_HEADROOM_MIB above the analysis's cap, so that
measure.py survives the analysis being killed and records it:
container-mib prints that size, and run refuses a smaller container."""


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


run = load("evaluation_run", EVALUATION / "common" / "run.py")
projects = load("scale_projects", SCALE / "projects.py")


class MeasureError(Exception):
    pass


def outcome_of(record, events_before, events_after):
    if record["status"] == "ok":
        return OUTCOME_FINISHED
    if record["status"] == "memory":
        return OUTCOME_KILLED_BY_THE_CAP
    if record["status"] == "crash" and record.get("exit_status") == -signal.SIGKILL:
        return killed_from_outside(events_before, events_after)
    return record["status"]


def killed_from_outside(events_before, events_after):
    if events_before is None or events_after is None:
        return OUTCOME_KILLED
    if events_after["oom"] > events_before["oom"]:
        return OUTCOME_CONTAINER_OUT_OF_MEMORY
    if events_after["oom_kill"] > events_before["oom_kill"]:
        return OUTCOME_MACHINE_OUT_OF_MEMORY
    return OUTCOME_KILLED


def memory_available_mib(meminfo):
    try:
        text = Path(meminfo).read_text(encoding="ascii")
    except FileNotFoundError:
        return None
    for line in text.splitlines():
        fields = line.split()
        if fields[0] == "MemAvailable:":
            assert fields[2:] == ["kB"], line
            return int(fields[1]) // KIB_PER_MIB
    raise MeasureError(f"{meminfo} has no MemAvailable")


def memory_events(path):
    try:
        text = Path(path).read_text(encoding="ascii")
    except FileNotFoundError:
        return None
    counts = {}
    for line in text.splitlines():
        name, value = line.split()
        counts[name] = int(value)
    assert {"oom", "oom_kill"} <= counts.keys(), path
    return counts


def record_path(out, name, package):
    return run.graph_file(Path(out) / name, f"scale/{package}.record")


def container_limit_mib(cgroup_memory_max):
    try:
        text = Path(cgroup_memory_max).read_text(encoding="ascii").strip()
    except FileNotFoundError:
        return None
    return None if text == CGROUP_NO_LIMIT else int(text) // MIB


def check_headroom(memory_mib, cgroup_memory_max):
    limit = container_limit_mib(cgroup_memory_max)
    if limit is not None and limit - memory_mib < RUNNER_HEADROOM_MIB:
        raise MeasureError(
            f"the container's memory limit of {limit} MiB leaves "
            f"{limit - memory_mib} MiB above the cap of {memory_mib} MiB; "
            f"measure.py needs {RUNNER_HEADROOM_MIB} MiB to record a run "
            "that the cap kills: give the container "
            f"{memory_mib + RUNNER_HEADROOM_MIB} MiB (container-mib)"
        )


def measure(
    checkout,
    name,
    project,
    out,
    memory_mib,
    timeout_seconds,
    python,
    flavour,
    cgroup_memory_max=CGROUP_MEMORY_MAX,
    cgroup_memory_events=CGROUP_MEMORY_EVENTS,
    meminfo=PROC_MEMINFO,
):
    check_headroom(memory_mib, cgroup_memory_max)
    version = run.git_version(checkout)
    if version["commit"] is None:
        raise MeasureError(f"{checkout} is not a git checkout")
    if version["dirty"]:
        raise MeasureError(f"{checkout} has changes; commit them")
    files = tuple(project.source_files())
    if not files:
        raise MeasureError(
            f"{project.directory} has no Python source: run make eval-inputs"
        )
    tool = run.Tool(name, flavour, Path(checkout).resolve(), python)
    job = run.Job(f"scale/{project.name}", files, project.root)
    graph = run.graph_file(Path(out) / name, job.key)
    available = memory_available_mib(meminfo)
    events_before = memory_events(cgroup_memory_events)
    record = run.run_job(tool, job, graph, timeout_seconds, memory_mib)
    events_after = memory_events(cgroup_memory_events)
    finished = record["status"] == "ok"
    result = {
        "package": project.name,
        "version": project.version,
        "archive_sha256": project.sha256,
        "tool": version,
        "flavour": flavour,
        "python": ".".join(map(str, run.python_version(python))),
        "hash_seed": tool.hash_seed,
        "memory_cap_mib": memory_mib,
        "memory_available_mib": available,
        "timeout": timeout_seconds,
        "files": len(files),
        "outcome": outcome_of(record, events_before, events_after),
        "seconds": record.get("seconds"),
        "wall_seconds": record.get("wall_seconds"),
        "peak_rss_mib": record.get("peak_rss_mib"),
        "graph_sha256": hashlib.sha256(graph.read_bytes()).hexdigest()
        if finished
        else None,
        "run": record,
    }
    path = record_path(out, name, project.name)
    path.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    return result


def shown(value):
    return "-" if value is None else str(value)


def change(before, now):
    if before is None or now is None or before == 0:
        return "-"
    return f"{(now - before) / before:+.1%}"


ROWS = (
    ("commit", lambda r: r["tool"]["commit"][:10]),
    ("outcome", lambda r: r["outcome"]),
    ("seconds", lambda r: r["seconds"]),
    ("wall seconds", lambda r: r["wall_seconds"]),
    ("peak MiB", lambda r: r["peak_rss_mib"]),
    ("MiB available at the start", lambda r: r.get("memory_available_mib")),
    ("graph SHA-256", lambda r: r["graph_sha256"]),
)
MEASURED_ROWS = ("seconds", "wall seconds", "peak MiB")


def heading(result):
    return (
        f"{result['package']} {result['version']}: {result['files']} files, "
        f"cap {result['memory_cap_mib']} MiB, flavour {result['flavour']}, "
        f"Python {result['python']}"
    )


def report(result):
    lines = [heading(result), "", "| | value |", "|---|---|"]
    lines += [f"| {label} | {shown(value(result))} |" for label, value in ROWS]
    if result["run"].get("error"):
        lines.append(f"| error | {result['run']['error']} |")
    return "\n".join(lines)


def comparison(base, now):
    if (base["package"], base["archive_sha256"]) != (
        now["package"],
        now["archive_sha256"],
    ):
        raise MeasureError("the two records are of different packages")
    for side, result in (("base", base), ("this", now)):
        if result["outcome"] in OUTCOMES_KILLED_FROM_OUTSIDE:
            raise MeasureError(
                f"the {side} run was killed ({result['outcome']}) and is not a "
                "measurement: run it again with the container's memory free"
            )
    lines = [heading(now), "", "| | base | this | change |", "|---|---|---|---|"]
    for label, value in ROWS:
        before, after = value(base), value(now)
        delta = change(before, after) if label in MEASURED_ROWS else ""
        lines.append(f"| {label} | {shown(before)} | {shown(after)} | {delta} |")
    if base["graph_sha256"] is None or now["graph_sha256"] is None:
        lines += ["", "no two call graphs to compare: a run did not finish"]
    elif base["graph_sha256"] == now["graph_sha256"]:
        lines += ["", "the call graphs are byte-identical"]
    else:
        lines += ["", "the call graphs differ"]
    return "\n".join(lines)


def read_record(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def records_in(result):
    found = sorted((Path(result) / "scale").glob("*.record.json"))
    return {record["package"]: record for record in map(read_record, found)}


def ratio(now, oracle):
    if now is None or oracle is None or oracle == 0:
        return "-"
    return f"{now / oracle:.3f}"


def graphs(now, oracle):
    if now["graph_sha256"] is None or oracle["graph_sha256"] is None:
        return "-"
    return "identical" if now["graph_sha256"] == oracle["graph_sha256"] else "differ"


def summary(result, oracle=None):
    measured = records_in(result)
    if not measured:
        raise MeasureError(f"{result} has no records of the scale set")
    oracles = {} if oracle is None else records_in(oracle)
    columns = ["package", "outcome", "seconds", "peak MiB"]
    if oracle is not None:
        columns += [
            "oracle outcome",
            "oracle seconds",
            "time ratio",
            "oracle peak MiB",
            "memory ratio",
            "graphs",
        ]
    columns.append("error")
    lines = [
        "| " + " | ".join(columns) + " |",
        "|" + "---|" * len(columns),
    ]
    for package, record in measured.items():
        cells = [
            package,
            record["outcome"],
            shown(record["seconds"]),
            shown(record["peak_rss_mib"]),
        ]
        if oracle is not None:
            base = oracles.get(package)
            if base is None:
                cells += ["not measured", "-", "-", "-", "-", "-"]
            else:
                cells += [
                    base["outcome"],
                    shown(base["seconds"]),
                    ratio(record["seconds"], base["seconds"]),
                    shown(base["peak_rss_mib"]),
                    ratio(record["peak_rss_mib"], base["peak_rss_mib"]),
                    graphs(record, base),
                ]
        cells.append(record["run"].get("error") or "")
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=DESCRIPTION, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    commands = parser.add_subparsers(dest="command", required=True)
    measuring = commands.add_parser("run", help="measure one package")
    measuring.add_argument("--checkout", type=Path, required=True)
    measuring.add_argument("--name", required=True, help="name of the results")
    measuring.add_argument(
        "--flavour", choices=sorted(run.analyse.FLAVOURS), required=True
    )
    measuring.add_argument("--package", required=True)
    measuring.add_argument("--out", type=Path, required=True)
    measuring.add_argument("--memory-mib", type=int, required=True)
    measuring.add_argument("--timeout", type=float, default=run.TIMEOUT_SECONDS_DEFAULT)
    measuring.add_argument("--python", default=sys.executable)
    comparing = commands.add_parser("compare", help="compare two records")
    comparing.add_argument("base", type=Path)
    comparing.add_argument("record", type=Path)
    summarising = commands.add_parser(
        "summary", help="one row for each package measured in a result"
    )
    summarising.add_argument("result", type=Path)
    summarising.add_argument("--oracle", type=Path)
    sizing = commands.add_parser(
        "container-mib", help="the memory of the container for a cap"
    )
    sizing.add_argument("memory_mib", type=int)
    args = parser.parse_args(argv)
    if args.command == "container-mib":
        print(args.memory_mib + RUNNER_HEADROOM_MIB)
        return 0
    try:
        if args.command == "compare":
            print(comparison(read_record(args.base), read_record(args.record)))
            return 0
        if args.command == "summary":
            print(summary(args.result, args.oracle))
            return 0
        found = projects.load_projects()
        if args.package not in found:
            raise MeasureError(
                f"{args.package} is not in the scale set: {', '.join(sorted(found))}"
            )
        result = measure(
            args.checkout,
            args.name,
            found[args.package],
            args.out,
            args.memory_mib,
            args.timeout,
            args.python,
            args.flavour,
        )
    except (MeasureError, ValueError, OSError) as error:
        print(f"measure.py: {error}", file=sys.stderr)
        return 1
    print(report(result))
    print(f"record: {record_path(args.out, args.name, args.package)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
