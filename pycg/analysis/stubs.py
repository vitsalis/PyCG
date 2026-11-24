"""What the stubs of typeshed say about the builtins, the standard library
and the third-party distributions that typeshed has stubs for.

The data is in `stub_data/`, one JSON file per top-level module, generated
by `tools/generate_stubs.py` from one commit of typeshed (see
`stub_data/README.md`): the standard library's in `stub_data/`, the
distributions' in `stub_data/third_party/`. A top-level name that the
standard library has is never a distribution's. A file is read when the
analysis first asks for one of its modules, and once per process, so a
program that imports no third-party module reads no third-party data.
Nothing is imported: the stubs are data.

Format. A file is `{"modules": {name: module}}` with every module of the
top-level module (`os`, `os.path`). A module is `{"names": {name: entry},
"all": [...]}`; `all` is its `__all__`. The data is the union of every
Python version and platform. Every entry has a kind `k`:

- `"f"`, a function or method: `s`, its signatures (the overloads, of every
  version); `d`, `"classmethod"` or `"staticmethod"`; `x`, abstract. A
  signature has `p`, its parameters, `r`, the type of its result, `a` if it
  is a coroutine function (`async def`). A parameter is `[name,
  kind, default, type]`: kind `"/"` positional-only, `""` positional or
  keyword, `"*"` the `*args` parameter, `"k"` keyword-only, `"**"` the
  `**kwargs` parameter; default 1 if it has one.
- `"c"`, a class: `b`, its base classes (types, without `Generic` and
  `Protocol`); `m`, its members (entries); `tp`, its type parameters (type
  variable names); `proto`, a protocol; `final`; `tco`, a class that exists
  only in stubs (`@type_check_only`); `meta`, its metaclass; `pub`, its
  public name where it is not its definition path (see below).
- `"p"`, a property: `t`, its type; `set`, it has a setter; `x`.
- `"v"`, a variable or attribute: `t`, its type.
- `"r"`, a reference: `to`, the definitions it may be, `[module, qualified
  name]` each (an empty name for a module). Imports, re-exports and
  assignments of names are references; a name that platforms or versions
  bind differently has every definition. A definition that another version
  or platform re-exports from elsewhere has those in `also`.

A *definition path* is the module that defines something, then its
qualified name (`re.Pattern.match`, `asyncio.events.AbstractEventLoop`). A
class's *public name* is its shortest path through public modules and
names (`asyncio.AbstractEventLoop`; `io.TextIOWrapper` for
`_io.TextIOWrapper`), preferring its own module; nested classes are named
through their enclosing class.

A type is null (unknown: `Any`, or what the generator dropped), a string,
or a list:

- `"module.Class"`, an instance of that class (its definition path);
  `"*none"`, `None` or no value; `"*self"`, the type of the receiver;
- `["module.Class", arg, ...]`, an instance of a generic class with its
  type arguments, `"..."` for the variadic part of a tuple;
- `["|", type, ...]`, a union;
- `["*type", type]`, the class itself (`type[C]`);
- `["*call", result, params]`, a callable, with the types of its
  parameters, or null when they are not listed;
- `["*var", name]`, `["*var", name, bound]` or `["*var", name, union,
  "c"]`, a type variable, with its bound, or the union of its constraints
  (`AnyStr`: the variable is one of them).
"""

import json
from functools import cache
from pathlib import Path

from .mro import linearize

DATA = Path(__file__).with_name("stub_data")
# The directory of the data of the third-party distributions, in DATA.
THIRD_PARTY = "third_party"

# The implicit base of every class.
OBJECT = "builtins.object"
# The metaclass of a protocol class.
PROTOCOL_META = "typing._ProtocolMeta"

# The module of the abstract classes that `typing` re-exports as aliases.
ABC_MODULE = "collections.abc"

# The mixin methods of `collections.abc` that return `self` in Python, where
# typeshed declares a new iterator, by the module and qualified name that
# define them in the stubs: their result is read as `Self` (`Generator`
# inherits `Iterator.__iter__`; typeshed restates it).
RETURNS_SELF = {
    "typing": ("Iterator.__iter__", "Generator.__iter__", "AsyncIterator.__aiter__")
}


class Definition:
    """What a name or path in the stubs is: `kind` is one of module,
    class, function, property, variable; `path` its definition path;
    `entry` its data (None for a module); `owner` the definition path of
    the class whose body defines it, for a member."""

    __slots__ = ("kind", "path", "entry", "owner")

    KINDS = {"c": "class", "f": "function", "p": "property", "v": "variable"}

    def __init__(self, kind, path, entry, owner=None):
        self.kind = kind
        self.path = path
        self.entry = entry
        self.owner = owner

    def __repr__(self):
        return f"<{self.kind} {self.path}>"

    def __eq__(self, other):
        return isinstance(other, Definition) and (self.kind, self.path, self.owner) == (
            other.kind,
            other.path,
            other.owner,
        )

    def __hash__(self):
        return hash((self.kind, self.path, self.owner))


class Stubs:
    """The stub data in `directory`."""

    def __init__(self, directory=DATA):
        self._directory = Path(directory)
        # The answers of `module`, `definition` and `member`, which the
        # rules ask for again at every object and site: the data does not
        # change, so each is found once.
        self._modules = {}
        self._definitions = {}
        self._members = {}
        self._mros = {}
        self._abstract = {}
        self._abstract_reach = {}
        self._abc_names = None

    def module(self, name):
        """The data of the module `name`, or None if no stub has it."""
        try:
            return self._modules[name]
        except KeyError:
            pass
        package = _load(self._directory, name.partition(".")[0])
        data = None if package is None else package["modules"].get(name)
        self._modules[name] = data
        return data

    def find(self, path):
        """The definitions that the dotted path `path` (as code reaches it:
        `os.path.join`, `collections.abc.MutableMapping.update`) may be:
        attributes of modules, submodules and members of classes, the
        latter found through the class hierarchy."""
        parts = path.split(".")
        if self.module(parts[0]) is None:
            return []
        found = [Definition("module", parts[0], None)]
        for part in parts[1:]:
            found = _unique(d for base in found for d in self.attribute(base, part))
        return found

    def attribute(self, definition, name):
        """The definitions of the attribute `name` of a module or class."""
        if definition.kind == "module":
            data = self.module(definition.path)
            entry = data["names"].get(name)
            if entry is not None:
                return self._follow(f"{definition.path}.{name}", entry, None)
            submodule = f"{definition.path}.{name}"
            if self.module(submodule) is not None:
                return [Definition("module", submodule, None)]
            return []
        if definition.kind == "class":
            return self.member(definition.path, name) or self.metaclass_member(
                definition.path, name
            )
        return []

    def metaclass_member(self, cls, name):
        """The definitions of `name` in the metaclass of the class `cls`:
        what a load through the class finds after the class's own MRO
        (`ValueError.mro`)."""
        return self.member(self.metaclass(cls), name)

    def metaclass(self, cls):
        """The definition path of the metaclass of the class `cls`: the
        first that a class of its MRO names, else `typing._ProtocolMeta`
        for a class that is or derives from a protocol (the data drops
        `Protocol` from the bases, and so its metaclass, an `ABCMeta`),
        else `builtins.type`."""
        protocol = False
        for owner in self.mro(cls):
            definition = self.definition(owner)
            if definition is not None and definition.entry.get("meta"):
                names = class_names(definition.entry["meta"])
                if names:
                    return names[0]
            if definition is not None and definition.entry.get("proto"):
                protocol = True
        return PROTOCOL_META if protocol else "builtins.type"

    def member(self, cls, name):
        """The definitions of `name` that a lookup on the class `cls` finds:
        in the first class of its MRO that defines it. The list is shared:
        a caller does not change it."""
        key = (cls, name)
        found = self._members.get(key)
        if found is None:
            found = self._members[key] = self._find_member(cls, name)
        return found

    def _find_member(self, cls, name):
        for owner in self.mro(cls):
            entry = self.definition(owner)
            if entry is None:
                continue
            member = entry.entry["m"].get(name)
            if member is not None:
                return self._follow(f"{owner}.{name}", member, owner)
        return []

    def definition(self, path):
        """The definition whose definition path is `path`, or None."""
        try:
            return self._definitions[path]
        except KeyError:
            pass
        found = self._definitions[path] = self._find_definition(path)
        return found

    def _find_definition(self, path):
        module = path
        while module:
            data = self.module(module)
            if data is not None:
                break
            module = module.rpartition(".")[0]
        if not module:
            return None
        if module == path:
            return Definition("module", path, None)
        names, entry, owner = data["names"], None, None
        qualname = path[len(module) + 1 :].split(".")
        for index, part in enumerate(qualname):
            entry = names.get(part)
            if entry is None:
                return None
            if index < len(qualname) - 1:
                if entry["k"] != "c":
                    return None
                owner = ".".join([module, *qualname[: index + 1]])
                names = entry["m"]
        if entry["k"] == "r":
            return None
        return Definition(Definition.KINDS[entry["k"]], path, entry, owner)

    def _follow(self, path, entry, owner):
        """The definitions of an entry: itself and what other versions
        re-export (`also`), or the targets of a reference (which the
        generator never makes another reference)."""
        found = []
        if entry["k"] != "r":
            found.append(Definition(Definition.KINDS[entry["k"]], path, entry, owner))
        for module, qualname in [*entry.get("to", []), *entry.get("also", [])]:
            if not qualname:
                found.append(Definition("module", module, None))
                continue
            target = self.definition(f"{module}.{qualname}")
            if target is not None:
                found.append(target)
        return found

    def mro(self, cls):
        """The method resolution order of the class `cls` (a definition
        path), by C3 over the bases of every version, ending with
        `builtins.object`; classes that the stubs do not have are left
        out."""
        if cls not in self._mros:
            self._mros[cls] = [cls]
            definition = self.definition(cls)
            bases = []
            if definition is not None and definition.kind == "class":
                for base in definition.entry["b"]:
                    for name in class_names(base):
                        target = self.definition(name)
                        if target is not None and target.kind == "class":
                            bases.append(name)
            if not bases and cls != OBJECT:
                bases.append(OBJECT)
            self._mros[cls] = linearize(cls, bases, self.mro)
        return self._mros[cls]

    def abstract(self, cls):
        """Whether the concrete class of an instance of the class `cls` is
        not known: a protocol, a class that exists only in stubs, or a
        class whose MRO has an abstract method that no class before it
        overrides."""
        if cls not in self._abstract:
            definition = self.definition(cls)
            result = True
            if definition is not None and definition.kind == "class":
                entry = definition.entry
                result = bool(entry.get("proto") or entry.get("tco"))
                seen = set()
                for owner in self.mro(cls):
                    if result:
                        break
                    found = self.definition(owner)
                    if found is None:
                        continue
                    for name, member in found.entry["m"].items():
                        if name not in seen:
                            seen.add(name)
                            result = result or bool(member.get("x"))
            self._abstract[cls] = result
        return self._abstract[cls]

    def abstract_reach(self, cls):
        """The classes that the class `cls` reaches through abstract classes
        only: `cls` if it is abstract, and what each of its stub bases that
        is abstract reaches; empty for a concrete `cls`."""
        if cls not in self._abstract_reach:
            reach = set()
            pending = [cls]
            while pending:
                current = pending.pop()
                if current in reach or not self.abstract(current):
                    continue
                reach.add(current)
                definition = self.definition(current)
                if definition is not None and definition.kind == "class":
                    for base in definition.entry["b"]:
                        for name in class_names(base):
                            target = self.definition(name)
                            if target is not None and target.kind == "class":
                                pending.append(name)
            self._abstract_reach[cls] = frozenset(reach)
        return self._abstract_reach[cls]

    def abc_name(self, path):
        """The name in `collections.abc` of the class whose definition path
        is `path`, if typeshed defines it in `typing` and `collections.abc`
        re-exports it (`collections.abc.Set` for `typing.AbstractSet`); else
        None. At run time the class is `collections.abc`'s, and the name in
        `typing` an alias of it."""
        if self._abc_names is None:
            self._abc_names = {}
            module = self.module(ABC_MODULE)
            for name, entry in (module or {"names": {}})["names"].items():
                for target, qualname in entry.get("to", ()):
                    if target == "typing":
                        self._abc_names[f"typing.{qualname}"] = f"{ABC_MODULE}.{name}"
        return self._abc_names.get(path)

    def public_name(self, cls):
        """The public name of the class whose definition path is `cls`."""
        definition = self.definition(cls)
        if definition is None or definition.kind != "class":
            return cls
        return definition.entry.get("pub", cls)


def class_names(reduced):
    """The definition paths of the classes that a type names at its top
    level: a class, a generic class, or the arms of a union."""
    if isinstance(reduced, str):
        return [] if reduced.startswith("*") else [reduced]
    if isinstance(reduced, list) and reduced:
        if reduced[0] == "|":
            return [name for arm in reduced[1:] for name in class_names(arm)]
        if isinstance(reduced[0], str) and not reduced[0].startswith("*"):
            return [reduced[0]]
    return []


def _unique(definitions):
    return list(dict.fromkeys(definitions))


@cache
def _load(directory, top):
    """The data of the top-level module `top`: the standard library's, else
    a third-party distribution's; None if no stub has it."""
    for path in (directory / f"{top}.json", directory / THIRD_PARTY / f"{top}.json"):
        if path.is_file():
            package = json.loads(path.read_text(encoding="utf-8"))
            _return_self(package["modules"].get(top), RETURNS_SELF.get(top, ()))
            return package
    return None


def _return_self(module, qualnames):
    """Read the result of each method `qualnames` names in `module` as
    `Self` (see `RETURNS_SELF`)."""
    for qualname in qualnames:
        cls, method = qualname.split(".")
        entry = module["names"].get(cls) if module else None
        member = entry["m"].get(method) if entry and entry["k"] == "c" else None
        for signature in member["s"] if member else ():
            signature["r"] = "*self"
