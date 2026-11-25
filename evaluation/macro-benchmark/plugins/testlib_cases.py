import inspect

import pytest

CASE_GENERATOR_HOOK_NAME = "test_cases"


@pytest.hookimpl(wrapper=True)
def pytest_make_collect_report(collector):
    if isinstance(collector, pytest.Module):
        try:
            module = collector.obj
        except Exception:  # noqa: BLE001 - pytest reports the import error itself
            module = None
        hook = getattr(module, CASE_GENERATOR_HOOK_NAME, None)
        if inspect.isgeneratorfunction(hook):
            for _ in hook():
                pass
    return (yield)


@pytest.hookimpl(tryfirst=True)
def pytest_pycollect_makeitem(collector, name, obj):
    if name == CASE_GENERATOR_HOOK_NAME and inspect.isgeneratorfunction(obj):
        return []
    return None
