"""Build the document that PyCG writes (docs/format.md) from the analysis
of a program. Every part is sorted, so the document does not depend on the
order of the analysis."""

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

# The commit of typeshed that the stub data comes from, as its README states.
_STUB_README = Path(__file__).resolve().parent.parent / "analysis/stub_data/README.md"

# The implicit construct that makes the calls of each role of the engine
# (see `Analysis.site_call`; the class statement's steps are roles of one
# name). A role that a builtin also makes while it runs a call expression
# (`list(x)` iterates, `str(x)` converts, `getattr(o, n)` loads) belongs to
# that call where its site is the call's; `len(x)`, `sorted(key=f)`,
# `map(f, xs)`, `filter(f, xs)`, `reversed(x)` and `type(name, bases, dict)`
# only make calls of that kind.
CONSTRUCTS = {
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

# The roles of constructs that are always written as such, also at the site
# of a call expression (`with f():`, `if f():`, `{f(): v}`).
_WRITTEN = frozenset(
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

_ITERATION = frozenset({"iterate", "index", "callable"})

# The roles of an attribute access, with its kind (Load, Store, Delete).
_ACCESSES = frozenset({"accessor", "getattr", "hook", "property"})


def build(program, package_name=None, package_version=None):
    analysis = program.analysis
    definitions = _definitions(program)
    calls = _calls(program, definitions)
    callees = {name for sites in calls.values() for s in sites for name in s["callees"]}
    extensions = program.extension_modules
    outside = {
        name: {"known": _known(name, analysis.external_callees, extensions)}
        for name in sorted(callees)
        if name not in definitions
    }
    return {
        "format": FORMAT,
        "tool": {
            "name": "pycg",
            "version": __version__,
            "typeshed": _typeshed(),
            "cap": program.analysis.solver.cap,
        },
        "package": {"name": package_name, "version": package_version},
        "modules": _modules(program),
        "definitions": definitions,
        "exports": _exports(program),
        "outside": outside,
        "calls": calls,
    }


def _known(name, external_callees, extensions):
    """How the analysis knows the outside callee `name`: "extension" for a
    name in an extension module of the package, else as the engine
    recorded it (see `Analysis.external_callees`). A callee that the engine
    did not record as outside is a name that the builtin models give to
    analysed code that does not define it (`functools.partial.__call__`,
    which an analysed `functools.wraps` returns): "stub"."""
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
    """Each module, function and class by name. Of two definitions of one
    name, a module comes before a function and a function before a class
    (the call graph has no class nodes), then the first by position."""
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
    """The names of the linearization of `cls`: the analysed classes and
    the outside classes where the analysis stops, whose own linearization
    is outside code; one of analysed classes only ends with `object`. A
    class whose order is not known (a saturated base or metaclass) lists
    itself only."""
    if cls.unknown:
        return [cls.name]
    names = [base.name for base in cls.mro]
    if all(isinstance(base, Class) for base in cls.mro):
        names.append(f"{BUILTIN_MODULE}.object")
    return names


def _position(function):
    return (function.module, function.lineno, function.end_lineno, function.name)


def _exports(program):
    """Each name that a module binds to a module, class or function of
    another qualified name, with the sorted names of those."""
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
    """The call sites of each caller, by the source module of each site,
    then by position and construct. The definitions of one name share the
    name's sites, as in the classic call graph; a site in another module
    than the name's definition (`definitions`) names its module."""
    analysis = program.analysis
    expressions = {(caller, site) for caller, site, _ in analysis.call_expressions}
    records = {}
    for (caller, site, construct), callees in analysis.site_edges.items():
        at_call = (caller, site) in expressions
        iterated = (caller, site) in analysis.iterated_expressions
        word = _word(construct, at_call, iterated)
        records.setdefault((caller, site, word), set()).update(callees)
    causes = analysis.unresolved_calls()
    for caller, site in causes:
        records.setdefault((caller, site, None), set())
    functions = {}
    for function in sorted(analysis.functions, key=_position):
        functions.setdefault(function.name, []).append(function)
    # The sites of each caller by source module, start, end and construct:
    # records of one node and construct are one site (a loop's `__iter__`
    # and `__next__`), and no source overwrites another.
    calls = {}
    for (caller, site, word), callees in records.items():
        module, start, end = _parts(site)
        if not _in_code(caller, module, start[0], program.modules, functions):
            # Python's code that the caller runs makes the call (see
            # `_in_code`): the site is the caller's definition.
            first = functions[caller][0]
            module = first.module
            start = (first.lineno, first.col_offset)
            end = (first.end_lineno, first.end_col_offset)
        own = definitions[caller]["module"]
        key = ("" if module == own else module, start, end, word or "")
        site_record = calls.setdefault(caller, {}).setdefault(key, [set(), None])
        site_record[0].update(callees)
        if (caller, site) in causes:
            site_record[1] = causes[caller, site]
    return {
        caller: [
            _record(key, callees, cause)
            for key, (callees, cause) in sorted(calls[caller].items())
        ]
        for caller in sorted(calls)
    }


def _record(key, callees, cause):
    module, start, end, word = key
    record = {"line": start[0], "col": start[1], "end": list(end)}
    record["callees"] = sorted(callees)
    if word:
        record["implicit"] = word
    elif not callees:
        record["unresolved"] = cause
    if module:
        record["module"] = module
    return record


def _in_code(caller, module, line, modules, functions):
    """Whether the code of `caller` (the module of that name, or the
    functions of that name) has line `line` of `module`. A call has its
    site in its caller's code, but for the accessor that a class's own
    attribute hook calls (`C.__setattr__ -> C.value`): the access is
    elsewhere, and the hook's body runs Python's code that calls the
    accessor."""
    if caller in modules and module == caller:
        return True
    return caller not in functions or any(
        function.module == module and function.lineno <= line <= function.end_lineno
        for function in functions[caller]
    )


def _word(construct, at_call, iterated):
    """The implicit construct of the calls of `construct` (see
    `semantics._construct`), or None for a call expression; `at_call` if
    their site is that of a call expression, `iterated` if a statement or
    a comprehension iterates the expression at the site."""
    if construct == "call":
        return None
    if construct == "decorator":
        return "decorator"
    role = construct[0]
    if at_call and role not in _WRITTEN and not (role in _ITERATION and iterated):
        return None
    if construct == ("subscript", "__delitem__"):
        return "delete"
    if role in _ACCESSES and construct[1] == "Delete":
        return "delete"
    return CONSTRUCTS[role]


# A site: `module:line:col#end_line:end_col`, the span of the construct's
# `ast` node, and for the fields of a literal format `#index` (see the
# builder's `_site`).
_SITE = re.compile(r"(.*):(\d+):(\d+)#(\d+):(\d+)(?:#\d+)?")


def _parts(site):
    """The module, the start (line, column) and the end of `site`."""
    module, line, col, end_line, end_col = _SITE.fullmatch(site).groups()
    return module, (int(line), int(col)), (int(end_line), int(end_col))


@cache
def _typeshed():
    match = re.search(r"`([0-9a-f]{40})`", _STUB_README.read_text(encoding="utf-8"))
    return match[1]
