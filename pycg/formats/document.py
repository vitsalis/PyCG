import os
import re
from functools import cache
from pathlib import Path

from pycg import __version__
from pycg.analysis.model import (
    BUILTIN_MODULE,
    Class,
    External,
    Function,
    Module,
    base_order,
)
from pycg.formats import FORMAT

_STUB_DATA_README_PATH = (
    Path(__file__).resolve().parent.parent / "analysis/stub_data/README.md"
)

IMPLICIT_CONSTRUCT_BY_ROLE = {
    "accessor": "attribute",
    "await": "await",
    "call back": None,
    "callable": "iteration",
    "class get": "attribute",
    "class statement": "class",
    "compare": "operator",
    "convert": "format",
    "enter": "with",
    "exit": "with",
    "format": "format",
    "getattr": "attribute",
    "hash": "dict",
    "hash_eq": "dict",
    "hook": "attribute",
    "index": "iteration",
    "init_subclass": "class",
    "iterate": "iteration",
    "key": None,
    "filter": None,
    "map": None,
    "module getattr": "attribute",
    "named load": "attribute",
    "operator": "operator",
    "prepare": "class",
    "property": "attribute",
    "protocol": None,
    "raise": "raise",
    "reversed": None,
    "set_name": "class",
    "special": "match",
    "subscript": "subscript",
    "truth": "truth",
    "type": None,
}

_ROLES_IMPLICIT_AT_CALL_EXPRESSION = frozenset(
    {
        "await",
        "class statement",
        "compare",
        "enter",
        "exit",
        "hash",
        "hash_eq",
        "init_subclass",
        "operator",
        "prepare",
        "raise",
        "set_name",
        "special",
        "subscript",
        "truth",
    }
)

_ROLES_ITERATION = frozenset({"iterate", "index", "callable"})

_ROLES_ATTRIBUTE_ACCESS = frozenset({"accessor", "getattr", "hook", "property"})


def build(program, package_name=None, package_version=None):
    analysis = program.analysis
    definitions = _definitions(program)
    calls = _calls(program, definitions)
    callees = {name for sites in calls.values() for s in sites for name in s["callees"]}
    extensions = program.extension_modules
    outside = {
        name: {"known": _outside_known(name, analysis.external_callees, extensions)}
        for name in sorted(callees)
        if name not in definitions
    }
    return {
        "format": FORMAT,
        "tool": {
            "name": "pycg",
            "version": __version__,
            "typeshed": _typeshed_commit(),
            "cap": program.analysis.solver.cap,
        },
        "package": {"name": package_name, "version": package_version},
        "modules": _modules(program),
        "definitions": definitions,
        "exports": _exports(program),
        "outside": outside,
        "calls": calls,
    }


def _outside_known(name, external_callees, extensions):
    parts = name.split(".")
    if any(".".join(parts[:end]) in extensions for end in range(1, len(parts))):
        return "extension"
    return external_callees.get(name, "stub")


def _modules(program):
    modules = {}
    for name, module in program.modules.items():
        modules[name] = {
            "file": _relative(module.file, program.root),
            "kind": "source",
            "status": module.status,
        }
        if module.cause is not None:
            modules[name]["cause"] = module.cause
    for name, file in program.extension_modules.items():
        modules[name] = {"file": _relative(file, program.root), "kind": "extension"}
    for name, module in modules.items():
        file = os.path.join(program.root, module["file"])
        shadows = [
            _relative(other, program.root) for other in program.shadowed(name, file)
        ]
        if shadows:
            module["shadows"] = sorted(shadows)
    return dict(sorted(modules.items()))


def _relative(path, root):
    return os.path.relpath(path, root).replace(os.sep, "/")


def _definitions(program):
    analysis = program.analysis
    found = {}
    for name in sorted(program.modules):
        lines = program.modules[name].line_count
        found[name] = {
            "kind": "module",
            "module": name,
            "lines": [min(lines, 1), lines],
        }
    for function in sorted(analysis.functions, key=_position):
        found.setdefault(
            function.name,
            {
                "kind": "function",
                "module": function.module,
                "lines": [function.lineno, function.end_lineno],
            },
        )
    for cls in sorted(analysis.classes, key=base_order):
        found.setdefault(
            cls.name,
            {
                "kind": "class",
                "module": cls.module,
                "lines": [cls.lineno, cls.end_lineno],
                "mro": _mro(cls),
            },
        )
    return dict(sorted(found.items()))


def _mro(cls):
    if cls.unknown:
        return [cls.name]
    names = [base.name for base in cls.mro]
    if all(isinstance(base, Class) for base in cls.mro):
        names.append(f"{BUILTIN_MODULE}.object")
    return names


def _position(function):
    return (function.module, function.lineno, function.end_lineno, function.name)


def _exports(program):
    analysis = program.analysis
    exports = {}
    for name in sorted(program.modules):
        module = analysis.module(name)
        for attribute in sorted(module.defines):
            path = f"{name}.{attribute}"
            field = analysis.field(module, attribute)
            targets = {
                obj.name
                for obj in analysis.solver.objects(field)
                if isinstance(obj, (Module, Class, Function, External))
                and obj.name != path
            }
            if targets:
                exports[path] = sorted(targets)
    return exports


def _calls(program, definitions):
    analysis = program.analysis
    expressions = {(caller, site) for caller, site, _ in analysis.call_expressions}
    records = {}
    for (caller, site, construct), callees in analysis.site_edges.items():
        at_call_expression = (caller, site) in expressions
        iterated = (caller, site) in analysis.iterated_expressions
        implicit = _implicit_construct(construct, at_call_expression, iterated)
        records.setdefault((caller, site, implicit), set()).update(callees)
    causes = analysis.unresolved_calls()
    for caller, site in causes:
        records.setdefault((caller, site, None), set())
    functions = {}
    for function in sorted(analysis.functions, key=_position):
        functions.setdefault(function.name, []).append(function)
    calls = {}
    for (caller, site, implicit), callees in records.items():
        module, start, end = _site_parts(site)
        if not _caller_code_has_line(
            caller, module, start[0], program.modules, functions
        ):
            first_definition = functions[caller][0]
            module = first_definition.module
            start = (first_definition.lineno, first_definition.col_offset)
            end = (first_definition.end_lineno, first_definition.end_col_offset)
        own = definitions[caller]["module"]
        key = ("" if module == own else module, start, end, implicit or "")
        site_record = calls.setdefault(caller, {}).setdefault(key, [set(), None])
        site_record[0].update(callees)
        if (caller, site) in causes:
            site_record[1] = causes[caller, site]
    return {
        caller: [
            _site_record(key, callees, cause)
            for key, (callees, cause) in sorted(calls[caller].items())
        ]
        for caller in sorted(calls)
    }


def _site_record(key, callees, cause):
    module, start, end, implicit = key
    record = {"line": start[0], "col": start[1], "end": list(end)}
    record["callees"] = sorted(callees)
    if implicit:
        record["implicit"] = implicit
    elif not callees:
        record["unresolved"] = cause
    if module:
        record["module"] = module
    return record


def _caller_code_has_line(caller, module, line, modules, functions):
    if caller in modules and module == caller:
        return True
    return caller not in functions or any(
        function.module == module and function.lineno <= line <= function.end_lineno
        for function in functions[caller]
    )


def _implicit_construct(construct, at_call_expression, iterated):
    if construct == "call":
        return None
    if construct == "decorator":
        return "decorator"
    role = construct[0]
    iterated_by_statement = role in _ROLES_ITERATION and iterated
    if (
        at_call_expression
        and role not in _ROLES_IMPLICIT_AT_CALL_EXPRESSION
        and not iterated_by_statement
    ):
        return None
    if construct == ("subscript", "__delitem__"):
        return "delete"
    if role in _ROLES_ATTRIBUTE_ACCESS and construct[1] == "Delete":
        return "delete"
    return IMPLICIT_CONSTRUCT_BY_ROLE[role]


_SITE_PATTERN = re.compile(r"(.*):(\d+):(\d+)#(\d+):(\d+)(?:#\d+)?")


def _site_parts(site):
    match = _SITE_PATTERN.fullmatch(site)
    assert match is not None, site
    module, line, column, end_line, end_column = match.groups()
    return module, (int(line), int(column)), (int(end_line), int(end_column))


@cache
def _typeshed_commit():
    readme = _STUB_DATA_README_PATH.read_text(encoding="utf-8")
    match = re.search(r"`([0-9a-f]{40})`", readme)
    assert match is not None, _STUB_DATA_README_PATH
    return match[1]
