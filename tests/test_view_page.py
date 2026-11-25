import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

import pytest
from test_view import HOSTILE, document, hostile_document

from pycg import formats, view
from pycg.pycg import CallGraphGenerator

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

HERE = Path(__file__).resolve().parent
SAMPLE = HERE / "data" / "view" / "sample.json"
GENERATE = HERE / "data" / "view" / "generate.py"
FAKE_DOM = HERE / "view_dom.js"

ALL = {"outside": True, "implicit": True, "unresolved": True}
NO_OUTSIDE = {**ALL, "outside": False}
NO_IMPLICIT = {**ALL, "implicit": False}
NO_UNRESOLVED = {**ALL, "unresolved": False}


def script(name):
    match = re.search(rf'<script id="{name}">(.*?)</script>', view.template(), re.S)
    assert match is not None
    return match.group(1)


def run_node(program, tmp_path):
    path = tmp_path / "program.js"
    path.write_text(program, encoding="utf-8")
    result = subprocess.run(
        [NODE, str(path)], capture_output=True, text=True, timeout=300
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def logic(tmp_path, expression, source=SAMPLE):
    program = script("pycg-logic") + (
        "\nconst fs = require('fs');\n"
        f"const doc = JSON.parse(fs.readFileSync({json.dumps(str(source))}, 'utf8'));\n"
        "const index = PyCG.buildIndex(doc);\n"
        f"const ALL = {json.dumps(ALL)};\n"
        f"process.stdout.write(JSON.stringify({expression}));\n"
    )
    return run_node(program, tmp_path)


def rows(tmp_path, function, name, filters=ALL):
    return logic(
        tmp_path,
        f"PyCG.{function}(index, {json.dumps(name)}, {json.dumps(filters)})"
        ".map(r => [r.name, r.sites.map(s => [s.line, s.col, s.implicit || null])])",
    )


def page(tmp_path, steps, source=SAMPLE, hash=""):
    html = view.render(Path(source).read_text(encoding="utf-8"))
    html_path = tmp_path / "page.html"
    html_path.write_text(html, encoding="utf-8")
    program = (
        f"const {{loadPage, Event}} = require({json.dumps(str(FAKE_DOM))});\n"
        "const fs = require('fs');\n"
        f"const html = fs.readFileSync({json.dumps(str(html_path))}, 'utf8');\n"
        f"const page = loadPage(html, {{hash: {json.dumps(hash)}}});\n"
        "const out = {};\n"
        f"{steps}\n"
        "process.stdout.write(JSON.stringify(out));\n"
    )
    return run_node(program, tmp_path)


def write_json(path, value):
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    return path


def test_counts(tmp_path):
    assert logic(tmp_path, "index.counts") == {
        "modules": 9,
        "definitions": 40,
        "sites": 47,
        "edges": 46,
        "outside": 16,
        "unresolved": 3,
    }


def test_callees_are_in_the_order_of_their_first_site(tmp_path):
    assert rows(tmp_path, "callees", "shop.cli.main") == [
        ["shop.cart.Cart.__init__", [[15, 11, None]]],
        ["shop.cli.Session.__enter__", [[16, 9, "with"]]],
        ["shop.cli.Session.__exit__", [[16, 9, "with"]]],
        ["shop.cart.Cart.add", [[17, 8, None]]],
        ["json.loads", [[17, 17, None]]],
        ["requests.get", [[18, 11, None]]],
        ["requests.Response.json", [[18, 11, None]]],
        ["<builtin>.print", [[19, 4, None]]],
        ["shop._speedups.escape", [[19, 10, None]]],
        ["<builtin>.str.__new__", [[19, 17, None]]],
        ["shop.cart.Cart.__str__", [[19, 17, None]]],
        ["shop.util.load", [[20, 11, None]]],
    ]


def test_a_site_shows_its_end_only_to_tell_it_from_another(tmp_path):
    labels = logic(
        tmp_path,
        'PyCG.callees(index, "shop.cli.main", ALL)'
        ".map(r => [r.name, r.sites.map(s => PyCG.siteLabel(index, s))])",
    )
    labels = dict(labels)
    assert labels["requests.get"] == ["18:11–32"]
    assert labels["requests.Response.json"] == ["18:11–39"]
    assert labels["shop.cart.Cart.__init__"] == ["15:11"]
    assert labels["shop.cli.Session.__enter__"] == ["16:9"]


def test_a_site_in_another_module_shows_its_file(tmp_path):
    labels = "r => [r.name, r.sites.map(s => PyCG.siteLabel(index, s))]"
    callees = logic(tmp_path, f'PyCG.callees(index, "shop.check", ALL).map({labels})')
    assert callees == [
        ["shop.check.report", ["10:0"]],
        ["shop.cli.main", ["shop/__init__.py 7:11"]],
        ["<builtin>.str.__new__", ["shop/__init__.py 7:17"]],
        ["shop.cart.Cart.__str__", ["shop/__init__.py 7:17"]],
    ]
    callers = logic(
        tmp_path, f'PyCG.callers(index, "shop.cli.main", ALL).map({labels})'
    )
    assert callers == [
        ["shop.check", ["shop/__init__.py 7:11"]],
        ["shop.cli", ["23:4"]],
    ]
    check = logic(tmp_path, 'PyCG.describe(index, "shop.check")')
    assert (check["file"], check["lines"]) == ("shop/check.py", [1, 10])
    assert check["otherModules"] == ["shop"]


def test_the_links_of_a_comparison_chain_are_two_sites(tmp_path):
    result = logic(
        tmp_path,
        'PyCG.callees(index, "shop.check.report", ALL)'
        ".map(r => [r.name, r.sites.map(s => [PyCG.siteLabel(index, s), s.implicit])])",
    )
    assert result == [
        ["shop.check.Level.__lt__", [["8:11", "operator"], ["8:17", "operator"]]]
    ]


def test_sites_in_other_modules_come_last_and_keep_their_own_position(tmp_path):
    def site(line, col, end, callees, **rest):
        return {"line": line, "col": col, "end": end, "callees": callees, **rest}

    source = write_json(
        tmp_path / "graph.json",
        document(
            modules={
                "m": {"file": "m.py", "kind": "source", "status": "analysed"},
                "n": {"file": "n.py", "kind": "source", "status": "analysed"},
            },
            definitions={"m": {"kind": "module", "module": "m", "lines": [1, 3]}},
            outside={name: {"known": "name"} for name in "abcde"},
            calls={
                "m": [
                    site(1, 0, [1, 7], ["e"]),
                    site(2, 0, [2, 3], ["c"]),
                    site(1, 0, [1, 5], ["a"], module="n"),
                    site(1, 0, [1, 9], ["b"], module="n"),
                    site(1, 0, [1, 5], ["d"], module="o"),
                ]
            },
        ),
    )
    result = logic(
        tmp_path,
        'PyCG.callees(index, "m", ALL)'
        ".map(r => [r.name, r.sites.map(s => PyCG.siteLabel(index, s))])",
        source,
    )
    assert result == [
        ["e", ["1:0"]],
        ["c", ["2:0"]],
        ["a", ["n.py 1:0–5"]],
        ["b", ["n.py 1:0–9"]],
        ["d", ["o 1:0"]],
    ]


def test_sites_with_the_same_start_are_ordered_by_their_end(tmp_path):
    def site(line, col, end, callees, **rest):
        return {"line": line, "col": col, "end": end, "callees": callees, **rest}

    source = write_json(
        tmp_path / "graph.json",
        document(
            modules={"m": {"file": "m.py", "kind": "source", "status": "analysed"}},
            definitions={"m": {"kind": "module", "module": "m", "lines": [1, 3]}},
            outside={name: {"known": "name"} for name in "abcd"},
            calls={
                "m": [
                    site(1, 0, [1, 5], ["b"]),
                    site(1, 0, [3, 1], ["a"]),
                    site(2, 4, [2, 9], ["c"]),
                    site(2, 4, [2, 9], ["d"], implicit="with"),
                ]
            },
        ),
    )
    result = logic(
        tmp_path,
        'PyCG.callees(index, "m", ALL)'
        ".map(r => [r.name, r.sites.map(s => PyCG.siteLabel(index, s))])",
        source,
    )
    assert result == [
        ["b", ["1:0–5"]],
        ["a", ["1:0–3:1"]],
        ["c", ["2:4"]],
        ["d", ["2:4"]],
    ]


def test_callees_without_outside_callees(tmp_path):
    names = [name for name, _ in rows(tmp_path, "callees", "shop.cli.main", NO_OUTSIDE)]
    assert names == [
        "shop.cart.Cart.__init__",
        "shop.cli.Session.__enter__",
        "shop.cli.Session.__exit__",
        "shop.cart.Cart.add",
        "shop.cart.Cart.__str__",
        "shop.util.load",
    ]


def test_callees_without_implicit_calls(tmp_path):
    names = [
        name for name, _ in rows(tmp_path, "callees", "shop.cli.main", NO_IMPLICIT)
    ]
    assert "shop.cli.Session.__enter__" not in names
    assert "shop.cli.Session.__exit__" not in names
    assert "shop.cart.Cart.__init__" in names
    assert rows(tmp_path, "callees", "shop.cart.Cart.total", NO_IMPLICIT) == []


def test_callees_of_a_name_without_calls(tmp_path):
    assert rows(tmp_path, "callees", "shop.util.<lambda1>") == []
    assert rows(tmp_path, "callees", "json.loads") == []
    assert rows(tmp_path, "callees", "no.such.name") == []


def test_callers_group_the_sites_of_each_caller(tmp_path):
    assert rows(tmp_path, "callers", "shop.util.fmt") == [
        ["shop.base.Base.describe", [[8, 15, None], [8, 32, None]]],
        ["shop.cart.Cart.__str__", [[28, 15, None]]],
        ["shop.check.Level.__lt__", [[5, 15, None], [5, 27, None]]],
        ["shop.deep.build", [[4, 11, None]]],
        ["shop.util.apply", [[24, 16, None]]],
    ]


def test_callers_follow_the_filters(tmp_path):
    assert rows(tmp_path, "callers", "json.loads") == [
        ["shop.cli.main", [[17, 17, None]]]
    ]
    assert rows(tmp_path, "callers", "json.loads", NO_OUTSIDE) == []
    assert rows(tmp_path, "callers", "shop.cli.Session.__enter__", NO_IMPLICIT) == []
    assert rows(tmp_path, "callers", "shop.cli.main") == [
        ["shop.check", [[7, 11, None]]],
        ["shop.cli", [[23, 4, None]]],
    ]


def test_a_callback_is_a_callee_of_the_library_call(tmp_path):
    assert rows(tmp_path, "callees", "shop.util.apply") == [
        ["<builtin>.list.__init__", [[24, 11, None]]],
        ["<builtin>.map.__init__", [[24, 16, None]]],
        ["shop.util.<lambda1>", [[24, 16, None]]],
        ["shop.util.fmt", [[24, 16, None]]],
    ]


def test_unresolved_sites_and_their_cause(tmp_path):
    expression = (
        "PyCG.unresolved(index, {name}, {filters})"
        ".map(s => [s.line, s.col, s.unresolved])"
    )
    for name, causes in [
        ("shop.util.call_by_name", [[31, 11, "computed name"]]),
        ("shop.util.run_hook", [[39, 11, "no value"], [40, 11, "outside value"]]),
    ]:
        result = logic(
            tmp_path, expression.format(name=json.dumps(name), filters=json.dumps(ALL))
        )
        assert result == causes
        hidden = expression.format(
            name=json.dumps(name), filters=json.dumps(NO_UNRESOLVED)
        )
        assert logic(tmp_path, hidden) == []
    assert (
        logic(tmp_path, expression.format(name='"shop.cli.main"', filters="ALL")) == []
    )


def expand(tmp_path, name, direction, path, filters=ALL):
    return logic(
        tmp_path,
        f"PyCG.expand(index, {json.dumps(name)}, {json.dumps(direction)}, "
        f"{json.dumps(filters)}, {json.dumps(path)})"
        ".map(r => [r.name, r.recursive, r.expandable])",
    )


def test_expanding_marks_direct_recursion(tmp_path):
    walk = "shop.util.walk"
    assert expand(tmp_path, walk, "callees", [walk]) == [[walk, True, False]]
    assert expand(tmp_path, walk, "callers", [walk]) == [
        ["shop.cart.Cart.tree", False, False],
        [walk, True, False],
    ]


def test_expanding_marks_mutual_recursion_on_the_path(tmp_path):
    even, odd = "shop.util.is_even", "shop.util.is_odd"
    assert expand(tmp_path, even, "callees", [even]) == [[odd, False, True]]
    assert expand(tmp_path, odd, "callees", [even, odd]) == [[even, True, False]]


def test_a_row_is_expandable_only_with_visible_children(tmp_path):
    name = "shop.cart.Cart.__str__"
    total = [
        row for row in expand(tmp_path, name, "callees", [name]) if "total" in row[0]
    ]
    assert total == [["shop.cart.Cart.total", False, True]]
    hidden = expand(tmp_path, name, "callees", [name], NO_IMPLICIT)
    assert ["shop.cart.Cart.total", False, False] in hidden
    outside = expand(tmp_path, "shop.util.fmt", "callees", ["shop.util.fmt"])
    assert outside == [["<builtin>.str.format", False, False]]


def search(tmp_path, query, limit=10, source=SAMPLE):
    return logic(
        tmp_path,
        f"(r => [r.total, r.entries.map(e => [e.name, e.kind, e.target])])"
        f"(PyCG.search(index, {json.dumps(query)}, {limit}))",
        source,
    )


def test_search_ranks_an_exact_last_name_first(tmp_path):
    total, entries = search(tmp_path, "walk")
    assert entries[0] == ["shop.util.walk", "function", "shop.util.walk"]
    total, entries = search(tmp_path, "  WALK ")
    assert entries[0][0] == "shop.util.walk"


def test_search_ranks_definitions_before_exports_and_outside_names(tmp_path):
    total, entries = search(tmp_path, "cart")
    assert [entry[0] for entry in entries[:3]] == [
        "shop.cart.Cart",
        "shop.cart",
        "shop.Cart",
    ]
    assert entries[2] == ["shop.Cart", "export", "shop.cart.Cart"]


def test_search_matches_a_dotted_suffix(tmp_path):
    total, entries = search(tmp_path, "Cart.add")
    assert entries[0][0] == "shop.cart.Cart.add"


def test_search_finds_outside_names_exports_and_modules_without_definitions(
    tmp_path,
):
    assert search(tmp_path, "safe_load")[1][0] == [
        "yaml.safe_load",
        "outside",
        "yaml.safe_load",
    ]
    assert search(tmp_path, "shop.escape")[1][0] == [
        "shop.escape",
        "export",
        "shop._speedups.escape",
    ]
    assert search(tmp_path, "broken")[1] == [["shop.broken", "module", "shop.broken"]]
    assert search(tmp_path, "speedups")[1][0] == [
        "shop._speedups",
        "module",
        "shop._speedups",
    ]


def test_search_limits_the_entries_and_counts_every_match(tmp_path):
    total, entries = search(tmp_path, "s", limit=5)
    assert len(entries) == 5
    assert total > 40
    assert search(tmp_path, "") == [0, []]
    assert search(tmp_path, "   ") == [0, []]
    assert search(tmp_path, "zzz") == [0, []]


def module_map(tmp_path, filters=ALL):
    rows = logic(tmp_path, f"PyCG.moduleMap(index, {json.dumps(filters)})")
    return {row["name"]: row for row in rows}


def test_module_map_counts_edges_between_modules(tmp_path):
    modules = module_map(tmp_path)
    assert list(modules) == sorted(modules)
    cli = modules["shop.cli"]
    assert cli["out"] == [["shop.cart", 3], ["shop._speedups", 1], ["shop.util", 1]]
    assert (cli["within"], cli["outside"], cli["callsOut"]) == (3, 5, 5)
    assert modules["shop.util"]["in"] == [
        ["shop.cart", 2],
        ["shop.base", 1],
        ["shop.check", 1],
        ["shop.cli", 1],
        ["shop.deep", 1],
    ]
    shop, check = modules["shop"], modules["shop.check"]
    assert (shop["out"], shop["outside"]) == ([["shop.cart", 1], ["shop.cli", 1]], 1)
    assert (check["out"], check["within"]) == ([["shop.util", 1]], 2)
    assert modules["shop.util"]["within"] == 9
    assert modules["shop.util"]["definitions"] == 12
    assert modules["shop.base"]["outside"] == 1


def test_module_map_marks_failed_and_extension_modules(tmp_path):
    modules = module_map(tmp_path)
    broken = modules["shop.broken"]
    assert (broken["status"], broken["cause"]) == (
        "failed",
        "SyntaxError (line 3)",
    )
    assert broken["definitions"] == 0
    deep = modules["shop.deep"]
    assert (deep["status"], deep["cause"]) == ("partial", "RecursionError")
    assert deep["definitions"] == 1
    speedups = modules["shop._speedups"]
    assert speedups["kind"] == "extension"
    assert speedups["in"] == [["shop.cli", 1]]
    assert speedups["definitions"] == 1


def test_module_map_and_describe_give_the_files_that_a_module_shadows(tmp_path):
    modules = module_map(tmp_path)
    assert modules["shop.util"]["shadows"] == [
        "shop/util.abi3.so",
        "shop/util.cpython-312-darwin.so",
    ]
    assert modules["shop.cart"]["shadows"] == []
    assert logic(tmp_path, 'PyCG.describe(index, "shop")')["shadows"] == ["shop.py"]
    assert logic(tmp_path, 'PyCG.describe(index, "shop.util.fmt")')["shadows"] == []


def test_module_map_follows_the_filters(tmp_path):
    cli = module_map(tmp_path, NO_OUTSIDE)["shop.cli"]
    assert cli["out"] == [["shop.cart", 3], ["shop.util", 1]]
    assert cli["outside"] == 0
    modules = module_map(tmp_path, NO_IMPLICIT)
    assert modules["shop.cli"]["within"] == 1
    assert modules["shop.util"]["within"] == 8
    total = sum(
        row["within"] + row["outside"] + row["callsOut"]
        for row in module_map(tmp_path).values()
    )
    assert total == 46


def test_module_members_are_in_line_order(tmp_path):
    members = logic(tmp_path, 'PyCG.members(index, "shop.cart")')
    assert members[:3] == [
        "shop.cart.Cart",
        "shop.cart.Cart.__init__",
        "shop.cart.Cart.add",
    ]
    assert logic(tmp_path, 'PyCG.members(index, "shop._speedups")') == [
        "shop._speedups.escape"
    ]
    assert logic(tmp_path, 'PyCG.members(index, "shop.broken")') == []


def test_tree_nests_modules_classes_and_functions(tmp_path):
    assert logic(tmp_path, "PyCG.children(index, null)") == ["shop"]
    assert logic(tmp_path, 'PyCG.children(index, "shop")') == [
        "shop._speedups",
        "shop.base",
        "shop.broken",
        "shop.cart",
        "shop.check",
        "shop.cli",
        "shop.deep",
        "shop.util",
    ]
    util = logic(tmp_path, 'PyCG.children(index, "shop.util")')
    assert util[0] == "shop.util.register"
    assert util[-1] == "shop.util.<lambda1>"
    assert "shop.util.outer.inner" not in util
    assert logic(tmp_path, 'PyCG.children(index, "shop.util.outer")') == [
        "shop.util.outer.inner"
    ]
    assert logic(tmp_path, 'PyCG.children(index, "shop._speedups")') == [
        "shop._speedups.escape"
    ]


def test_describe(tmp_path):
    cart = logic(tmp_path, 'PyCG.describe(index, "shop.cart.Cart")')
    assert cart["kind"] == "class"
    assert (cart["file"], cart["lines"]) == ("shop/cart.py", [4, 31])
    assert cart["mro"] == ["shop.cart.Cart", "shop.base.Base", "<builtin>.object"]
    assert cart["exportedAs"] == ["shop.Cart", "shop.cli.Cart"]
    error = logic(tmp_path, 'PyCG.describe(index, "shop.cart.CartError")')
    assert error["mro"] == ["shop.cart.CartError", "<builtin>.ValueError"]
    broken = logic(tmp_path, 'PyCG.describe(index, "shop.broken")')
    assert (broken["kind"], broken["status"]) == ("module", "failed")
    assert broken["lines"] == [0, 0]
    assert broken["cause"] == "SyntaxError (line 3)"
    escape = logic(tmp_path, 'PyCG.describe(index, "shop._speedups.escape")')
    assert (escape["kind"], escape["known"]) == ("outside", "extension")
    assert (escape["module"], escape["file"]) == (
        "shop._speedups",
        "shop/_speedups.cpython-312-darwin.so",
    )
    assert escape["exportedAs"] == ["shop.cli.escape", "shop.escape"]
    loads = logic(tmp_path, 'PyCG.describe(index, "yaml.safe_load")')
    assert (loads["known"], loads["module"], loads["file"]) == ("name", None, None)
    assert logic(tmp_path, 'PyCG.describe(index, "no.such.name")') is None
    json_module = logic(tmp_path, 'PyCG.describe(index, "json")')
    assert (json_module["kind"], json_module["known"]) == ("outside", None)
    assert json_module["exportedAs"] == ["shop.cli.json"]


def test_names_of_object_properties_are_plain_names(tmp_path):
    names = ["constructor", "__proto__", "toString", "hasOwnProperty"]
    source = write_json(
        tmp_path / "graph.json",
        document(
            modules={
                "constructor": {"file": "c.py", "kind": "source", "status": "analysed"}
            },
            definitions={
                "constructor": {
                    "kind": "module",
                    "module": "constructor",
                    "lines": [1, 3],
                },
                "constructor.__proto__": {
                    "kind": "function",
                    "module": "constructor",
                    "lines": [2, 3],
                },
            },
            outside={"toString": {"known": "name"}},
            calls={
                "constructor": [
                    {
                        "line": 1,
                        "col": 0,
                        "end": [1, 9],
                        "callees": ["constructor.__proto__", "toString"],
                    }
                ]
            },
        ),
    )
    result = logic(
        tmp_path,
        "[index.counts, "
        + ", ".join(f'PyCG.describe(index, "{name}")' for name in names)
        + ', PyCG.callees(index, "constructor", ALL).map(r => r.name)'
        + ', PyCG.callers(index, "toString", ALL).map(r => r.name)'
        + ', PyCG.callees(index, "hasOwnProperty", ALL)'
        + ', PyCG.search(index, "proto", 5).entries.map(e => e.name)]',
        source,
    )
    counts, constructor, proto, to_string, has_own, callees, callers, none, found = (
        result
    )
    assert counts["definitions"] == 2 and counts["edges"] == 2
    assert constructor["kind"] == "module"
    assert proto is None
    assert to_string["kind"] == "outside"
    assert has_own is None
    assert callees == ["constructor.__proto__", "toString"]
    assert callers == ["constructor"]
    assert none == []
    assert found == ["constructor.__proto__"]


def test_header_shows_the_package_tool_and_counts(tmp_path):
    out = page(
        tmp_path,
        "out.title = page.document.title;out.header = page.text(page.first('top'));",
    )
    assert out["title"] == "shop 2.1.0 call graph"
    header = out["header"]
    for text in [
        "shop",
        "2.1.0",
        "pycg 0.1.0.dev0",
        "9 modules",
        "40 definitions",
        "47 call sites",
        "46 edges",
        "16 outside callees",
        "3 unresolved sites",
    ]:
        assert text in header


def test_search_with_keys_opens_the_function(tmp_path):
    out = page(
        tmp_path,
        """
        const search = page.byId('search');
        page.key(page.document.body, '/');
        out.focused = page.document.activeElement === search;
        page.type(search, 'is_');
        out.results = page.all('result').map(r => page.text(r.firstChild));
        page.key(search, 'ArrowDown');
        out.selected = page.all('result').map(r => r.getAttribute('aria-selected'));
        out.activedescendant = search.getAttribute('aria-activedescendant');
        page.key(search, 'Enter');
        out.hash = page.location.hash;
        page.settle();
        out.node = page.text(page.first('node-name'));
        out.card = page.text(page.first('card'));
        out.callees = page.all('row', page.byId('callees')).map(r => page.text(r));
        """,
    )
    assert out["focused"] is True
    assert out["results"] == ["shop.util.is_odd", "shop.util.is_even"]
    assert out["selected"] == ["false", "true"]
    assert out["activedescendant"] == "result-1"
    assert out["hash"] == "#shop.util.is_even"
    assert out["node"] == "shop.util.is_even"
    assert "shop/util.py, lines 17–18" in out["card"]
    assert len(out["callees"]) == 1 and "shop.util.is_odd" in out["callees"][0]


def test_expanding_a_callee_in_place_marks_recursion(tmp_path):
    out = page(
        tmp_path,
        """
        const callees = page.byId('callees');
        page.first('toggle', callees).click();
        out.rows = page.all('row', callees).map(r => page.text(r));
        out.recursive = page.all('recursive', callees).length;
        out.toggles = page.all('toggle', callees)
          .filter(t => t.tagName === 'BUTTON').length;
        page.first('toggle', callees).click();
        out.collapsed = page.all('row', callees).length;
        """,
        hash="#shop.util.is_even",
    )
    assert len(out["rows"]) == 2
    assert "shop.util.is_odd" in out["rows"][0]
    assert "shop.util.is_even" in out["rows"][1]
    assert out["recursive"] >= 1
    assert out["toggles"] == 1
    assert out["collapsed"] == 1


def test_expanded_rows_stay_expanded_when_a_filter_changes(tmp_path):
    out = page(
        tmp_path,
        """
        const callees = page.byId('callees');
        page.first('toggle', callees).click();
        out.before = page.all('row', callees).length;
        page.byId('filter-outside').click();
        out.after = page.all('row', callees).length;
        page.location.hash = '#shop.util.is_odd';
        page.settle();
        out.other = page.all('row', page.byId('callees')).length;
        """,
        hash="#shop.util.is_even",
    )
    assert (out["before"], out["after"], out["other"]) == (2, 2, 1)


def test_callee_rows_show_sites_constructs_and_how_outside_names_are_known(tmp_path):
    out = page(
        tmp_path,
        """
        const callees = () =>
          page.all('row', page.byId('callees')).map(r => page.text(r));
        out.main = callees();
        page.location.hash = '#shop.util.load';
        page.settle();
        out.load = callees();
        """,
        hash="#shop.cli.main",
    )
    main = out["main"]
    assert "16:9 with" in main[1]
    get = next(text for text in main if "requests.get" in text)
    assert "18:11–32" in get
    json_loads = next(text for text in main if "json.loads" in text)
    assert "stub" in json_loads and "17:17" in json_loads
    assert "extension" in next(text for text in main if "escape" in text)
    assert "17:8" in next(text for text in main if "Cart.add" in text)
    assert len(out["load"]) == 1 and "name" in out["load"][0].replace("yaml", "")


def test_filters_apply_to_the_hierarchy(tmp_path):
    out = page(
        tmp_path,
        """
        const count = () => page.all('row', page.byId('callees')).length;
        out.all = count();
        page.byId('filter-outside').click();
        out.noOutside = count();
        page.byId('filter-implicit').click();
        out.noImplicit = count();
        page.location.hash = '#shop.util.call_by_name';
        page.settle();
        out.unresolved = page.text(page.byId('unresolved'));
        page.byId('filter-unresolved').click();
        out.hidden = page.byId('unresolved').hidden;
        """,
        hash="#shop.cli.main",
    )
    assert (out["all"], out["noOutside"], out["noImplicit"]) == (12, 6, 4)
    assert "31:11" in out["unresolved"] and "computed name" in out["unresolved"]
    assert out["hidden"] is True


def test_callers_and_the_card_of_an_outside_name(tmp_path):
    out = page(
        tmp_path,
        """
        out.card = page.text(page.first('card'));
        out.callers = page.all('row', page.byId('callers')).map(r => page.text(r));
        """,
        hash="#shop._speedups.escape",
    )
    assert "extension" in out["card"]
    assert "shop.escape" in out["card"]
    assert len(out["callers"]) == 1 and "shop.cli.main" in out["callers"][0]


def test_card_and_rows_of_a_name_with_sites_in_two_modules(tmp_path):
    out = page(
        tmp_path,
        """
        out.card = page.text(page.first('card'));
        out.callees = page.all('row', page.byId('callees')).map(r => page.text(r));
        page.location.hash = '#shop.check.report';
        page.settle();
        out.chain = page.all('site', page.byId('callees')).map(s => page.text(s));
        """,
        hash="#shop.check",
    )
    assert "shop/check.py, lines 1–10" in out["card"]
    assert "shop/__init__.py" in out["card"]
    main = next(text for text in out["callees"] if "shop.cli.main" in text)
    assert "shop/__init__.py 7:11" in main
    assert out["chain"] == ["8:11 operator", "8:17 operator"]


def test_card_of_an_outside_module_that_the_package_exports(tmp_path):
    out = page(tmp_path, "out.card = page.text(page.first('card'));", hash="#json")
    assert "outside" in out["card"]
    assert "shop.cli.json" in out["card"]
    assert "No module" not in out["card"]


def test_failed_module_card_shows_the_cause(tmp_path):
    out = page(
        tmp_path, "out.card = page.text(page.first('card'));", hash="#shop.broken"
    )
    assert "failed" in out["card"]
    assert "failed: SyntaxError (line 3)" in out["card"]
    assert "shop/broken.py" in out["card"] and "lines" not in out["card"]


def test_partial_module_is_marked_incomplete(tmp_path):
    out = page(
        tmp_path,
        """
        out.card = page.text(page.first('card'));
        const tree = page.byId('tree');
        page.first('toggle', tree).click();
        out.tree = page.all('tree-item', tree).map(i => page.text(i.firstChild));
        page.byId('tab-modules').click();
        out.row = page.text(page.byId('module-shop.deep'));
        """,
        hash="#shop.deep",
    )
    assert "partial: RecursionError" in out["card"]
    assert "may call less" in out["card"]
    assert "deep" in next(text for text in out["tree"] if "partial" in text)
    assert "partial" in out["row"] and "RecursionError" in out["row"]


def test_shadowed_files_are_marked_on_the_card_tree_and_module_map(tmp_path):
    out = page(
        tmp_path,
        """
        out.card = page.text(page.first('card'));
        const tree = page.byId('tree');
        out.root = page.text(page.first('tree-item', tree).firstChild);
        page.byId('tab-modules').click();
        out.util = page.text(page.byId('module-shop.util'));
        out.cart = page.text(page.byId('module-shop.cart'));
        """,
        hash="#shop.util",
    )
    shadows = "shadows shop/util.abi3.so, shop/util.cpython-312-darwin.so: not analysed"
    assert shadows in out["card"]
    assert shadows in out["util"]
    assert "shadows" not in out["cart"]
    assert "shadows" in out["root"]


def test_constructs_and_causes_have_their_description_as_tooltip(tmp_path):
    out = page(
        tmp_path,
        """
        const chip = page.withText('site', '16:9 with', page.byId('callees'));
        out.chip = chip.getAttribute('title');
        page.location.hash = '#shop.util.run_hook';
        page.settle();
        const items = page.byId('unresolved').children[1].children;
        out.unresolved = items.map(i => [page.text(i), i.getAttribute('title')]);
        """,
        hash="#shop.cli.main",
    )
    assert out["chip"].startswith("with: ")
    assert "__enter__" in out["chip"]
    assert out["unresolved"][0][0] == "39:11 no value"
    assert out["unresolved"][1][0] == "40:11–54 outside value"
    assert out["unresolved"][1][1].startswith("outside value: ")


def test_unknown_name_in_the_address(tmp_path):
    out = page(tmp_path, "out.card = page.text(page.first('card'));", hash="#no.such")
    assert "no.such" in out["card"]
    out = page(tmp_path, "out.card = page.text(page.first('card'));", hash="#%E0%A4%A")
    assert "%E0%A4%A" in out["card"]


def test_tree_opens_lazily_and_selects(tmp_path):
    out = page(
        tmp_path,
        """
        const tree = page.byId('tree');
        out.before = page.all('tree-item', tree).length;
        page.first('toggle', tree).click();
        out.after = page.all('tree-item', tree).map(i => page.text(i.firstChild));
        page.withText('label', 'util', tree).click();
        out.hash = page.location.hash;
        """,
    )
    assert out["before"] == 1
    assert len(out["after"]) == 9
    assert any("failed" in text for text in out["after"])
    assert any("extension" in text for text in out["after"])
    assert out["hash"] == "#shop.util"


def test_module_map_opens_a_function_in_the_hierarchy(tmp_path):
    out = page(
        tmp_path,
        """
        page.byId('tab-modules').click();
        out.hierarchyHidden = page.byId('hierarchy').hidden;
        const table = page.byId('module-table');
        out.rows = page.all('module-row', table).map(r => page.text(r));
        page.withText('module-name', 'shop.cli', table).click();
        out.detail = page.text(page.first('module-detail', table));
        const detail = page.first('module-detail', table);
        page.withText('label', 'shop.cli.main', detail).click();
        out.hash = page.location.hash;
        page.settle();
        out.modulesHidden = page.byId('modules').hidden;
        out.node = page.text(page.first('node-name'));
        """,
    )
    assert out["hierarchyHidden"] is True
    assert len(out["rows"]) == 9
    broken = next(row for row in out["rows"] if row.startswith("shop.broken"))
    assert "failed" in broken and "SyntaxError" in broken
    assert "extension" in next(
        row for row in out["rows"] if row.startswith("shop._speedups")
    )
    assert "shop.cart" in out["detail"] and "3" in out["detail"]
    assert out["hash"] == "#shop.cli.main"
    assert out["modulesHidden"] is True
    assert out["node"] == "shop.cli.main"


def test_module_map_follows_the_filters_on_the_page(tmp_path):
    out = page(
        tmp_path,
        """
        page.byId('tab-modules').click();
        const cells = () =>
          page.byId('module-shop.cli').children.map(td => page.text(td));
        out.before = cells();
        page.byId('filter-outside').click();
        out.after = cells();
        """,
    )
    assert out["before"] == ["shop.cli", "analysed", "4", "5", "1", "3", "5"]
    assert out["after"] == ["shop.cli", "analysed", "4", "4", "1", "3", "–"]


def test_hostile_names_are_shown_as_text(tmp_path):
    source = write_json(tmp_path / "hostile.json", hostile_document())
    module = f"m0.{HOSTILE[0]}"
    out = page(
        tmp_path,
        """
        out.title = page.document.title;
        out.header = page.text(page.first('top'));
        out.node = page.text(page.first('node-name'));
        out.card = page.text(page.first('card'));
        out.callees = page.text(page.byId('callees'));
        page.type(page.byId('search'), 'script');
        out.results = page.all('result').length;
        page.byId('tab-modules').click();
        out.modules = page.text(page.byId('module-table'));
        out.scripts = page.tags().filter(tag => tag === 'SCRIPT').length;
        """,
        source=source,
        hash="#" + quote(module, safe=""),
    )
    assert HOSTILE[0] in out["title"]
    assert HOSTILE[0] in out["header"]
    assert out["node"] == module
    assert f"x.{HOSTILE[0]}" in out["callees"]
    assert HOSTILE[0] in out["card"]
    assert out["results"] >= 4
    assert HOSTILE[0] in out["modules"]
    assert out["scripts"] == 1


def test_page_refuses_an_unknown_format(tmp_path):
    source = write_json(tmp_path / "graph.json", document(format="pycg/9"))
    out = page(tmp_path, "out.text = page.text(page.byId('app'));", source=source)
    assert "pycg/9" in out["text"]


def test_page_reports_a_malformed_document(tmp_path):
    source = write_json(
        tmp_path / "graph.json",
        document(calls={"m": [{"line": 1, "col": 0, "end": [1, 3]}]}),
    )
    out = page(tmp_path, "out.text = page.text(page.byId('app'));", source=source)
    assert "cannot be read" in out["text"]


@pytest.fixture(scope="module")
def own(tmp_path_factory):
    root = HERE.parent
    files = sorted(str(path) for path in (root / "pycg").rglob("*.py"))
    generator = CallGraphGenerator(files, str(root))
    generator.analyze()
    document = generator.document("pycg", None)
    path = tmp_path_factory.mktemp("own") / "pycg.json"
    path.write_text(formats.dumps(document), encoding="utf-8")
    return path, document


def test_callers_and_callees_are_the_edges_of_a_real_document(own, tmp_path):
    path, document = own
    expected = formats.edges(document)
    callers = {name: set() for name in expected}
    for caller, callees in expected.items():
        for callee in callees:
            callers[callee].add(caller)
    result = logic(
        tmp_path,
        """(() => {
          const names = %s;
          const sorted = (rows) => rows.map((row) => row.name).sort();
          return {
            counts: index.counts,
            callees: Object.fromEntries(
              names.map((n) => [n, sorted(PyCG.callees(index, n, ALL))])),
            callers: Object.fromEntries(
              names.map((n) => [n, sorted(PyCG.callers(index, n, ALL))])),
          };
        })()"""
        % json.dumps(sorted(expected)),
        path,
    )
    assert result["callees"] == expected
    assert result["callers"] == {name: sorted(found) for name, found in callers.items()}
    counts = result["counts"]
    assert counts["definitions"] == len(document["definitions"])
    assert counts["edges"] == sum(len(callees) for callees in expected.values())
    assert counts["sites"] == sum(len(sites) for sites in document["calls"].values())


def test_page_of_a_real_document(own, tmp_path):
    path, document = own
    caller = "pycg.view.main"
    expected = formats.edges(document)[caller]
    out = page(
        tmp_path,
        """
        out.header = page.text(page.first('top'));
        out.callees = page.all('row', page.byId('callees'))
          .map(r => page.text(page.first('label', r)));
        page.byId('tab-modules').click();
        out.modules = page.all('module-row').length;
        """,
        source=path,
        hash="#" + caller,
    )
    assert f"{len(document['modules'])} modules" in out["header"]
    assert sorted(out["callees"]) == expected
    assert out["modules"] == len(document["modules"])


@pytest.fixture(scope="module")
def large(tmp_path_factory):
    path = tmp_path_factory.mktemp("large") / "large.json"
    subprocess.run([sys.executable, str(GENERATE), str(path)], check=True)
    return path


def test_large_document_has_the_stated_size(large, tmp_path):
    counts = logic(tmp_path, "index.counts", large)
    assert counts["definitions"] >= 20000
    assert counts["sites"] >= 100000


def test_logic_is_fast_on_a_large_document(large, tmp_path):
    timings = logic(
        tmp_path,
        """(() => {
          const t = {};
          const time = (name, f) => {
            const start = process.hrtime.bigint();
            const value = f();
            t[name] = Number(process.hrtime.bigint() - start) / 1e6;
            return value;
          };
          const text = fs.readFileSync(%s, 'utf8');
          const parsed = time('parse', () => JSON.parse(text));
          time('index', () => PyCG.buildIndex(parsed));
          for (const query of ['a', 'f1', 'hub', 'm001.f', 'zzzz'])
            time('search ' + query, () => PyCG.search(index, query, 50));
          const hub = PyCG.search(index, 'hub', 1).entries[0].name;
          t.hubCallers = time('callers', () => PyCG.callers(index, hub, ALL)).length;
          time('expand', () => PyCG.expand(index, hub, 'callers', ALL, [hub]));
          time('modules', () => PyCG.moduleMap(index, ALL));
          return t;
        })()"""
        % json.dumps(str(large)),
        large,
    )
    print(json.dumps(timings, indent=1))
    assert timings["hubCallers"] >= 1000
    assert timings["index"] < 3000
    assert max(v for k, v in timings.items() if k.startswith("search")) < 200
    assert timings["expand"] < 500
    assert timings["modules"] < 2000


def test_page_renders_only_what_is_visible_on_a_large_document(large, tmp_path):
    out = page(
        tmp_path,
        """
        out.load = page.created();
        page.type(page.byId('search'), 'hub');
        page.key(page.byId('search'), 'Enter');
        page.settle();
        out.callers = page.all('row', page.byId('callers')).length;
        out.more = page.all('more', page.byId('callers')).length;
        out.hub = page.created();
        page.byId('tab-modules').click();
        out.modules = page.all('module-row').length;
        out.total = page.created();
        """,
        source=large,
    )
    print(json.dumps(out))
    assert out["callers"] <= 200
    assert out["more"] == 1
    assert out["load"] < 5000
    assert out["total"] < 20000
