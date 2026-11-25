from programs import callees, main_graph


def test_too_few_or_too_many_positional_arguments(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def none(): pass
        def one(a): pass
        def optional(a, b=1): pass
        def run(f):
            f(1)
        for f in (none, one, optional):
            run(f)
        def two(f):
            f(1, 2, 3)
        two(optional)
        """,
    )

    assert callees(graph, "main.run") == ["main.one", "main.optional"]
    assert callees(graph, "main.two") == []


def test_keywords_must_name_a_parameter(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def plain(a): pass
        def keyword(*, key): pass
        def anything(**kwargs): pass
        def positional_only(a, /): pass
        def run(f):
            f(key=1)
        for f in (plain, keyword, anything, positional_only):
            run(f)
        def twice(f):
            f(1, a=2)
        twice(plain)
        """,
    )

    assert callees(graph, "main.run") == ["main.anything", "main.keyword"]
    assert callees(graph, "main.twice") == []


def test_a_required_parameter_must_get_a_value(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def keyword(*, key): pass
        def default(*, key=1): pass
        def run(f):
            f()
        for f in (keyword, default):
            run(f)
        """,
    )

    assert callees(graph, "main.run") == ["main.default"]


def test_receivers_count_as_arguments(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class Base:
            def __init__(self, value): pass
            def method(self): pass
            @classmethod
            def make(cls): pass
            @staticmethod
            def util(): pass
        class Empty:
            def __init__(self): pass
        def build(kind):
            obj = kind()
            obj.method()
            kind.make()
            kind.util()
        build(Base)
        build(Empty)
        """,
    )

    assert callees(graph, "main.build") == [
        "main.Base.make",
        "main.Base.method",
        "main.Base.util",
        "main.Empty.__init__",
    ]


def test_call_of_an_instance_binds_to_its_call_method(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class Handler:
            def __call__(self, event): pass
        def fire(handler):
            handler()
        fire(Handler())
        """,
    )

    assert callees(graph, "main.fire") == []


def test_unknown_arguments_or_signatures_keep_the_edge(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import ext
        @ext.register
        def decorated(a): pass
        def one(a): pass
        def run(args, kw):
            decorated()
            one(*args)
            one(**kw)
        run((), {})
        """,
    )

    assert callees(graph, "main.run") == ["main.decorated", "main.one"]


def test_call_backs_keep_their_edges(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def double(x): return x
        def run(xs):
            return list(map(double, xs))
        run([1])
        """,
    )

    assert "main.double" in callees(graph, "main.run")


def test_a_default_of_none_makes_a_parameter_optional(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def optional(a, b=None, *, key=None): pass
        def run():
            optional(1)
        run()
        """,
    )

    assert callees(graph, "main.run") == ["main.optional"]


def test_a_statement_that_calls_a_function_that_cannot_bind_ends_the_path(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def warn(major, minor, cause, fix): pass
        def keyed(*, key): pass
        def after(): pass
        def missing():
            warn(0, 13, "cause")
            after()
        def assigned():
            result = keyed(1)
            after()
        def unknown_keyword():
            warn(0, 13, "cause", fix="fix", extra=1)
            after()
        def binds():
            warn(0, 13, "cause", fix="fix")
            after()
        def unpacked(args):
            warn(*args)
            after()
        def nested():
            print(warn(0))
            after()
        def guarded():
            try:
                warn(0)
            except TypeError:
                pass
            after()
        def decorated_wrapper(f):
            return f
        @decorated_wrapper
        def decorated(a): pass
        def through_decorator():
            decorated()
            after()
        def rebound_name():
            twice()
            after()
        def twice(a): pass
        twice = after
        for function in (missing, assigned, unknown_keyword, binds, unpacked,
                         nested, guarded, through_decorator, rebound_name):
            function()
        """,
    )

    for function in ("missing", "assigned", "unknown_keyword"):
        assert callees(graph, f"main.{function}") == [], function
    for function in ("binds", "unpacked", "nested", "guarded"):
        assert "main.after" in callees(graph, f"main.{function}"), function
    assert "main.after" in callees(graph, "main.through_decorator")
    assert callees(graph, "main.rebound_name") == ["main.after"]
