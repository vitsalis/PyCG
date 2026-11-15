"""Results of calls of outside code without stubs (design, *External names*).

The result of calling an outside value that no stub describes has no name:
nothing loaded from it, no element of it and no call of it names a callee.
Names that do not pass through a call keep their path, values that the stubs
describe keep their type, and the instance of an outside class that a base
class or an `except` clause gives keeps the name of the class.
"""

import pytest
from programs import analysed, callees, main_graph


@pytest.mark.parametrize(
    "use",
    [
        # An attribute of the result, also through a name.
        "lib.make().run()",
        "x = lib.make()\nx.run()",
        "x = lib.make()\nwhile x:\n    x = x.next()",
        # An element of the result.
        "lib.make()[0].run()",
        "for x in lib.make():\n    x.run()",
        "a, b = lib.make()\na.run()",
        # A class without stubs called: its instance.
        "lib.Cls().run()",
        # A context manager that the call returns.
        "with lib.make() as x:\n    x.run()",
    ],
)
def test_the_result_of_an_outside_call_without_stubs_names_nothing(tmp_path, use):
    graph = main_graph(tmp_path, "import lib\n" + use + "\n")

    assert callees(graph, "main") == ["lib.Cls" if "Cls" in use else "lib.make"]


def test_an_awaited_outside_call_without_stubs_names_nothing(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import lib
        async def use():
            x = await lib.fetch()
            x.run()
            async with lib.session() as s:
                s.get()
            async for item in lib.stream():
                item.run()
        """,
    )

    assert callees(graph, "main.use") == ["lib.fetch", "lib.session", "lib.stream"]


def test_a_method_called_on_the_result_is_named_by_its_path_only(tmp_path):
    # x = x.next(): the method is a path from the import, its result is not.
    graph = main_graph(
        tmp_path,
        """
        import lib
        x = lib
        while x:
            x.visit()
            x = x.next()
        """,
    )

    # x never holds a name past the result of lib.next() (`lib.next.visit`).
    assert callees(graph, "main") == ["lib.next", "lib.visit"]


@pytest.mark.parametrize(
    "decorators",
    [
        # A decorator factory.
        "@lib.task()",
        # A stored factory.
        "deco = lib.task()\n@deco",
        # A method of an unnamed instance, called or not.
        'app = lib.App()\n@app.route("/")',
        "app = lib.App()\n@app.register",
        # A pair of outside decorators, both or one of them a factory.
        "@lib.first()\n@lib.second()",
        "@lib.first\n@lib.second()",
    ],
)
def test_an_unnamed_outside_decorator_keeps_what_it_decorates(tmp_path, decorators):
    # As for a named outside decorator, the name holds the unnamed result and
    # the undecorated function or class.
    graph = main_graph(
        tmp_path,
        "import lib\n"
        + decorators
        + "\ndef job(): pass\n"
        + decorators
        + "\nclass Model:\n    def run(self): pass\n"
        + "def use():\n    job()\n    Model().run()\n",
    )

    assert callees(graph, "main.use") == ["main.Model.run", "main.job"]


def test_an_ordinary_call_of_an_outside_value_returns_no_argument(tmp_path):
    # Only a decorator may return what it gets; a call of a named or an
    # unnamed outside value with a function as argument does not.
    graph = main_graph(
        tmp_path,
        """
        import lib
        def job(): pass
        def use():
            lib.make(job)()
            lib.make()(job)()
        """,
    )

    assert callees(graph, "main.use") == ["lib.make"]


def test_a_class_built_on_the_result_has_no_outside_base(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import lib
        class Model(lib.declarative_base()):
            pass
        Model().query()
        """,
    )

    assert callees(graph, "main") == ["lib.declarative_base"]


def test_a_call_of_the_result_is_unresolved_as_an_outside_value(tmp_path):
    found = analysed(
        tmp_path,
        {"main.py": "import lib\nlib.make()()\nlib.make().run()\n"},
    ).document()

    assert found["calls"]["main"] == [
        {"line": 2, "col": 0, "end": [2, 10], "callees": ["lib.make"]},
        {
            "line": 2,
            "col": 0,
            "end": [2, 12],
            "callees": [],
            "unresolved": "outside value",
        },
        {"line": 3, "col": 0, "end": [3, 10], "callees": ["lib.make"]},
        {
            "line": 3,
            "col": 0,
            "end": [3, 16],
            "callees": [],
            "unresolved": "outside value",
        },
    ]
    assert found["outside"] == {"lib.make": {"known": "name"}}


def test_a_known_attribute_name_of_the_result_is_an_outside_value(tmp_path):
    # getattr with a name that the analysis knows loads from the unnamed
    # result: the call is unresolved as an outside value, as with a literal.
    found = analysed(
        tmp_path,
        {
            "main.py": """\
import lib
def invoke(name):
    getattr(lib.make(), name)()
def guess(name):
    getattr(lib.make(), name)()
invoke("run")
"""
        },
    ).document()

    assert [site.get("unresolved") for site in found["calls"]["main.invoke"]] == [
        None,
        "outside value",
        None,
    ]
    # A name that the analysis does not know.
    assert [site.get("unresolved") for site in found["calls"]["main.guess"]] == [
        None,
        "computed name",
        None,
    ]


def test_names_that_do_not_pass_through_a_call_keep_their_path(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import lib
        import lib.sub.deep
        lib.sub.helper()
        lib.ITEMS[0].close()
        for item in lib.ITEMS:
            item.run()
        with lib.lock as held:
            held.release()
        p = lib.sub
        p.join()
        """,
    )

    assert callees(graph, "main") == [
        "lib.ITEMS.close",
        "lib.ITEMS.run",
        "lib.lock.release",
        "lib.sub.helper",
        "lib.sub.join",
    ]


def test_results_that_the_stubs_describe_keep_their_type(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import re
        import requests
        re.compile("a").match("a").group()
        requests.get("u").json()
        """,
    )

    assert callees(graph, "main") == [
        "re.Match.group",
        "re.Pattern.match",
        "re.compile",
        "requests.Response.json",
        "requests.get",
    ]


def test_instances_of_an_outside_class_from_a_base_or_a_handler_keep_its_name(
    tmp_path,
):
    graph = main_graph(
        tmp_path,
        """
        import lib
        class Task(lib.Base):
            pass
        def use():
            Task().run()
            try:
                pass
            except lib.Error as error:
                error.details()
        """,
    )

    assert callees(graph, "main.use") == [
        "lib.Base.__init__",
        "lib.Base.run",
        "lib.Error.details",
    ]
