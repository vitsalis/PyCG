#
# Copyright (c) 2020 Vitalis Salis.
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

from pycg import utils
from pycg.machinery.imports import ImportManager, ImportManagerError
from pycg.pycg import CallGraphGenerator


def make_files(root, *paths, content=""):
    for path in paths:
        file = root / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(content)


def manager_in(root, current_mod, current_file):
    """Return an ImportManager for `root` that analyses `current_file`."""
    make_files(root, current_file)
    im = ImportManager()
    im.set_pkg(str(root))
    im.create_node(current_mod)
    im.set_filepath(current_mod, str(root / current_file))
    im.set_current_mod(current_mod, str(root / current_file))
    return im


# Import graph


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


def test_create_edge_from_current_module():
    im = ImportManager()
    im.create_node("node1")
    im.create_node("node2")

    # no current module yet
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


# Path containment


def test_is_internal(tmp_path):
    im = ImportManager()
    im.set_pkg(str(tmp_path / "pkg"))

    assert im.is_internal(str(tmp_path / "pkg" / "mod.py"))
    assert im.is_internal(str(tmp_path / "pkg" / "sub" / "mod.py"))
    assert im.is_internal(str(tmp_path / "pkg"))
    # A sibling directory whose name starts with the root name is outside.
    assert not im.is_internal(str(tmp_path / "pkg2" / "mod.py"))
    assert not im.is_internal(str(tmp_path / "mod.py"))


def test_set_pkg_makes_root_absolute(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    im = ImportManager()
    im.set_pkg("pkg")

    assert im.get_mod_dir() == str(tmp_path / "pkg")
    assert im.is_internal(str(tmp_path / "pkg" / "mod.py"))


# Absolute imports


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
    # from pkg import mod
    make_files(tmp_path, "pkg/__init__.py", "pkg/mod.py")
    im = manager_in(tmp_path, "main", "main.py")

    assert im.handle_import("pkg.mod", 0) == "pkg.mod"


def test_from_package_import_attribute(tmp_path):
    # from pkg import func, where func is defined in pkg/__init__.py
    make_files(tmp_path, "pkg/__init__.py")
    im = manager_in(tmp_path, "main", "main.py")

    assert im.handle_import("pkg.func", 0) == "pkg"
    assert im.get_node("pkg.func") is None
    assert im.get_imports("main") == {"pkg"}


def test_from_module_import_attribute(tmp_path):
    # from mod import func
    make_files(tmp_path, "mod.py")
    im = manager_in(tmp_path, "main", "main.py")

    assert im.handle_import("mod.func", 0) == "mod"


def test_from_package_import_star(tmp_path):
    make_files(tmp_path, "pkg/__init__.py")
    im = manager_in(tmp_path, "main", "main.py")

    assert im.handle_import("pkg.*", 0) == "pkg"
    # Even a file named "*.py" is not a module.
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

    # name is the module name.py, so "sub" can only be an attribute of it.
    assert im.handle_import("name.sub", 0) == "name"
    assert im.get_filepath("name") == str(tmp_path / "name.py")


def test_namespace_package(tmp_path):
    # nest/ has no __init__.py
    make_files(tmp_path, "nest/imported.py")
    im = manager_in(tmp_path, "main", "main.py")

    assert im.handle_import("nest.imported", 0) == "nest.imported"
    assert im.get_filepath("nest.imported") == str(tmp_path / "nest" / "imported.py")
    assert im.get_imports("main") == {"nest", "nest.imported"}
    # A namespace package has no file to analyse.
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
        # Python runs pkg/__init__.py and mod.py before the import fails, so
        # they are in the graph.
        ("pkg.missing.sub", {"pkg": "pkg/__init__.py"}),
        ("pkg.sub.missing.thing", {"pkg": "pkg/__init__.py", "pkg.sub": None}),
        ("mod.sub.func", {"mod": "mod.py"}),
    ],
)
def test_missing_module(tmp_path, name, found):
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
    # Without an __init__.py file, pkg is a namespace package.
    assert im.handle_import("pkg", 0) == "pkg"
    assert not im.get_filepath("pkg")


def test_module_name_is_case_sensitive(tmp_path):
    make_files(tmp_path, "lower.py", "pkg/__init__.py")
    im = manager_in(tmp_path, "main", "main.py")

    assert im.handle_import("Lower", 0) is None
    assert im.handle_import("PKG", 0) is None


def test_resolution_does_not_import_or_touch_sys(tmp_path):
    make_files(tmp_path, "boom.py", "pkg/__init__.py", content="raise SystemExit(1)\n")
    im = manager_in(tmp_path, "main", "main.py")
    path, path_hooks = list(sys.path), list(sys.path_hooks)
    modules = set(sys.modules)

    assert im.handle_import("boom", 0) == "boom"
    assert im.handle_import("pkg", 0) == "pkg"
    # A frozen module that nothing has imported; importing it prints a line.
    assert "__hello__" not in modules
    assert im.handle_import("__hello__", 0) is None
    assert sys.path == path
    assert sys.path_hooks == path_hooks
    assert set(sys.modules) == modules


# Relative imports


def test_relative_import_from_module(tmp_path):
    make_files(
        tmp_path,
        "pkg/__init__.py",
        "pkg/other.py",
        "pkg/sub/__init__.py",
        "pkg/sub/sibling.py",
    )
    im = manager_in(tmp_path, "pkg.sub.mod", "pkg/sub/mod.py")

    # from . import sibling
    assert im.handle_import("sibling", 1) == "pkg.sub.sibling"
    # from .sibling import func
    assert im.handle_import("sibling.func", 1) == "pkg.sub.sibling"
    # from .. import other
    assert im.handle_import("other", 2) == "pkg.other"
    # from . import func, where func is defined in pkg/sub/__init__.py
    assert im.handle_import("func", 1) == "pkg.sub"


def test_relative_import_from_init(tmp_path):
    make_files(tmp_path, "pkg/__init__.py", "pkg/other.py", "pkg/sub/mod.py")
    im = manager_in(tmp_path, "pkg.sub", "pkg/sub/__init__.py")

    # from . import mod
    assert im.handle_import("mod", 1) == "pkg.sub.mod"
    # from .. import other
    assert im.handle_import("other", 2) == "pkg.other"


def test_relative_import_does_not_add_edge_to_current_module(tmp_path):
    make_files(tmp_path, "pkg/mod.py")
    im = manager_in(tmp_path, "pkg", "pkg/__init__.py")

    assert im.handle_import("mod", 1) == "pkg.mod"
    assert im.get_imports("pkg") == {"pkg.mod"}


@pytest.mark.parametrize(
    ("current_mod", "current_file", "level"),
    [
        # The package root is not a package.
        ("main", "main.py", 1),
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

    # from . import sys
    assert im.handle_import("sys", 1) == "pkg.sys"


# Call graph


def test_failed_import_still_runs_package_init(tmp_path):
    # Python runs pkg/__init__.py before "from pkg.missing import" fails.
    package_init = "def setup():\n    pass\n\nsetup()\n"
    main = "try:\n    from pkg.missing import thing\nexcept ImportError:\n    pass\n"
    make_files(tmp_path, "pkg/__init__.py", content=package_init)
    make_files(tmp_path, "main.py", content=main)
    generator = CallGraphGenerator(
        [str(tmp_path / "main.py")], str(tmp_path), -1, utils.constants.CALL_GRAPH_OP
    )
    generator.analyze()

    assert "pkg.setup" in generator.output().get("pkg", set())


def test_directory_named_like_a_source_file_does_not_crash_analysis(tmp_path):
    (tmp_path / "mod.py").mkdir()
    (tmp_path / "pkg" / "__init__.py").mkdir(parents=True)
    make_files(tmp_path, "main.py", content="import mod\nimport pkg\n")
    generator = CallGraphGenerator(
        [str(tmp_path / "main.py")], str(tmp_path), -1, utils.constants.CALL_GRAPH_OP
    )
    generator.analyze()

    assert generator.output() == {"main": set()}
