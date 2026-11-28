import importlib.util
import json
import shutil
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tools/tests/fixtures/typeshed"


def _load_generator():
    spec = importlib.util.spec_from_file_location(
        "generate_stubs", ROOT / "tools/generate_stubs.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


generate_stubs = _load_generator()


@pytest.fixture(scope="module")
def reader():
    return generate_stubs.StubReader.from_typeshed(FIXTURE)


@pytest.fixture(scope="module")
def data(reader):
    return reader.generate()


def _names(data, module):
    top = module.partition(".")[0]
    return data[top]["modules"][module]["names"]


def _files(directory):
    return sorted(
        str(path.relative_to(directory))
        for path in directory.rglob("*")
        if path.is_file()
    )


def test_the_fixture_regenerates_to_the_committed_files(tmp_path, reader, data):
    generate_stubs.write(data, tmp_path, "fixture", None, reader.distributions)
    expected = FIXTURE / "expected"
    written = _files(tmp_path)
    assert written == _files(expected)
    for name in written:
        assert (tmp_path / name).read_bytes() == (expected / name).read_bytes(), name


def test_third_party_data_goes_to_its_own_directory(tmp_path, reader, data):
    generate_stubs.write(data, tmp_path, "fixture", None, reader.distributions)
    standard = sorted(path.name for path in tmp_path.glob("*.json"))
    third_party = sorted(path.name for path in (tmp_path / "third_party").iterdir())
    assert standard == [
        "abc.json",
        "builtins.json",
        "legacy.json",
        "shapes.json",
        "typing.json",
    ]
    assert third_party == ["alpha.json", "backport.json", "extras.json", "ns.json"]


def test_third_party_stubs_leave_the_standard_library_data_unchanged(tmp_path, data):
    checkout = tmp_path / "typeshed"
    shutil.copytree(FIXTURE / "stdlib", checkout / "stdlib")
    alone = generate_stubs.StubReader.from_typeshed(checkout)
    assert alone.distributions == []
    standard = alone.generate()
    assert sorted(standard) == ["abc", "builtins", "legacy", "shapes", "typing"]
    for top, expected in standard.items():
        assert generate_stubs.dumps(data[top]) == generate_stubs.dumps(expected), top


def test_the_output_does_not_depend_on_the_order_of_reading():
    first = generate_stubs.StubReader.from_typeshed(FIXTURE)
    second = generate_stubs.StubReader.from_typeshed(FIXTURE)
    second.resolve("shapes", "Shape")
    assert generate_stubs.dumps(first.generate()) == generate_stubs.dumps(
        second.generate()
    )


def test_writing_replaces_old_files_and_copies_the_licence(tmp_path, reader, data):
    (tmp_path / "stale.json").write_text("{}")
    licence = tmp_path / "LICENCE-SOURCE"
    licence.write_text("Apache License")
    output = tmp_path / "out"
    (output / "third_party").mkdir(parents=True)
    (output / "stale.json").write_text("{}")
    (output / "third_party" / "stale.json").write_text("{}")

    generate_stubs.write(data, output, "abc123", licence, reader.distributions)

    assert not (output / "stale.json").exists()
    assert not (output / "third_party" / "stale.json").exists()
    assert (output / "LICENSE").read_text() == "Apache License"
    assert "`abc123`" in (output / "README.md").read_text()


def test_version_branches_keep_every_signature(data):
    init = _names(data, "shapes._impl")["Circle"]["m"]["__init__"]
    assert [[p[0] for p in s["p"]] for s in init["s"]] == [
        ["self", "radius", "label"],
        ["self", "radius"],
    ]
    assert init["s"][0]["p"][2] == ["label", "k", 1, "builtins.str"]
    assert all("v" not in s for s in init["s"])
    assert "v" not in data["legacy"]["modules"]["legacy"]


def test_a_signature_that_branches_repeat_is_kept_once():
    text = textwrap.dedent(
        """
        import sys
        if sys.platform == "win32":
            def f(x: int) -> str: ...
        else:
            def f(x: int) -> str: ...
            def f(x: int, y: int) -> str: ...
        """
    )
    data = generate_stubs.StubReader({"m": (text, False)}).generate()
    signatures = data["m"]["modules"]["m"]["names"]["f"]["s"]
    assert [[p[0] for p in s["p"]] for s in signatures] == [["x"], ["x", "y"]]


def test_two_layers_of_generic_arguments_are_kept():
    sources = dict(generate_stubs.StubReader.from_typeshed(FIXTURE).sources)
    sources["m"] = ("two: list[list[str]]\nthree: list[list[list[str]]]\n", False)
    data = generate_stubs.StubReader(sources).generate()
    names = data["m"]["modules"]["m"]["names"]
    assert names["two"]["t"] == ["builtins.list", ["builtins.list", "builtins.str"]]
    assert names["three"]["t"] == ["builtins.list", ["builtins.list", "builtins.list"]]


def test_platform_branches_keep_every_definition(data):
    runner = _names(data, "shapes._impl")["Runner"]
    assert sorted(runner["m"]) == ["run", "start"]


def test_a_definition_keeps_the_re_export_of_another_version(data):
    extra = _names(data, "shapes._impl")["Extra"]
    assert extra["k"] == "c" and sorted(extra["m"]) == ["old"]
    assert extra["also"] == [["shapes._extra", "Extra"]]


def test_members_of_classes(data):
    shape = _names(data, "shapes._impl")["Shape"]
    members = shape["m"]
    assert members["name"] == {"k": "p", "t": "builtins.str", "set": 1}
    assert members["sides"] == {"k": "v", "t": "builtins.int"}
    assert members["area"]["x"] == 1
    assert members["copy"]["s"][0]["r"] == "*self"
    assert members["unit"]["d"] == "classmethod"
    assert members["unit"]["s"][0]["r"] == ["shapes._impl.Shape", "builtins.int"]
    assert members["kinds"]["d"] == "staticmethod"
    assert members["alias"] == {"k": "r", "to": [["shapes._impl", "Shape.copy"]]}
    assert shape["tp"] == ["shapes._impl._T"]
    circle = _names(data, "shapes._impl")["Circle"]
    assert circle["b"] == [["shapes._impl.Shape", "builtins.float"]]


def test_public_names_of_classes(data):
    names = _names(data, "shapes._impl")
    assert names["Shape"]["pub"] == "shapes.Shape"
    assert names["Circle"]["pub"] == "shapes.Circle"
    assert names["_Hidden"]["pub"] == "shapes.Hidden"
    assert names["Shape"]["m"]["Edge"]["pub"] == "shapes.Shape.Edge"
    assert "pub" not in names["_Callback"]
    assert "pub" not in _names(data, "builtins")["str"]


def test_what_a_module_keeps(data):
    package = _names(data, "shapes")
    assert package["Hidden"] == {"k": "r", "to": [["shapes._impl", "_Hidden"]]}
    assert package["Circle"] == {"k": "r", "to": [["shapes._impl", "Circle"]]}
    assert "Any" not in package and "sys" not in package
    impl = _names(data, "shapes._impl")
    for name in ("Iterable", "_T", "_Number", "_Handler", "abstractmethod"):
        assert name not in impl
    assert data["shapes"]["modules"]["shapes"]["all"] == [
        "Hidden",
        "Shape",
        "area",
        "scale",
    ]
    assert _names(data, "typing")["Text"] == {"k": "r", "to": [["builtins", "str"]]}


def test_types_of_signatures(data):
    names = _names(data, "shapes._impl")
    area = names["area"]["s"]
    assert area[1]["p"][0] == ["shape", "/", 0, "*none"]
    assert area[1]["r"] == "builtins.int"
    scale = names["scale"]["s"][0]
    assert scale["p"] == [
        ["shape", "", 0, ["shapes._impl.Shape", ["*var", "shapes._impl._T"]]],
        ["factor", "", 1, ["|", "builtins.float", "*none"]],
        ["factors", "*", 0, "builtins.float"],
        ["key", "k", 0, ["*call", "builtins.int", [["*var", "shapes._impl._T"]]]],
        ["options", "**", 0, None],
    ]
    anystr = ["*var", "typing.AnyStr", ["|", "builtins.str", "builtins.bytes"], "c"]
    assert names["pattern"]["s"][0]["r"] == ["builtins.list", anystr]
    assert names["identity"]["s"][0]["r"] == ["*var", "shapes._impl._T"]
    assert names["make"]["s"][0]["p"][0][3] == ["*type", ["*var", "shapes._impl._T"]]
    assert names["wait"]["s"][0]["a"] == 1
    kinds = [p[1] for p in names["legacy"]["s"][0]["p"]]
    assert kinds == ["/", "/", ""]
    assert names["Circle"]["m"]["scaled"]["s"][0]["p"][1][1] == "/"


def test_a_method_of_a_module_instance_is_a_function(data):
    names = _names(data, "shapes._impl")
    assert names["default_area"] == {
        "k": "f",
        "s": [{"p": [], "r": "builtins.float"}],
    }
    assert names["default_kinds"]["s"][0]["r"] == ["builtins.list", "builtins.str"]
    assert "d" not in names["default_kinds"]
    assert names["_default"] == {"k": "v", "t": "shapes._impl.Circle"}


def test_arguments_that_a_function_passes_on_are_any_object(data):
    submit = _names(data, "shapes._impl")["submit"]["s"][0]["p"]
    assert submit == [
        ["fn", "", 0, ["*call", "builtins.int", None]],
        ["args", "*", 0, "builtins.object"],
        ["kwargs", "**", 0, "builtins.object"],
    ]


def test_types_of_callable_parameters(data):
    names = _names(data, "shapes._impl")
    run = names["Runner"]["m"]["run"]["s"][0]["p"][1]
    start = names["Runner"]["m"]["start"]["s"][0]["p"][1]
    assert run[3] == ["*call", "*none", ["builtins.str"]]
    assert start[3] == ["|", "shapes._impl._Callback", "*none"]


def test_a_namespace_package_is_a_module_without_names(data):
    assert data["ns"]["modules"] == {
        "ns": {"names": {}},
        "ns.one": {
            "names": {"first": {"k": "f", "s": [{"p": [], "r": "builtins.int"}]}}
        },
        "ns.two": {
            "names": {
                "Two": {
                    "k": "c",
                    "b": [],
                    "m": {
                        "count": {
                            "k": "f",
                            "s": [{"p": [["self", "", 0, None]], "r": "builtins.int"}],
                        }
                    },
                },
                "first": {"k": "r", "to": [["ns.one", "first"]]},
            }
        },
    }


def test_stubs_of_a_distribution_use_the_standard_library(data):
    tool = _names(data, "extras.core")["Tool"]
    assert tool["b"] == ["shapes._impl.Circle"]
    register = _names(data, "extras.core")["register"]["s"][0]["p"]
    assert register == [["callback", "", 0, ["*call", "*none", []]]]


def test_public_names_go_through_the_distribution_of_the_class(data):
    assert _names(data, "shapes._impl")["_Hidden"]["pub"] == "shapes.Hidden"
    assert _names(data, "extras.core")["Tool"]["pub"] == "extras.Tool"
    assert _names(data, "alpha") == {
        "Hidden": {"k": "r", "to": [["shapes._impl", "_Hidden"]]},
        "Tool": {"k": "r", "to": [["extras.core", "Tool"]]},
    }


def test_the_standard_library_keeps_its_top_level_names(data):
    assert sorted(_names(data, "legacy")) == ["old"]
    assert sorted(_names(data, "backport")) == ["run"]


def test_files_under_tests_directories_are_not_stubs(data):
    assert not [top for top in data if top.startswith("@")]
    assert "not_a_stub" not in data


def test_the_distributions_record_their_metadata(reader):
    found = {d.name: d for d in reader.distributions}
    assert sorted(found) == [
        "alpha",
        "extras-lib",
        "legacy-backport",
        "ns-one",
        "ns-two",
    ]
    assert found["extras-lib"].version == "1.2.*"
    assert found["extras-lib"].top_level_modules == ["extras"]
    assert found["ns-one"].obsolete_since == "2.1.0"
    assert found["ns-two"].partial
    assert not found["ns-one"].partial and found["ns-two"].obsolete_since is None
    assert found["legacy-backport"].top_level_modules == ["backport"]
    assert found["legacy-backport"].top_level_modules_left_out == ["legacy"]


def test_the_readme_lists_the_distributions(tmp_path, reader, data):
    generate_stubs.write(data, tmp_path, "abc123", None, reader.distributions)
    readme = (tmp_path / "README.md").read_text()
    assert "| extras-lib | 1.2.* | `extras` |  |" in readme
    assert "| ns-one | 2.0.* | `ns` | obsolete since 2.1.0 |" in readme
    assert "| ns-two | 3.* | `ns` | partial |" in readme
    assert (
        "| legacy-backport | 1.0 | `backport` | `legacy` left out: the standard"
        " library has it |" in readme
    )


def _distribution(checkout, name, files):
    directory = checkout / "stubs" / name
    directory.mkdir(parents=True)
    (directory / "METADATA.toml").write_text('version = "1"\n')
    for path, text in files.items():
        (directory / path).parent.mkdir(parents=True, exist_ok=True)
        (directory / path).write_text(text)


def test_one_module_in_two_distributions_stops_the_generator(tmp_path):
    checkout = tmp_path / "typeshed"
    shutil.copytree(FIXTURE / "stdlib", checkout / "stdlib")
    _distribution(checkout, "first", {"pkg/__init__.pyi": "", "pkg/a.pyi": ""})
    _distribution(checkout, "second", {"pkg/a.pyi": "def f() -> None: ...\n"})

    with pytest.raises(ValueError, match="pkg.a is in two distributions"):
        generate_stubs.StubReader.from_typeshed(checkout)


@pytest.mark.parametrize("package, namespace", [("a", "b"), ("b", "a")])
def test_a_package_wins_over_a_namespace_package_of_one_name_in_either_order(
    tmp_path, package, namespace
):
    checkout = tmp_path / "typeshed"
    shutil.copytree(FIXTURE / "stdlib", checkout / "stdlib")
    _distribution(checkout, package, {"pkg/__init__.pyi": "def f() -> None: ...\n"})
    _distribution(checkout, namespace, {"pkg/b.pyi": ""})

    reader = generate_stubs.StubReader.from_typeshed(checkout)
    modules = reader.generate()["pkg"]["modules"]
    assert sorted(modules) == ["pkg", "pkg.b"]
    assert sorted(modules["pkg"]["names"]) == ["f"]


def test_the_committed_data_says_where_it_comes_from():
    data = ROOT / "crates/stubs/stub_data"
    readme = (data / "README.md").read_text()
    assert "https://github.com/python/typeshed" in readme
    assert "| requests | ~=2.33.0 | `requests` |" in readme
    assert "Apache License" in (data / "LICENSE").read_text()
    builtins = json.loads((data / "builtins.json").read_text())
    assert "list" in builtins["modules"]["builtins"]["names"]
    yaml = json.loads((data / "third_party" / "yaml.json").read_text())
    assert "load" in yaml["modules"]["yaml"]["names"]
    assert "https://github.com/python/cpython" in readme
    for version in ("3.12.16", "3.13.18", "3.14.10", "3.15.2"):
        assert f"| {version} | `" in readme
    functools = json.loads((data / "functools.json").read_text())
    wrapper = functools["modules"]["functools"]["names"]["_lru_cache_wrapper"]
    assert wrapper["pub"] == "_functools._lru_cache_wrapper"


FACADE_STUB = """
class _Wrapper:
    class Inner: ...
class _Pure: ...
class _Redefined: ...
class _Disputed: ...
class _Newer: ...
class _Conditional: ...
class Exported: ...
class Unlisted: ...
__all__ = ["Exported"]
"""


def _cpython_library(root, version, modules):
    checkout = root / f"cpython-{version}"
    (checkout / "Include").mkdir(parents=True)
    (checkout / "Include/patchlevel.h").write_text(
        f'#define PY_VERSION              "{version}"\n'
    )
    for path, text in modules.items():
        (checkout / "Lib" / path).parent.mkdir(parents=True, exist_ok=True)
        (checkout / "Lib" / path).write_text(textwrap.dedent(text))
    return generate_stubs.read_cpython_library(checkout, f"commit-{version}")


def _facade_source(newer=""):
    return f"""
        try:
            from _facade import _Wrapper
        except ImportError:
            def _Wrapper(): pass
        from _facade_py import _Pure
        from _facade import _Redefined
        class _Redefined: pass
        from _facade import _Disputed
        if FLAG:
            from _facade import _Conditional
        from _facade import Exported, Unlisted
        {newer}
    """


def _facade_names(tmp_path, versions):
    libraries = [
        _cpython_library(tmp_path, version, modules)
        for version, modules in versions.items()
    ]
    reader = generate_stubs.StubReader(
        {"facade": (FACADE_STUB, False)}, cpython_libraries=libraries
    )
    names = reader.generate()["facade"]["modules"]["facade"]["names"]
    return names, reader.extension_name_conflicts


def test_a_class_that_the_facade_imports_from_an_extension_is_named_there(tmp_path):
    names, conflicts = _facade_names(
        tmp_path,
        {
            "3.12.1": {
                "facade.py": _facade_source(),
                "_facade_py.py": "class _Pure: pass\n",
            },
            "3.14.1": {
                "facade.py": _facade_source("from _facade import _Newer"),
                "_facade_py.py": "class _Pure: pass\n",
            },
            "3.15.1": {
                "facade/__init__.py": _facade_source(
                    "from _facade import _Newer"
                ).replace("import _Disputed", "import _Other as _Disputed"),
                "_facade_py.py": "class _Pure: pass\n",
            },
        },
    )
    assert names["_Wrapper"]["pub"] == "_facade._Wrapper"
    assert names["_Wrapper"]["m"]["Inner"]["pub"] == "_facade._Wrapper.Inner"
    assert names["_Newer"]["pub"] == "_facade._Newer"
    assert names["Unlisted"]["pub"] == "_facade.Unlisted"
    for kept in ("_Pure", "_Redefined", "_Disputed", "_Conditional", "Exported"):
        assert "pub" not in names[kept], kept
    assert conflicts == [
        "facade._Disputed (3.12.1: _facade._Disputed, 3.14.1: _facade._Disputed,"
        " 3.15.1: _facade._Other)"
    ]


def test_without_cpython_sources_the_stub_names_stay(tmp_path):
    names, conflicts = _facade_names(tmp_path, {})
    assert all("pub" not in entry for entry in names.values())
    assert conflicts == []


def test_a_cpython_library_records_its_version_and_python_modules(tmp_path):
    library = _cpython_library(
        tmp_path, "3.13.2", {"pkg/__init__.py": "", "pkg/mod.py": "", "plain.py": ""}
    )
    assert library.version == "3.13.2"
    assert library.commit == "commit-3.13.2"
    assert {"pkg", "pkg.mod", "plain"} <= library.python_modules
    assert generate_stubs.final_binding(library, "absent", "name") is None
    assert generate_stubs.final_binding(library, "plain", "name") is None


def test_the_readme_records_the_cpython_commits(tmp_path, reader, data):
    libraries = [
        _cpython_library(tmp_path, version, {})
        for version in ("3.15.0", "3.12.9", "3.13.1")
    ]
    generate_stubs.write(data, tmp_path / "out", "abc123", None, (), libraries)
    readme = (tmp_path / "out" / "README.md").read_text()
    rows = [line for line in readme.splitlines() if line.startswith("| 3.")]
    assert rows == [
        "| 3.12.9 | `commit-3.12.9` |",
        "| 3.13.1 | `commit-3.13.1` |",
        "| 3.15.0 | `commit-3.15.0` |",
    ]
    assert "Do not edit by hand: regenerate." in readme
