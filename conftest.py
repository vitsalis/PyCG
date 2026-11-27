import os

SHARD = os.environ.get("PYCG_TEST_SHARD")
collect_ignore = ["tests/cases"]


def pytest_collection_modifyitems(config, items):
    if SHARD is None:
        return
    index, count = (int(part) for part in SHARD.split("/"))
    assert 0 <= index < count, SHARD
    kept = [item for position, item in enumerate(items) if position % count == index]
    left = [item for position, item in enumerate(items) if position % count != index]
    config.hook.pytest_deselected(items=left)
    items[:] = kept
