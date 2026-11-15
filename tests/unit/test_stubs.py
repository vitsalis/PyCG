"""The loader of the stub data (pycg/analysis/stubs.py): on the data that
the package ships, and on the data of the fixture typeshed checkout."""

from pathlib import Path

import pytest

from pycg.analysis.stubs import Stubs, class_names

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures/typeshed/expected"


@pytest.fixture(scope="module")
def stubs():
    return Stubs()


def _paths(definitions):
    return [(d.kind, d.path, d.owner) for d in definitions]


def test_functions_of_modules(stubs):
    (compile,) = stubs.find("re.compile")
    assert (compile.kind, compile.path, compile.owner) == (
        "function",
        "re.compile",
        None,
    )
    results = {str(s["r"]) for s in compile.entry["s"]}
    assert all(result.startswith("['re.Pattern'") for result in results)


def test_methods_are_found_through_the_class(stubs):
    assert _paths(stubs.find("re.Pattern.match")) == [
        ("function", "re.Pattern.match", "re.Pattern")
    ]
    # Inherited: the class of the MRO that defines it.
    assert _paths(stubs.find("collections.OrderedDict.get")) == [
        ("function", "builtins.dict.get", "builtins.dict")
    ]
    assert _paths(stubs.find("builtins.bool.__init__")) == [
        ("function", "builtins.object.__init__", "builtins.object")
    ]


def test_paths_through_re_exports_and_submodules(stubs):
    # `os.path` is a submodule whose names come from a module per platform.
    assert _paths(stubs.find("os.path.join")) == [
        ("function", "ntpath.join", None),
        ("function", "posixpath.join", None),
    ]
    assert _paths(stubs.find("collections.abc.MutableMapping")) == [
        ("class", "typing.MutableMapping", None)
    ]
    assert _paths(stubs.find("concurrent.futures.Future.result")) == [
        (
            "function",
            "concurrent.futures._base.Future.result",
            "concurrent.futures._base.Future",
        )
    ]
    assert _paths(stubs.find("xml.etree.ElementTree")) == [
        ("module", "xml.etree.ElementTree", None)
    ]


def test_properties_and_attributes(stubs):
    (flags,) = stubs.find("re.Pattern.flags")
    assert flags.kind == "property" and flags.entry["t"] == "builtins.int"
    (name,) = stubs.find("threading.Thread.name")
    assert name.kind == "variable" and name.entry["t"] == "builtins.str"


def test_what_the_stubs_do_not_have(stubs):
    assert stubs.find("no_such_module.f") == []
    assert stubs.find("re.no_such_name") == []
    assert stubs.find("re.Pattern.no_such_method") == []
    # Attributes of functions and variables are not described.
    assert stubs.find("re.compile.cache") == []
    assert stubs.module("no_such_module") is None
    assert stubs.definition("re.no_such_name") is None


def test_public_names(stubs):
    assert stubs.public_name("asyncio.events.AbstractEventLoop") == (
        "asyncio.AbstractEventLoop"
    )
    assert stubs.public_name("concurrent.futures._base.Future") == (
        "concurrent.futures.Future"
    )
    assert stubs.public_name("_io.TextIOWrapper") == "io.TextIOWrapper"
    assert stubs.public_name("re.Pattern") == "re.Pattern"
    assert stubs.public_name("builtins.str") == "builtins.str"
    # A function has no public name of its own.
    assert stubs.public_name("re.compile") == "re.compile"


def test_mro(stubs):
    assert stubs.mro("builtins.bool") == [
        "builtins.bool",
        "builtins.int",
        "builtins.object",
    ]
    assert stubs.mro("builtins.object") == ["builtins.object"]
    mro = stubs.mro("collections.OrderedDict")
    assert mro[:3] == [
        "collections.OrderedDict",
        "builtins.dict",
        "typing.MutableMapping",
    ]
    assert mro[-1] == "builtins.object"


def test_parameters(stubs):
    (thread_init,) = stubs.find("threading.Thread.__init__")
    for signature in thread_init.entry["s"]:
        target = next(p for p in signature["p"] if p[0] == "target")
        assert target[3] == ["|", ["*call", "builtins.object", None], "*none"]
    (append,) = stubs.find("builtins.list.append")
    assert append.entry["s"][0]["p"][1] == ["object", "/", 0, ["*var", "builtins._T"]]


def test_the_fixture_data(tmp_path):
    stubs = Stubs(FIXTURE)
    assert _paths(stubs.find("shapes.Circle.copy")) == [
        ("function", "shapes._impl.Shape.copy", "shapes._impl.Shape")
    ]
    assert _paths(stubs.find("shapes.Shape.alias")) == [
        ("function", "shapes._impl.Shape.copy", "shapes._impl.Shape")
    ]
    assert _paths(stubs.find("shapes.Shape.Edge.length")) == [
        ("function", "shapes._impl.Shape.Edge.length", "shapes._impl.Shape.Edge")
    ]
    assert stubs.public_name("shapes._impl._Hidden") == "shapes.Hidden"
    # Both the definition and the re-export of another version.
    assert _paths(stubs.find("shapes._impl.Extra")) == [
        ("class", "shapes._impl.Extra", None),
        ("class", "shapes._extra.Extra", None),
    ]
    assert stubs.mro("shapes._impl.Circle") == [
        "shapes._impl.Circle",
        "shapes._impl.Shape",
        "builtins.object",
    ]


def test_the_fixture_third_party_data():
    stubs = Stubs(FIXTURE)
    assert _paths(stubs.find("extras.Tool.use")) == [
        ("function", "extras.core.Tool.use", "extras.core.Tool")
    ]
    # Inherited from a class of the standard library.
    assert _paths(stubs.find("extras.Tool.copy")) == [
        ("function", "shapes._impl.Shape.copy", "shapes._impl.Shape")
    ]
    assert stubs.mro("extras.core.Tool") == [
        "extras.core.Tool",
        "shapes._impl.Circle",
        "shapes._impl.Shape",
        "builtins.object",
    ]
    assert stubs.public_name("extras.core.Tool") == "extras.Tool"
    # A namespace package that two distributions share.
    assert _paths(stubs.find("ns.one")) == [("module", "ns.one", None)]
    assert _paths(stubs.find("ns.two.first")) == [("function", "ns.one.first", None)]
    # The standard library's `legacy`, not legacy-backport's.
    assert _paths(stubs.find("legacy.old")) == [("function", "legacy.old", None)]
    assert stubs.find("legacy.new") == []
    assert _paths(stubs.find("backport.run")) == [("function", "backport.run", None)]


def test_third_party_definitions(stubs):
    # requests.get is defined in requests.api and re-exported by requests.
    (get,) = stubs.find("requests.get")
    assert (get.kind, get.path) == ("function", "requests.api.get")
    assert {s["r"] for s in get.entry["s"]} == {"requests.models.Response"}
    assert stubs.public_name("requests.models.Response") == "requests.Response"
    assert _paths(stubs.find("yaml.SafeLoader")) == [
        ("class", "yaml.loader.SafeLoader", None)
    ]
    # A namespace package: protobuf gives google.protobuf.
    assert _paths(stubs.find("google.protobuf")) == [
        ("module", "google.protobuf", None)
    ]


@pytest.mark.parametrize(
    "reduced, names",
    [
        ("re.Pattern", ["re.Pattern"]),
        (["re.Pattern", "builtins.str"], ["re.Pattern"]),
        (
            ["|", "builtins.int", "*none", ["builtins.list", None]],
            ["builtins.int", "builtins.list"],
        ),
        ("*self", []),
        (["*type", "builtins.int"], []),
        (["*call", None, None], []),
        (None, []),
    ],
)
def test_class_names(reduced, names):
    assert class_names(reduced) == names
