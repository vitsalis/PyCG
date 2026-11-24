"""Tests of the committed table evaluation/common/same_function.json, on the
interpreter that runs them: every group names one object of its standard
library (a name that this interpreter lacks fails the test, unless ABSENT
exempts it explicitly; it exempts none today), and the table is
in order. The gate runs them on Python 3.12 and 3.15; the table holds only
groups that are one object on every supported CPython."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

COMMON = Path(__file__).resolve().parents[1] / "common"
_spec = importlib.util.spec_from_file_location("lookup", COMMON / "lookup.py")
lookup = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lookup)
GROUPS = json.loads((COMMON / "same_function.json").read_text())["groups"]


# Names that are absent on purpose on a supported Python, by version:
# {name: (major, minor) of the first version that has it}. None today.
ABSENT = {}


@pytest.mark.parametrize("group", GROUPS, ids=[g["representative"] for g in GROUPS])
def test_every_name_of_a_group_is_one_object(group):
    names = [n for n in group["names"] if sys.version_info[:2] >= ABSENT.get(n, (0, 0))]
    found = [lookup.resolve(name) for name in names]
    unresolved = [n for n, (status, _) in zip(names, found) if status != "object"]
    assert not unresolved, unresolved
    assert all(obj is found[0][1] for _, obj in found), group["names"]


def test_the_table_is_in_order_and_each_name_has_one_group():
    representatives = [g["representative"] for g in GROUPS]
    assert representatives == sorted(representatives)
    names = [name for g in GROUPS for name in g["names"]]
    assert len(names) == len(set(names))
    for group in GROUPS:
        assert group["names"] == sorted(group["names"])
        assert len(group["names"]) > 1
        assert group["representative"] in group["names"]
        assert group["source"]
