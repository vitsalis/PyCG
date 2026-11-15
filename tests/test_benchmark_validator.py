"""Behaviour tests for micro-benchmark/validate.py."""

import importlib.util
import json
import sys
from pathlib import Path
from textwrap import dedent

import pytest

if sys.version_info < (3, 14):
    pytest.skip("the validator needs Python 3.14 or later", allow_module_level=True)

VALIDATOR_PATH = Path(__file__).resolve().parents[1] / "micro-benchmark" / "validate.py"
_spec = importlib.util.spec_from_file_location("benchmark_validate", VALIDATOR_PATH)
validate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(validate)


def make_case(root, files, graph=None):
    """Write a snippet directory from {relative path: source} and a call graph."""
    for name, source in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(dedent(source))
    if graph is not None:
        (root / "callgraph.json").write_text(json.dumps(graph))
    return root


def edges_of(root, files):
    result = validate.trace(make_case(root, files))
    assert result.error is None, result.error
    return result.edges


def test_nested_function_is_named_without_locals(tmp_path):
    result = validate.trace(
        make_case(
            tmp_path,
            {
                "main.py": """
                    def outer():
                        def inner():
                            pass
                        inner()

                    outer()
                """
            },
        )
    )
    assert result.edges == {("main", "main.outer"), ("main.outer", "main.outer.inner")}
    assert result.functions == {"main.outer", "main.outer.inner"}
    assert result.modules == {"main"}


def test_lambdas_are_numbered_per_scope_in_source_order(tmp_path):
    edges = edges_of(
        tmp_path,
        {
            "main.py": """
                first, second = lambda: 1, lambda: 2
                second()

                def func():
                    third = lambda: 3
                    third()
                    return lambda: 4

                func()()
            """
        },
    )
    assert edges == {
        ("main", "main.<lambda2>"),
        ("main", "main.func"),
        ("main.func", "main.func.<lambda1>"),
        ("main", "main.func.<lambda2>"),
    }


def test_lambda_numbering_follows_source_position_not_evaluation_order(tmp_path):
    edges = edges_of(
        tmp_path,
        {
            "main.py": """
                f = (lambda: 1) if (lambda: False)() else (lambda: 2)
                f()
                g, h = [lambda: 3 for _ in range(1)][0], (lambda: 4)
                h()
            """
        },
    )
    assert edges == {
        ("main", "main.<lambda2>"),
        ("main", "main.<lambda3>"),
        ("main", "<builtin>.range"),
        ("main", "main.<lambda5>"),
    }


def test_class_instantiation_calls_init_from_the_mro(tmp_path):
    edges = edges_of(
        tmp_path,
        {
            "main.py": """
                class Base:
                    def __init__(self):
                        pass

                class Child(Base):
                    def method(self):
                        pass

                class Plain:
                    pass

                Child().method()
                Plain()
            """
        },
    )
    assert edges == {("main", "main.Base.__init__"), ("main", "main.Child.method")}


def test_init_inherited_from_outside_the_snippet_is_named_by_its_owner(tmp_path):
    edges = edges_of(
        tmp_path,
        {
            "main.py": """
                from collections import UserList

                class Error(Exception):
                    pass

                class Items(UserList):
                    pass

                class Own(Exception):
                    def __init__(self):
                        super().__init__()

                Error()
                Items()
                Own()
            """
        },
    )
    assert edges == {
        ("main", "<builtin>.Exception.__init__"),  # named through Exception
        ("main", "collections.UserList.__init__"),
        ("main", "main.Own.__init__"),
        ("main.Own.__init__", "<builtin>.super"),
        ("main.Own.__init__", "<builtin>.BaseException.__init__"),
    }


def test_calls_in_class_body_belong_to_enclosing_scope(tmp_path):
    edges = edges_of(
        tmp_path,
        {
            "main.py": """
                def helper():
                    return 1

                class A:
                    value = helper()

                    @staticmethod
                    def method():
                        pass
            """
        },
    )
    assert edges == {("main", "main.helper"), ("main", "<builtin>.staticmethod")}


def test_builtin_functions_types_and_methods(tmp_path):
    edges = edges_of(
        tmp_path,
        {
            "main.py": """
                len([1])
                range(3)
                " ".join(["a"])
                {"a": 1}.items()
                str.upper("a")

                class MyList(list):
                    pass

                append = MyList().append  # a bound builtin method object
                append(1)
            """
        },
    )
    assert edges == {
        ("main", "<builtin>.len"),
        ("main", "<builtin>.range"),
        ("main", "<builtin>.str.join"),
        ("main", "<builtin>.dict.items"),
        ("main", "<builtin>.str.upper"),
        ("main", "<builtin>.list.__init__"),
        ("main", "<builtin>.list.append"),
    }


def test_implicit_interpreter_calls_to_builtins_are_ignored(tmp_path):
    edges = edges_of(
        tmp_path,
        {
            "main.py": """
                class Seq:
                    def __iter__(self):
                        return iter([])

                with open(__file__) as f:
                    pass
                f.__exit__(None, None, None)
                for item in Seq():
                    pass
                d = {}
                d["key"] = 1
            """
        },
    )
    assert edges == {
        ("main", "<builtin>.open"),
        ("main", "_io._IOBase.__exit__"),
        ("main", "main.Seq.__iter__"),
        ("main.Seq.__iter__", "<builtin>.iter"),
    }


def test_callback_from_builtin_belongs_to_the_caller_of_the_builtin(tmp_path):
    edges = edges_of(
        tmp_path,
        {
            "main.py": """
                def func(x):
                    return x

                def key(x):
                    return x

                def run():
                    return sorted([2, 1], key=key)

                list(map(func, [1, 2]))
                run()
            """
        },
    )
    assert edges == {
        ("main", "<builtin>.list"),
        ("main", "<builtin>.map"),
        ("main", "main.func"),
        ("main", "main.run"),
        ("main.run", "<builtin>.sorted"),
        ("main.run", "main.key"),
    }


def test_comprehension_and_generator_expression_belong_to_enclosing_scope(tmp_path):
    edges = edges_of(
        tmp_path,
        {
            "main.py": """
                def func(x):
                    return x

                def run():
                    return [func(x) for x in range(2)], sum(func(x) for x in range(2))

                run()
            """
        },
    )
    assert edges == {
        ("main", "main.run"),
        ("main.run", "main.func"),
        ("main.run", "<builtin>.range"),
        ("main.run", "<builtin>.sum"),
    }


def test_generator_edge_comes_from_the_call_site_not_the_consumer(tmp_path):
    edges = edges_of(
        tmp_path,
        {
            "main.py": """
                def gen():
                    yield 1

                def consume(it):
                    for _ in it:
                        pass

                consume(gen())
            """
        },
    )
    assert edges == {("main", "main.gen"), ("main", "main.consume")}


def test_multi_module_snippet_names_modules_by_path(tmp_path):
    result = validate.trace(
        make_case(
            tmp_path,
            {
                "main.py": """
                    from pkg.mod import func
                    func()
                """,
                "pkg/__init__.py": """
                    def setup():
                        pass

                    setup()
                """,
                "pkg/mod.py": """
                    def helper():
                        pass

                    def func():
                        helper()

                    helper()
                """,
            },
        )
    )
    assert result.error is None
    assert result.modules == {"main", "pkg", "pkg.mod"}
    assert result.edges == {
        ("pkg", "pkg.setup"),
        ("pkg.mod", "pkg.mod.helper"),
        ("main", "pkg.mod.func"),
        ("pkg.mod.func", "pkg.mod.helper"),
    }


def test_eval_calls_belong_to_the_scope_that_runs_eval(tmp_path):
    edges = edges_of(
        tmp_path,
        {
            "main.py": """
                def func():
                    pass

                eval("func() or len([])")
            """
        },
    )
    assert edges == {
        ("main", "<builtin>.eval"),
        ("main", "main.func"),
        ("main", "<builtin>.len"),
    }


def test_library_internals_are_not_recorded(tmp_path):
    edges = edges_of(
        tmp_path,
        {
            "main.py": """
                import json
                json.dumps([1])
            """
        },
    )
    assert edges == {("main", "json.dumps")}


def test_callees_outside_the_snippet_match_any_name_that_resolves_to_them(tmp_path):
    case = make_case(
        tmp_path,
        {
            "main.py": """
                import fractions
                import os
                import random
                import threading

                class Error(Exception):
                    pass

                class Worker(threading.Thread):
                    pass

                " ".join(["a"])
                {"a": 1}.items()
                dict.fromkeys(["a"])
                os.path.join("a", "b")
                random.random()  # a builtin method bound to a hidden instance
                random.shuffle([1, 2])  # a Python method bound to that instance
                fractions.Fraction.from_float(0.5)  # a Python classmethod
                Error()
                worker = Worker()
                worker.start()
                worker.join()
            """
        },
        graph={
            "main": [
                "<builtin>.str.join",
                "<builtin>.dict.items",
                "<builtin>.dict.fromkeys",
                "os.path.join",
                "random.random",
                "random.shuffle",
                "fractions.Fraction.from_float",
                "<builtin>.Exception.__init__",
                "threading.Thread.__init__",
                "threading.Thread.start",
                "threading.Thread.join",
            ],
            "<builtin>.str.join": [],
            "<builtin>.dict.items": [],
            "<builtin>.dict.fromkeys": [],
            "os.path.join": [],
            "random.random": [],
            "random.shuffle": [],
            "fractions.Fraction.from_float": [],
            "<builtin>.Exception.__init__": [],
            "threading.Thread.__init__": [],
            "threading.Thread.start": [],
            "threading.Thread.join": [],
        },
    )
    assert validate.validate(case) == []


def test_unmatched_outside_callee_is_shown_under_its_defining_name(tmp_path):
    case = make_case(
        tmp_path,
        {"main.py": "import os\nos.path.join('a', 'b')\n"},
        graph={"main": []},
    )
    assert validate.validate(case) == [
        "missing edge: main -> posixpath.join",
        "missing node: posixpath.join",
    ]


def test_two_names_for_one_callee_match_only_once(tmp_path):
    case = make_case(
        tmp_path,
        {"main.py": "import os\nos.path.join('a', 'b')\n"},
        graph={
            "main": ["os.path.join", "posixpath.join"],
            "os.path.join": [],
            "posixpath.join": [],
        },
    )
    assert validate.validate(case) == ["unobserved edge: main -> posixpath.join"]


def test_resolving_expected_names_imports_nothing(tmp_path):
    case = make_case(
        tmp_path,
        {
            "main.py": "import os\nos.path.join('a', 'b')\n",
            "marker.py": "open('imported', 'w').close()\ndef func():\n    pass\n",
        },
        # marker.func sorts first, so it is resolved while matching os.path.join.
        graph={
            "main": ["marker.func", "os.path.join"],
            "marker.func": [],
            "os.path.join": [],
        },
    )
    assert validate.validate(case) == ["unobserved edge: main -> marker.func"]
    assert not (case / "imported").exists()


def test_bare_raise_of_a_class_calls_its_inherited_init(tmp_path):
    edges = edges_of(
        tmp_path,
        {
            "main.py": """
                class Error(Exception):
                    pass

                class Outer:
                    class Inner(Exception):
                        pass

                def raise_class():
                    raise Error

                def raise_attribute():
                    raise Outer.Inner from None

                def raise_instance(error):
                    raise error

                calls = [
                    (raise_class, ()),
                    (raise_attribute, ()),
                    (raise_instance, (Error(),)),
                ]
                for func, arg in calls:
                    try:
                        func(*arg)
                    except Exception:
                        pass
            """
        },
    )
    assert edges == {
        ("main", "<builtin>.Exception.__init__"),
        ("main", "main.raise_class"),
        ("main", "main.raise_attribute"),
        ("main", "main.raise_instance"),
        ("main.raise_class", "<builtin>.Exception.__init__"),
        ("main.raise_attribute", "<builtin>.Exception.__init__"),
    }


def test_missing_external_module_is_stubbed_and_named_by_dotted_path(tmp_path):
    result = validate.trace(
        make_case(
            tmp_path,
            {
                "main.py": """
                    from ext import Cls, parent
                    import ext.sub as sub

                    class Child(parent):
                        def run(self):
                            self.parent_fn()

                    class Own(parent):
                        def __init__(self):
                            super().__init__()

                    Cls().fun()
                    Child().run()
                    Own()
                    sub.function()
                """
            },
        )
    )
    assert result.error is None
    assert result.stubbed == {"ext", "ext.sub"}
    assert result.edges == {
        ("main", "ext.Cls"),
        ("main", "ext.Cls.fun"),
        ("main", "ext.parent.__init__"),
        ("main", "main.Child.run"),
        ("main.Child.run", "ext.parent.parent_fn"),
        ("main", "main.Own.__init__"),
        ("main.Own.__init__", "<builtin>.super"),
        ("main.Own.__init__", "ext.parent.__init__"),
        ("main", "ext.sub.function"),
    }


def test_missing_submodule_of_a_real_package_is_an_error(tmp_path):
    result = validate.trace(
        make_case(tmp_path, {"main.py": "import pkg.missing\n", "pkg/__init__.py": ""})
    )
    assert result.error is not None
    assert "ModuleNotFoundError" in result.error


def test_snippet_that_raises_reports_error_and_keeps_earlier_edges(tmp_path):
    case = make_case(
        tmp_path,
        {
            "main.py": """
                def func():
                    pass

                func()
                raise ValueError("boom")
            """
        },
        graph={
            "main": ["main.func", "<builtin>.ValueError"],
            "main.func": [],
            "<builtin>.ValueError": [],
        },
    )
    result = validate.trace(case)
    assert result.edges == {("main", "main.func"), ("main", "<builtin>.ValueError")}
    assert result.error == "ValueError: boom (main.py:6)"
    assert validate.validate(case) == [
        "snippet did not finish: ValueError: boom (main.py:6)"
    ]


def test_snippet_output_and_clean_exit_do_not_matter(tmp_path):
    case = make_case(
        tmp_path,
        {"main.py": "import sys\nprint('noise')\nsys.exit(0)\n"},
        graph={
            "main": ["<builtin>.print", "sys.exit"],
            "<builtin>.print": [],
            "sys.exit": [],
        },
    )
    assert validate.validate(case) == []


def test_snippet_module_named_like_a_loaded_module_is_an_error(tmp_path):
    result = validate.trace(
        make_case(
            tmp_path, {"main.py": "import json\n", "json.py": "def f():\n    pass\n"}
        )
    )
    assert result.error == "snippet modules have the names of loaded modules: json"


def test_binary_output_does_not_break_the_run(tmp_path):
    case = make_case(
        tmp_path,
        {"main.py": "import sys\nsys.stdout.buffer.write(b'\\xff')\n"},
        graph={"main": ["_io.BufferedWriter.write"]},
    )
    result = validate.trace(case)
    assert result.error is None


def test_nonzero_exit_after_the_trace_is_written_is_an_error(tmp_path):
    result = validate.trace(
        make_case(
            tmp_path, {"main.py": "import atexit, os\natexit.register(os._exit, 5)\n"}
        )
    )
    assert result.error == "exit status 5"


def test_snippet_that_hangs_times_out(tmp_path):
    result = validate.trace(
        make_case(tmp_path, {"main.py": "while True:\n    pass\n"}), timeout=2
    )
    assert result.error == "timed out after 2s"


def test_correct_ground_truth_has_no_problems(tmp_path):
    case = make_case(
        tmp_path,
        {
            "main.py": """
                def func():
                    pass

                def unused():
                    pass

                func()
            """
        },
        graph={"main": ["main.func"], "main.func": [], "main.unused": []},
    )
    assert validate.validate(case) == []


def test_ground_truth_missing_an_edge_and_a_node_is_reported(tmp_path):
    case = make_case(
        tmp_path,
        {
            "main.py": """
                def func():
                    pass

                func()
                len([])
            """
        },
        graph={"main": ["main.func"], "main.func": []},
    )
    assert validate.validate(case) == [
        "missing edge: main -> <builtin>.len",
        "missing node: <builtin>.len",
    ]


def test_ground_truth_with_an_extra_edge_and_node_is_reported(tmp_path):
    case = make_case(
        tmp_path,
        {
            "main.py": """
                def func():
                    pass

                def other():
                    pass

                func()
            """
        },
        graph={
            "main": ["main.func", "main.other"],
            "main.func": [],
            "main.other": [],
            "main.ghost": [],
        },
    )
    assert validate.validate(case) == [
        "unobserved edge: main -> main.other",
        "unexpected node: main.ghost",
    ]


def test_case_without_ground_truth_or_with_bad_ground_truth(tmp_path):
    case = make_case(tmp_path, {"main.py": "pass\n"})
    assert validate.validate(case) == ["callgraph.json not found"]
    (case / "callgraph.json").write_text('{"main": "not a list"}')
    [problem] = validate.validate(case)
    assert problem.startswith("bad callgraph.json:")


def test_command_line_reports_failures_with_exit_status(tmp_path, capsys):
    good = make_case(tmp_path / "good", {"main.py": "pass\n"}, graph={"main": []})
    bad = make_case(tmp_path / "bad", {"main.py": "len([])\n"}, graph={"main": []})
    assert validate.main([str(good)]) == 0
    assert validate.main([str(good), str(bad)]) == 1
    out = capsys.readouterr().out
    assert "missing edge: main -> <builtin>.len" in out


def test_whole_benchmark_matches_its_ground_truth(capsys):
    status = validate.main([])
    assert status == 0, capsys.readouterr().out
