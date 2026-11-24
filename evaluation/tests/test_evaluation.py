"""Behaviour tests for evaluation/common/score.py, on small hand-made graphs
and fake PyCG checkouts written to tmp_path. No network is needed.

The scorer reuses macro-benchmark/check.py, which loads the tracer: it
needs Python 3.14 or later. tests/test_evaluation_runner.py tests the
runner on every version.
"""

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest

if sys.version_info < (3, 14):
    pytest.skip(
        "the scorer loads macro-benchmark/check.py, which needs Python 3.14",
        allow_module_level=True,
    )

_spec = importlib.util.spec_from_file_location(
    "evaluation_fakes", Path(__file__).resolve().parent / "evaluation_fakes.py"
)
fakes = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fakes)


_load = fakes.load
run, project, tool, fake_checkout = (
    fakes.run,
    fakes.project,
    fakes.tool,
    fakes.fake_checkout,
)
score = _load("common/score")

PACKAGES = ("pkg",)


def compare(tool, truth, **names):
    return score.compare(tool, truth, PACKAGES, score.Names(**names))


def counts(result, edge_set="all"):
    c = result[edge_set]
    return (c.tool, c.truth, c.tp, c.fp, c.fn)


# --------------------------------------------------------------------------
# Scorer: matching names
# --------------------------------------------------------------------------

TRACE = {
    "aliases": {"posixpath.join": ["os.path.join"], "yaml.main.load": ["yaml.load"]},
    "edges": {"pkg.f": ["posixpath.join", "yaml.main.load"]},
}


def test_an_alias_of_the_trace_matches_the_ground_truth_name():
    # yaml is not in the standard library: only the trace knows its names.
    tool = {"pkg.f": ["yaml.main.load"]}
    truth = {"pkg.f": ["yaml.load"]}
    ids = score.identities(TRACE)
    assert counts(compare(tool, truth, identities=ids)) == (1, 1, 1, 0, 0)
    # Without the trace, the two names are two functions.
    assert counts(compare(tool, truth)) == (1, 1, 0, 1, 1)


def test_one_function_under_two_names_counts_once():
    tool = {"pkg.f": ["os.path.join", "posixpath.join"]}
    truth = {"pkg.f": ["os.path.join"]}
    result = compare(tool, truth, identities=score.identities(TRACE))
    assert counts(result) == (1, 1, 1, 0, 0)
    assert result["false_positives"] == []


def test_a_name_that_the_trace_does_not_know_is_matched_by_string_equality():
    tool = {"pkg.f": ["json.dumps", "json.loads"]}
    truth = {"pkg.f": ["json.dumps", "json.load"]}
    result = compare(tool, truth, identities=score.identities(TRACE))
    assert counts(result) == (2, 2, 1, 1, 1)
    assert result["false_positives"] == [["pkg.f", "json.loads"]]
    assert result["false_negatives"] == [["pkg.f", "json.load"]]


def test_a_node_key_is_renamed_as_its_edges_are():
    truth = {"main": ["types.GeneratorType.send"], "types.GeneratorType.send": []}
    tool = {"main": ["<builtin>.generator.send"], "<builtin>.generator.send": []}
    result = score.score_micro_case(tool, truth)
    assert flags(result, "raw") == (False, False, False)
    assert flags(result, "normalised") == (True, True, True)


def test_a_name_of_two_traced_callees_identifies_neither():
    # Classes that a library creates at run time can share one qualified
    # name: each `type("Call", (Base,), {"__call__": staticmethod(f)})` is
    # another class named lib.Call, so lib.Call.__call__ names every f.
    trace = {"aliases": {"a.f": ["lib.Call.__call__"], "c.f": ["lib.Call.__call__"]}}
    ids = score.identities(trace)
    assert ids == {"a.f": "a.f", "c.f": "c.f"}
    # The shared name is matched by string equality only: it is neither.
    truth = {"pkg.g": ["a.f", "c.f"]}
    tool = {"pkg.g": ["lib.Call.__call__", "a.f"]}
    result = compare(tool, truth, identities=ids)
    assert result["false_positives"] == [["pkg.g", "lib.Call.__call__"]]
    assert result["false_negatives"] == [["pkg.g", "c.f"]]


def test_a_canonical_name_that_is_also_another_callees_alias_stays_itself():
    trace = {"aliases": {"a.f": ["b.f"], "b.f": ["c.f"]}}
    assert score.identities(trace) == {"a.f": "a.f", "c.f": "b.f"}


def test_the_shared_name_does_not_depend_on_the_order_of_the_trace():
    one = {"aliases": {"a.f": ["x.f", "s.f"], "c.f": ["s.f"]}}
    two = {"aliases": {"c.f": ["s.f"], "a.f": ["s.f", "x.f"]}}
    assert score.identities(one) == score.identities(two)
    assert score.identities(one) == {"a.f": "a.f", "x.f": "a.f", "c.f": "c.f"}


@pytest.mark.parametrize("owners", [3, 5])
def test_a_name_of_many_traced_callees_identifies_none(owners):
    callees = [f"m{i}.f" for i in range(owners)]
    expected = {callee: callee for callee in callees}
    for order in (callees, callees[::-1], callees[1:] + callees[:1]):
        trace = {"aliases": {callee: ["s.f"] for callee in order}}
        assert score.identities(trace) == expected


def test_a_name_listed_twice_for_one_callee_is_not_shared():
    trace = {"aliases": {"a.f": ["x.f", "x.f"]}}
    assert score.identities(trace) == {"a.f": "a.f", "x.f": "a.f"}


def test_a_shared_name_still_gets_the_table_of_names_of_one_function():
    # The trace gives the shared name to no callee; the table of names of
    # one standard-library function applies after the trace, as to any name.
    trace = {"aliases": {"a.f": ["os._Environ.get"], "c.f": ["os._Environ.get"]}}
    tool = {"pkg.g": ["os._Environ.get"]}
    truth = {"pkg.g": ["collections.abc.Mapping.get"]}
    result = compare(tool, truth, identities=score.identities(trace))
    assert counts(result)[2:] == (1, 0, 0)


# --------------------------------------------------------------------------
# Scorer: normalisation
# --------------------------------------------------------------------------

OWNERS = {"pkg.mod.C": "pkg.mod", "pkg.mod.f.D": "pkg.mod.f"}


def test_a_class_body_caller_is_renamed_only_when_normalised():
    tool = {"pkg.mod.C": ["typing.override"], "pkg.mod.f.D": ["pkg.mod.g"]}
    truth = {
        "pkg.mod": ["typing.override"],
        "pkg.mod.f": ["pkg.mod.g"],
        "pkg.mod.g": [],
    }
    raw = compare(tool, truth, owners=OWNERS, nodes=truth)
    assert counts(raw) == (2, 2, 0, 2, 2)
    assert raw["extra_nodes"] == ["pkg.mod.C", "pkg.mod.f.D"]
    normalised = compare(tool, truth, owners=OWNERS, nodes=truth, normalise=True)
    assert counts(normalised) == (2, 2, 2, 0, 0)
    assert normalised["extra_nodes"] == []


def test_a_class_that_is_also_a_node_keeps_its_name():
    # pkg.mod.C is a class and, in the ground truth, a function.
    tool = {"pkg.mod.C": ["x"]}
    truth = {"pkg.mod.C": [], "pkg.mod": ["x"]}
    result = compare(tool, truth, owners=OWNERS, nodes=truth, normalise=True)
    assert counts(result) == (1, 1, 0, 1, 1)


def test_a_class_as_callee_is_not_renamed():
    tool = {"pkg.mod": ["pkg.mod.C"]}
    truth = {"pkg.mod": ["pkg.mod"]}
    result = compare(tool, truth, owners=OWNERS, nodes=truth, normalise=True)
    assert counts(result) == (1, 1, 0, 1, 1)


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("<**PyStr**>.join", "<builtin>.str.join"),
        ("<**PyChar**>.isupper", "<builtin>.str.isupper"),
        ("<**PyList**>.append", "<builtin>.list.append"),
        ("<**PyDict**>.get", "<builtin>.dict.get"),
        ("<**PySet**>.add", "<builtin>.set.add"),
        ("<builtin>.generator.send", "types.GeneratorType.send"),
    ],
)
def test_names_of_builtin_types_are_renamed_only_when_normalised(old, new):
    tool, truth = {"pkg.f": [old]}, {"pkg.f": [new]}
    assert counts(compare(tool, truth)) == (1, 1, 0, 1, 1)
    assert counts(compare(tool, truth, normalise=True)) == (1, 1, 1, 0, 0)


@pytest.mark.parametrize(
    "name",
    [
        "<**PyFile**>.write",  # no single type
        "<**PyIter**>.__next__",
        "<**PyDict**>pop",  # not a method name of the scheme
        "pkg.<**PyStr**>.join",  # not a prefix
        "<builtin>.generators.send",
    ],
)
def test_other_names_are_not_renamed(name):
    names = score.Names(normalise=True)
    assert names.callee(name) == name


def test_the_normalisation_table_lists_every_rule():
    rules = [rule[0] for rule in score.NORMALISATIONS]
    assert rules == [
        "class-body caller",
        "2021 names of builtin types",
        "generator type",
    ]
    assert all(len(rule) == 4 and all(rule) for rule in score.NORMALISATIONS)


def test_class_owners_names_classes_as_the_benchmarks_do(tmp_path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text(
        dedent("""
            class A:
                class B:
                    pass

            def f():
                class C:
                    def m(self):
                        class D:
                            pass
                return C

            if True:
                class E(A):
                    pass
        """)
    )
    (tmp_path / "pkg" / "old.py").write_text("print 'Python 2'\n")
    # An invalid escape warns; pytest makes the warning an error.
    (tmp_path / "pkg" / "escape.py").write_text('PATTERN = "\\d"\nclass F:\n    pass\n')
    files = sorted(tmp_path.rglob("*.py"))
    assert score.class_owners(files, tmp_path) == {
        "pkg.A": "pkg",
        "pkg.A.B": "pkg",
        "pkg.f.C": "pkg.f",
        "pkg.f.C.m.D": "pkg.f.C.m",
        "pkg.E": "pkg",
        "pkg.escape.F": "pkg.escape",
    }


# --------------------------------------------------------------------------
# Scorer: edge sets, nodes, empty output
# --------------------------------------------------------------------------


def test_edges_are_split_by_where_the_callee_is():
    tool = {"pkg.f": ["pkg.g", "pkg.h", "<builtin>.len", "os.getcwd"]}
    truth = {"pkg.f": ["pkg.g", "pkg.k", "<builtin>.len"], "pkg.g": []}
    result = compare(tool, truth)
    assert counts(result, "inside") == (2, 2, 1, 1, 1)
    assert counts(result, "outside") == (2, 1, 1, 1, 0)
    assert counts(result, "all") == (4, 3, 2, 2, 1)


def test_a_package_name_prefix_is_not_the_package():
    result = compare({"pkg.f": ["pkgx.g"]}, {"pkg.f": []})
    assert counts(result, "outside") == (1, 0, 0, 1, 0)


def test_an_empty_tool_graph_has_no_precision_and_zero_recall():
    truth = {"pkg.f": ["pkg.g"], "pkg.g": []}
    result = compare({}, truth)
    c = result["all"]
    assert (c.tool, c.tp, c.fn) == (0, 0, 1)
    assert c.precision is None and c.recall == 0.0 and c.f1 is None
    assert result["missing_nodes"] == ["pkg.f", "pkg.g"]
    assert c.to_json()["precision"] is None


def test_a_caller_that_the_ground_truth_does_not_know_is_scored():
    tool = {"pkg.f": ["pkg.g"], "pkg.f.Helper": ["pkg.g"], "pkg.g": []}
    truth = {"pkg.f": ["pkg.g"], "pkg.g": [], "pkg.h": []}
    result = compare(tool, truth)
    assert counts(result) == (2, 1, 1, 1, 0)
    assert result["false_positives"] == [["pkg.f.Helper", "pkg.g"]]
    assert result["extra_nodes"] == ["pkg.f.Helper"]
    assert result["missing_nodes"] == ["pkg.h"]


def test_counts_add_up_and_give_f1():
    total = score.Counts(4, 5, 3) + score.Counts(1, 0, 0)
    assert total == score.Counts(5, 5, 3)
    assert (total.fp, total.fn) == (2, 2)
    assert total.f1 == pytest.approx(0.6)
    assert score.Counts(2, 2, 0).f1 == 0.0


def test_score_macro_reads_ground_truth_trace_runs_and_source(tmp_path):
    benchmark = tmp_path / "bench"
    source = benchmark / "projects" / "demo" / "src" / "demo"
    source.mkdir(parents=True)
    (source / "__init__.py").write_text(
        "import os\n\nclass C:\n    x = os.getcwd()\n\ndef f():\n    pass\n"
    )
    (benchmark / "projects.toml").write_text(
        dedent("""
            [demo]
            root = "src"
            packages = ["demo"]
            exclude = []
            dependencies = []
            pytest_args = []
            test_requirements = []

            [other]
            root = "."
            packages = ["other"]
            exclude = []
            dependencies = []
            pytest_args = []
            test_requirements = []
        """)
    )
    (benchmark / "ground-truth").mkdir()
    truth = {"demo": ["posix.getcwd"], "demo.f": []}
    (benchmark / "ground-truth" / "demo.json").write_text(json.dumps(truth))
    (benchmark / "dynamic").mkdir()
    trace = {"aliases": {"posix.getcwd": ["os.getcwd"]}, "edges": {}}
    (benchmark / "dynamic" / "demo.json").write_text(json.dumps(trace))
    tool_dir = tmp_path / "tool"
    (tool_dir / "macro").mkdir(parents=True)
    graph = {"demo.C": ["os.getcwd"], "demo.f": []}
    (tool_dir / "macro" / "demo.json").write_text(json.dumps(graph))

    scores = score.score_macro(tool_dir, config=benchmark / "projects.toml")
    assert list(scores) == ["demo"]  # no ground truth for `other`
    assert scores["demo"]["status"] == "ok"
    assert counts(scores["demo"]["raw"]) == (1, 1, 0, 1, 1)
    assert counts(scores["demo"]["normalised"]) == (1, 1, 1, 0, 0)

    # A run that crashed: its graph is not read, every edge is missed.
    (tool_dir / "macro" / "runs.json").write_text(
        json.dumps({"runs": {"macro/demo": {"status": "crash"}}})
    )
    scores = score.score_macro(tool_dir, config=benchmark / "projects.toml")
    assert scores["demo"]["status"] == "crash"
    assert counts(scores["demo"]["raw"]) == (0, 1, 0, 0, 1)


# --------------------------------------------------------------------------
# Scorer: micro-benchmark
# --------------------------------------------------------------------------

MICRO_TRUTH = {"main": ["main.f", "<builtin>.len"], "main.f": [], "<builtin>.len": []}


def flags(result, mode="raw"):
    return tuple(result[mode][flag] for flag in ("complete", "sound", "exact"))


@pytest.mark.parametrize("mode", ["raw", "normalised"])
def test_every_name_of_a_group_of_the_table_is_its_representative(mode):
    truth = {"pkg.f": ["collections.abc.Mapping.get", "pkg.g"], "pkg.g": []}
    tool = {"pkg.f": ["os._Environ.get", "pkg.g"], "pkg.g": []}
    result = score.score_macro_project(tool, truth, PACKAGES)[mode]
    outside = result["outside"]
    assert (outside.tp, outside.fp, outside.fn) == (1, 0, 0)
    assert result["inside"].tp == 1
    assert result["false_positives"] == result["false_negatives"] == []


def test_a_group_counts_once_on_one_side():
    truth = {"pkg.f": ["argparse._StoreTrueAction.__call__"]}
    tool = {
        "pkg.f": [
            "argparse._StoreConstAction.__call__",
            "argparse._StoreFalseAction.__call__",
        ]
    }
    assert counts(compare(tool, truth, packages=PACKAGES)) == (1, 1, 1, 0, 0)


def test_a_name_that_is_not_in_the_table_is_matched_as_written():
    # One object on Python 3.15 only, so not in the table; and dict's own get.
    for tool_name, truth_name in (
        ("urllib.parse.SplitResult.geturl", "urllib.parse.SplitResultBytes.geturl"),
        ("collections.abc.Mapping.get", "<builtin>.dict.get"),
        ("os.path.join", "posixpath.join"),
    ):
        tool, truth = {"pkg.f": [tool_name]}, {"pkg.f": [truth_name]}
        assert counts(compare(tool, truth, packages=PACKAGES)) == (1, 1, 0, 1, 1)


def test_a_name_of_the_analysed_package_never_stands_for_the_library(tmp_path):
    # The analysed package is called os; its _Environ.get is its own.
    truth = {"os.f": ["os._Environ.get"], "os._Environ.get": []}
    tool = {"os.f": ["collections.abc.Mapping.get"], "os._Environ.get": []}
    for mode in ("raw", "normalised"):
        result = score.score_macro_project(tool, truth, ("os",))[mode]
        assert (result["inside"].tp, result["inside"].fn) == (0, 1)
        assert (result["outside"].tp, result["outside"].fp) == (0, 1)
    # Nor is a library name mapped to a representative inside the package:
    # the analysed package is called collections.
    names = score.Names().for_packages(("collections",))
    assert names.callee("os._Environ.get") == "os._Environ.get"


def test_the_table_is_used_only_with_the_packages_of_a_comparison():
    names = score.Names().for_packages(PACKAGES)
    assert names.callee("os._Environ.get") == "collections.abc.Mapping.get"
    assert score.Names().callee("os._Environ.get") == "os._Environ.get"


SCORE_WITHOUT_IMPORTS = """
import builtins, importlib, importlib.util, json, sys
spec = importlib.util.spec_from_file_location("score", sys.argv[1])
score = importlib.util.module_from_spec(spec)
spec.loader.exec_module(score)

def refuse(*args, **kwargs):
    raise AssertionError("the scoring imported or looked up a module")

builtins.__import__ = refuse
importlib.import_module = refuse
names = score.Names().for_packages(("pkg",))
result = score.compare(
    {"pkg.f": ["os._Environ.get", "zoneinfo.ZoneInfo"]},
    {"pkg.f": ["collections.abc.Mapping.get"]},
    ("pkg",),
    names,
)
print(result["outside"].tp, result["outside"].fp, result["outside"].fn)
"""


def test_scoring_imports_and_looks_up_nothing(tmp_path):
    script = tmp_path / "score_without_imports.py"
    script.write_text(SCORE_WITHOUT_IMPORTS)
    done = subprocess.run(
        [sys.executable, "-I", str(script), str(score.__file__)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert done.stdout.split() == ["1", "1", "0"]


def test_every_result_records_the_table_that_scored_it(tmp_path):
    empty = tmp_path / "table.json"
    empty.write_text(json.dumps({"groups": []}))
    mapping, digest = score.same_function_table(empty)
    assert mapping == {} and digest != score.SAME_FUNCTION_SHA256
    assert score.scorer()["table"] == score.SAME_FUNCTION_SHA256
    committed = (Path(score.__file__).parent / "same_function.json").read_bytes()
    assert score.SAME_FUNCTION_SHA256 == hashlib.sha256(committed).hexdigest()


def test_a_micro_case_matches_two_names_of_one_function():
    truth = {"main": ["collections.abc.Mapping.get"]}
    tool = {"main": ["os._Environ.get"]}
    result = score.score_micro_case(tool, truth)["raw"]
    assert result["complete"] and result["sound"]


def test_a_micro_graph_with_an_extra_edge_is_sound_but_not_complete():
    tool = {**MICRO_TRUTH, "main.f": ["main.g"], "main.g": []}
    assert flags(score.score_micro_case(tool, MICRO_TRUTH)) == (False, True, False)


def test_a_micro_graph_with_a_missing_edge_is_complete_but_not_sound():
    tool = {**MICRO_TRUTH, "main": ["main.f"]}
    assert flags(score.score_micro_case(tool, MICRO_TRUTH)) == (True, False, False)


def test_an_exact_micro_graph_has_the_nodes_of_the_ground_truth():
    assert flags(score.score_micro_case(MICRO_TRUTH, MICRO_TRUTH)) == (True,) * 3
    tool = {k: v for k, v in MICRO_TRUTH.items() if k != "main.f"}
    assert flags(score.score_micro_case(tool, MICRO_TRUTH)) == (True, True, False)


def test_a_micro_case_without_a_graph_is_neither_complete_nor_sound():
    result = score.score_micro_case(None, MICRO_TRUTH)
    assert flags(result) == (False, False, False)
    assert result["raw"]["counts"]["all"] == score.Counts(0, 2, 0)
    assert result["raw"]["counts"]["inside"] == score.Counts(0, 1, 0)
    assert result["raw"]["counts"]["outside"] == score.Counts(0, 1, 0)


def test_a_micro_class_body_caller_is_exact_when_normalised():
    truth = {"main": ["main.deco"], "main.deco": []}
    tool = {"main": [], "main.C": ["main.deco"], "main.deco": []}
    result = score.score_micro_case(tool, truth, owners={"main.C": "main"})
    assert flags(result, "raw") == (False, False, False)
    assert flags(result, "normalised") == (True, True, True)


def test_micro_categories_count_skipped_and_failed_cases():
    ok = {"status": "ok", **score.score_micro_case(MICRO_TRUTH, MICRO_TRUTH)}
    crashed = {"status": "crash", **score.score_micro_case(None, MICRO_TRUTH)}
    cases = {"a/one": ok, "a/two": crashed, "a/three": {"status": "skipped"}}
    rows = score.micro_categories(cases, "raw")
    row = rows["a"]
    assert {k: row[k] for k in ("cases", "skipped", "failed", "exact")} == {
        "cases": 3,
        "skipped": 1,
        "failed": 1,
        "exact": 1,
    }
    assert row["counts"]["all"] == score.Counts(2, 4, 2)
    assert row["counts"]["inside"] == score.Counts(1, 2, 1)
    assert score.micro_total(rows)["counts"]["outside"] == score.Counts(1, 2, 1)
    assert score.micro_total(rows)["cases"] == 3


def test_score_micro_scores_each_case_with_its_run_status(tmp_path):
    snippets = tmp_path / "snippets"
    for case in ("a/ok", "a/new", "b/crash", "b/lost"):
        (snippets / case).mkdir(parents=True)
        (snippets / case / "callgraph.json").write_text(json.dumps(MICRO_TRUTH))
    tool_dir = tmp_path / "tool"
    (tool_dir / "micro" / "a").mkdir(parents=True)
    (tool_dir / "micro" / "a" / "ok.json").write_text(json.dumps(MICRO_TRUTH))
    (tool_dir / "micro" / "a" / "new.json").write_text(json.dumps(MICRO_TRUTH))
    runs = {
        "micro/a/ok": {"status": "ok"},
        "micro/a/new": {"status": "skipped"},
        "micro/b/crash": {"status": "crash"},
    }
    (tool_dir / "micro" / "runs.json").write_text(json.dumps({"runs": runs}))
    cases = score.score_micro(tool_dir, snippets)
    assert {k: v["status"] for k, v in cases.items()} == {
        "a/new": "skipped",
        "a/ok": "ok",
        "b/crash": "crash",
        "b/lost": "not run",
    }
    assert cases["a/new"] == {"status": "skipped"}
    assert flags(cases["a/ok"]) == (True, True, True)
    # The case has no module: no callee is inside it.
    assert cases["a/ok"]["raw"]["counts"]["inside"] == score.Counts(0, 0, 0)
    (snippets / "a" / "ok" / "main.py").write_text("")
    counts = score.score_micro(tool_dir, snippets)["a/ok"]["raw"]["counts"]
    assert counts["inside"] == score.Counts(1, 1, 1)  # main -> main.f
    assert counts["outside"] == score.Counts(1, 1, 1)  # main -> <builtin>.len
    assert flags(cases["b/crash"]) == (False, False, False)
    total = score.micro_total(score.micro_categories(cases, "raw"))
    assert (total["cases"], total["skipped"], total["failed"], total["exact"]) == (
        4,
        1,
        2,
        1,
    )


# --------------------------------------------------------------------------
# Review fixes: matching, provenance, missing graphs
# --------------------------------------------------------------------------


def test_aliases_do_not_apply_to_callers():
    # Callers are package functions, matched as written.
    ids = score.identities({"aliases": {"posixpath.join": ["os.path.join"]}})
    result = compare({"os.path.join": ["x"]}, {"posixpath.join": ["x"]}, identities=ids)
    assert counts(result) == (1, 1, 0, 1, 1)


def test_one_scored_edge_is_listed_once_with_its_spellings():
    ids = score.identities(TRACE)
    tool = {"pkg.f": ["os.path.join", "posixpath.join", "json.dumps"]}
    result = compare(tool, {"pkg.f": []}, identities=ids)
    assert counts(result) == (2, 0, 0, 2, 0)
    assert result["false_positives"] == [
        ["pkg.f", "json.dumps"],
        ["pkg.f", "posixpath.join"],
    ]
    assert result["spellings"] == {
        "pkg.f -> posixpath.join": [
            ["pkg.f", "os.path.join"],
            ["pkg.f", "posixpath.join"],
        ]
    }


def test_runs_of_two_commits_under_one_name_are_rejected(tmp_path):
    tool_dir = tmp_path / "tool"
    for benchmark, commit in (("macro", "a" * 40), ("micro", "b" * 40)):
        (tool_dir / benchmark).mkdir(parents=True)
        runs = {"tool": {"name": "tool", "commit": commit}, "runs": {}}
        (tool_dir / benchmark / "runs.json").write_text(json.dumps(runs))
    with pytest.raises(ValueError, match="macro and micro ran different tools"):
        score.tool_results(tool_dir, snippets=tmp_path / "no-snippets")


def test_a_successful_run_without_its_graph_is_a_failure(tmp_path):
    tool_dir = tmp_path / "tool"
    (tool_dir / "micro").mkdir(parents=True)
    runs = {"runs": {"micro/a/ok": {"status": "ok"}}}
    (tool_dir / "micro" / "runs.json").write_text(json.dumps(runs))
    snippets = tmp_path / "snippets"
    (snippets / "a" / "ok").mkdir(parents=True)
    (snippets / "a" / "ok" / "callgraph.json").write_text(json.dumps(MICRO_TRUTH))
    case = score.score_micro(tool_dir, snippets)["a/ok"]
    assert case["status"] == "missing graph"
    total = score.micro_total(score.micro_categories({"a/ok": case}, "raw"))
    assert total["failed"] == 1


# --------------------------------------------------------------------------
# Review fixes: the lookup of names
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("files", "root", "packages", "truth"),
    [
        # An initializer file names its package.
        (["pkg/__init__.py", "pkg/other.py"], ".", ["pkg/__init__.py"], "pkg"),
        (["single.py", "single_helper.py"], ".", ["single.py"], "single"),
        (["pkg/__init__.py", "pkg/mod.py"], ".", ["pkg"], "pkg.mod"),
        (["src/pkg/__init__.py"], "src", ["pkg"], "pkg"),
    ],
)
def test_the_package_name_of_an_entry_puts_its_edges_inside(
    tmp_path, files, root, packages, truth
):
    benchmark = tmp_path / "bench"
    for path in files:
        target = benchmark / "projects" / "demo" / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("def f():\n    pass\n")
    (benchmark / "projects.toml").write_text(
        f'[demo]\nroot = "{root}"\npackages = {json.dumps(packages)}\n'
        "exclude = []\ndependencies = []\npytest_args = []\ntest_requirements = []\n"
    )
    graph = {truth: [f"{truth}.f"], f"{truth}.f": []}
    (benchmark / "ground-truth").mkdir()
    (benchmark / "ground-truth" / "demo.json").write_text(json.dumps(graph))
    tool_dir = tmp_path / "tool"
    (tool_dir / "macro").mkdir(parents=True)
    helper = {"single_helper": ["single_helper.f"]} if "single.py" in packages else {}
    (tool_dir / "macro" / "demo.json").write_text(json.dumps({**graph, **helper}))
    result = score.score_macro(tool_dir, benchmark / "projects.toml")["demo"]["raw"]
    assert (result["inside"].tp, result["outside"].tp) == (1, 0)
    # A module that only shares a prefix with the package is outside it.
    assert result["outside"].fp == len(helper)
