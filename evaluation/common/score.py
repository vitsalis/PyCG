"""Score call graphs against the ground truths of the micro- and macro-benchmark.

A tool directory has the layout that evaluation/common/run.py writes:
macro/<project>.json and micro/<category>/<case>.json, each a call graph
`{caller: [callees]}`, and optionally <benchmark>/runs.json with the status
of each run. Graphs of other tools in this layout are scored too; without
runs.json a missing graph counts as a failed run. tool_results gives the
scores of one tool directory.

Edges are compared as sets of (caller, callee) pairs, in two modes:
- raw: the names as the tool writes them. A callee outside the package
  that the project's trace knows (dynamic/<name>.json, `aliases`) is
  matched by the function it resolves to: every name that resolves to one
  traced function counts as that function, with check.callee_names. A
  callee outside the package that is in a group of the table
  same_function.json (names of one function of the standard library)
  counts as the group's representative. Any other name is matched by string
  equality. Nothing is imported or looked up while scoring.
- normalised: the same, after the renamings of NORMALISATIONS, applied to
  both graphs. None changes the function that an edge refers to.
"""

import ast
import hashlib
import importlib.util
import json
import platform
import re
import statistics
import sys
import warnings
from pathlib import Path
from typing import NamedTuple

HERE = Path(__file__).resolve().parent
EVALUATION = HERE.parent
REPO = EVALUATION.parent


def _load(name, path):
    """Load a script by path: neither evaluation/ nor macro-benchmark/ is a package."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


run = _load("evaluation_run", HERE / "run.py")
BENCHMARK = run.BENCHMARK
SNIPPETS = run.SNIPPETS
check = _load("macro_check", BENCHMARK / "check.py")
# JSON with each container of scalars on one line.
dumps = run.dumps

MODES = ("raw", "normalised")
# The headline is "inside": edges whose callee is in the analysed package.
# The names of outside callees depend on how a tool models code that it does
# not analyse; "all" is kept for comparison with PyCG's 2021 evaluation.
EDGE_SETS = ("inside", "outside", "all")

# The renamings of the normalised mode: (rule, what it renames, example,
# why the edge still refers to the same function). Applied to both graphs.
NORMALISATIONS = (
    (
        "class-body caller",
        "a caller that is a class of the analysed source (and not also a "
        "module or function) becomes the scope that runs the class body: "
        "the nearest enclosing function, else the module",
        "`tenacity.stop.stop_any -> typing.override` becomes "
        "`tenacity.stop -> typing.override`",
        "a class is not a node of the benchmarks; the calls of a class body "
        "(decorators of methods, default values, base classes) run when the "
        "enclosing scope runs. Only the caller changes; the callee is the same",
    ),
    (
        "2021 names of builtin types",
        "`<**PyStr**>.m`, `<**PyChar**>.m` become `<builtin>.str.m`; "
        "`<**PyList**>`, `<**PyDict**>`, `<**PySet**>`, `<**PyTuple**>` become "
        "`<builtin>.list`, `.dict`, `.set`, `.tuple`. `<**PyFile**>` and "
        "`<**PyIter**>` stay: they name no single type",
        "`<**PyStr**>.join` becomes `<builtin>.str.join`",
        "the 2021 ground truths name the method `m` of the builtin type `T` "
        "`<**PyT**>.m`; today's rule names it `<builtin>.T.m`",
    ),
    (
        "generator type",
        "`<builtin>.generator.m` becomes `types.GeneratorType.m`",
        "`<builtin>.generator.send` becomes `types.GeneratorType.send`",
        "`builtins` has no `generator`, so the name can only mean the type of "
        "generator objects; the benchmark names a type outside `builtins` by "
        "its public path, `types.GeneratorType`",
    ),
)

_OLD_BUILTIN_TYPES = {
    "PyStr": "str",
    "PyChar": "str",
    "PyList": "list",
    "PyDict": "dict",
    "PySet": "set",
    "PyTuple": "tuple",
}
_OLD_BUILTIN = re.compile(r"^<\*\*(\w+)\*\*>(?=\.|$)")
_GENERATOR = re.compile(r"^<builtin>\.generator(?=\.|$)")


# --------------------------------------------------------------------------
# Names
# --------------------------------------------------------------------------


def _parse(path):
    try:
        with warnings.catch_warnings():  # invalid escapes in old code
            warnings.simplefilter("ignore", SyntaxWarning)
            return ast.parse(Path(path).read_bytes())
    except (SyntaxError, ValueError):
        return None


def module_name(path, root):
    """The dotted name of a module file; a package __init__.py is the package."""
    parts = list(Path(path).resolve().relative_to(Path(root).resolve()).parts)
    parts[-1] = parts[-1].removesuffix(".py")
    if parts[-1] == "__init__" and len(parts) > 1:
        parts.pop()
    return ".".join(parts)


def class_owners(files, root):
    """{class: owner} for the classes defined in `files` (read with `ast`).

    The owner is the node whose code runs the class body: the nearest
    enclosing function, else the module. Names are relative to `root`. A
    file that does not parse (Python 2 code) is skipped."""
    owners = {}
    for path in files:
        tree = _parse(path)
        if tree is None:
            continue
        name = module_name(path, root)
        _add_classes(tree, name, name, owners)
    return owners


def _add_classes(node, scope, owner, owners):
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.ClassDef):
            name = f"{scope}.{child.name}"
            owners.setdefault(name, owner)
            _add_classes(child, name, owner, owners)
        elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            name = f"{scope}.{child.name}"
            _add_classes(child, name, name, owners)
        else:
            _add_classes(child, scope, owner, owners)


# Groups of names of one function of the standard library, each with its
# representative: a committed table, reviewed by a person, so that the
# scores depend on no interpreter (README, "How names are matched").
SAME_FUNCTION_TABLE = HERE / "same_function.json"


def same_function_table(path=SAME_FUNCTION_TABLE):
    """({name: representative} of the table, the SHA-256 of its bytes)."""
    data = Path(path).read_bytes()
    groups = json.loads(data.decode("utf-8"))["groups"]
    mapping = {name: g["representative"] for g in groups for name in g["names"]}
    return mapping, hashlib.sha256(data).hexdigest()


# The table that this scorer loaded, and the hash that every result records.
SAME_FUNCTION, SAME_FUNCTION_SHA256 = same_function_table()


class Names:
    """How the names of one comparison are matched.

    `identities` maps the name of an outside callee to the traced function
    that it resolves to; `owners` maps a class to the scope that runs its
    body; `nodes` are the modules and functions (a class-body caller is
    renamed only if the class name is not also one of them). With
    `packages` (for_packages), a callee outside them that is a name of a
    group of the table SAME_FUNCTION stands for the group's representative;
    a name in the packages never changes, and nor does a name whose
    representative would be in them. Callers are matched as written: the
    identities and the table apply to callees only. Without `normalise`, no
    renaming applies."""

    def __init__(
        self, identities=None, owners=None, nodes=(), normalise=False, packages=None
    ):
        self.identities = identities or {}
        self.owners = owners or {}
        self.nodes = frozenset(nodes)
        self.normalise = normalise
        self.packages = packages

    def for_packages(self, packages):
        """These names, with the table applied outside `packages`."""
        return Names(
            self.identities, self.owners, self.nodes, self.normalise, tuple(packages)
        )

    def caller(self, name):
        if not self.normalise:
            return name
        if name in self.owners and name not in self.nodes:
            return self.owners[name]
        return _rename(name)

    def callee(self, name):
        if self.normalise:
            name = _rename(name)
        name = self.identities.get(name, name)
        if self.packages is None or check.ledger.in_package(name, self.packages):
            return name
        found = SAME_FUNCTION.get(name)
        if found is None or check.ledger.in_package(found, self.packages):
            return name
        return found


def _rename(name):
    """The renamings of NORMALISATIONS that apply to any name."""
    name = _OLD_BUILTIN.sub(_new_builtin, name)
    return _GENERATOR.sub("types.GeneratorType", name)


def _new_builtin(match):
    new = _OLD_BUILTIN_TYPES.get(match[1])
    return f"<builtin>.{new}" if new else match[0]


def identities(trace):
    """{name: canonical name} for every name of a traced callee outside the package.

    The names of one callee are check.callee_names. A name that the trace
    gives to two or more callees identifies none of them and is left out,
    so the trace maps it to nothing (the table of names of one function
    still applies to it afterwards, as to any name): classes that a library
    creates at run time can share one qualified name (each `type("Call",
    (Base,), {"__call__": staticmethod(f)})` is another class of that
    name), and then `lib.Call.__call__` is a name of every `f`."""
    callees = {}
    for callee in trace.get("aliases", {}):
        for name in check.callee_names(trace, callee):
            callees.setdefault(name, set()).add(callee)
    return {
        name: next(iter(found))
        for name, found in sorted(callees.items())
        if len(found) == 1
    }


# --------------------------------------------------------------------------
# Counting
# --------------------------------------------------------------------------


class Counts(NamedTuple):
    tool: int
    truth: int
    tp: int

    @property
    def fp(self):
        return self.tool - self.tp

    @property
    def fn(self):
        return self.truth - self.tp

    @property
    def precision(self):
        return self.tp / self.tool if self.tool else None

    @property
    def recall(self):
        return self.tp / self.truth if self.truth else None

    @property
    def f1(self):
        p, r = self.precision, self.recall
        if p is None or r is None:
            return None
        return 2 * p * r / (p + r) if p + r else 0.0

    def __add__(self, other):
        return Counts(*(a + b for a, b in zip(self, other)))

    def to_json(self):
        def rounded(x):
            return None if x is None else round(x, 4)

        return {
            "tool": self.tool,
            "truth": self.truth,
            "tp": self.tp,
            "fp": self.fp,
            "fn": self.fn,
            "precision": rounded(self.precision),
            "recall": rounded(self.recall),
            "f1": rounded(self.f1),
        }


ZERO = Counts(0, 0, 0)


def _edges(graph, names):
    """{(caller, callee) matched: [(caller, callee) as written]}."""
    edges = {}
    for caller, callees in graph.items():
        for callee in callees:
            key = (names.caller(caller), names.callee(callee))
            edges.setdefault(key, []).append((caller, callee))
    return edges


def _nodes(graph, names):
    nodes = {names.caller(n) for n in graph}
    nodes |= {names.callee(c) for callees in graph.values() for c in callees}
    return nodes


def compare(tool, truth, packages, names):
    """Compare a tool graph with a ground truth of a package.

    Every tool edge is scored. "inside" are the edges whose callee is in
    `packages` (by name), "outside" the others. Returns the counts per edge
    set, the false positives and negatives as written in each graph, and
    the nodes: those of the ground truth that the tool lacks, and the
    tool's nodes in the package that the ground truth lacks."""
    names = names.for_packages(packages)
    tool_edges, truth_edges = _edges(tool, names), _edges(truth, names)
    result = split_counts(tool_edges.keys(), truth_edges.keys(), packages)
    tool_nodes, truth_nodes = _nodes(tool, names), set(truth)
    # One entry per scored edge, by its matched names; the spellings of an
    # edge whose names in the graph differ from the matched ones.
    false_positives = sorted(tool_edges.keys() - truth_edges.keys())
    false_negatives = sorted(truth_edges.keys() - tool_edges.keys())
    result["false_positives"] = [list(edge) for edge in false_positives]
    result["false_negatives"] = [list(edge) for edge in false_negatives]
    result["spellings"] = {}
    for edges, written in (
        (false_positives, tool_edges),
        (false_negatives, truth_edges),
    ):
        for edge in edges:
            spelt = sorted(set(written[edge]))
            if spelt != [edge]:
                result["spellings"][f"{edge[0]} -> {edge[1]}"] = [
                    list(w) for w in spelt
                ]
    result["missing_nodes"] = sorted(truth_nodes - tool_nodes)
    result["extra_nodes"] = sorted(
        n for n in tool_nodes - truth_nodes if check.ledger.in_package(n, packages)
    )
    return result


def split_counts(tool_edges, truth_edges, packages):
    """{edge set: Counts} of two sets of matched edges. "inside": the callee
    is in `packages` (by name)."""
    tool_edges, truth_edges = set(tool_edges), set(truth_edges)

    def inside(edge):
        return check.ledger.in_package(edge[1], packages)

    result = {}
    for edge_set, keep in (
        ("inside", inside),
        ("outside", lambda e: not inside(e)),
        ("all", lambda e: True),
    ):
        t = {e for e in tool_edges if keep(e)}
        g = {e for e in truth_edges if keep(e)}
        result[edge_set] = Counts(len(t), len(g), len(t & g))
    return result


# --------------------------------------------------------------------------
# Macro-benchmark
# --------------------------------------------------------------------------


def score_macro_project(tool, truth, packages, trace=None, owners=None):
    """The comparison of one project in both modes; `tool` None: no graph."""
    ids = identities(trace) if trace else {}
    result = {}
    for mode in MODES:
        names = Names(ids, owners, truth.keys(), normalise=mode == "normalised")
        result[mode] = compare(tool or {}, truth, packages, names)
    return result


def macro_projects(config=None):
    """For each project of `config` (default: macro-benchmark/projects.toml)
    with a ground truth: (name, project, truth, trace or None, class owners).
    The benchmark directory is the directory of `config`, with projects/,
    ground-truth/ and dynamic/."""
    config = Path(config or check.macro_trace.CONFIG_PATH).resolve()
    benchmark_dir = config.parent
    for name, project in check.macro_trace.load_projects(config).items():
        truth_path = benchmark_dir / "ground-truth" / f"{name}.json"
        if not truth_path.exists():
            continue
        trace_path = benchmark_dir / "dynamic" / f"{name}.json"
        trace = None
        if trace_path.exists():
            trace = json.loads(trace_path.read_text())
        owners = class_owners(project.source_files(), project.root)
        yield name, project, check.load_graph(truth_path), trace, owners


def score_macro(tool_dir, config=None):
    """Score the macro-benchmark graphs of a tool directory against the
    projects of `config` (projects.toml) that have a ground truth."""
    runs = _runs(tool_dir, "macro")
    scores = {}
    for name, project, truth, trace, owners in macro_projects(config):
        status, tool = _graph(tool_dir, f"macro/{name}", runs)
        scores[name] = {
            "status": status,
            **score_macro_project(tool, truth, project.package_names, trace, owners),
        }
    return scores


def macro_edges(tool_dir, config=None, mode="raw"):
    """{project: {"status", "tp", "fp", "fn": sets of matched (caller,
    callee), and "packages": the package names}} of a tool directory."""
    runs = _runs(tool_dir, "macro")
    result = {}
    for name, project, truth, trace, owners in macro_projects(config):
        status, tool = _graph(tool_dir, f"macro/{name}", runs)
        ids = identities(trace) if trace else {}
        names = Names(ids, owners, truth.keys(), normalise=mode == "normalised")
        names = names.for_packages(project.package_names)
        tool_edges = set(_edges(tool or {}, names))
        truth_edges = set(_edges(truth, names))
        result[name] = {
            "status": status,
            "tp": tool_edges & truth_edges,
            "fp": tool_edges - truth_edges,
            "fn": truth_edges - tool_edges,
            "packages": project.package_names,
        }
    return result


def _runs(tool_dir, benchmark):
    """The runs.json of a tool directory, or None."""
    path = Path(tool_dir) / benchmark / "runs.json"
    return json.loads(path.read_text()) if path.exists() else None


def _graph(tool_dir, key, runs):
    """(status, graph or None) of one job of a tool directory. A run that
    runs.json records as ok but whose graph is gone is "missing graph"."""
    path = Path(tool_dir) / f"{key}.json"
    status = runs["runs"].get(key, {}).get("status", "not run") if runs else None
    if status not in (None, "ok"):
        return status, None
    if path.exists():
        return "ok", check.load_graph(path)
    return ("missing graph" if status == "ok" else "no graph"), None


def summed(per_project, mode, edge_set):
    total = ZERO
    for result in per_project.values():
        total += result[mode][edge_set]
    return total


# --------------------------------------------------------------------------
# Micro-benchmark
# --------------------------------------------------------------------------


def score_micro_case(tool, truth, owners=None, packages=("main",)):
    """Complete, sound and exact for one case in both modes (tool None: no
    graph), and the edge counts per edge set (`packages`: the top-level
    modules of the case).

    As in PyCG's 2021 evaluation, a call graph is complete if every edge it
    reports is in the ground truth (no false positive) and sound if it
    reports every edge of the ground truth (no false negative), all edges
    counted. Exact:
    the graph equals the ground truth, nodes included, as
    tests/test_micro_benchmark.py compares them. Without a graph, all three
    are false."""
    result = {}
    for mode in MODES:
        names = Names(owners=owners, nodes=truth.keys(), normalise=mode == "normalised")
        names = names.for_packages(packages)
        counts = split_counts(_edges(tool or {}, names), _edges(truth, names), packages)
        ok = tool is not None
        result[mode] = {
            "complete": ok and counts["all"].fp == 0,
            "sound": ok and counts["all"].fn == 0,
            "exact": ok and _canonical(tool, names) == _canonical(truth, names),
            "counts": counts,
        }
    return result


def _canonical(graph, names):
    """The graph with matched names: keys that name one node are merged."""
    result = {}
    for caller, callees in graph.items():
        result.setdefault(names.caller(caller), set()).update(
            names.callee(c) for c in callees
        )
    return {node: sorted(callees) for node, callees in result.items()}


def score_micro(tool_dir, snippets=SNIPPETS):
    """Score the micro-benchmark graphs of a tool directory, per case."""
    runs = _runs(tool_dir, "micro")
    cases = {}
    for case in sorted(p for p in Path(snippets).glob("*/*") if p.is_dir()):
        key = f"{case.parent.name}/{case.name}"
        status, tool = _graph(tool_dir, f"micro/{key}", runs)
        if status == "skipped":
            cases[key] = {"status": status}
            continue
        truth = check.load_graph(case / "callgraph.json")
        files = sorted(case.rglob("*.py"))
        owners = class_owners(files, case)
        packages = tuple(sorted({module_name(f, case).split(".")[0] for f in files}))
        cases[key] = {
            "status": status,
            **score_micro_case(tool, truth, owners, packages),
        }
    return cases


def micro_categories(cases, mode):
    """Per category: cases, skipped, failed, complete, sound, exact, counts."""
    rows = {}
    for key, case in cases.items():
        row = rows.setdefault(
            key.split("/")[0],
            {
                "cases": 0,
                "skipped": 0,
                "failed": 0,
                "complete": 0,
                "sound": 0,
                "exact": 0,
                "counts": dict.fromkeys(EDGE_SETS, ZERO),
            },
        )
        row["cases"] += 1
        if case["status"] == "skipped":
            row["skipped"] += 1
            continue
        if case["status"] != "ok":
            row["failed"] += 1
        scored = case[mode]
        for flag in ("complete", "sound", "exact"):
            row[flag] += scored[flag]
        for edge_set in EDGE_SETS:
            row["counts"][edge_set] += scored["counts"][edge_set]
    return dict(sorted(rows.items()))


def micro_total(categories):
    total = {"cases": 0, "skipped": 0, "failed": 0, "complete": 0, "sound": 0}
    total |= {"exact": 0, "counts": dict.fromkeys(EDGE_SETS, ZERO)}
    for row in categories.values():
        for field in total:
            if field == "counts":
                for edge_set in EDGE_SETS:
                    total["counts"][edge_set] += row["counts"][edge_set]
            else:
                total[field] += row[field]
    return total


# --------------------------------------------------------------------------
# Results
# --------------------------------------------------------------------------


def scorer():
    """What scored a result: the SHA-256 of the table of names of one
    function that it used (`table`), which the counts depend on, and the
    interpreter (recorded only: the counts do not depend on it)."""
    return {
        "table": SAME_FUNCTION_SHA256,
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": f"{sys.platform} {platform.machine()}",
    }


def tool_results(tool_dir, config=None, snippets=SNIPPETS):
    """The scores of one tool directory, as JSON data (`config`: the
    projects.toml of the macro-benchmark)."""
    tool_dir = Path(tool_dir)
    data = {"tool": {"name": tool_dir.name}, "macro": None, "micro": None}
    data["scorer"] = scorer()
    tools = {}
    for benchmark in ("macro", "micro"):
        runs = _runs(tool_dir, benchmark)
        if runs:
            tools[benchmark] = runs["tool"]
            data[f"{benchmark}_runs"] = _run_records(runs, full=benchmark == "macro")
    if len({json.dumps(t, sort_keys=True) for t in tools.values()}) > 1:
        raise ValueError(
            f"{tool_dir}: macro and micro ran different tools: {tools['macro']} and "
            f"{tools['micro']}; run both again under one name"
        )
    if tools:
        data["tool"] = next(iter(tools.values()))
    if (tool_dir / "macro").is_dir():
        projects = score_macro(tool_dir, config)
        data["macro"] = {
            "projects": {
                name: {
                    "status": result["status"],
                    **{mode: _comparison_json(result[mode]) for mode in MODES},
                }
                for name, result in projects.items()
            },
            "summed": {
                mode: {
                    edge_set: summed(projects, mode, edge_set).to_json()
                    for edge_set in EDGE_SETS
                }
                for mode in MODES
            },
        }
    if (tool_dir / "micro").is_dir():
        cases = score_micro(tool_dir, snippets)
        data["micro"] = {
            "categories": {
                mode: {
                    name: _row_json(row)
                    for name, row in micro_categories(cases, mode).items()
                }
                for mode in MODES
            },
            "total": {
                mode: _row_json(micro_total(micro_categories(cases, mode)))
                for mode in MODES
            },
            "cases": {
                key: {
                    "status": case["status"],
                    **{
                        mode: {
                            flag: case[mode][flag]
                            for flag in ("complete", "sound", "exact")
                        }
                        | {
                            "tp": case[mode]["counts"]["all"].tp,
                            "fp": case[mode]["counts"]["all"].fp,
                            "fn": case[mode]["counts"]["all"].fn,
                        }
                        for mode in MODES
                        if mode in case
                    },
                }
                for key, case in cases.items()
            },
        }
    data["failed"] = failed_runs(data)
    return data


def failed_runs(data):
    """The runs that did not give a scored graph, from the scored statuses
    (a run that runs.json records as ok but whose graph is gone is one), with
    the error and its place from the run record when it has them."""
    records = dict((data.get("macro_runs") or {}).get("runs", {}))
    records.update((data.get("micro_runs") or {}).get("failed", {}))
    statuses = {}
    for name, project in (data.get("macro") or {}).get("projects", {}).items():
        statuses[f"macro/{name}"] = project["status"]
    for case, scored in (data.get("micro") or {}).get("cases", {}).items():
        statuses[f"micro/{case}"] = scored["status"]
    failed = []
    for key, status in sorted(statuses.items()):
        if status in ("ok", "skipped"):
            continue
        record = records.get(key, {})
        details = record if record.get("status") == status else {}
        failed.append(
            {"run": key, "status": status}
            | {k: details[k] for k in ("error", "where") if k in details}
        )
    return failed


def _run_records(runs, full):
    """How a benchmark ran: every run record, or (not `full`) a summary of
    the statuses, times and memory, with the runs that did not finish."""
    result = {
        key: runs.get(key)
        for key in ("tool", "benchmark", "python", "hash_seed", "timeout")
    }
    records = runs["runs"]
    if full:
        return result | {"runs": records}
    finished = [r for r in records.values() if "seconds" in r]
    seconds = [r["seconds"] for r in finished]
    statuses = {}
    for record in records.values():
        statuses[record["status"]] = statuses.get(record["status"], 0) + 1
    return result | {
        "statuses": dict(sorted(statuses.items())),
        "seconds": {
            "total": round(sum(seconds), 3),
            "median": statistics.median(seconds) if seconds else None,
            "max": max(seconds, default=None),
        },
        "peak_rss_mib": max((r["peak_rss_mib"] for r in finished), default=None),
        "failed": {
            key: record
            for key, record in records.items()
            if record["status"] not in ("ok", "skipped")
        },
    }


def _comparison_json(result):
    return {
        **{edge_set: result[edge_set].to_json() for edge_set in EDGE_SETS},
        **{
            field: result[field]
            for field in (
                "missing_nodes",
                "extra_nodes",
                "false_positives",
                "false_negatives",
                "spellings",
            )
        },
    }


def _row_json(row):
    return {
        **{k: v for k, v in row.items() if k != "counts"},
        **{edge_set: row["counts"][edge_set].to_json() for edge_set in EDGE_SETS},
    }
