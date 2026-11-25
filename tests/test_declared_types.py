from programs import call_graph, callees, main_graph


def test_self_is_an_instance_of_the_class(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class Parser:
            def parse(self):
                self.step()
            def step(self):
                self.finish()
            def finish(self): pass
        """,
    )

    assert callees(graph, "main.Parser.parse") == ["main.Parser.step"]
    assert callees(graph, "main.Parser.step") == ["main.Parser.finish"]


def test_self_is_an_instance_of_every_subclass(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class Base:
            def run(self):
                self.step()
            def step(self): pass
        class Child(Base):
            def step(self): pass
        """,
    )

    assert callees(graph, "main.Base.run") == ["main.Base.step", "main.Child.step"]


def test_limit_a_method_that_analysed_code_calls_keeps_those_receivers(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class Base:
            def run(self):
                self.step()
            def step(self): pass
        class Child(Base):
            def step(self): pass
        Base().run()
        """,
    )

    assert callees(graph, "main.Base.run") == ["main.Base.step"]


def test_subclasses_in_other_modules(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "base.py": """
            class Base:
                def run(self):
                    self.step()
                def step(self): pass
            """,
            "child.py": """
            from base import Base
            class Child(Base):
                def step(self): pass
            """,
            "main.py": "import base, child\n",
        },
    )

    assert callees(graph, "base.Base.run") == ["base.Base.step", "child.Child.step"]


def test_a_subclass_that_overrides_the_method_is_no_receiver(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class Base:
            def run(self):
                self.step()
            def step(self): pass
            @classmethod
            def make(cls):
                cls.step(None)
        class Child(Base):
            def run(self): pass
            def step(self): pass
            @classmethod
            def make(cls): pass
        class Heir(Base):
            def step(self): pass
        """,
    )

    assert callees(graph, "main.Base.run") == ["main.Base.step", "main.Heir.step"]
    assert callees(graph, "main.Base.make") == ["main.Base.step", "main.Heir.step"]


def test_an_alias_of_the_same_method_is_no_override(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class Base:
            def run(self):
                self.step()
            def step(self): pass
        class Child(Base):
            run = Base.run
            def step(self): pass
        """,
    )

    assert callees(graph, "main.Base.run") == ["main.Base.step", "main.Child.step"]


def test_an_override_that_calls_super_passes_its_receiver(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import ext
        class Base:
            def run(self):
                self.step()
            def step(self): pass
        class Child(Base):
            def run(self):
                if ext.flag:
                    super().run()
            def step(self): pass
        """,
    )

    assert callees(graph, "main.Base.run") == ["main.Base.step", "main.Child.step"]


def test_class_and_static_methods(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class Base:
            @classmethod
            def make(cls):
                cls.build()
            @classmethod
            def build(cls): pass
            @staticmethod
            def util(target=None):
                target.run()
            def run(self): pass
        class Child(Base):
            @classmethod
            def build(cls): pass
        """,
    )

    assert callees(graph, "main.Base.make") == ["main.Base.build", "main.Child.build"]
    assert callees(graph, "main.Base.util") == []


def test_a_method_with_only_args_gets_its_receiver_first(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class C:
            def run(*args):
                args[0].helper()
            def helper(self): pass
        """,
    )

    assert callees(graph, "main.C.run") == ["main.C.helper"]


def test_limit_a_decorators_wrapper_gets_no_receiver(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def decorate(function):
            def wrapper(*args):
                args[0].before()
                return function(*args)
            return wrapper
        class C:
            def before(self): pass
            @decorate
            def run(self):
                self.before()
        """,
    )

    assert callees(graph, "main.decorate.wrapper") == ["main.C.run"]
    assert callees(graph, "main.C.run") == ["main.C.before"]


def test_limit_no_arguments_from_callers_that_the_analysis_does_not_see(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def api(callback):
            callback()
        class Service:
            def run(self, callback):
                callback()
        """,
    )

    assert callees(graph, "main.api") == []
    assert callees(graph, "main.Service.run") == []


def test_a_class_with_an_abstract_method_has_no_instance_of_its_own(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import abc
        from abc import abstractmethod
        class Base(abc.ABC):
            def run(self):
                self.step()
            @abc.abstractmethod
            def step(self): pass
        class Other(abc.ABC):
            def run(self):
                self.step()
            @abstractmethod
            def step(self): pass
        class Child(Base):
            def step(self): pass
        """,
    )

    assert callees(graph, "main.Base.run") == ["main.Child.step"]
    assert callees(graph, "main.Other.run") == []


def test_a_protocol_class_has_no_instance_of_its_own(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import typing
        from typing import Protocol
        class Logger(Protocol):
            def log(self):
                self.flush()
            def flush(self): pass
        class Sink(typing.Protocol):
            def log(self):
                self.flush()
            def flush(self): pass
        class FileLogger(Logger):
            def flush(self): pass
        """,
    )

    assert callees(graph, "main.Logger.log") == ["main.FileLogger.flush"]
    assert callees(graph, "main.Sink.log") == []


def test_a_subclass_that_inherits_an_abstract_method_has_no_instance(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import abc
        class Base(abc.ABC):
            def run(self):
                self.step()
            @abc.abstractmethod
            def step(self): pass
        class Middle(Base):
            pass
        """,
    )

    assert callees(graph, "main.Base.run") == []


def test_defaults_flow_where_a_call_may_omit_them(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def g(): pass
        def h(): pass
        def given(cb=g, *, key=g):
            cb()
            key()
        given(h, key=h)
        def omitted(cb=g):
            cb()
        omitted()
        """,
    )

    assert callees(graph, "main.given") == ["main.h"]
    assert callees(graph, "main.omitted") == ["main.g"]


def test_an_entry_point_takes_its_defaults(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def g(): pass
        def api(cb=g, *, key=g):
            cb()
            key()
        class Service:
            def run(self, cb=g):
                cb()
        """,
    )

    assert callees(graph, "main.api") == ["main.g"]
    assert callees(graph, "main.Service.run") == ["main.g"]


def test_a_class_method_entry_point_gets_every_subclass(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        from abc import ABC, abstractmethod
        class Base(ABC):
            @classmethod
            def make(cls):
                cls.build()
            @classmethod
            def build(cls): pass
        class Child(Base):
            @abstractmethod
            def required(self): pass
            @classmethod
            def build(cls): pass
        """,
    )

    assert callees(graph, "main.Base.make") == ["main.Base.build", "main.Child.build"]
