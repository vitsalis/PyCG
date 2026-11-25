import textwrap

from programs import call_graph, callees, main_graph

DEFINITIONS = """
def f(): pass
def g(): pass
def h(): pass
"""


def graph_of(tmp_path, source):
    return main_graph(tmp_path, DEFINITIONS + textwrap.dedent(source))


def test_a_read_gets_the_last_definition_before_it(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        def before():
            handler = f
            handler = g
            handler()
        def after():
            handler = f
            handler()
            handler = g
        """,
    )

    assert callees(graph, "main.before") == ["main.g"]
    assert callees(graph, "main.after") == ["main.f"]


def test_module_names_read_by_the_module_follow_its_statements(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        handler = f
        handler()
        handler = g
        """,
    )

    assert callees(graph, "main") == ["main.f"]


def test_a_function_reads_every_definition_of_a_module_name(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "main.py": DEFINITIONS
            + """
handler = f
def run():
    handler()
handler = g
""",
            "other.py": """
from main import handler
handler()
""",
        },
        entry_points=("main.py", "other.py"),
    )

    assert callees(graph, "main.run") == ["main.f", "main.g"]
    assert callees(graph, "other") == ["main.f", "main.g"]


def test_a_closure_reads_every_definition_and_its_scope_reads_in_order(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        def outer():
            handler = f
            def inner():
                handler()
            handler()
            handler = g
            return inner
        """,
    )

    assert callees(graph, "main.outer.inner") == ["main.f", "main.g"]
    assert callees(graph, "main.outer") == ["main.f"]


def test_a_name_rebound_through_global_or_nonlocal_keeps_every_value(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        handler = f
        def install():
            global handler
            handler = g
        handler()
        def outer():
            local = f
            def swap():
                nonlocal local
                local = g
            local()
        """,
    )

    assert callees(graph, "main") == ["main.f", "main.g"]
    assert callees(graph, "main.outer") == ["main.f", "main.g"]


def test_swap_reads_the_values_before_it(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        a, b = f, g
        a, b = b, a
        a()
        """,
    )

    assert callees(graph, "main") == ["main.g"]


def test_definitions_by_statements(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        import ext
        def imported():
            from ext import f
            f()
        def defined():
            g = ext.make
            def g(): pass
            g()
        class Accumulator:
            def __iadd__(self, other):
                return other
            def __call__(self):
                pass
        def augmented():
            handler = Accumulator()
            handler += f
            handler()
        def walrus():
            handler = f
            (handler := g)
            handler()
        """,
    )

    assert callees(graph, "main.imported") == ["ext.f"]
    assert callees(graph, "main.defined") == ["main.defined.g"]
    assert callees(graph, "main.augmented") == [
        "main.Accumulator.__iadd__",
        "main.f",
    ]
    assert callees(graph, "main.walrus") == ["main.g"]


def test_an_untracked_value_replaces_the_definitions(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        def use():
            handler = f
            handler = None
            handler()
        """,
    )

    assert callees(graph, "main.use") == []


def test_del_ends_a_definition(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        def use():
            handler = f
            del handler
            handler = g
            handler()
        """,
    )

    assert callees(graph, "main.use") == ["main.g"]


def test_a_module_name_that_may_be_unbound_may_be_the_builtin(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        import ext
        if ext.legacy:
            len = f
        len()
        """,
    )

    assert callees(graph, "main") == ["<builtin>.len", "main.f"]


def test_if_joins_the_definitions_of_its_branches(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        import ext
        def both():
            if ext.flag:
                handler = f
            elif ext.other:
                handler = g
            else:
                handler = h
            handler()
        def one_branch():
            handler = f
            if ext.flag:
                handler = g
            handler()
        """,
    )

    assert callees(graph, "main.both") == ["main.f", "main.g", "main.h"]
    assert callees(graph, "main.one_branch") == ["main.f", "main.g"]


def test_a_branch_that_ends_does_not_reach_what_follows(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        import ext
        def use():
            handler = f
            if ext.flag:
                handler = g
                return
            elif ext.other:
                handler = g
                raise ValueError()
            handler()
        """,
    )

    assert callees(graph, "main.use") == ["<builtin>.ValueError", "main.f"]


def test_conditional_operands_join_what_they_bind(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        import ext
        def either():
            handler = f
            ext.flag or (handler := g)
            handler()
        def chosen():
            handler = f
            (handler := g) if ext.flag else None
            handler()
        """,
    )

    assert callees(graph, "main.either") == ["main.f", "main.g"]
    assert callees(graph, "main.chosen") == ["main.f", "main.g"]


def test_match_joins_its_cases(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        import ext
        def some(command):
            handler = f
            match command:
                case "a":
                    handler = g
                case "b":
                    handler = h
            handler()
        def every(command):
            handler = f
            match command:
                case "a":
                    handler = g
                case _:
                    handler = h
            handler()
        """,
    )

    assert callees(graph, "main.some") == ["main.f", "main.g", "main.h"]
    assert callees(graph, "main.every") == ["main.g", "main.h"]


def test_a_loop_reads_what_its_body_binds_on_the_iteration_before(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        def use():
            handler = f
            for following in (g, h):
                handler()
                handler = following
            handler()
        """,
    )

    assert callees(graph, "main.use") == ["main.f", "main.g", "main.h"]


def test_a_loop_variable_after_the_loop(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        def use():
            handler = f
            for handler in (g,):
                pass
            handler()
        """,
    )

    assert callees(graph, "main.use") == ["main.f", "main.g"]


def test_break_and_continue_carry_their_definitions(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        import ext
        def broken():
            handler = f
            for item in ext.items:
                handler = g
                if ext.done:
                    handler = h
                    break
                handler = f
            handler()
        def continued():
            for item in ext.items:
                handler = g
                if ext.skip:
                    handler = h
                    continue
                handler = f
            handler()
        def otherwise():
            handler = f
            while ext.more():
                handler = g
                if ext.done:
                    break
                handler = h
            else:
                handler()
        """,
    )

    assert callees(graph, "main.broken") == ["main.f", "main.h"]
    assert callees(graph, "main.continued") == ["main.f", "main.h"]
    assert callees(graph, "main.otherwise") == ["ext.more", "main.f", "main.h"]


def test_a_while_test_binds_on_each_iteration(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        import ext
        def use():
            line = f
            while line := ext.read():
                line()
            line()
        """,
    )

    assert callees(graph, "main.use") == ["ext.read"]


def test_the_else_block_of_a_loop_leaves_the_enclosing_loop(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        import ext
        def use():
            handler = f
            for outer in ext.items:
                for inner in ext.items:
                    pass
                else:
                    handler = g
                    break
                handler = h
            handler()
        """,
    )

    assert callees(graph, "main.use") == ["main.f", "main.g"]


def test_a_handler_starts_from_any_point_of_the_try_body(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        import ext
        def handled():
            handler = f
            try:
                handler = g
                ext.risky()
                handler = h
            except ValueError:
                handler()
        def after():
            handler = f
            try:
                handler = g
                ext.risky()
                handler = h
            except ValueError:
                return
            handler()
        """,
    )

    assert callees(graph, "main.handled") == [
        "ext.risky",
        "main.f",
        "main.g",
        "main.h",
    ]
    assert callees(graph, "main.after") == ["ext.risky", "main.h"]


def test_each_handler_name_holds_what_its_handler_catches(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        import ext
        class First(Exception):
            def report(self): pass
        class Second(Exception):
            def report(self): pass
        def use():
            try:
                ext.run()
            except First as error:
                pass
            try:
                ext.run()
            except Second as error:
                error.report()
        First()
        Second()
        """,
    )

    assert callees(graph, "main.use") == ["ext.run", "main.Second.report"]


def test_the_name_of_a_handler_is_unbound_after_it(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        import ext
        class Failure(Exception):
            def __call__(self): pass
        def use():
            error = f
            try:
                ext.run()
            except Failure as error:
                pass
            error()
        Failure()
        """,
    )

    assert callees(graph, "main.use") == ["ext.run", "main.f"]


def test_finally_starts_anywhere_and_its_definitions_follow(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        import ext
        def inside():
            handler = f
            try:
                handler = g
                ext.run()
                handler = h
            finally:
                handler()
        def after():
            handler = f
            try:
                ext.run()
            finally:
                handler = g
            handler()
        def normal():
            handler = f
            try:
                handler = g
                ext.run()
                handler = h
            finally:
                ext.cleanup()
            handler()
        """,
    )

    assert callees(graph, "main.inside") == ["ext.run", "main.f", "main.g", "main.h"]
    assert callees(graph, "main.after") == ["ext.run", "main.g"]
    assert callees(graph, "main.normal") == ["ext.cleanup", "ext.run", "main.h"]


def test_a_jump_through_finally_takes_its_definitions(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        import ext
        def use():
            handler = f
            for item in ext.items:
                try:
                    if ext.done:
                        break
                finally:
                    handler = g
                handler = h
            handler()
        """,
    )

    assert callees(graph, "main.use") == ["main.f", "main.g", "main.h"]


def test_a_jump_waits_for_finally_which_may_replace_it(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        import ext
        def returned():
            while True:
                try:
                    break
                finally:
                    return
            f()
        def replaced():
            handler = f
            while True:
                try:
                    break
                finally:
                    handler = g
            handler()
        def kept_kind():
            handler = f
            while True:
                try:
                    continue
                finally:
                    handler = g
            handler()
        def nested():
            handler = f
            while True:
                try:
                    try:
                        break
                    finally:
                        handler = g
                finally:
                    ext.cleanup()
            handler()
        def nested_leaves():
            while True:
                try:
                    try:
                        break
                    finally:
                        ext.cleanup()
                finally:
                    return
            f()
        def from_handler():
            for item in ext.items:
                try:
                    ext.run()
                except ValueError:
                    continue
                finally:
                    break
                f()
            g()
        """,
    )

    assert callees(graph, "main.returned") == []
    assert callees(graph, "main.nested_leaves") == ["ext.cleanup"]
    assert callees(graph, "main.from_handler") == ["ext.run", "main.g"]
    assert callees(graph, "main.replaced") == ["main.g"]
    assert callees(graph, "main.kept_kind") == []
    assert callees(graph, "main.nested") == ["ext.cleanup", "main.g"]


def test_a_jump_of_a_loop_inside_the_try_does_not_wait_for_finally(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        import ext
        def use():
            handler = f
            try:
                while True:
                    break
                handler = g
            finally:
                ext.cleanup()
            handler()
        """,
    )

    assert callees(graph, "main.use") == ["ext.cleanup", "main.g"]


def test_with_may_suppress_an_exception_of_its_body(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        import contextlib, ext
        def use():
            handler = f
            with contextlib.suppress(KeyError):
                handler = ext.table["key"]
                handler = g
            handler()
        """,
    )

    assert callees(graph, "main.use") == [
        "contextlib.suppress",
        "ext.table",
        "main.f",
        "main.g",
    ]


def test_a_class_namespace_holds_what_reaches_the_end_of_its_body(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        class C:
            handler = f
            handler()
            handler = g
        def use():
            C.handler()
        """,
    )

    assert callees(graph, "main") == ["main.f"]
    assert callees(graph, "main.use") == ["main.g"]


def test_a_class_body_reads_the_module_until_it_binds_the_name(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        import ext
        handler = f
        class C:
            handler()
            if ext.flag:
                handler = g
            handler()
            handler = h
        """,
    )

    assert callees(graph, "main") == ["main.f", "main.g"]


def test_a_class_body_that_uses_its_namespace_also_reads_the_module(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        class C:
            locals()
            f()
            f = g
        def builtin():
            class D:
                vars()
                len()
                len = h
        def outer():
            f = h
            class Inner:
                locals()
                f()
                f = g
        def function():
            locals()
            f()
            f = g
        """,
    )

    assert callees(graph, "main") == ["<builtin>.locals", "main.f", "main.g"]
    assert callees(graph, "main.builtin") == [
        "<builtin>.len",
        "<builtin>.vars",
        "main.h",
    ]
    assert callees(graph, "main.outer") == ["<builtin>.locals", "main.f", "main.g"]
    assert callees(graph, "main.function") == ["<builtin>.locals", "main.g"]


def test_a_method_that_rebinds_self_still_gets_outside_receivers(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        class Base:
            def run(self, reset=False):
                if reset:
                    self = Base()
                self.step()
            def step(self):
                pass
        class Child(Base):
            def step(self):
                pass
        child = Child()
        """,
    )

    assert callees(graph, "main.Base.run") == ["main.Base.step", "main.Child.step"]


def test_a_comprehension_assignment_expression_keeps_every_value(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        last = h
        [last := handler for handler in (f, g)]
        last()
        """,
    )

    assert callees(graph, "main") == ["main.f", "main.g", "main.h"]


def test_a_module_with_a_star_import_keeps_every_value(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "main.py": DEFINITIONS
            + """
from tools import *
handler = f
handler()
handler = g
""",
            "tools.py": "def handler(): pass\n",
        },
    )

    assert callees(graph, "main") == ["main.f", "main.g", "tools.handler"]


def test_and_and_or_keep_the_operands_that_can_be_the_result(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        import ext
        def first():
            handler = None or f
            handler()
        def second():
            def one(): pass
            def two(): pass
            handler = one and two
            handler()
        def third():
            def one(): pass
            handler = one or f
            handler()
        def unknown():
            handler = ext.value or f
            handler()
        def chain():
            def one(): pass
            def two(): pass
            handler = () or (one and two) or f
            handler()
        def module_names():
            handler = f and g
            handler()
        """,
    )

    assert callees(graph, "main.first") == ["main.f"]
    assert callees(graph, "main.second") == ["main.second.two"]
    assert callees(graph, "main.third") == ["main.third.one"]
    assert callees(graph, "main.unknown") == ["ext.value", "main.f"]
    assert callees(graph, "main.chain") == ["main.chain.two"]
    assert callees(graph, "main.module_names") == ["main.f", "main.g"]


def test_a_conditional_expression_with_a_known_test_keeps_one_arm(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        import ext
        verbose = True
        quiet = not verbose
        empty = ()
        (f if verbose else g)()
        (f if quiet else g)()
        (h if empty else g)()
        def use():
            (f if verbose else g)()
        """,
    )

    assert callees(graph, "main") == ["main.f", "main.g"]
    assert callees(graph, "main.use") == ["main.f", "main.g"]


def test_a_known_test_chooses_a_base_class(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        class Fast:
            def run(self): pass
        class Safe:
            def run(self): pass
        USE_FAST = True
        class Runner(Fast if USE_FAST else Safe):
            pass
        Runner().run()
        """,
    )

    assert callees(graph, "main") == ["main.Fast.run"]


def test_values_whose_truth_may_change_or_differ_keep_both_operands(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        import ext
        def joined():
            flag = True
            if ext.other:
                flag = False
            (f if flag else g)()
        def mutated():
            pending = []
            pending.append(h)
            handler = pending and f
            handler()
        def looped():
            done = False
            while ext.more():
                (f if done else g)()
                done = True
        def wrapped():
            @ext.register
            def decorated(): pass
            (decorated or f)()
        """,
    )

    assert callees(graph, "main.joined") == ["main.f", "main.g"]
    assert callees(graph, "main.mutated") == ["<builtin>.list.append", "main.f"]
    assert callees(graph, "main.looped") == ["ext.more", "main.f", "main.g"]
    assert callees(graph, "main.wrapped") == [
        "ext.register",
        "main.f",
        "main.wrapped.decorated",
    ]


def test_an_operand_that_never_runs_binds_nothing(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        def use():
            handler = f
            True or (handler := g)
            handler()
            other = f
            (other := g) if () else None
            other()
        """,
    )

    assert callees(graph, "main.use") == ["main.f"]


def test_statements_after_a_jump_do_not_run(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        import ext
        def returned():
            f()
            return
            g()
        def raised():
            raise ValueError()
            g()
        def every_branch():
            if ext.flag:
                return f()
            else:
                raise ValueError()
            g()
        def looped():
            for item in ext.items:
                if ext.flag:
                    continue
                    g()
                break
                h()
            f()
        def finished():
            try:
                return f()
            finally:
                ext.release()
            g()
        """,
    )

    assert callees(graph, "main.returned") == ["main.f"]
    assert callees(graph, "main.raised") == ["<builtin>.ValueError"]
    assert callees(graph, "main.every_branch") == ["<builtin>.ValueError", "main.f"]
    assert callees(graph, "main.looped") == ["main.f"]
    assert callees(graph, "main.finished") == ["ext.release", "main.f"]


def test_handlers_and_suppressing_managers_keep_what_follows(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        import ext
        def handled():
            try:
                return ext.run()
            except ValueError:
                pass
            f()
        def managed():
            with ext.manager():
                return ext.run()
            g()
        """,
    )

    assert callees(graph, "main.handled") == ["ext.run", "main.f"]
    assert callees(graph, "main.managed") == ["ext.manager", "ext.run", "main.g"]


def test_a_branch_whose_test_cannot_hold_does_not_run(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        import ext
        if False:
            f()
        while 0:
            f()
        if ():
            f()
        elif ext.flag:
            g()
        else:
            h()
        fast = True
        if fast:
            def handler():
                g()
        else:
            def handler():
                f()
        handler()
        if not fast:
            def unused():
                pass
        """,
    )

    assert callees(graph, "main") == ["main.g", "main.h", "main.handler"]
    assert callees(graph, "main.handler") == ["main.g"]
    assert "main.unused" not in graph


def test_a_loop_whose_test_always_holds_ends_only_by_break(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        import ext
        def endless():
            while True:
                ext.step()
            else:
                f()
            g()
        def broken():
            while 1:
                if ext.done():
                    break
            else:
                f()
            g()
        """,
    )

    assert callees(graph, "main.endless") == ["ext.step"]
    assert callees(graph, "main.broken") == ["ext.done", "main.g"]


def test_operands_that_cannot_run_are_not_analysed(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        import ext
        True or f()
        () and f()
        None or g()
        h() if 1 else f()
        ext.flag or ext.other()
        """,
    )

    assert callees(graph, "main") == ["ext.other", "main.g", "main.h"]


def test_an_assert_message_runs_only_where_the_test_fails(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        import ext
        def holds():
            assert True, f()
            g()
        def unknown():
            assert ext.check(), f()
            g()
        def fails():
            assert (), f()
            g()
        """,
    )

    assert callees(graph, "main.holds") == ["main.g"]
    assert callees(graph, "main.unknown") == ["ext.check", "main.f", "main.g"]
    assert callees(graph, "main.fails") == ["main.f"]


def test_code_under_type_checking_does_not_run(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "main.py": DEFINITIONS
            + """
from typing import TYPE_CHECKING
import typing
import typing_extensions as extensions
if TYPE_CHECKING:
    from plugins import Plugin
    f()
else:
    g()
if typing.TYPE_CHECKING or extensions.TYPE_CHECKING:
    f()
if not TYPE_CHECKING:
    h()
def use():
    Plugin()
""",
            "plugins.py": "class Plugin:\n    def __init__(self): pass\nprint()\n",
        },
    )

    assert callees(graph, "main") == ["main.g", "main.h"]
    assert "plugins" not in graph
    assert callees(graph, "main.use") == []


def test_a_name_defined_only_in_code_that_cannot_run_is_not_an_attribute(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        from typing import TYPE_CHECKING
        class Base:
            def run(self):
                f()
        class Child(Base):
            if TYPE_CHECKING:
                def run(self): ...
            temporary = g
            del temporary
        def use():
            Child().run()
            Child.temporary()
        """,
    )

    assert callees(graph, "main.use") == ["main.Base.run"]


def test_literal_values_decide_comparisons(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        import ext
        mode = "fast"
        if mode == "slow":
            f()
        elif mode in ("fast", "quick") and mode is not None:
            g()
        else:
            h()
        level = 2 if ext.flag else 3
        if level > 1:
            g()
        else:
            f()
        if level == 2:
            h()
        if mode < 1:
            h()
        """,
    )

    assert callees(graph, "main") == ["main.g", "main.h"]


def test_the_name_of_a_module_tells_whether_it_runs_as_main(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "main.py": """
import helper
if __name__ == "__main__":
    helper.run()
""",
            "helper.py": """
def run(): pass
def selftest(): pass
if __name__ == "__main__":
    selftest()
if __name__ == "helper":
    run()
""",
        },
    )

    assert callees(graph, "main") == ["helper.run"]
    assert callees(graph, "helper") == ["helper.run"]


def test_a_match_on_a_literal_runs_the_case_that_matches(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        import ext
        command = "stop"
        match command:
            case "go":
                f()
            case "stop" | "halt":
                g()
            case _:
                h()
        match command:
            case [first, *rest]:
                f()
            case None:
                f()
            case word if ext.check(word):
                h()
        """,
    )

    assert callees(graph, "main") == ["ext.check", "main.g", "main.h"]


def test_type_checking_is_false_in_functions_too(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        import ext
        import typing
        from typing import TYPE_CHECKING, cast
        flag = False
        def use(value):
            if TYPE_CHECKING:
                value = cast(int, value)
            if typing.TYPE_CHECKING:
                f()
            if flag:
                g()
        def rebinding():
            global flag
            flag = ext.value
        """,
    )

    assert callees(graph, "main.use") == ["main.g"]


def test_except_star_handlers_run_in_sequence(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        def run():
            handler = f
            try:
                raise ExceptionGroup("errors", [ValueError(), TypeError()])
            except* ValueError:
                handler = g
            except* TypeError:
                handler()
        """,
    )

    assert callees(graph, "main.run") == [
        "<builtin>.ExceptionGroup",
        "<builtin>.TypeError",
        "<builtin>.ValueError",
        "main.f",
        "main.g",
    ]


def test_a_capture_of_the_whole_subject_binds_the_subject(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        class C:
            pass
        def run():
            handler = f
            match handler:
                case handler:
                    handler()
        def named(value):
            match g:
                case _ as captured:
                    captured()
        def checked():
            match h:
                case C() as instance:
                    instance()
        """,
    )

    assert callees(graph, "main.run") == ["main.f"]
    assert callees(graph, "main.named") == ["main.g"]
    assert callees(graph, "main.checked") == ["main.h"]


def test_comparisons_after_one_that_fails_do_not_run(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        import ext
        def known():
            handler = f
            2 < 1 < (handler := g)
            handler()
        def unknown():
            handler = f
            ext.a < ext.b < (handler := g)
            handler()
        """,
    )

    assert callees(graph, "main.known") == ["main.f"]
    assert callees(graph, "main.unknown") == ["main.f", "main.g"]


def test_a_dict_display_evaluates_each_key_before_its_value(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        def run():
            handler = f
            {(handler := g): handler()}
        """,
    )

    assert callees(graph, "main.run") == ["main.g"]


def test_an_augmented_assignment_reads_its_target_first(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        class A:
            def __iadd__(self, other):
                return self
        class B:
            def __iadd__(self, other):
                return self
        def run():
            value = A()
            value += (value := B())
        """,
    )

    assert callees(graph, "main.run") == ["main.A.__iadd__"]


def test_an_assert_message_does_not_reach_what_follows(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        import ext
        def known():
            handler = f
            assert True, (handler := g)
            handler()
        def unknown():
            handler = f
            assert ext.ok, (handler := g)
            handler()
        """,
    )

    assert callees(graph, "main.known") == ["main.f"]
    assert callees(graph, "main.unknown") == ["main.f"]


def test_a_module_may_be_false(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "main.py": """
import tools
def fallback(): pass
(tools or fallback)()
""",
            "tools.py": "",
        },
    )

    assert callees(graph, "main") == ["main.fallback"]


def test_names_of_a_scope_that_reads_or_writes_them_dynamically(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        import sys
        def namespace():
            handler = f
            handler()
            locals()
            handler = g
        def evaluated():
            handler = f
            handler()
            eval("handler")
            handler = g
        def described():
            handler = f
            handler()
            vars()
            handler = g
        def shadowed():
            vars = ext.vars
            handler = f
            handler()
            vars()
            handler = g
        def other_object(value):
            handler = f
            handler()
            vars(value)
            handler = g
        import ext
        """,
    )

    assert callees(graph, "main.namespace") == ["<builtin>.locals", "main.f", "main.g"]
    assert callees(graph, "main.evaluated") == ["<builtin>.eval", "main.f", "main.g"]
    assert callees(graph, "main.described") == ["<builtin>.vars", "main.f", "main.g"]
    assert callees(graph, "main.shadowed") == ["ext.vars", "main.f"]
    assert callees(graph, "main.other_object") == ["<builtin>.vars", "main.f"]


def test_a_module_that_uses_its_own_namespace_keeps_every_value(tmp_path):
    for use in ("globals()", 'exec("pass")', "sys.modules[__name__]"):
        graph = graph_of(
            tmp_path / use.partition("(")[0].partition(".")[0],
            f"""
            import sys
            handler = f
            handler()
            {use}
            handler = g
            """,
        )

        assert {"main.f", "main.g"} <= set(callees(graph, "main")), use


CLASS_MEMBERS = """
class Base:
    def method(self):
        f()
    def other(self):
        f()
class Field:
    def __set_name__(self, owner, name):
        pass
class Plugin(Base):
    {use}
    field = Field()
    def method(self):
        g()
    def __init_subclass__(cls):
        cls()
    def __init__(self):
        pass
    def __call__(self):
        h()
    if False:
        def other(self):
            pass
class Concrete(Plugin):
    pass
def use():
    Plugin().method()
    Plugin().__init_subclass__()
    Plugin().other()
"""


def test_a_class_body_that_uses_its_namespace_keeps_its_members(tmp_path):
    graph = graph_of(tmp_path / "pass", CLASS_MEMBERS.format(use="pass"))

    assert callees(graph, "main") == [
        "main.Field.__set_name__",
        "main.Plugin.__init_subclass__",
    ]
    assert callees(graph, "main.use") == [
        "main.Base.other",
        "main.Plugin.__init__",
        "main.Plugin.__init_subclass__",
        "main.Plugin.method",
    ]
    assert callees(graph, "main.Plugin.__init_subclass__") == ["main.Plugin.__init__"]

    def functions(graph):
        return {name: graph[name] for name in graph if name.startswith("main.")}

    for use in ("locals", "vars", "exec", "eval"):
        call = f'{use}("0")' if use in ("exec", "eval") else f"{use}()"
        dynamic = graph_of(tmp_path / use, CLASS_MEMBERS.format(use=call))
        assert callees(dynamic, "main") == sorted(
            callees(graph, "main") + [f"<builtin>.{use}"]
        ), use
        assert functions(dynamic) == functions(graph), use


def test_a_function_that_rebinds_a_global_between_two_uses(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        handler = f
        handler()
        def install():
            global handler
            handler = g
        install()
        handler()
        """,
    )

    assert callees(graph, "main") == ["main.f", "main.g", "main.install"]


def test_a_generator_expression_reads_every_value(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        def run():
            handler = f
            calls = (handler() for _ in range(1))
            handler = g
            list(calls)
        """,
    )

    assert "main.g" in callees(graph, "main.run")
    assert "main.f" in callees(graph, "main.run")


def test_a_method_reads_a_class_attribute_at_call_time(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        class C:
            handler = f
            def run(self):
                self.handler()
                C.handler()
        C.handler = g
        C().run()
        """,
    )

    assert callees(graph, "main.C.run") == ["main.f", "main.g"]


def test_names_that_one_path_unbinds_or_never_binds(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        import ext
        def deleted():
            handler = f
            if ext.flag:
                del handler
            handler()
        def raised():
            handler = f
            try:
                handler = g
                raise ValueError()
            except ValueError:
                handler()
        for item in ext.items:
            len = f
        len()
        """,
    )

    assert callees(graph, "main.deleted") == ["main.f"]
    assert callees(graph, "main.raised") == ["<builtin>.ValueError", "main.f", "main.g"]
    assert callees(graph, "main") == ["<builtin>.len", "main.f"]


def test_literals_of_different_types_stay_apart(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        import ext
        def identity():
            value = True if ext.flag else 1
            if value is not True:
                f()
        def matched():
            value = 1 if ext.flag else True
            match value:
                case True:
                    g()
        def equal():
            if 1 == True:
                h()
        """,
    )

    assert callees(graph, "main.identity") == ["main.f"]
    assert callees(graph, "main.matched") == ["main.g"]
    assert callees(graph, "main.equal") == ["main.h"]


def test_an_except_star_clause_that_raises_does_not_stop_the_others(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        def run():
            flag = False
            try:
                raise ExceptionGroup("errors", [ValueError(), TypeError()])
            except* ValueError:
                flag = True
                raise RuntimeError()
            except* TypeError:
                if flag:
                    f()
        """,
    )

    assert "main.f" in callees(graph, "main.run")


def test_an_entry_module_may_also_be_imported(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "main.py": "import worker\n",
            "worker.py": """
def hit(): pass
def run(): pass
if __name__ != "__main__":
    hit()
if __name__ == "__main__":
    run()
""",
        },
        entry_points=("main.py", "worker.py"),
    )

    assert callees(graph, "worker") == ["worker.hit", "worker.run"]


def test_a_module_that_uses_its_namespace_has_no_known_name(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "main.py": "import helper\n",
            "helper.py": """
def hit(): pass
exec("__name__ = 'other'")
if __name__ == "other":
    hit()
""",
        },
    )

    assert callees(graph, "helper") == ["<builtin>.exec", "helper.hit"]


def test_a_module_name_that_a_path_may_leave_unbound_also_reads_the_builtin(
    tmp_path,
):
    graph = main_graph(
        tmp_path,
        """
        import sys
        if sys.platform == "win32":
            callable = lambda value: True
        len = len
        def check(value):
            callable(value)
            len(value)
        """,
    )

    assert callees(graph, "main.check") == [
        "<builtin>.callable",
        "<builtin>.len",
        "main.<lambda1>",
    ]
