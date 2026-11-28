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

COMMON = Path(__file__).resolve().parent


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


run = _load("evaluation_run", COMMON / "run.py")
BENCHMARK = run.BENCHMARK
SNIPPETS = run.SNIPPETS
check = _load("macro_check", BENCHMARK / "check.py")
dumps = run.dumps

MODES = ("raw", "normalised")
EDGE_SETS = ("inside", "outside", "all")


class Normalisation(NamedTuple):
    rule: str
    renames: str
    example: str
    why_the_edge_keeps_its_function: str


NORMALISATIONS = (
    Normalisation(
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
    Normalisation(
        "2021 names of builtin types",
        "`<**PyStr**>.m`, `<**PyChar**>.m` become `<builtin>.str.m`; "
        "`<**PyList**>`, `<**PyDict**>`, `<**PySet**>`, `<**PyTuple**>` become "
        "`<builtin>.list`, `.dict`, `.set`, `.tuple`. `<**PyFile**>` and "
        "`<**PyIter**>` stay: they name no single type",
        "`<**PyStr**>.join` becomes `<builtin>.str.join`",
        "the 2021 ground truths name the method `m` of the builtin type `T` "
        "`<**PyT**>.m`; today's rule names it `<builtin>.T.m`",
    ),
    Normalisation(
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


def _parse_ignoring_syntax_warnings(path):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            return ast.parse(Path(path).read_bytes())
    except SyntaxError, ValueError:
        return None


def module_name(path, root):
    parts = list(Path(path).resolve().relative_to(Path(root).resolve()).parts)
    parts[-1] = parts[-1].removesuffix(".py")
    if parts[-1] == "__init__" and len(parts) > 1:
        parts.pop()
    return ".".join(parts)


def class_owners(files, root):
    owners = {}
    for path in files:
        tree = _parse_ignoring_syntax_warnings(path)
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


SAME_FUNCTION_TABLE_PATH = COMMON / "same_function.json"


def same_function_table(path=SAME_FUNCTION_TABLE_PATH):
    data = Path(path).read_bytes()
    groups = json.loads(data.decode("utf-8"))["groups"]
    representative_by_name = {
        name: g["representative"] for g in groups for name in g["names"]
    }
    return representative_by_name, hashlib.sha256(data).hexdigest()


SAME_FUNCTION_REPRESENTATIVE_BY_NAME, SAME_FUNCTION_SHA256 = same_function_table()


class Names:
    def __init__(
        self, identities=None, owners=None, nodes=(), normalise=False, packages=None
    ):
        self.identities = identities or {}
        self.owners = owners or {}
        self.nodes = frozenset(nodes)
        self.normalise = normalise
        self.packages = packages

    def for_packages(self, packages):
        return Names(
            self.identities, self.owners, self.nodes, self.normalise, tuple(packages)
        )

    def caller(self, name):
        if not self.normalise:
            return name
        if name in self.owners and name not in self.nodes:
            return self.owners[name]
        return _rename_by_normalisations_of_any_name(name)

    def callee(self, name):
        if self.normalise:
            name = _rename_by_normalisations_of_any_name(name)
        name = self.identities.get(name, name)
        if self.packages is None or check.ledger.in_package(name, self.packages):
            return name
        found = SAME_FUNCTION_REPRESENTATIVE_BY_NAME.get(name)
        if found is None or check.ledger.in_package(found, self.packages):
            return name
        return found


def _rename_by_normalisations_of_any_name(name):
    name = _OLD_BUILTIN.sub(_new_builtin, name)
    return _GENERATOR.sub("types.GeneratorType", name)


def _new_builtin(match):
    new = _OLD_BUILTIN_TYPES.get(match[1])
    return f"<builtin>.{new}" if new else match[0]


def identities(trace):
    callees = {}
    for callee in trace.get("aliases", {}):
        for name in check.callee_names(trace, callee):
            callees.setdefault(name, set()).add(callee)
    return {
        name: next(iter(found))
        for name, found in sorted(callees.items())
        if len(found) == 1
    }


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


def _written_edges_by_matched_edge(graph, names):
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
    names = names.for_packages(packages)
    tool_edges, truth_edges = (
        _written_edges_by_matched_edge(tool, names),
        _written_edges_by_matched_edge(truth, names),
    )
    result = split_counts(tool_edges.keys(), truth_edges.keys(), packages)
    tool_nodes, truth_nodes = _nodes(tool, names), set(truth)
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


def score_macro_project(tool, truth, packages, trace=None, owners=None):
    ids = identities(trace) if trace else {}
    result = {}
    for mode in MODES:
        names = Names(ids, owners, truth.keys(), normalise=mode == "normalised")
        result[mode] = compare(tool or {}, truth, packages, names)
    return result


def macro_projects(config=None):
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
    runs = _runs_or_none(tool_dir, "macro")
    scores = {}
    for name, project, truth, trace, owners in macro_projects(config):
        status, tool = _status_and_graph(tool_dir, f"macro/{name}", runs)
        scores[name] = {
            "status": status,
            **score_macro_project(tool, truth, project.package_names, trace, owners),
        }
    return scores


def macro_edges(tool_dir, config=None, mode="raw"):
    runs = _runs_or_none(tool_dir, "macro")
    result = {}
    for name, project, truth, trace, owners in macro_projects(config):
        status, tool = _status_and_graph(tool_dir, f"macro/{name}", runs)
        ids = identities(trace) if trace else {}
        names = Names(ids, owners, truth.keys(), normalise=mode == "normalised")
        names = names.for_packages(project.package_names)
        tool_edges = set(_written_edges_by_matched_edge(tool or {}, names))
        truth_edges = set(_written_edges_by_matched_edge(truth, names))
        result[name] = {
            "status": status,
            "tp": tool_edges & truth_edges,
            "fp": tool_edges - truth_edges,
            "fn": truth_edges - tool_edges,
            "packages": project.package_names,
        }
    return result


def _runs_or_none(tool_dir, benchmark):
    path = Path(tool_dir) / benchmark / "runs.json"
    return json.loads(path.read_text()) if path.exists() else None


def _status_and_graph(tool_dir, key, runs):
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


def score_micro_case(tool, truth, owners=None, packages=("main",)):
    result = {}
    for mode in MODES:
        names = Names(owners=owners, nodes=truth.keys(), normalise=mode == "normalised")
        names = names.for_packages(packages)
        counts = split_counts(
            _written_edges_by_matched_edge(tool or {}, names),
            _written_edges_by_matched_edge(truth, names),
            packages,
        )
        ok = tool is not None
        result[mode] = {
            "complete": ok and counts["all"].fp == 0,
            "sound": ok and counts["all"].fn == 0,
            "exact": ok
            and _graph_with_matched_names(tool, names)
            == _graph_with_matched_names(truth, names),
            "counts": counts,
        }
    return result


def _graph_with_matched_names(graph, names):
    result = {}
    for caller, callees in graph.items():
        result.setdefault(names.caller(caller), set()).update(
            names.callee(c) for c in callees
        )
    return {node: sorted(callees) for node, callees in result.items()}


def score_micro(tool_dir, snippets=SNIPPETS):
    runs = _runs_or_none(tool_dir, "micro")
    cases = {}
    for case in sorted(p for p in Path(snippets).glob("*/*") if p.is_dir()):
        key = f"{case.parent.name}/{case.name}"
        status, tool = _status_and_graph(tool_dir, f"micro/{key}", runs)
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


def scorer():
    return {
        "table": SAME_FUNCTION_SHA256,
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": f"{sys.platform} {platform.machine()}",
    }


def tool_results(tool_dir, config=None, snippets=SNIPPETS):
    tool_dir = Path(tool_dir)
    data = {"tool": {"name": tool_dir.name}, "macro": None, "micro": None}
    data["scorer"] = scorer()
    tools = {}
    for benchmark in ("macro", "micro"):
        runs = _runs_or_none(tool_dir, benchmark)
        if runs:
            tools[benchmark] = runs["tool"]
            data[f"{benchmark}_runs"] = _run_records(
                runs, every_record=benchmark == "macro"
            )
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


def _run_records(runs, every_record):
    result = {key: runs.get(key) for key in ("tool", "benchmark", "python", "timeout")}
    records = runs["runs"]
    if every_record:
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
