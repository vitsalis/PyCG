import ast
import gc

import pytest
from programs import analysed

NESTED_SCOPES = {
    "main.py": """
        import helper

        class Outer:
            class Inner:
                def method(self):
                    return [item for item in range(3)]

        def outer():
            def inner():
                return lambda: helper.run()
            return inner

        outer()()()
        Outer.Inner().method()
    """,
    "helper.py": """
        def run():
            return {key: value for key, value in ((1, 2),)}
    """,
}


@pytest.fixture
def collector_off():
    collecting = gc.isenabled()
    gc.collect()
    gc.disable()
    yield
    if collecting:
        gc.enable()


def test_no_syntax_tree_outlives_the_analysis(tmp_path, collector_off):
    analysed(tmp_path, NESTED_SCOPES)
    trees = (ast.Module, ast.stmt, ast.expr)
    assert not [obj for obj in gc.get_objects() if isinstance(obj, trees)]


@pytest.mark.parametrize("collecting", [True, False])
def test_the_analysis_leaves_the_collector_as_it_found_it(tmp_path, collecting):
    was = gc.isenabled()
    try:
        if collecting:
            gc.enable()
        else:
            gc.disable()
        analysed(tmp_path, NESTED_SCOPES)
        assert gc.isenabled() is collecting
    finally:
        if was:
            gc.enable()
        else:
            gc.disable()
