import json
from functools import cache
from pathlib import Path

from .mro import linearize

DATA_DIRECTORY = Path(__file__).with_name("stub_data")
THIRD_PARTY_DIRECTORY_NAME = "third_party"

IMPLICIT_BASE = "builtins.object"
PROTOCOL_METACLASS = "typing._ProtocolMeta"

ABC_MODULE = "collections.abc"

RETURNS_SELF = {
    "typing": ("Iterator.__iter__", "Generator.__iter__", "AsyncIterator.__aiter__")
}


class Definition:
    __slots__ = ("kind", "path", "entry", "owner")

    KINDS = {"c": "class", "f": "function", "p": "property", "v": "variable"}

    def __init__(self, kind, path, entry, owner=None):
        assert kind == "module" or kind in self.KINDS.values()
        assert (entry is None) == (kind == "module")
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
    def __init__(self, directory=DATA_DIRECTORY):
        self._directory = Path(directory)
        self._module_by_name = {}
        self._definition_by_path = {}
        self._members_by_class_and_name = {}
        self._mro_by_class = {}
        self._abstract_by_class = {}
        self._abstract_reach_by_class = {}
        self._abc_name_by_typing_path = None

    def module(self, name):
        try:
            return self._module_by_name[name]
        except KeyError:
            pass
        package = _load_top_level_module(self._directory, name.partition(".")[0])
        data = None if package is None else package["modules"].get(name)
        self._module_by_name[name] = data
        return data

    def find(self, path):
        parts = path.split(".")
        if self.module(parts[0]) is None:
            return []
        found = [Definition("module", parts[0], None)]
        for part in parts[1:]:
            found = _unique(d for base in found for d in self.attribute(base, part))
        return found

    def attribute(self, definition, name):
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
        return self.member(self.metaclass(cls), name)

    def metaclass(self, cls):
        protocol = False
        for owner in self.mro(cls):
            definition = self.definition(owner)
            if definition is not None and definition.entry.get("meta"):
                names = class_names(definition.entry["meta"])
                if names:
                    return names[0]
            if definition is not None and definition.entry.get("proto"):
                protocol = True
        return PROTOCOL_METACLASS if protocol else "builtins.type"

    def member(self, cls, name):
        key = (cls, name)
        found = self._members_by_class_and_name.get(key)
        if found is None:
            found = self._members_by_class_and_name[key] = self._find_member(cls, name)
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
        try:
            return self._definition_by_path[path]
        except KeyError:
            pass
        found = self._definition_by_path[path] = self._find_definition(path)
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
        if cls not in self._mro_by_class:
            self._mro_by_class[cls] = [cls]
            definition = self.definition(cls)
            bases = []
            if definition is not None and definition.kind == "class":
                for base in definition.entry["b"]:
                    for name in class_names(base):
                        target = self.definition(name)
                        if target is not None and target.kind == "class":
                            bases.append(name)
            if not bases and cls != IMPLICIT_BASE:
                bases.append(IMPLICIT_BASE)
            self._mro_by_class[cls] = linearize(cls, bases, self.mro)
        return self._mro_by_class[cls]

    def abstract(self, cls):
        if cls not in self._abstract_by_class:
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
            self._abstract_by_class[cls] = result
        return self._abstract_by_class[cls]

    def abstract_reach(self, cls):
        if cls not in self._abstract_reach_by_class:
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
            self._abstract_reach_by_class[cls] = frozenset(reach)
        return self._abstract_reach_by_class[cls]

    def abc_name(self, path):
        if self._abc_name_by_typing_path is None:
            self._abc_name_by_typing_path = {}
            module = self.module(ABC_MODULE)
            for name, entry in (module or {"names": {}})["names"].items():
                for target, qualname in entry.get("to", ()):
                    if target == "typing":
                        self._abc_name_by_typing_path[f"typing.{qualname}"] = (
                            f"{ABC_MODULE}.{name}"
                        )
        return self._abc_name_by_typing_path.get(path)

    def public_name(self, cls):
        definition = self.definition(cls)
        if definition is None or definition.kind != "class":
            return cls
        return definition.entry.get("pub", cls)


def class_names(reduced):
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
def _load_top_level_module(directory, top):
    for path in (
        directory / f"{top}.json",
        directory / THIRD_PARTY_DIRECTORY_NAME / f"{top}.json",
    ):
        if path.is_file():
            package = json.loads(path.read_text(encoding="utf-8"))
            _read_result_as_self(package["modules"].get(top), RETURNS_SELF.get(top, ()))
            return package
    return None


def _read_result_as_self(module, qualnames):
    for qualname in qualnames:
        cls, method = qualname.split(".")
        entry = module["names"].get(cls) if module else None
        member = entry["m"].get(method) if entry and entry["k"] == "c" else None
        for signature in member["s"] if member else ():
            signature["r"] = "*self"
