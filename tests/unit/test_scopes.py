"""Name resolution and scope naming, computed from the AST."""

import ast
import textwrap

import pytest

from pycg.analysis.scopes import analyse_scopes


def scopes_of(source, module="mod"):
    return analyse_scopes(ast.parse(textwrap.dedent(source)), module)


def scope_named(scopes, name):
    matches = [scope for scope in scopes.scopes if scope.name == name]
    assert len(matches) == 1, f"{name}: {[scope.name for scope in scopes.scopes]}"
    return matches[0]


def binder(scopes, scope_name, name):
    """Return the name of the scope that binds `name` as seen from a scope."""
    return scopes.resolve(scope_named(scopes, scope_name), name).name


def test_local_and_global_names():
    scopes = scopes_of(
        """
        x = 1
        def f():
            x = 2
            return x
        def g():
            return x
        """
    )

    assert binder(scopes, "mod.f", "x") == "mod.f"
    assert binder(scopes, "mod.g", "x") == "mod"


def test_unknown_name_falls_back_to_the_module():
    scopes = scopes_of("def f():\n    print(undefined)\n")

    assert binder(scopes, "mod.f", "print") == "mod"
    assert binder(scopes, "mod.f", "undefined") == "mod"
    assert "print" not in scopes.module.bound


def test_global_declaration_binds_in_the_module():
    scopes = scopes_of(
        """
        def f():
            global x
            x = 1
        def g():
            return x
        """
    )

    assert binder(scopes, "mod.f", "x") == "mod"
    assert binder(scopes, "mod.g", "x") == "mod"
    assert "x" in scopes.module.bound
    assert "x" not in scope_named(scopes, "mod.f").bound


def test_global_declaration_in_an_enclosing_function_reaches_nested_scopes():
    scopes = scopes_of(
        """
        def outer():
            global x
            x = 1
            def inner():
                return x
        """
    )

    assert binder(scopes, "mod.outer.inner", "x") == "mod"


def test_nonlocal_declaration_binds_in_the_enclosing_function():
    scopes = scopes_of(
        """
        def outer():
            x = 1
            def middle():
                def inner():
                    nonlocal x
                    x = 2
                return inner
        """
    )

    assert binder(scopes, "mod.outer.middle.inner", "x") == "mod.outer"
    assert "x" not in scope_named(scopes, "mod.outer.middle.inner").bound


def test_class_body_names_are_invisible_to_nested_functions():
    scopes = scopes_of(
        """
        x = 0
        def outer():
            y = 0
            class C:
                x = 1
                y = 1
                z = x
                def m(self):
                    return x, y
        """
    )

    assert binder(scopes, "mod.outer.C", "x") == "mod.outer.C"
    assert binder(scopes, "mod.outer.C.m", "x") == "mod"
    assert binder(scopes, "mod.outer.C.m", "y") == "mod.outer"


def test_comprehension_variables_are_local_to_the_comprehension():
    scopes = scopes_of(
        """
        def f():
            x = 1
            return [x for x in range(3)]
        """
    )

    assert binder(scopes, "mod.f.<listcomp>", "x") == "mod.f.<listcomp>"
    assert binder(scopes, "mod.f", "x") == "mod.f"


def test_comprehension_in_a_class_body_cannot_see_class_names():
    scopes = scopes_of(
        """
        class C:
            items = []
            names = {item: items for item in items}
        """
    )

    assert binder(scopes, "mod.C.<dictcomp>", "items") == "mod"
    assert binder(scopes, "mod.C.<dictcomp>", "item") == "mod.C.<dictcomp>"
    assert binder(scopes, "mod.C", "items") == "mod.C"


def test_walrus_in_a_comprehension_binds_in_the_enclosing_function():
    scopes = scopes_of(
        """
        def f(data):
            if any((hit := d) for d in data):
                return hit
        """
    )

    assert binder(scopes, "mod.f", "hit") == "mod.f"
    assert binder(scopes, "mod.f.<genexpr>", "hit") == "mod.f"
    assert "hit" not in scope_named(scopes, "mod.f.<genexpr>").bound


def test_walrus_in_a_module_level_comprehension_binds_a_global():
    scopes = scopes_of("values = [(last := v) for v in range(3)]\n")

    assert binder(scopes, "mod.<listcomp>", "last") == "mod"
    assert "last" in scopes.module.bound


def test_all_binding_forms_bind_locally():
    scopes = scopes_of(
        """
        def f(a, /, b, *args, c, **kwargs):
            import os.path
            import json as js
            from x import y as z, w
            for i in a: pass
            with b as fh: pass
            try:
                pass
            except E as err:
                pass
            match c:
                case [first, *rest]: pass
                case {"k": val, **others}: pass
                case P(x=px) as p: pass
            n: int
            def inner(): pass
            class K: pass
            type Alias = int
        """
    )

    f = scope_named(scopes, "mod.f")
    assert set(f.bound) == {
        "a",
        "b",
        "args",
        "c",
        "kwargs",
        "os",
        "js",
        "z",
        "w",
        "i",
        "fh",
        "err",
        "first",
        "rest",
        "val",
        "others",
        "px",
        "p",
        "n",
        "inner",
        "K",
        "Alias",
    }


def test_star_import_binds_nothing():
    scopes = scopes_of("from m import *\n")

    assert dict(scopes.module.bound) == {}


def test_lambdas_are_numbered_per_enclosing_scope_in_source_order():
    scopes = scopes_of(
        """
        a = lambda: 1
        def f():
            b = lambda: 2
            c = (lambda: 3)(lambda: 4)
        d = [lambda: 5 for _ in range(2)]
        e = lambda: lambda: 6
        """
    )

    lambdas = [
        (node.lineno, node.col_offset, scopes.scope_of(node).name)
        for node in ast.walk(scopes.tree)
        if isinstance(node, ast.Lambda)
    ]
    assert sorted(lambdas) == [
        (2, 4, "mod.<lambda1>"),
        (4, 8, "mod.f.<lambda1>"),
        (5, 9, "mod.f.<lambda2>"),
        (5, 20, "mod.f.<lambda3>"),
        (6, 5, "mod.<lambda2>"),
        (7, 4, "mod.<lambda3>"),
        (7, 12, "mod.<lambda3>.<lambda1>"),
    ]


def test_defaults_and_decorators_belong_to_the_enclosing_scope():
    scopes = scopes_of(
        """
        @(lambda f: f)
        def f(cb=lambda: 1):
            return lambda: 2
        """
    )

    names = sorted(
        scopes.scope_of(node).name
        for node in ast.walk(scopes.tree)
        if isinstance(node, ast.Lambda)
    )
    assert names == ["mod.<lambda1>", "mod.<lambda2>", "mod.f.<lambda1>"]


def test_qualified_names_of_nested_definitions():
    scopes = scopes_of(
        """
        class A:
            class B:
                def m(self):
                    def inner(): pass
        def g[T](x: T) -> T:
            pass
        class C[T]:
            def m(self): pass
        """
    )

    assert [scope.name for scope in scopes.scopes] == [
        "mod",
        "mod.A",
        "mod.A.B",
        "mod.A.B.m",
        "mod.A.B.m.inner",
        "mod.g",
        "mod.C",
        "mod.C.m",
    ]


@pytest.mark.parametrize(
    ("scope_name", "owner"),
    [
        ("mod", "mod"),
        ("mod.f", "mod.f"),
        ("mod.f.<listcomp>", "mod.f"),
        ("mod.f.<listcomp>.<genexpr>", "mod.f"),
        ("mod.C", "mod.C"),
    ],
)
def test_owner_is_the_nearest_scope_that_is_not_a_comprehension(scope_name, owner):
    scopes = scopes_of(
        """
        def f(rows):
            return [list(x for x in row) for row in rows]
        class C:
            pass
        """
    )

    assert scope_named(scopes, scope_name).owner.name == owner


def test_private_names_are_mangled_inside_classes():
    scopes = scopes_of(
        """
        class _Outer:
            __a = 1
            __dunder__ = 2
            def method(self, __p):
                __local = 3
                global __g
                __g = 4
            class __Inner:
                __b = 5
        class ___:
            __c = 6
        __module_level = 7
        """
    )

    assert set(scope_named(scopes, "mod._Outer").bound) == {
        "_Outer__a",
        "__dunder__",
        "method",
        "_Outer__Inner",
    }
    assert set(scope_named(scopes, "mod._Outer.method").bound) == {
        "self",
        "_Outer__p",
        "_Outer__local",
    }
    # A nested class mangles with its own name.
    assert set(scope_named(scopes, "mod._Outer.__Inner").bound) == {"_Inner__b"}
    # A class name made only of underscores mangles nothing.
    assert set(scope_named(scopes, "mod.___").bound) == {"__c"}
    assert set(scopes.module.bound) == {"_Outer", "___", "__module_level", "_Outer__g"}


# What the builder follows by definition (see `ModuleScopes.tracked`)


def test_names_that_another_scope_rebinds_are_not_tracked():
    scopes = scopes_of(
        """
        rebound = read = 1
        def install():
            global rebound
            rebound = 2
        def reader():
            global read
            return read
        def outer():
            mine = cell = 1
            def inner():
                nonlocal cell
                cell = 2
            [last := x for x in ()]
        """
    )
    outer = scope_named(scopes, "mod.outer")

    assert not scopes.tracked(scopes.module, "rebound")
    # Reading a global does not rebind it.
    assert scopes.tracked(scopes.module, "read")
    assert scopes.tracked(outer, "mine")
    assert not scopes.tracked(outer, "cell")
    # A comprehension binds `last` on each of its iterations.
    assert not scopes.tracked(outer, "last")
    assert not scopes.tracked(scope_named(scopes, "mod.outer.<listcomp>"), "x")


def test_a_module_with_a_star_import_tracks_no_name():
    scopes = scopes_of("from os import *\nx = 1\n")

    assert not scopes.tracked(scopes.module, "x")


def test_class_bodies_and_comprehensions_run_inline_and_functions_do_not():
    scopes = scopes_of(
        """
        def f():
            class C:
                [y for y in ()]
                (z for z in ())
                def method(self): pass
            lambda: 0
        """
    )
    function = scope_named(scopes, "mod.f")
    body = scope_named(scopes, "mod.f.C")

    assert scopes.inline(function, function)
    assert scopes.inline(body, function)
    assert scopes.inline(scope_named(scopes, "mod.f.C.<listcomp>"), function)
    assert not scopes.inline(scope_named(scopes, "mod.f.C.<genexpr>"), function)
    assert not scopes.inline(scope_named(scopes, "mod.f.C.method"), function)
    assert not scopes.inline(scope_named(scopes, "mod.f.<lambda1>"), function)
    assert not scopes.inline(function, scopes.module)


def test_loops_record_the_names_their_iterations_bind():
    scopes = scopes_of(
        """
        for target in items:
            body = 1
            while (tested := 2):
                inner = 3
                del body
            else:
                after_inner = 4
            try:
                pass
            except E as error:
                pass
            def function():
                local = 5
        else:
            after = 6
        """
    )
    outer, inner = [
        node for node in ast.walk(scopes.tree) if isinstance(node, (ast.For, ast.While))
    ]

    assert scopes.loop_bindings(outer) == {
        "target": False,
        "body": True,
        "tested": False,
        "inner": False,
        "after_inner": False,
        "error": True,
        "function": False,
    }
    assert scopes.loop_bindings(inner) == {
        "tested": False,
        "inner": False,
        "body": True,
    }


def test_names_that_only_one_import_binds():
    scopes = scopes_of(
        """
        import typing as t
        import os.path
        from typing import TYPE_CHECKING
        from . import sibling
        from typing import cast
        cast = None
        import json
        def f():
            global json
            json = 1
        """
    )
    module = scopes.module

    assert scopes.imported(module, "t") == "typing"
    assert scopes.imported(module, "os") == "os"
    assert scopes.imported(module, "TYPE_CHECKING") == "typing.TYPE_CHECKING"
    # A relative import, a name bound another way, a name another scope binds.
    assert scopes.imported(module, "sibling") is None
    assert scopes.imported(module, "cast") is None
    assert scopes.imported(module, "json") is None


def test_scopes_that_use_their_namespace_track_no_name():
    scopes = scopes_of(
        """
        import sys
        def reads():
            x = 1
            return locals()
        def described(obj):
            x = 1
            return vars(obj)
        def shadowed():
            locals = dict
            x = 1
            return locals()
        def runs():
            x = 1
            exec("y = 2")
        """
    )

    assert not scopes.tracked(scope_named(scopes, "mod.reads"), "x")
    assert scopes.tracked(scope_named(scopes, "mod.described"), "x")
    assert scopes.tracked(scope_named(scopes, "mod.shadowed"), "x")
    # exec also reaches the module's names.
    assert not scopes.tracked(scope_named(scopes, "mod.runs"), "x")
    assert not scopes.tracked(scopes.module, "sys")
    plain = scopes_of("import sys\nx = 1\nsys.modules['other']\n")
    assert plain.tracked(plain.module, "x")
    patched = scopes_of("import sys\nx = 1\nsys.modules[__name__].x = 2\n")
    assert not patched.tracked(patched.module, "x")
