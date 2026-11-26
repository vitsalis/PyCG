from programs import callees, main_graph


def test_with_calls_enter_and_exit_and_binds_the_result_of_enter(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def f(): pass
        class Lock:
            def __enter__(self):
                return f
            def __exit__(self, kind, value, traceback):
                pass
        def use(lock):
            with lock as acquired:
                acquired()
        use(Lock())
        """,
    )

    assert callees(graph, "main.use") == [
        "main.Lock.__enter__",
        "main.Lock.__exit__",
        "main.f",
    ]


def test_async_with(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class Session:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *exc):
                pass
            def get(self): pass
        async def use():
            async with Session() as session:
                session.get()
        """,
    )

    assert callees(graph, "main.use") == [
        "main.Session.__aenter__",
        "main.Session.__aexit__",
        "main.Session.get",
    ]


def test_async_with_awaits_what_aenter_and_aexit_return(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class Pending:
            def __await__(self):
                yield
        class Manager:
            async def __aenter__(self): return self
            def __aexit__(self, *args): return Pending()
        class Unbound:
            def __aenter__(self): return Pending()
            async def __aexit__(self, *args): pass
        class Sync:
            def __enter__(self): return Pending()
            def __exit__(self, *args): return Pending()
        async def bound():
            async with Manager() as manager:
                pass
        async def unbound():
            async with Unbound():
                pass
        def sync():
            with Sync():
                pass
        """,
    )

    assert callees(graph, "main.bound") == [
        "main.Manager.__aenter__",
        "main.Manager.__aexit__",
        "main.Pending.__await__",
    ]
    assert callees(graph, "main.unbound") == [
        "main.Pending.__await__",
        "main.Unbound.__aenter__",
        "main.Unbound.__aexit__",
    ]
    assert callees(graph, "main.sync") == ["main.Sync.__enter__", "main.Sync.__exit__"]


def test_with_on_external_objects_gives_no_implicit_edges(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import ext
        def read(path):
            with open(path) as file, ext.connection as connection:
                file.read()
                connection.close()
        """,
    )

    assert callees(graph, "main.read") == [
        "<builtin>.open",
        "ext.connection.close",
        "io.TextIOWrapper.read",
    ]


def test_raise_instantiates_a_class(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class Failure(Exception):
            def __init__(self, message="failed"):
                self.message = message
        class Plain(Exception):
            pass
        class Cause(Exception):
            def __init__(self): pass
        def check(flag):
            if flag:
                raise Failure
            raise Plain from Failure()
        def chain():
            raise Plain from Cause
        """,
    )

    assert callees(graph, "main.check") == [
        "<builtin>.Exception.__init__",
        "main.Failure.__init__",
    ]
    assert callees(graph, "main.chain") == [
        "<builtin>.Exception.__init__",
        "main.Cause.__init__",
    ]


def test_raise_of_a_builtin_class_without_a_call_gives_no_edge(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def stop():
            raise StopIteration
        def fail():
            raise ValueError("bad")
        """,
    )

    assert callees(graph, "main.stop") == []
    assert callees(graph, "main.fail") == ["<builtin>.ValueError"]


def test_handler_name_holds_instances_of_the_handled_classes(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class Error(Exception):
            def report(self): pass
        class Timeout(Error):
            def report(self): pass
        class Other(Exception):
            def report(self): pass
        def run():
            raise Timeout()
        def other():
            raise Other()
        try:
            run()
        except Error as error:
            error.report()
        """,
    )

    assert callees(graph, "main") == [
        "main.Error.report",
        "main.Timeout.report",
        "main.run",
    ]


def test_handler_with_a_tuple_and_with_external_classes(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import ext
        class A(Exception):
            def a(self): pass
        class B(Exception):
            def b(self): pass
        def run():
            raise A()
            raise B()
        try:
            run()
        except (A, B) as error:
            error.a()
            error.b()
        except ext.Error as error:
            error.details()
        """,
    )

    assert {"ext.Error.details", "main.A.a", "main.B.b"} <= set(callees(graph, "main"))


def test_handler_with_a_tuple_that_contains_itself_terminates(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class Error(Exception):
            def report(self): pass
        kinds = ()
        kinds = (kinds, Error)
        def run():
            raise Error()
        try:
            run()
        except kinds as error:
            error.report()
        """,
    )

    assert "main.Error.report" in callees(graph, "main")


def test_a_handler_tuple_nested_twice_catches_its_class_once(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class E(Exception):
            def m(self): pass
        inner = (E,)
        outer = (inner,)
        def run():
            try:
                pass
            except (inner, outer) as error:
                error.m()
        run()
        """,
    )

    assert callees(graph, "main.run") == ["main.E.m"]
