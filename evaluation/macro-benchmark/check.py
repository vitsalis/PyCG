#!/usr/bin/env python3
"""Check the hand-written ground truth of the macro-benchmark projects.

    cd evaluation/macro-benchmark
    python -I check.py [PROJECT ...]           # check
    python -I check.py --write PROJECT ...      # regenerate the graph
    python -I check.py --skeleton PROJECT      # print a new ledger
    python -I check.py --report PROJECT        # report for auditors
    python -I check.py --report PROJECT --without-candidates
    python -I check.py --origin [PROJECT ...]  # traced and added edges

For each project (default: every project of projects.toml), print the size
of the analysed source and of its call sites, read with `ast`, and each
candidate callee of 50 or more sites (see README, "Writing a ground
truth"). The ground truth is the call-site ledger
ground-truth/PROJECT.ledger. If it exists,
check that:

- it has an entry for every call site that needs one, and every entry is a
  site of the source with the same text;
- every candidate of a site is a callee or rejected with a reason (or by a
  default rejection), a value site has a note, an explicit site has callees
  or a note, an exclusion names a node that is not a candidate, and nothing
  is undecided;
- ground-truth/PROJECT.json is the graph that the ledger gives (--write
  writes it), and every callee in the package is a module, function or
  lambda of the source;
- if dynamic/PROJECT.json exists, every edge of the trace is in the graph,
  or in ground-truth/PROJECT.rejected.json with a reason;
- ground-truth/PROJECT.added.json is the edges of the graph that the trace
  does not have, with the ledger sites that give them (--write writes it),
  and the graph is the traced edges without the rejected ones, plus the
  added edges.

--origin reads only the committed files (the graph, the added edges, the
trace and the rejected edges), checks the last point, and prints a table:
per project, where the edges of the graph come from.

The exit status is 1 if a check fails.
"""

import argparse
import importlib.util
import json
import re
from collections import Counter
from pathlib import Path


def _load(name):
    """Load a sibling script by path: its directory is not a package."""
    path = Path(__file__).resolve().parent / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"macro_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


macro_trace = _load("trace")
sites = _load("sites")
ledger = _load("ledger")

# The size report lists each candidate of at least this many sites.
_MANY_SITES = 50


def load_graph(path):
    """Read a graph: a JSON object that maps each node to a list of callees."""
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
    """Read {caller: {callee: reason}}: trace edges that are not package edges."""
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
    """Return (errors, statistics) for a graph, a trace and rejected edges."""
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
    confirmed = traced_names(trace).keys() & expected
    run = len(source.functions & set(trace["executed"]))
    statistics.append(
        f"trace: {len(dynamic)} edges; confirms {len(confirmed)} of {len(expected)} "
        f"ground-truth edges ({_percent(len(confirmed), len(expected))}); "
        f"{run} of {len(source.functions)} functions run "
        f"({_percent(run, len(source.functions))}); {len(rejected)} rejected"
    )
    return errors, statistics


def callee_names(trace, callee):
    """The names that resolve to a callee of the trace: its canonical name,
    then the other names (`aliases`) of a callee outside the package. A
    ground-truth callee matches the trace callee if it is one of them."""
    return (callee, *trace["aliases"].get(callee, ()))


def traced_names(trace):
    """{(caller, name): trace callee} for each edge of the trace, under each
    name of its callee (callee_names). A graph edge with one of these names
    is a traced edge, also where the graph names the callee by an alias."""
    names = {}
    for caller, callees in sorted(trace["edges"].items()):
        for callee in sorted(callees):
            for name in callee_names(trace, callee):
                names.setdefault((caller, name), callee)
    return names


def added_edges(parsed, trace, trace_name):
    """The content of ground-truth/PROJECT.added.json: the edges of the
    ledger's graph that the trace does not have.

    "edges" maps each caller to {callee: [site, ...]}: the ledger entries
    that give the edge, in site order. A site is written as the ledger
    writes it, after its module: `jmespath.parser 102:31 call  self._parse(x)`.
    "notes" maps each of these sites that has notes to its notes. "trace" is
    the path of the trace, or None for a project without a trace: then every
    edge is added.
    """
    traced = traced_names(trace) if trace is not None else {}
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


# A site of the added edges: the module, then the site line of the ledger.
_ADDED_SITE = re.compile(r"\S+ \d+:\d+ \S+(  .*)?$")


def load_added(path, trace_name):
    """Read the added edges of a project whose trace would be `trace_name`."""
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
                    isinstance(site, str) and _ADDED_SITE.match(site) for site in sites_
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
    if shape:  # a note belongs to a site of an added edge
        listed = {
            site
            for callees in data["edges"].values()
            for sites_ in callees.values()
            for site in sites_
        }
        shape = data["notes"].keys() <= listed
    if not shape:
        raise ValueError(
            f'{path.name}: expected {{"trace": "{trace_name}" or null, '
            '"edges": {caller: {callee: [site, ...]}}, "notes": {site: [note, ...]}}'
        )
    return data


def origin(graph, added, trace):
    """Check, edge by edge, that every edge of the graph is traced or added,
    and not both, and that every added edge is in the graph. (The rest of
    the identity, that the graph has each trace edge that is not rejected,
    is the check of _missing_edges.) Return (errors, the traced edges of the
    graph, the other edges of the graph)."""
    edges = {(caller, callee) for caller in graph for callee in graph[caller]}
    listed = {(caller, callee) for caller in added for callee in added[caller]}
    traced = traced_names(trace) if trace is not None else {}
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
    """The checks of the rejected edges, shared by the check and --origin.
    No rejected edge is in the graph. With a trace, see _missing_edges.
    Without a trace, nothing ran, so no edge can be a rejected trace edge."""
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
    """Trace edges that neither the graph nor the rejected edges have; trace
    edges that the graph has under one name and the rejected edges under
    another (a traced callee and its aliases are one callee); and rejected
    edges that the trace does not have."""
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
                # (The same name in both: "rejected edge is in the ground truth".)
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


def _summary(project, source):
    """The size of the source and of its sites, and the candidates that make
    many sites: the first ones to consider for a default rejection."""
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
    frequent = [(name, n) for name, n in counts.items() if n >= _MANY_SITES]
    if frequent:
        lines.append(f"  candidates at {_MANY_SITES} or more sites:")
        for name, n in sorted(frequent, key=lambda item: (-item[1], item[0])):
            lines.append(f"    {n} {name}")
    return lines


class _Files:
    """The ground-truth and trace files of a project."""

    def __init__(self, project, benchmark_dir):
        truth = benchmark_dir / "ground-truth"
        self.ledger = truth / f"{project.name}.ledger"
        self.graph = truth / f"{project.name}.json"
        self.rejected = truth / f"{project.name}.rejected.json"
        self.added = truth / f"{project.name}.added.json"
        self.trace_name = f"dynamic/{project.name}.json"  # as the added edges name it
        self.trace = benchmark_dir / self.trace_name

    def load_trace(self):
        if not self.trace.exists():
            return None
        return json.loads(self.trace.read_text(encoding="utf-8"))

    def load_rejected(self):
        return load_rejected(self.rejected) if self.rejected.exists() else {}

    def load_added(self):
        return load_added(self.added, self.trace_name)

    def trace_errors(self, added):
        """Whether the added edges know of the trace that exists, or not."""
        if added["trace"] is None and self.trace.exists():
            return [
                f"{self.added.name} says that the project has no trace, "
                f"but {self.trace_name} exists"
            ]
        if added["trace"] is not None and not self.trace.exists():
            return [
                f"{self.added.name} names the trace {self.trace_name}, "
                "which does not exist"
            ]
        return []


def _dumps(data):
    """The text of a generated file: sorted keys, stable formatting."""
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


def _missing_file(path):
    return f"{path.name} is missing (run check.py --write)"


def check_project(project, benchmark_dir, write=False):
    """Print the report for one project; return the number of errors."""
    source = sites.scan_source(project)
    if not source.modules:
        print(
            f"{project.name}: no source in {project.root} (submodule not checked out?)"
        )
        return 1
    print("\n".join(_summary(project, source)))
    files = _Files(project, benchmark_dir)
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
    added = added_edges(parsed, trace, files.trace_name)
    try:
        if write:
            files.graph.write_text(_dumps(graph), encoding="utf-8")
            files.added.write_text(_dumps(added), encoding="utf-8")
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
    except ValueError as exc:  # json.JSONDecodeError is a ValueError
        print(f"  error: {exc}")
        return 1
    more, statistics = check(project, source, graph, trace, rejected)
    errors += more
    if committed is not None:
        errors += files.trace_errors(committed)
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
    """(counts, errors) of one project, from its committed files only.

    counts is None without a ground truth, or if a file cannot be read; else
    (trace edges or None, rejected edges, traced edges of the graph, added
    edges, graph edges), each set of edges as (all, inside the package).
    """
    files = _Files(project, benchmark_dir)
    if not files.graph.exists():
        return None, []
    if not files.added.exists():
        return None, [_missing_file(files.added)]
    try:
        graph = load_graph(files.graph)
        added = files.load_added()
        rejected = files.load_rejected()
        trace = files.load_trace()
    except ValueError as exc:  # json.JSONDecodeError is a ValueError
        return None, [str(exc)]
    errors = files.trace_errors(added)
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
    """Print where the edges of each graph come from; return the number of
    errors. Graph edges = traced edges in the graph + added edges."""

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
    """Print the report for auditors (with no ledger: that of the skeleton).

    With `listed`, a default rejection, also list the sites that it decides;
    with `without_candidates`, the implicit sites without candidates.
    """
    source = sites.scan_source(project)
    files = _Files(project, benchmark_dir)
    if files.ledger.exists():
        text = files.ledger.read_text(encoding="utf-8")
    else:
        text = ledger.skeleton(source, project.name)
    parsed, syntax_errors = ledger.parse(text)
    if listed is not None and listed not in parsed.defaults:
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
    print("\n".join(_summary(project, source)))
    if syntax_errors:
        print(f"  the ledger has {len(syntax_errors)} syntax errors (run check.py)")
    for line in ledger.report(parsed, source, missing, listed, without_candidates):
        print(f"  {line}")
    return 0


def _skeleton(project, benchmark_dir):
    """A new ledger, with the header of the existing one: its comments and
    default rejections, before its first module."""
    source = sites.scan_source(project)
    files = _Files(project, benchmark_dir)
    defaults, header = {}, None
    if files.ledger.exists():
        text = files.ledger.read_text(encoding="utf-8")
        defaults = ledger.parse(text)[0].defaults
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
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
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
            print(_skeleton(projects[name], benchmark_dir), end="")
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
