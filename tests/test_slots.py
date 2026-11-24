from programs import callees, main_graph


def test_a_slot_load_does_not_call_getattr(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def work(): pass
        class Cache:
            __slots__ = ("_store", "__self__")
            def __init__(self):
                self._store = work
            def __getattr__(self, name):
                return work
            def run(self):
                self._store()
                self.__self__
        Cache().run()
        """,
    )

    assert callees(graph, "main.Cache.run") == ["main.work"]


def test_slots_as_a_string_or_a_list(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def work(): pass
        class Base:
            def __getattr__(self, name): pass
        class One(Base):
            __slots__ = "value"
            def run(self):
                self.value
        class Many(Base):
            __slots__ = ["first", "second"]
            def run(self):
                self.second
        """,
    )

    assert callees(graph, "main.One.run") == []
    assert callees(graph, "main.Many.run") == []


def test_a_slot_shadows_a_property_of_a_base(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        from typing import Protocol
        class Wrapped(Protocol):
            @property
            def __wrapped__(self): pass
        class Wrapper(Wrapped):
            __slots__ = ("__wrapped__",)
            def __init__(self, f):
                self.__wrapped__ = f
            def run(self):
                return self.__wrapped__
        """,
    )

    assert callees(graph, "main.Wrapper.run") == []


def test_a_private_slot_is_mangled(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class Node:
            __slots__ = ("__parent",)
            def __getattr__(self, name): pass
            def run(self):
                self.__parent
        """,
    )

    assert callees(graph, "main.Node.run") == []


def test_slots_of_another_form_define_nothing(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        NAMES = ("value",)
        class Node:
            __slots__ = NAMES
            def __getattr__(self, name): pass
            def run(self):
                self.value
        """,
    )

    assert callees(graph, "main.Node.run") == ["main.Node.__getattr__"]


def test_a_slot_of_a_subclass_does_not_hide_the_base_attribute(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class Base:
            def __getattr__(self, name): pass
            def run(self):
                self.value
        class Child(Base):
            __slots__ = ("value",)
        Base().run()
        """,
    )

    assert callees(graph, "main.Base.run") == ["main.Base.__getattr__"]


def test_dict_and_weakref_in_slots_are_no_slots(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class Relay:
            __slots__ = ("__dict__", "__weakref__")
            def run(self):
                self.__dict__.values()
        """,
    )

    assert callees(graph, "main.Relay.run") == ["<builtin>.dict.values"]


def test_slots_follow_the_binding_that_reaches_the_end_of_the_body(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class Base:
            def run(self): pass
        class Child(Base):
            __slots__ = ("run",)
            __slots__ = ()
        Child().run()
        """,
    )

    assert callees(graph, "main") == ["main.Base.run"]


def test_slots_bound_on_some_paths_define_no_names(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import ext
        class Base:
            def run(self): pass
        class Child(Base):
            if ext.flag:
                __slots__ = ("run",)
        Child().run()
        """,
    )

    assert callees(graph, "main") == ["main.Base.run"]


def test_slots_given_as_a_dict_and_the_weakref_slot(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class Node:
            __slots__ = {"value": "the value", "__weakref__": None}
            def __getattr__(self, name): pass
            def run(self):
                self.value
                self.__weakref__
        """,
    )

    assert callees(graph, "main.Node.run") == []


def test_a_later_plain_binding_replaces_an_uncertain_one(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import ext
        def work(): pass
        class Base:
            def run(self): pass
        class Child(Base):
            if ext.flag:
                __slots__ = ()
            __slots__ = ("run",)
        child = Child()
        child.run = work
        child.run()
        """,
    )

    assert callees(graph, "main") == ["main.work"]
