"""A namespace read by reflection holds the namespace: `C.__dict__` and
`vars(C)` of a class, and `inspect.getmembers(x)` of a class or an instance.
The namespace of an instance stays what the stubs say."""

from programs import analysed, call_graph, callees, main_graph


def test_vars_of_a_class_holds_what_its_body_binds(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class A:
            def _f_one(self): pass
            def _f_two(self): pass
        def run():
            for name, member in vars(A).items():
                member(A())
        run()
        """,
    )

    assert {"main.A._f_one", "main.A._f_two"} <= set(callees(graph, "main.run"))


def test_the_dict_of_a_class_holds_what_its_body_binds(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class A:
            def _f_one(self): pass
            def _f_two(self): pass
        def run():
            for name, member in A.__dict__.items():
                member(A())
        run()
        """,
    )

    assert {"main.A._f_one", "main.A._f_two"} <= set(callees(graph, "main.run"))


def test_getmembers_of_a_class_with_a_predicate(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import inspect
        class A:
            def _f_one(self): pass
            def _f_two(self): pass
        def run():
            for name, member in inspect.getmembers(A, inspect.isfunction):
                member(A())
        run()
        """,
    )

    assert {"main.A._f_one", "main.A._f_two"} <= set(callees(graph, "main.run"))


def test_limit_the_dict_of_an_instance_is_what_the_stubs_say(tmp_path):
    # Python's `vars(job)` holds `action`; the analysis keeps the stubs'
    # dict of unknown values for an instance, whose code may write it.
    graph = main_graph(
        tmp_path,
        """
        class Job:
            def __init__(self, action):
                self.action = action
            def run(self): pass
        def build(): pass
        def by_values():
            for value in Job(build).__dict__.values():
                value()
        def by_vars():
            vars(Job(build))["action"]()
        def of_the_class():
            vars(Job)["run"](Job(build))
        by_values()
        by_vars()
        of_the_class()
        """,
    )

    assert "main.build" not in callees(graph, "main.by_values")
    assert "main.build" not in callees(graph, "main.by_vars")
    # The class's namespace is read in the same program.
    assert "main.Job.run" in callees(graph, "main.of_the_class")


def test_a_constant_key_selects_one_member(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class C:
            def first(self): pass
            def second(self): pass
        def run():
            C.__dict__["first"](C())
        run()
        """,
    )

    assert "main.C.first" in callees(graph, "main.run")
    assert "main.C.second" not in callees(graph, "main.run")


def test_the_keys_are_the_names(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class A:
            def one(self): pass
            def two(self): pass
        def run():
            for name in vars(A):
                getattr(A(), name)()
        run()
        """,
    )

    assert {"main.A.one", "main.A.two"} <= set(callees(graph, "main.run"))


def test_inherited_names_are_members_but_not_in_the_dict(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import inspect
        class A:
            def base(self): pass
        class B(A):
            def own(self): pass
        def own_namespace():
            for name, member in B.__dict__.items():
                member(B())
        def members():
            for name, member in inspect.getmembers(B):
                member(B())
        own_namespace()
        members()
        """,
    )

    assert "main.B.own" in callees(graph, "main.own_namespace")
    assert "main.A.base" not in callees(graph, "main.own_namespace")
    assert {"main.A.base", "main.B.own"} <= set(callees(graph, "main.members"))


def test_getmembers_of_an_instance_binds_the_methods(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import inspect
        class A:
            def __init__(self, action):
                self.action = action
            def method(self): pass
        def action(): pass
        def run():
            for name, member in inspect.getmembers(A(action)):
                member()
        run()
        """,
    )

    assert {"main.A.method", "main.action"} <= set(callees(graph, "main.run"))


def test_static_and_class_methods_in_the_dict_and_as_members(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import inspect
        class C:
            @staticmethod
            def static(): pass
            @classmethod
            def klass(cls): pass
        def from_dict():
            C.__dict__["static"]()
            C.__dict__["klass"]()
        def members():
            for name, member in inspect.getmembers(C):
                member()
        from_dict()
        members()
        """,
    )

    # A staticmethod object is callable; a classmethod object is not.
    assert "main.C.static" in callees(graph, "main.from_dict")
    assert "main.C.klass" not in callees(graph, "main.from_dict")
    assert {"main.C.klass", "main.C.static"} <= set(callees(graph, "main.members"))


def test_a_name_stored_on_the_class_from_outside_its_body(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class A:
            pass
        def run():
            for member in vars(A).values():
                member(A())
        def extra(self): pass
        A.extra = extra
        run()
        """,
    )

    assert "main.extra" in callees(graph, "main.run")


def test_a_class_body_that_uses_its_namespace(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class C:
            def f(self): pass
            locals()
        def run():
            for member in C.__dict__.values():
                member(C())
        run()
        """,
    )

    assert "main.C.f" in callees(graph, "main.run")


def test_limit_a_filter_on_the_name_is_not_evaluated(tmp_path):
    # Python calls only `_func_a`; the analysis does not evaluate the test
    # on the name, and calls every member.
    graph = main_graph(
        tmp_path,
        """
        class A:
            def _func_a(self): pass
            def other(self): pass
        def run():
            for name, member in vars(A).items():
                if name.startswith("_func_"):
                    member(A())
        run()
        """,
    )

    assert {"main.A._func_a", "main.A.other"} <= set(callees(graph, "main.run"))


def test_a_metaclass_that_defines_dict_hides_the_namespace(tmp_path):
    # `vars(C)` and `C.__dict__` are the metaclass's `__dict__` attribute.
    graph = main_graph(
        tmp_path,
        """
        def wrong(): pass
        def right(): pass
        class M(type):
            __dict__ = {}
        class C(metaclass=M):
            __slots__ = ()
            x = staticmethod(wrong)
        class D:
            __dict__ = {}
            x = staticmethod(right)
        def hidden():
            for value in vars(C).values():
                value()
            C.__dict__["x"]()
        def plain():
            vars(D)["x"]()
        hidden()
        plain()
        """,
    )

    assert "main.wrong" not in callees(graph, "main.hidden")
    # A class body's own `__dict__` is not in the way: the namespace
    # descriptor of the metaclass wins.
    assert "main.right" in callees(graph, "main.plain")


def test_limit_an_analysed_dir_leaves_getmembers_to_the_stubs(tmp_path):
    # Python's getmembers lists what `__dir__` returns; the analysis does
    # not evaluate it and lists nothing: edges may be lost, none added.
    graph = main_graph(
        tmp_path,
        """
        import inspect
        class C:
            def hidden(self): pass
            def __dir__(self): return ["shown"]
            def shown(self): pass
        class Meta(type):
            def __dir__(cls): return []
        class K(metaclass=Meta):
            def hidden(self): pass
        class Plain:
            def listed(self): pass
        def of_an_instance():
            for name, value in inspect.getmembers(C()):
                value()
        def of_a_class():
            for name, value in inspect.getmembers(K):
                value(K())
        def control():
            for name, value in inspect.getmembers(Plain()):
                value()
        of_an_instance()
        of_a_class()
        control()
        """,
    )

    called = set(callees(graph, "main.of_an_instance"))
    assert not {"main.C.hidden", "main.C.shown"} & called
    assert "main.K.hidden" not in callees(graph, "main.of_a_class")
    assert "main.Plain.listed" in callees(graph, "main.control")


def test_limit_transformed_class_fields_are_the_values_as_a_load_gives(tmp_path):
    # Python's class attribute is a field descriptor (NamedTuple, a dataclass
    # with slots) or a member (Enum), which calling raises; the analysis
    # takes the value bound in the body, for a load and for the namespace
    # alike.
    graph = main_graph(
        tmp_path,
        """
        import enum
        from dataclasses import dataclass
        from typing import NamedTuple
        def callback(): pass
        class Fn:
            def __call__(self): pass
        class T(NamedTuple):
            field: object = callback
        @dataclass(slots=True)
        class S:
            field: object = callback
        class E(enum.Enum):
            A = Fn()
        def direct():
            T.field()
            S.field()
            E.A()
        def through_the_namespace():
            T.__dict__["field"]()
            S.__dict__["field"]()
            E.__dict__["A"]()
        direct()
        through_the_namespace()
        """,
    )

    expected = {"main.callback", "main.Fn.__call__"}
    assert expected <= set(callees(graph, "main.direct"))
    assert expected <= set(callees(graph, "main.through_the_namespace"))


def test_limit_the_pairs_of_getmembers_do_not_keep_names_apart(tmp_path):
    # As for any list of pairs (`dict([("x", f), ("y", g)])`), a dict made
    # of the pairs gives every value under every name: Python calls only
    # `chosen`.
    graph = main_graph(
        tmp_path,
        """
        import inspect
        def chosen(): pass
        def other(): pass
        class C:
            x = staticmethod(chosen)
            y = staticmethod(other)
        def members():
            dict(inspect.getmembers(C))["x"]()
        def pairs():
            dict([("x", chosen), ("y", other)])["x"]()
        members()
        pairs()
        """,
    )

    assert {"main.chosen", "main.other"} <= set(callees(graph, "main.members"))
    assert {"main.chosen", "main.other"} <= set(callees(graph, "main.pairs"))


def test_getmembers_of_a_module_adds_nothing(tmp_path):
    # The rule makes its list only for a class or an instance: at a cap of
    # one object, a module's members stay the stubs' list.
    source = "import inspect, math\ninspect.getmembers(math).append(None)\n"
    generator = analysed(tmp_path / "cap", {"main.py": source}, cap=1)

    assert "<builtin>.list.append" in generator.output()["main"]

    # A class at the same call gets its members.
    graph = main_graph(
        tmp_path / "control",
        """
        import inspect, math
        class C:
            def f(self): pass
        def run(x):
            for name, value in inspect.getmembers(x):
                value(C())
        run(math)
        run(C)
        """,
    )
    assert "main.C.f" in callees(graph, "main.run")


def test_limit_the_predicate_is_not_evaluated(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import inspect
        class A:
            def f(self): pass
        def run():
            for name, member in inspect.getmembers(A, lambda value: False):
                member(A())
        run()
        """,
    )

    assert "main.A.f" in callees(graph, "main.run")


def test_limit_names_that_python_adds_and_outside_members_are_absent(tmp_path):
    source = """
import inspect
class C:
    def f(self): pass
for name in vars(C):
    own = name
for name, value in inspect.getmembers(C):
    member = name
"""
    generator = analysed(tmp_path, {"main.py": source})
    points_to = generator.output_points_to()

    def names(values):
        # The stubs add a str of unknown value.
        return [value for value in values if value.startswith("'")]

    # Python lists `__module__`, `__dict__`, `__weakref__` and `__doc__`,
    # and getmembers every member of `object` too.
    assert names(points_to["main.own"]) == ["'f'"]
    assert names(points_to["main.member"]) == ["'f'"]


def test_limit_the_methods_of_a_class_namespace_are_named_as_a_dicts(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class C:
            def f(self): pass
        def run():
            for name, value in C.__dict__.items():
                value(C())
        run()
        """,
    )

    # Python: types.MappingProxyType.items.
    assert callees(graph, "main.run") == ["<builtin>.dict.items", "main.C.f"]


def test_limit_a_write_through_the_class_namespace_stays_in_the_dict(tmp_path):
    # Python's mappingproxy refuses the store; the analysis keeps it in the
    # dict that the namespace is, not on the class.
    graph = main_graph(
        tmp_path,
        """
        def f(): pass
        class C:
            def g(self): pass
        def write():
            d = C.__dict__
            d["x"] = f
            d["x"]()
            d["g"](C())
        def load():
            C.x()
        write()
        load()
        """,
    )

    assert {"main.f", "main.C.g"} <= set(callees(graph, "main.write"))
    assert "main.f" not in callees(graph, "main.load")


def test_limit_dir_modules_and_vars_without_an_argument(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "lib.py": "def f(): pass\n",
            "main.py": """
import inspect
import lib
class C:
    def g(self): pass
def by_dir():
    for name in dir(C):
        getattr(C, name)(C())
def of_a_module():
    for name, value in inspect.getmembers(lib):
        value()
    vars(lib)["f"]()
    lib.__dict__["f"]()
def without_an_argument():
    h = lib.f
    vars()["h"]()
def control():
    vars(C)["g"](C())
by_dir()
of_a_module()
without_an_argument()
control()
""",
        },
    )

    # Python calls `C.g`, then `lib.f` in each of the other two.
    assert "main.C.g" not in callees(graph, "main.by_dir")
    assert "lib.f" not in callees(graph, "main.of_a_module")
    assert "lib.f" not in callees(graph, "main.without_an_argument")
    assert "main.C.g" in callees(graph, "main.control")


def test_an_outside_dir_leaves_getmembers_to_the_stubs(tmp_path):
    # `EnumMeta.__dir__` lists the members only: Python's getmembers of the
    # class never loads `hidden`. `Enum.__dir__` of a member lists `hidden`,
    # whose load Python runs; the analysis does not evaluate a `__dir__`
    # other than the default one and loses that edge (a stated limit).
    graph = main_graph(
        tmp_path,
        """
        import enum
        import inspect
        def hit(): pass
        class D:
            def __get__(self, obj, owner):
                hit()
        class E(enum.Enum):
            A = 1
            hidden = D()
        class P:
            hidden = D()
        def of_the_class():
            inspect.getmembers(E)
        def of_a_member():
            inspect.getmembers(E(1))
        def default_directory():
            inspect.getmembers(P())
        of_the_class()
        of_a_member()
        default_directory()
        """,
    )

    assert "main.D.__get__" not in callees(graph, "main.of_the_class")
    assert "main.D.__get__" not in callees(graph, "main.of_a_member")
    assert "main.D.__get__" in callees(graph, "main.default_directory")


def test_a_class_made_by_abcmeta_gets_its_members(tmp_path):
    # `ABCMeta` defines neither `__dir__` nor `__dict__`: Python's own run.
    graph = main_graph(
        tmp_path,
        """
        import abc
        import inspect
        class A(abc.ABC):
            def f(self): pass
        class B(metaclass=abc.ABCMeta):
            def g(self): pass
        def run():
            for name, value in inspect.getmembers(A):
                value(A())
            for value in vars(B).values():
                value(B())
        run()
        """,
    )

    assert {"main.A.f", "main.B.g"} <= set(callees(graph, "main.run"))


def test_class_tests_on_reflected_values(tmp_path):
    # A namespace is not exact (Python gives a mappingproxy): it passes both
    # branches. The list of getmembers and its pairs are exact.
    graph = main_graph(
        tmp_path,
        """
        import inspect
        class C:
            def f(self): pass
        def namespace_is_dict():
            ns = vars(C)
            if isinstance(ns, dict):
                ns["f"](C())
        def namespace_is_not_dict():
            ns = vars(C)
            if not isinstance(ns, dict):
                ns["f"](C())
        def members_are_not_a_list():
            found = inspect.getmembers(C)
            if not isinstance(found, list):
                for name, value in found:
                    value(C())
        def pairs_are_not_tuples():
            for pair in inspect.getmembers(C):
                if not isinstance(pair, tuple):
                    pair[1](C())
        def pairs_are_tuples():
            for pair in inspect.getmembers(C):
                if isinstance(pair, tuple):
                    pair[1](C())
        namespace_is_dict()
        namespace_is_not_dict()
        members_are_not_a_list()
        pairs_are_not_tuples()
        pairs_are_tuples()
        """,
    )

    assert "main.C.f" in callees(graph, "main.namespace_is_dict")
    assert "main.C.f" in callees(graph, "main.namespace_is_not_dict")
    assert "main.C.f" not in callees(graph, "main.members_are_not_a_list")
    assert "main.C.f" not in callees(graph, "main.pairs_are_not_tuples")
    assert "main.C.f" in callees(graph, "main.pairs_are_tuples")


def test_the_first_definition_in_the_mro_decides_the_default(tmp_path):
    # `M(type, Hidden)`: `type` answers `__dict__` and `__dir__` before
    # `Hidden`, so Python uses the defaults; in `N(Hidden, type)` the
    # override wins.
    graph = main_graph(
        tmp_path,
        """
        import inspect
        class Hidden:
            __dict__ = {}
            def __dir__(self):
                return []
        class M(type, Hidden):
            pass
        class N(Hidden, type):
            pass
        class C(metaclass=M):
            def f(self): pass
        class K(metaclass=N):
            def g(self): pass
        def namespace():
            vars(C)["f"](C())
        def members():
            dict(inspect.getmembers(C))["f"](C())
        def hidden_namespace():
            vars(K)["g"](K())
        def hidden_members():
            dict(inspect.getmembers(K))["g"](K())
        namespace()
        members()
        hidden_namespace()
        hidden_members()
        """,
    )

    assert "main.C.f" in callees(graph, "main.namespace")
    assert "main.C.f" in callees(graph, "main.members")
    assert "main.K.g" not in callees(graph, "main.hidden_namespace")
    assert "main.K.g" not in callees(graph, "main.hidden_members")


def test_any_candidate_mro_that_reaches_the_default_applies_the_rule(tmp_path):
    # A base expression that may give either class: the rule applies when
    # some candidate MRO reaches the default `__dir__` first, as a lookup
    # takes every candidate MRO; with `Hidden` as the base, Python lists
    # nothing.
    graph = main_graph(
        tmp_path,
        """
        import inspect
        class Hidden:
            def __dir__(self):
                return []
        class Plain:
            pass
        def pick(flag):
            return Hidden if flag else Plain
        class C(pick(input())):
            def f(self): pass
        def members():
            for name, value in inspect.getmembers(C()):
                value()
        members()
        """,
    )

    assert "main.C.f" in callees(graph, "main.members")
