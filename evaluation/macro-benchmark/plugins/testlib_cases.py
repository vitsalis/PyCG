"""A pytest plugin: generate the test cases of a module that has a testlib hook.

markdown2's own harness (test/testlib.py, run by `make testone`) imports
test/test_markdown2.py and exhausts its generator `test_cases()`. That hook
adds one test method per case file to the unittest classes of the module.
pytest never calls it, so without this plugin it sees none of the cases.

The plugin exhausts the hook once, before pytest collects the module, so
that pytest collects the generated methods as unittest tests. The hook
itself is not a test: pytest 9 would refuse the whole module because a
function named test_* yields. The plugin runs only the project's own hook
and changes nothing in the checkout. trace.py loads it from `plugins` in
projects.toml; for the tracer it is client code.
"""

import inspect

import pytest

HOOK = "test_cases"


@pytest.hookimpl(wrapper=True)
def pytest_make_collect_report(collector):
    if isinstance(collector, pytest.Module):
        try:
            module = collector.obj
        except Exception:  # noqa: BLE001 - pytest reports the import error itself
            module = None
        hook = getattr(module, HOOK, None)
        if inspect.isgeneratorfunction(hook):
            for _ in hook():
                pass
    return (yield)


@pytest.hookimpl(tryfirst=True)
def pytest_pycollect_makeitem(collector, name, obj):
    if name == HOOK and inspect.isgeneratorfunction(obj):
        return []  # the hook, not a test
    return None
