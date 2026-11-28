#!/usr/bin/env python3
import argparse
import importlib.util
import json
import re
from collections import Counter
from pathlib import Path

DESCRIPTION = """Checks the hand-written ground truths of the macro-benchmark
(evaluation/benchmark-rules.md, "Writing a ground truth"). The exit
status is 1 if a check fails.

    cd evaluation/macro-benchmark
    python -I check.py [PROJECT ...]           # check
    python -I check.py --write PROJECT ...      # regenerate the graph
    python -I check.py --skeleton PROJECT      # print a new ledger
    python -I check.py --report PROJECT        # report for auditors
    python -I check.py --report PROJECT --without-candidates
    python -I check.py --origin [PROJECT ...]  # traced and added edges"""


def _load(name):
    path = Path(__file__).resolve().parent / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"macro_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


macro_trace = _load("trace")
sites = _load("sites")
ledger = _load("ledger")

CANDIDATE_SITES_REPORTED_MIN = 50


def load_graph(path):
    graph = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(graph, dict) or not all(
        isinstance(callees, list) and all(isinstance(c, str) for c in callees)
        for callees in graph.values()
    ):
        raise ValueError(
            f"{path}: expected an object that maps names to lists of names"
        )
    return graph


def load_rejected(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not all(
        isinstance(callees, dict)
        and all(isinstance(r, str) and r.strip() for r in callees.values())
        for callees in data.values()
    ):
        raise ValueError(
            f"{path}: expected an object that maps callers to {{callee: reason}}"
        )
    return {
        (caller, callee): reason
        for caller, callees in data.items()
        for callee, reason in callees.items()
    }


def check(project, source, graph, trace=None, rejected=None):
    rejected = rejected or {}
    nodes = source.modules | source.functions
    errors = [
        f"unknown node: {key} is not a module or function of the source"
        for key in sorted(graph.keys() - nodes)
    ]
    errors += [f"missing node: {node}" for node in sorted(nodes - graph.keys())]
    expected = {
        (caller, callee) for caller, callees in graph.items() for callee in callees
    }
    for caller, callee in sorted(expected):
        if ledger.in_package(callee, project.package_names) and callee not in nodes:
            errors.append(f"unknown callee: {caller} -> {callee}")
    errors += rejection_errors(trace, expected, rejected)
    internal = sum(callee in nodes for _, callee in expected)
    statistics = [
        f"ground truth: {len(expected)} edges ({internal} internal, "
        f"{len(expected) - internal} outside)"
    ]
    if trace is None:
        statistics.append("trace: none, static checks only")
        return errors, statistics

    if trace["commit"] != project.pin:
        errors.append(
            f"the trace is of commit {trace['commit']}, "
            f"projects.toml pins {project.pin}"
        )
    traced = set(trace["modules"]) | set(trace["functions"])
    errors += [
        f"trace node is not in the source: {node}" for node in sorted(traced - nodes)
    ]
    dynamic = {(c, e) for c, callees in trace["edges"].items() for e in callees}
    confirmed = trace_callee_by_named_edge(trace).keys() & expected
    run = len(source.functions & set(trace["executed"]))
    statistics.append(
        f"trace: {len(dynamic)} edges; confirms {len(confirmed)} of {len(expected)} "
        f"ground-truth edges ({_percent(len(confirmed), len(expected))}); "
        f"{run} of {len(source.functions)} functions run "
        f"({_percent(run, len(source.functions))}); {len(rejected)} rejected"
    )
    return errors, statistics


def callee_names(trace, callee):
    return (callee, *trace["aliases"].get(callee, ()))


def trace_callee_by_named_edge(trace):
    names = {}
    for caller, callees in sorted(trace["edges"].items()):
        for callee in sorted(callees):
            for name in callee_names(trace, callee):
                names.setdefault((caller, name), callee)
    return names


def added_edges(parsed, trace, trace_name):
    traced = trace_callee_by_named_edge(trace) if trace is not None else {}
    edges, notes = {}, {}
    for entry in sorted(parsed.entries, key=lambda entry: entry.key):
        site = f"{entry.module} {entry.line}:{entry.column} {entry.kind}"
        site = f"{site}  {entry.text}".rstrip()
        for callee in dict.fromkeys(entry.callees):
            if (entry.scope, callee) in traced:
                continue
            edges.setdefault(entry.scope, {}).setdefault(callee, []).append(site)
            if entry.notes:
                notes[site] = list(entry.notes)
    trace_name = None if trace is None else trace_name
    return {"trace": trace_name, "edges": edges, "notes": notes}


_ADDED_SITE_PATTERN = re.compile(r"\S+ \d+:\d+ \S+(  .*)?$")


def load_added(path, trace_name):
    data = json.loads(path.read_text(encoding="utf-8"))
    shape = (
        isinstance(data, dict)
        and data.keys() == {"trace", "edges", "notes"}
        and data["trace"] in (None, trace_name)
        and isinstance(data["edges"], dict)
        and all(
            isinstance(callees, dict)
            and all(
                isinstance(sites_, list)
                and sites_
                and all(
                    isinstance(site, str) and _ADDED_SITE_PATTERN.match(site)
                    for site in sites_
                )
                for sites_ in callees.values()
            )
            for callees in data["edges"].values()
        )
        and isinstance(data["notes"], dict)
        and all(
            isinstance(notes, list) and notes and all(isinstance(n, str) for n in notes)
            for notes in data["notes"].values()
        )
    )
    if shape:
        sites_of_added_edges = {
            site
            for callees in data["edges"].values()
            for sites_ in callees.values()
            for site in sites_
        }
        shape = data["notes"].keys() <= sites_of_added_edges
    if not shape:
        raise ValueError(
            f'{path.name}: expected {{"trace": "{trace_name}" or null, '
            '"edges": {caller: {callee: [site, ...]}}, "notes": {site: [note, ...]}}'
        )
    return data


def origin(graph, added, trace):
    edges = {(caller, callee) for caller in graph for callee in graph[caller]}
    listed = {(caller, callee) for caller in added for callee in added[caller]}
    traced = trace_callee_by_named_edge(trace) if trace is not None else {}
    errors = [
        f"added edge is not in the graph: {caller} -> {callee}"
        for caller, callee in sorted(listed - edges)
    ]
    for caller, callee in sorted(listed & traced.keys()):
        name = traced[caller, callee]
        also = f" (traced as {name})" if name != callee else ""
        errors.append(f"added edge is in the trace: {caller} -> {callee}{also}")
    errors += [
        f"graph edge is neither traced nor added: {caller} -> {callee}"
        for caller, callee in sorted(edges - listed - traced.keys())
    ]
    in_graph = edges & traced.keys()
    return errors, in_graph, edges - in_graph


def rejection_errors(trace, expected, rejected):
    errors = [
        f"rejected edge is in the ground truth: {caller} -> {callee}"
        for caller, callee in sorted(rejected.keys() & expected)
    ]
    if trace is None:
        return errors + [
            f"rejected edge is not in the trace: {caller} -> {callee} "
            "(the project has no trace)"
            for caller, callee in sorted(rejected)
        ]
    return errors + _missing_edges(trace, expected, rejected)


def _missing_edges(trace, expected, rejected):
    errors, used = [], set()
    for caller, callees in sorted(trace["edges"].items()):
        for callee in callees:
            names = {(caller, name) for name in callee_names(trace, callee)}
            used |= names & rejected.keys()
            in_graph, in_rejected = names & expected, names & rejected.keys()
            if not in_graph and not in_rejected:
                also = sorted(callee_names(trace, callee)[1:])
                note = f" (also named {', '.join(also)})" if also else ""
                errors.append(f"missing edge: {caller} -> {callee}{note}")
            elif in_graph and in_rejected and not in_graph & in_rejected:
                graph_names = ", ".join(sorted(name for _, name in in_graph))
                rejected_names = ", ".join(sorted(name for _, name in in_rejected))
                errors.append(
                    f"trace edge is both in the graph and rejected: {caller} -> "
                    f"{callee} (in the graph as {graph_names}, "
                    f"rejected as {rejected_names})"
                )
    errors += [
        f"rejected edge is not in the trace: {caller} -> {callee}"
        for caller, callee in sorted(rejected.keys() - used)
    ]
    return errors


def _percent(part, whole):
    return f"{100 * part / whole:.1f}%" if whole else "-"


def _size_report_lines(project, source):
    needed = [site for site in source.sites if site.needs_entry]
    kinds = Counter(site.kind for site in needed)
    by_kind = ", ".join(f"{kinds[k]} {k}" for k in sites.KINDS if kinds[k])
    lines = [
        f"{project.name}: {len(source.modules)} modules, {len(source.functions)} "
        f"functions ({source.lambdas} lambdas), {source.classes} classes, "
        f"{source.call_sites} calls",
        f"  sites: {len(needed)} ({by_kind}); "
        f"{sum(bool(s.candidates) for s in needed)} with candidates "
        f"({sum(len(s.candidates) for s in needed)} candidates); "
        f"{sum(s.value for s in needed)} value sites",
    ]
    counts = Counter(name for site in needed for name in site.candidates)
    frequent = [
        (name, n) for name, n in counts.items() if n >= CANDIDATE_SITES_REPORTED_MIN
    ]
    if frequent:
        lines.append(f"  candidates at {CANDIDATE_SITES_REPORTED_MIN} or more sites:")
        for name, n in sorted(frequent, key=lambda item: (-item[1], item[0])):
            lines.append(f"    {n} {name}")
    return lines


class _ProjectFiles:
    def __init__(self, project, benchmark_dir):
        truth = benchmark_dir / "ground-truth"
        self.ledger = truth / f"{project.name}.ledger"
        self.graph = truth / f"{project.name}.json"
        self.rejected = truth / f"{project.name}.rejected.json"
        self.added = truth / f"{project.name}.added.json"
        self.trace_name_in_added_edges = f"dynamic/{project.name}.json"
        self.trace = benchmark_dir / self.trace_name_in_added_edges

    def load_trace(self):
        if not self.trace.exists():
            return None
        return json.loads(self.trace.read_text(encoding="utf-8"))

    def load_rejected(self):
        return load_rejected(self.rejected) if self.rejected.exists() else {}

    def load_added(self):
        return load_added(self.added, self.trace_name_in_added_edges)

    def trace_presence_errors(self, added):
        if added["trace"] is None and self.trace.exists():
            return [
                f"{self.added.name} says that the project has no trace, "
                f"but {self.trace_name_in_added_edges} exists"
            ]
        if added["trace"] is not None and not self.trace.exists():
            return [
                f"{self.added.name} names the trace "
                f"{self.trace_name_in_added_edges}, which does not exist"
            ]
        return []


def _generated_file_text(data):
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


def _missing_file(path):
    return f"{path.name} is missing (run check.py --write)"


def check_project(project, benchmark_dir, write=False):
    source = sites.scan_source(project)
    if not source.modules:
        print(
            f"{project.name}: no source in {project.root} (submodule not checked out?)"
        )
        return 1
    print("\n".join(_size_report_lines(project, source)))
    files = _ProjectFiles(project, benchmark_dir)
    if not files.ledger.exists():
        generated = [path for path in (files.graph, files.added) if path.exists()]
        for path in generated:
            print(f"  error: {path.name} has no ledger {files.ledger.name}")
        if generated:
            return 1
        print("  no ground truth")
        return 0
    parsed, errors = ledger.parse(files.ledger.read_text(encoding="utf-8"))
    errors += ledger.check(parsed, source, project.package_names)
    graph = ledger.graph(parsed, source)
    trace = files.load_trace()
    added = added_edges(parsed, trace, files.trace_name_in_added_edges)
    try:
        if write:
            files.graph.write_text(_generated_file_text(graph), encoding="utf-8")
            files.added.write_text(_generated_file_text(added), encoding="utf-8")
        else:
            if not files.graph.exists() or load_graph(files.graph) != graph:
                errors.append(
                    f"{files.graph.name} is not the graph of the ledger "
                    "(run check.py --write)"
                )
            if not files.added.exists():
                errors.append(_missing_file(files.added))
            elif json.loads(files.added.read_text(encoding="utf-8")) != added:
                errors.append(
                    f"{files.added.name} is not the added edges of the ledger "
                    "and the trace (run check.py --write)"
                )
        rejected = files.load_rejected()
        committed = files.load_added() if files.added.exists() else None
    except ValueError as exc:
        print(f"  error: {exc}")
        return 1
    more, statistics = check(project, source, graph, trace, rejected)
    errors += more
    if committed is not None:
        errors += files.trace_presence_errors(committed)
        errors += origin(graph, committed["edges"], trace)[0]
    for line in statistics:
        print(f"  {line}")
    for error in errors:
        print(f"  error: {error}")
    print(f"{project.name}: {len(errors) or 'no'} errors")
    return len(errors)


_ORIGIN_COLUMNS = (
    "Project",
    "Trace edges",
    "Rejected",
    "Traced edges in the graph (inside / outside)",
    "Added (inside / outside)",
    "Graph edges (inside / outside)",
)


def origin_project(project, benchmark_dir):
    files = _ProjectFiles(project, benchmark_dir)
    if not files.graph.exists():
        return None, []
    if not files.added.exists():
        return None, [_missing_file(files.added)]
    try:
        graph = load_graph(files.graph)
        added = files.load_added()
        rejected = files.load_rejected()
        trace = files.load_trace()
    except ValueError as exc:
        return None, [str(exc)]
    errors = files.trace_presence_errors(added)
    more, traced, other = origin(graph, added["edges"], trace)
    errors += more
    edges = traced | other
    errors += rejection_errors(trace, edges, rejected)
    if trace is not None:
        dynamic = sum(len(callees) for callees in trace["edges"].values())
    else:
        dynamic = None

    def split(pairs):
        inside = sum(ledger.in_package(c, project.package_names) for _, c in pairs)
        return len(pairs), inside

    return (dynamic, len(rejected), split(traced), split(other), split(edges)), errors


def origin_table(projects, benchmark_dir):

    def cell(edges):
        everything, inside = edges
        return f"{everything} ({inside} / {everything - inside})"

    rows, problems = [], []
    total = [0, 0, (0, 0), (0, 0), (0, 0)]
    for project in projects:
        counts, errors = origin_project(project, benchmark_dir)
        problems += [f"{project.name}: error: {error}" for error in errors]
        if counts is None:
            if not errors:
                rows.append([project.name, "no ground truth", "-", "-", "-", "-"])
            continue
        dynamic, rejected, traced, added, edges = counts
        if dynamic is None:
            rows.append([project.name, "no trace", "-", "-", cell(added), cell(edges)])
        else:
            rows.append(
                [
                    project.name,
                    dynamic,
                    rejected,
                    cell(traced),
                    cell(added),
                    cell(edges),
                ]
            )
        total[0] += dynamic or 0
        total[1] += rejected if dynamic is not None else 0
        for n, pair in enumerate((traced, added, edges), 2):
            total[n] = (total[n][0] + pair[0], total[n][1] + pair[1])
    rows.append(["**All**", total[0], total[1], *map(cell, total[2:])])
    lines = [_ORIGIN_COLUMNS, ["---"] * len(_ORIGIN_COLUMNS), *rows]
    for line in lines:
        print(f"| {' | '.join(map(str, line))} |")
    for problem in problems:
        print(problem)
    return len(problems)


def report_project(project, benchmark_dir, listed=None, without_candidates=False):
    source = sites.scan_source(project)
    files = _ProjectFiles(project, benchmark_dir)
    if files.ledger.exists():
        text = files.ledger.read_text(encoding="utf-8")
    else:
        text = ledger.skeleton(source, project.name)
    parsed, syntax_errors = ledger.parse(text)
    if listed is not None and listed not in parsed.default_rejections:
        print(f"{project.name}: {listed} is not rejected by default")
        return 1
    missing = []
    trace = files.load_trace()
    if trace is not None:
        graph = ledger.graph(parsed, source)
        expected = {(caller, callee) for caller in graph for callee in graph[caller]}
        prefix = "missing edge: "
        missing = [
            error.removeprefix(prefix)
            for error in _missing_edges(trace, expected, files.load_rejected())
            if error.startswith(prefix)
        ]
    print("\n".join(_size_report_lines(project, source)))
    if syntax_errors:
        print(f"  the ledger has {len(syntax_errors)} syntax errors (run check.py)")
    for line in ledger.report(parsed, source, missing, listed, without_candidates):
        print(f"  {line}")
    return 0


def _skeleton_keeping_ledger_header(project, benchmark_dir):
    source = sites.scan_source(project)
    files = _ProjectFiles(project, benchmark_dir)
    defaults, header = {}, None
    if files.ledger.exists():
        text = files.ledger.read_text(encoding="utf-8")
        defaults = ledger.parse(text)[0].default_rejections
        header = []
        for line in text.splitlines():
            if line.startswith("=="):
                break
            header.append(line)
        while header and not header[-1].strip():
            header.pop()
    title = f"{project.name} at {project.pin or 'an unpinned commit'}"
    return ledger.skeleton(source, title, defaults, header)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=DESCRIPTION, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("projects", nargs="*", help="default: every project")
    parser.add_argument(
        "--benchmark-dir",
        type=Path,
        default=macro_trace.BENCHMARK_DIR,
        help="the benchmark directory: projects.toml, projects/, ground-truth/, "
        "dynamic/ (default: evaluation/macro-benchmark/)",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--write",
        action="store_true",
        help="write the graph of each ledger, then check",
    )
    mode.add_argument(
        "--skeleton",
        action="store_true",
        help="print a ledger with every site undecided",
    )
    mode.add_argument(
        "--report", action="store_true", help="print the sites that auditors look at"
    )
    mode.add_argument(
        "--origin",
        action="store_true",
        help="from the committed files only, check that each graph is the "
        "traced edges without the rejected ones plus the added edges, and "
        "count them",
    )
    parser.add_argument(
        "--default",
        metavar="CANDIDATE",
        help="with --report: list the sites that this default rejection decides",
    )
    parser.add_argument(
        "--without-candidates",
        action="store_true",
        help="with --report: list the implicit sites without candidates, "
        "which the skeleton leaves out",
    )
    args = parser.parse_args(argv)
    if args.default and not args.report:
        parser.error("--default needs --report")
    if args.without_candidates and not args.report:
        parser.error("--without-candidates needs --report")
    try:
        projects = macro_trace.load_projects(args.benchmark_dir / "projects.toml")
    except ValueError as exc:
        parser.error(str(exc))
    unknown = sorted(set(args.projects) - projects.keys())
    if unknown:
        parser.error(f"unknown projects: {', '.join(unknown)}")
    names = args.projects or list(projects)
    benchmark_dir = args.benchmark_dir.resolve()
    if args.skeleton:
        for name in names:
            print(
                _skeleton_keeping_ledger_header(projects[name], benchmark_dir), end=""
            )
        return 0
    if args.report:
        statuses = [
            report_project(
                projects[name], benchmark_dir, args.default, args.without_candidates
            )
            for name in names
        ]
        return max(statuses)
    if args.origin:
        problems = origin_table([projects[name] for name in names], benchmark_dir)
        return 1 if problems else 0
    failed = [
        name
        for name in names
        if check_project(projects[name], benchmark_dir, write=args.write)
    ]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
