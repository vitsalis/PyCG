"""The names that imports under `if TYPE_CHECKING:` would bind, which the
builder records for the reader of annotations and binds nothing to."""

import ast
import textwrap

from pycg.analysis.builder import ModuleBuilder
from pycg.analysis.imports import ImportManager
from pycg.analysis.semantics import Analysis


def type_only_names(tmp_path, source, name="pkg.mod"):
    path = tmp_path / "pkg" / "mod.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(source))
    imports = ImportManager()
    imports.set_pkg(str(tmp_path))
    imports.create_node(name)
    imports.set_filepath(name, str(path))
    imports.set_current_mod(name, str(path))
    analysis = Analysis()
    tree = ast.parse(path.read_text())
    builder = ModuleBuilder(analysis, imports, analysis.module(name), tree, False)
    builder.build()
    return builder.type_only_names, imports


def test_imports_of_type_checking_blocks_are_type_only(tmp_path):
    names, imports = type_only_names(
        tmp_path,
        """
        import typing
        from typing import TYPE_CHECKING
        if TYPE_CHECKING:
            from collections.abc import Sequence as Seq
            from .models import Model
            import os.path
            import xml.etree as tree
            if typing.TYPE_CHECKING:
                from json import loads
        else:
            from json import dumps
        if not TYPE_CHECKING:
            pass
        else:
            from .base import Base
        class C:
            if typing.TYPE_CHECKING:
                from .other import Other
        """,
    )

    assert names == {
        "pkg.mod.Seq": "collections.abc.Sequence",
        "pkg.mod.Model": "pkg.models.Model",
        "pkg.mod.os": "os",
        "pkg.mod.tree": "xml.etree",
        "pkg.mod.loads": "json.loads",
        "pkg.mod.Base": "pkg.base.Base",
        "pkg.mod.C.Other": "pkg.other.Other",
    }
    # They import nothing: no module of the package is discovered.
    assert "pkg.models" not in imports.get_imports("pkg.mod")


def test_other_dead_blocks_have_no_type_only_names(tmp_path):
    names, _ = type_only_names(
        tmp_path,
        """
        DEBUG = False
        if DEBUG:
            import pdb
        if False:
            import json
        """,
    )

    assert names == {}
