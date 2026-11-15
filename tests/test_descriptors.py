"""Descriptors other than functions, `staticmethod`, `classmethod` and
`property`: instances whose class defines `__get__`, `__set__` or
`__delete__`, found as class attributes."""

import textwrap

from programs import callees, main_graph

DEFINITIONS = """
def f(): pass
class Hook:
    def __get__(self, obj, owner=None):
        owner.made()
        obj.used()
        return f
class App:
    hook = Hook()
    @classmethod
    def made(cls): pass
    def used(self): pass
"""


def graph_of(tmp_path, source):
    return main_graph(tmp_path, DEFINITIONS + textwrap.dedent(source))


def test_a_load_through_an_instance_calls_get_with_the_instance_and_class(
    tmp_path,
):
    graph = graph_of(tmp_path, "App().hook()\n")

    # From the scope of the load; the load gives what `__get__` returns.
    assert callees(graph, "main") == [
        "<builtin>.classmethod",
        "main.Hook.__get__",
        "main.f",
    ]
    assert callees(graph, "main.Hook.__get__") == ["main.App.made", "main.App.used"]


def test_a_load_through_the_class_calls_get_without_an_instance(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        def load():
            App.hook()
        """,
    )

    assert callees(graph, "main.load") == ["main.Hook.__get__", "main.f"]
    # The instance is None: only the class is used.
    assert callees(graph, "main.Hook.__get__") == ["main.App.made"]


def test_an_instance_without_get_is_the_value_of_the_load(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        class Tool:
            def __call__(self): pass
        class Box:
            tool = Tool()
        def use():
            Box().tool()
        """,
    )

    assert callees(graph, "main.use") == ["main.Tool.__call__"]


def test_a_value_in_the_instance_is_no_descriptor(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        class Bare:
            pass
        def use():
            bare = Bare()
            bare.hook = Hook()
            bare.hook
        """,
    )

    # Python calls `__get__` only for what it finds on the class.
    assert callees(graph, "main.use") == []


def test_a_store_and_a_deletion_call_set_and_delete(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        class Field:
            def __set__(self, obj, value):
                value()
            def __delete__(self, obj):
                obj.used()
        class User:
            email = Field()
            def used(self): pass
        def use():
            user = User()
            user.email = f
            del user.email
        """,
    )

    assert callees(graph, "main.use") == ["main.Field.__delete__", "main.Field.__set__"]
    assert callees(graph, "main.Field.__set__") == ["main.f"]
    assert callees(graph, "main.Field.__delete__") == ["main.User.used"]


def test_the_class_hook_is_the_caller_of_get_and_super_is_not(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        class Hooked:
            hook = Hook()
            def __getattribute__(self, name):
                return object.__getattribute__(self, name)
        class Child(Hooked):
            def run(self):
                super().hook
        def use():
            Hooked().hook
        """,
    )

    # As for a property: the class's own hook runs the accessor.
    assert "main.Hook.__get__" in callees(graph, "main.Hooked.__getattribute__")
    assert "main.Hook.__get__" not in callees(graph, "main.use")
    assert callees(graph, "main.Child.run") == ["<builtin>.super", "main.Hook.__get__"]


def test_limit_object_hooks_by_name_run_no_descriptor(tmp_path):
    # Python's `object.__setattr__(self, "x", v)` and its siblings, also
    # through `super()`, run the data descriptor of the class. The analysis
    # does not: the stubs do not tell whose native slot a hook is, and a
    # star import may supply another `object` (a limit).
    graph = main_graph(
        tmp_path,
        """
class Field:
    def __get__(self, obj, owner=None): pass
    def __set__(self, obj, value): pass
    def __delete__(self, obj): pass
class User:
    email = Field()
    def by_object(self):
        object.__setattr__(self, "email", 1)
        object.__getattribute__(self, "email")
        object.__delattr__(self, "email")
    def by_super(self):
        super().__setattr__("email", 1)
        super().__delattr__("email")
User().by_object()
User().by_super()
""",
    )

    for method in ("by_object", "by_super"):
        found = callees(graph, f"main.User.{method}")
        assert not [c for c in found if c.startswith("main.Field")]
