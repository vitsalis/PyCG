#
# Copyright (c) 2026 Vitalis Salis.
#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
#
import os
import sys
from importlib.machinery import FrozenImporter

import pytest

from pycg.analysis.imports import ImportManager, ImportManagerError
from pycg.pycg import CallGraphGenerator


def make_files(root, *paths, content=""):
    for path in paths:
        file = root / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(content)


def manager_in(root, current_mod, current_file):
    make_files(root, current_file)
    im = ImportManager()
    im.set_pkg(str(root))
    im.create_node(current_mod)
    im.set_filepath(current_mod, str(root / current_file))
    im.set_current_mod(current_mod, str(root / current_file))
    return im


def test_create_node():
    im = ImportManager()
    im.create_node("node1")

    assert im.get_filepath("node1") == ""
    assert im.get_imports("node1") == set()


@pytest.mark.parametrize("name", ["", 1])
def test_create_node_rejects_invalid_names(name):
    with pytest.raises(ImportManagerError):
        ImportManager().create_node(name)


def test_create_node_rejects_duplicates():
    im = ImportManager()
    im.create_node("node1")

    with pytest.raises(ImportManagerError):
        im.create_node("node1")


def test_set_filepath_stores_absolute_path():
    im = ImportManager()
    im.create_node("node1")

    im.set_filepath("node1", "filepath1")
    assert im.get_filepath("node1") == os.path.abspath("filepath1")

    im.set_filepath("node1", "filepath2")
    assert im.get_filepath("node1") == os.path.abspath("filepath2")


@pytest.mark.parametrize("filename", ["", 1])
def test_set_filepath_rejects_invalid_names(filename):
    im = ImportManager()
    im.create_node("node1")

    with pytest.raises(ImportManagerError):
        im.set_filepath("node1", filename)


def test_set_filepath_requires_node():
    with pytest.raises(ImportManagerError):
        ImportManager().set_filepath("missing", "filepath")


def test_create_edge_requires_a_current_module_and_starts_there():
    im = ImportManager()
    im.create_node("node1")
    im.create_node("node2")

    with pytest.raises(ImportManagerError):
        im.create_edge("node2")

    im.set_current_mod("node1", "node1.py")
    im.create_edge("node2")
    assert im.get_imports("node1") == {"node2"}

    for name in ["", 1]:
        with pytest.raises(ImportManagerError):
            im.create_edge(name)


def test_get_imports_of_unknown_module():
    assert ImportManager().get_imports("missing") == []


def test_set_pkg_makes_root_absolute(tmp_path, monkeypatch):
    make_files(tmp_path, "pkg/mod.py", "pkg/main.py")
    monkeypatch.chdir(tmp_path)
    im = ImportManager()
    im.set_pkg("pkg")
    im.create_node("main")
    im.set_current_mod("main", "pkg/main.py")
    monkeypatch.chdir(tmp_path / "pkg")

    assert im.handle_import("mod", 0) == "mod"
    assert im.get_filepath("mod") == str(tmp_path / "pkg" / "mod.py")


def test_import_module_file(tmp_path):
    make_files(tmp_path, "to_import.py")
    im = manager_in(tmp_path, "main", "main.py")

    assert im.handle_import("to_import", 0) == "to_import"
    assert im.get_filepath("to_import") == str(tmp_path / "to_import.py")
    assert im.get_imports("main") == {"to_import"}


def test_import_package(tmp_path):
    make_files(tmp_path, "pkg/__init__.py")
    im = manager_in(tmp_path, "main", "main.py")

    assert im.handle_import("pkg", 0) == "pkg"
    assert im.get_filepath("pkg") == str(tmp_path / "pkg" / "__init__.py")


def test_import_submodule_adds_every_package_on_the_path(tmp_path):
    make_files(tmp_path, "pkg/__init__.py", "pkg/sub/__init__.py", "pkg/sub/mod.py")
    im = manager_in(tmp_path, "main", "main.py")

    assert im.handle_import("pkg.sub.mod", 0) == "pkg.sub.mod"
    assert im.get_imports("main") == {"pkg", "pkg.sub", "pkg.sub.mod"}
    assert im.get_filepath("pkg") == str(tmp_path / "pkg" / "__init__.py")
    assert im.get_filepath("pkg.sub") == str(tmp_path / "pkg" / "sub" / "__init__.py")
    assert im.get_filepath("pkg.sub.mod") == str(tmp_path / "pkg" / "sub" / "mod.py")


def test_from_package_import_submodule(tmp_path):
    make_files(tmp_path, "pkg/__init__.py", "pkg/mod.py")
    im = manager_in(tmp_path, "main", "main.py")

    assert im.handle_import("pkg.mod", 0) == "pkg.mod"


def test_from_package_import_attribute(tmp_path):
    make_files(tmp_path, "pkg/__init__.py")
    im = manager_in(tmp_path, "main", "main.py")

    assert im.handle_import("pkg.func", 0) == "pkg"
    assert im.get_node("pkg.func") is None
    assert im.get_imports("main") == {"pkg"}


def test_from_module_import_attribute(tmp_path):
    make_files(tmp_path, "mod.py")
    im = manager_in(tmp_path, "main", "main.py")

    assert im.handle_import("mod.func", 0) == "mod"


def test_from_package_import_star_is_the_package_even_beside_a_star_file(tmp_path):
    make_files(tmp_path, "pkg/__init__.py")
    im = manager_in(tmp_path, "main", "main.py")

    assert im.handle_import("pkg.*", 0) == "pkg"
    make_files(tmp_path, "pkg/*.py")
    assert im.handle_import("pkg.*", 0) == "pkg"


def test_package_takes_precedence_over_module_file(tmp_path):
    make_files(tmp_path, "name.py", "name/__init__.py")
    im = manager_in(tmp_path, "main", "main.py")

    assert im.handle_import("name", 0) == "name"
    assert im.get_filepath("name") == str(tmp_path / "name" / "__init__.py")


def test_module_file_takes_precedence_over_namespace_package(tmp_path):
    make_files(tmp_path, "name.py", "name/sub.py")
    im = manager_in(tmp_path, "main", "main.py")

    assert im.handle_import("name.sub", 0) == "name"
    assert im.get_filepath("name") == str(tmp_path / "name.py")


def test_namespace_package(tmp_path):
    make_files(tmp_path, "nest/imported.py")
    im = manager_in(tmp_path, "main", "main.py")

    assert im.handle_import("nest.imported", 0) == "nest.imported"
    assert im.get_filepath("nest.imported") == str(tmp_path / "nest" / "imported.py")
    assert im.get_imports("main") == {"nest", "nest.imported"}
    assert not im.get_filepath("nest")


def test_import_namespace_package_itself(tmp_path):
    make_files(tmp_path, "nest/imported.py")
    im = manager_in(tmp_path, "main", "main.py")

    assert im.handle_import("nest", 0) == "nest"
    assert not im.get_filepath("nest")


@pytest.mark.parametrize(
    ("name", "found"),
    [
        ("missing", {}),
        ("missing.sub", {}),
        ("pkg.missing.sub", {"pkg": "pkg/__init__.py"}),
        ("pkg.sub.missing.thing", {"pkg": "pkg/__init__.py", "pkg.sub": None}),
        ("mod.sub.func", {"mod": "mod.py"}),
    ],
)
def test_missing_module_keeps_the_modules_that_python_ran_before_failing(
    tmp_path, name, found
):
    make_files(tmp_path, "pkg/__init__.py", "pkg/sub/other.py", "mod.py")
    im = manager_in(tmp_path, "main", "main.py")

    assert im.handle_import(name, 0) is None
    assert im.get_imports("main") == set(found)
    for modname, filename in found.items():
        expected = str(tmp_path / filename) if filename else ""
        assert im.get_filepath(modname) == expected


def test_external_module(tmp_path):
    im = manager_in(tmp_path, "main", "main.py")

    assert im.handle_import("json", 0) is None
    assert im.handle_import("os.path", 0) is None
    assert im.get_imports("main") == set()
    assert set(im.get_import_graph()) == {"main"}


def test_builtin_module_wins_over_local_file(tmp_path):
    make_files(tmp_path, "sys.py")
    im = manager_in(tmp_path, "main", "main.py")

    assert "sys" in sys.builtin_module_names
    assert im.handle_import("sys", 0) is None


def test_frozen_module_wins_over_local_file(tmp_path):
    if FrozenImporter.find_spec("io") is None:
        pytest.skip("this interpreter does not freeze io and os")
    make_files(tmp_path, "io.py", "os.py")
    im = manager_in(tmp_path, "main", "main.py")

    assert im.handle_import("io", 0) is None
    assert im.handle_import("os.path", 0) is None
    assert im.get_imports("main") == set()


def skip_unless_importlib_util_is_frozen():
    if FrozenImporter.find_spec("importlib.util") is None:
        pytest.skip("this interpreter does not freeze importlib.util")
    assert FrozenImporter.find_spec("importlib") is None


def test_frozen_submodule_wins_over_local_file_of_a_local_package(tmp_path):
    skip_unless_importlib_util_is_frozen()
    make_files(
        tmp_path, "importlib/__init__.py", "importlib/util.py", "importlib/other.py"
    )
    im = manager_in(tmp_path, "main", "main.py")

    assert im.handle_import("importlib.util.find_spec", 0) is None
    assert im.handle_import("importlib.util", 0) is None
    assert im.get_imports("main") == {"importlib"}
    assert im.handle_import("importlib.other", 0) == "importlib.other"


def test_relative_import_of_a_frozen_submodule_name_is_local(tmp_path):
    make_files(tmp_path, "importlib/__init__.py", "importlib/util.py")
    im = manager_in(tmp_path, "importlib", "importlib/__init__.py")

    assert im.handle_import("util", 1) == "importlib.util"


def test_local_file_shadows_stdlib_module_that_is_not_frozen(tmp_path):
    make_files(tmp_path, "json.py")
    im = manager_in(tmp_path, "main", "main.py")

    assert "json" not in sys.builtin_module_names
    assert FrozenImporter.find_spec("json") is None
    assert im.handle_import("json", 0) == "json"


def test_directory_named_like_a_source_file_is_not_a_file(tmp_path):
    (tmp_path / "mod.py").mkdir()
    (tmp_path / "pkg" / "__init__.py").mkdir(parents=True)
    im = manager_in(tmp_path, "main", "main.py")

    assert im.handle_import("mod", 0) is None
    assert im.handle_import("pkg", 0) == "pkg"
    assert not im.get_filepath("pkg")


def test_module_name_is_case_sensitive(tmp_path):
    make_files(tmp_path, "lower.py", "pkg/__init__.py")
    im = manager_in(tmp_path, "main", "main.py")

    assert im.handle_import("Lower", 0) is None
    assert im.handle_import("PKG", 0) is None


@pytest.mark.parametrize(
    ("files", "name", "packages"),
    [
        (("pkg/__init__.py", "pkg/sub/__init__.py"), "pkg.sub.mod", ["pkg", "pkg.sub"]),
        (("ns/sub/mod.py",), "ns.sub.mod", ["ns", "ns.sub"]),
        pytest.param(
            ("ns.py", "ns/sub/mod.py"),
            "ns.sub.mod",
            [],
            id="module_file_wins_over_namespace_directory",
        ),
        (("ns/sub.py", "ns/sub/mod.py"), "ns.sub.mod", ["ns"]),
        pytest.param(
            ("os/sub/mod.py",),
            "os.sub.mod",
            [],
            id="builtin_or_frozen_module_wins_over_any_file",
        ),
        (("mod.py",), "mod", []),
        pytest.param(
            ("ns.cpython-312-darwin.so", "ns/sub/mod.py"),
            "ns.sub.mod",
            [],
            id="extension_module_wins_over_namespace_directory",
        ),
        pytest.param(
            ("pkg/__init__.py", "pkg/__init__/b.py"),
            "pkg.__init__.b",
            ["pkg"],
            id="init_name_is_the_module_init_py_not_a_package",
        ),
        (
            ("pkg/__init__.py", "pkg/__init__/__init__.py", "pkg/__init__/b.py"),
            "pkg.__init__.b",
            ["pkg", "pkg.__init__"],
        ),
    ],
)
def test_packages_are_the_prefixes_that_an_import_resolves_as_packages(
    tmp_path, files, name, packages
):
    make_files(tmp_path, *files)
    im = manager_in(tmp_path, "main", "main.py")

    assert im.packages(name) == packages
    assert im.extension_modules == {}


def test_resolution_does_not_import_or_touch_sys(tmp_path):
    make_files(tmp_path, "boom.py", "pkg/__init__.py", content="raise SystemExit(1)\n")
    im = manager_in(tmp_path, "main", "main.py")
    path, path_hooks = list(sys.path), list(sys.path_hooks)
    modules = set(sys.modules)

    assert im.handle_import("boom", 0) == "boom"
    assert im.handle_import("pkg", 0) == "pkg"
    frozen_module_that_prints_when_imported = "__hello__"
    assert frozen_module_that_prints_when_imported not in modules
    assert im.handle_import(frozen_module_that_prints_when_imported, 0) is None
    assert sys.path == path
    assert sys.path_hooks == path_hooks
    assert set(sys.modules) == modules


def test_relative_import_from_module(tmp_path):
    make_files(
        tmp_path,
        "pkg/__init__.py",
        "pkg/other.py",
        "pkg/sub/__init__.py",
        "pkg/sub/sibling.py",
    )
    im = manager_in(tmp_path, "pkg.sub.mod", "pkg/sub/mod.py")

    assert im.handle_import("sibling", 1) == "pkg.sub.sibling"
    assert im.handle_import("sibling.func", 1) == "pkg.sub.sibling"
    assert im.handle_import("other", 2) == "pkg.other"
    assert im.handle_import("func", 1) == "pkg.sub"


def test_relative_import_from_init(tmp_path):
    make_files(tmp_path, "pkg/__init__.py", "pkg/other.py", "pkg/sub/mod.py")
    im = manager_in(tmp_path, "pkg.sub", "pkg/sub/__init__.py")

    assert im.handle_import("mod", 1) == "pkg.sub.mod"
    assert im.handle_import("other", 2) == "pkg.other"


def test_relative_import_does_not_add_edge_to_current_module(tmp_path):
    make_files(tmp_path, "pkg/mod.py")
    im = manager_in(tmp_path, "pkg", "pkg/__init__.py")

    assert im.handle_import("mod", 1) == "pkg.mod"
    assert im.get_imports("pkg") == {"pkg.mod"}


@pytest.mark.parametrize(
    ("current_mod", "current_file", "level"),
    [
        pytest.param("main", "main.py", 1, id="package_root_is_not_a_package"),
        ("pkg.mod", "pkg/mod.py", 2),
        ("pkg", "pkg/__init__.py", 2),
        ("pkg.sub.mod", "pkg/sub/mod.py", 3),
    ],
)
def test_relative_import_beyond_top_level(tmp_path, current_mod, current_file, level):
    make_files(tmp_path, "pkg/__init__.py", "pkg/sub/__init__.py", "other.py")
    im = manager_in(tmp_path, current_mod, current_file)

    assert im.handle_import("other", level) is None
    assert im.get_imports(current_mod) == set()


def test_relative_import_of_builtin_name_is_local(tmp_path):
    make_files(tmp_path, "pkg/__init__.py", "pkg/sys.py")
    im = manager_in(tmp_path, "pkg.mod", "pkg/mod.py")

    assert im.handle_import("sys", 1) == "pkg.sys"


def test_failed_import_still_runs_package_init(tmp_path):
    package_init = "def setup():\n    pass\n\nsetup()\n"
    main = "try:\n    from pkg.missing import thing\nexcept ImportError:\n    pass\n"
    make_files(tmp_path, "pkg/__init__.py", content=package_init)
    make_files(tmp_path, "main.py", content=main)
    generator = CallGraphGenerator([str(tmp_path / "main.py")], str(tmp_path))
    generator.analyze()

    assert "pkg.setup" in generator.output()["pkg"]


def test_call_to_a_frozen_submodule_is_external(tmp_path):
    skip_unless_importlib_util_is_frozen()
    make_files(tmp_path, "importlib/__init__.py")
    make_files(tmp_path, "importlib/util.py", content="def find_spec(): pass\n")
    make_files(
        tmp_path,
        "main.py",
        content="from importlib.util import find_spec\nfind_spec('x')\n",
    )
    generator = CallGraphGenerator([str(tmp_path / "main.py")], str(tmp_path))
    generator.analyze()

    assert generator.output() == {
        "main": ["importlib.util.find_spec"],
        "importlib": [],
        "importlib.util.find_spec": [],
    }
    assert "importlib.util.find_spec" in generator.document()["outside"]


def test_directory_named_like_a_source_file_does_not_crash_analysis(tmp_path):
    (tmp_path / "mod.py").mkdir()
    (tmp_path / "pkg" / "__init__.py").mkdir(parents=True)
    make_files(tmp_path, "main.py", content="import mod\nimport pkg\n")
    generator = CallGraphGenerator([str(tmp_path / "main.py")], str(tmp_path))
    generator.analyze()

    assert generator.output() == {"main": []}


def test_limit_import_as_binds_the_submodule_not_the_package_attribute(tmp_path):
    package_init = (
        "from . import b\n"
        "class Replacement:\n"
        "    @staticmethod\n"
        "    def hit(): pass\n"
        "b = Replacement\n"
    )
    make_files(tmp_path, "a/__init__.py", content=package_init)
    make_files(tmp_path, "a/b.py", content="def hit(): pass\n")
    make_files(tmp_path, "main.py", content="import a.b as c\nc.hit()\n")
    generator = CallGraphGenerator([str(tmp_path / "main.py")], str(tmp_path))
    generator.analyze()

    assert generator.output()["main"] == ["a.b.hit"]


@pytest.mark.skipif(
    sys.version_info < (3, 15), reason="`lazy import` is Python 3.15 syntax"
)
def test_an_unread_lazy_import_as_reads_no_attribute(tmp_path):
    package_init = (
        "from . import b\n"
        "class Replacement:\n"
        "    @property\n"
        "    def c(self):\n"
        "        return 1\n"
        "b = Replacement()\n"
    )
    make_files(tmp_path, "a/__init__.py", content=package_init)
    make_files(tmp_path, "a/b/__init__.py", content="from . import c\n")
    make_files(tmp_path, "a/b/c.py")
    main = "import a\nlazy import a.b.c as target\n"
    make_files(tmp_path, "main.py", content=main)
    generator = CallGraphGenerator([str(tmp_path / "main.py")], str(tmp_path))
    generator.analyze()

    assert generator.output()["main"] == []


def test_a_literal_import_module_gives_the_module_whatever_the_package_binds(
    tmp_path,
):
    make_files(tmp_path, "a/__init__.py", content="from . import b\nb = None\n")
    make_files(tmp_path, "a/b.py", content="def hit(): pass\n")
    main = "import importlib\nimportlib.import_module('a.b').hit()\n"
    make_files(tmp_path, "main.py", content=main)
    generator = CallGraphGenerator([str(tmp_path / "main.py")], str(tmp_path))
    generator.analyze()

    assert "a.b.hit" in generator.output()["main"]


@pytest.mark.parametrize(
    ("statement", "binding"),
    [
        ("from pkg import x", "x = hit\n"),
        ("from pkg import __x", "__x = _C__x = hit\n"),
    ],
)
def test_limit_a_submodule_that_a_package_attribute_shadows_is_analysed(
    tmp_path, statement, binding
):
    name = statement.rpartition(" ")[2]
    make_files(tmp_path, "pkg/__init__.py", content="def hit(): pass\n" + binding)
    make_files(tmp_path, f"pkg/{name}.py", content="def hit(): pass\nhit()\n")
    main = f"class C:\n    {statement}\n    {name}()\n"
    make_files(tmp_path, "main.py", content=main)
    generator = CallGraphGenerator([str(tmp_path / "main.py")], str(tmp_path))
    generator.analyze()

    assert generator.output() == {
        "main": ["pkg.hit"],
        "pkg": [],
        "pkg.hit": [],
        f"pkg.{name}": [f"pkg.{name}.hit"],
        f"pkg.{name}.hit": [],
    }


def test_directory_named_like_an_extension_binary_is_not_a_module(tmp_path):
    (tmp_path / "ext.cpython-312-x86_64-linux-gnu.so").mkdir()
    im = manager_in(tmp_path, "main", "main.py")

    assert im.handle_import("ext", 0) is None
    assert im.extension_modules == {}
