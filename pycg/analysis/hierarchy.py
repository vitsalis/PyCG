from collections import deque
from functools import cache

from .builtin_models import DEFINES_MARKERS, TUPLE_STORAGE
from .model import (
    BUILTIN_MODULE,
    Class,
    External,
    Fallback,
    Function,
    Instance,
    Saturated,
    UnknownExternal,
    Wrapper,
    base_order,
)
from .mro import exhaustive_order, linearizations
from .outside import outside_name
from .solver import Constraint, Each, Node, Watch, Witness
from .stubs import Stubs, class_names

_STUBS = Stubs()

BUILTIN_OBJECT = f"{BUILTIN_MODULE}.object"
BUILTIN_TYPE = f"{BUILTIN_MODULE}.type"
OBJECT_PATH = "builtins.object"
BUILTIN_STUBS = "builtins."
BUILTIN_TYPE_PATH = "builtins.type"
ABC_META = "abc.ABCMeta"

HIERARCHIES_PER_CLASS_MAX = 8

_UNLESS_PYTHONS_OWN_METHOD = ("<python's own>",)

_UNLESS_DESCRIPTOR_ITSELF = ("<the descriptor itself>",)

_UNLESS_DEFAULT_MEMBER = ("<the default>",)

_OUTSIDE_GIVES_DEFAULT, _OUTSIDE_GIVES_OVERRIDE, _OUTSIDE_GIVES_INHERITED = (
    "default",
    "override",
    "inherited",
)

MAY_DERIVE = ("<may derive>",)
MAY_LACK = ("<may lack>",)
MAY_LACK_METHOD = ("<may lack the method>",)
NOT_NOMINAL = ("<not nominal>",)

_MODULES_OF_ABCS = frozenset({"abc", "typing", "typing_extensions", "_collections_abc"})

_GENERIC_CLASSES = frozenset({"typing.Generic", "typing_extensions.Generic"})

EXPLICIT = ("<explicit>",)

FINAL_BUILTIN_METHODS = frozenset({"__iter__", "__contains__"})


class Hierarchy:
    def new_class(
        self,
        name,
        module,
        defines,
        base_nodes,
        protocol=False,
        abstract_methods=frozenset(),
        metaclass=None,
        uses_namespace=False,
    ):
        cls = Class(name, module, defines, len(base_nodes))
        cls.instances = self.node()
        cls.metaclass = self.node()
        cls.instantiable = self.node()
        cls.protocol = protocol
        cls.abstract_methods = abstract_methods
        cls.uses_namespace = uses_namespace
        cls.index = len(self.classes)
        self.classes.append(cls)
        cls.ancestry = [n for n in (*base_nodes, metaclass, cls.metaclass) if n]
        if metaclass is not None:
            cls.keyword = {}
            self.solver.attach(metaclass, Each(self._keyword_candidate, cls))
        for index, node in enumerate(base_nodes):
            if node is None:
                cls.bases[index][None] = None
            else:
                self.solver.attach(node, _Bases(self, cls, index))
        self._update_mros(cls)
        return cls

    def lookup(self, cls, attr, receiver, after=None, unless=()):
        key = (attr, receiver, after, unless)
        if key not in cls.lookups:
            watched = (cls, attr, after, unless)
            if type(receiver) is Instance and watched not in self._watches:
                self._watches[watched] = watch = Watch()
                cls.lookups[key] = Witness(watch)
            else:
                cls.lookups[key] = Node()
            if cls.ready or cls.unknown:
                self._walk_mro(cls, attr, receiver, cls.lookups[key], after, unless)
        return cls.lookups[key]

    def later(self, cls, attr, receiver, after, unless, rule, *args):
        watched = (cls, attr, after, unless)
        if watched not in self._watches:
            self.lookup(cls, attr, receiver, after, unless)
        watch = self._watches[watched]
        if watch.waiting is None:
            rule(receiver, *args)
        else:
            watch.waiting.setdefault((rule, *args), []).append(receiver)

    def unknown_classes(self):
        solver = self.solver
        if not solver.absorbed_sets:
            return False
        added = False
        changed = True
        while changed:
            changed = False
            for cls in self.classes:
                if not cls.unknown and any(
                    obj is self.saturated or (type(obj) is Class and obj.unknown)
                    for node in cls.ancestry
                    for obj in solver.objects(node)
                ):
                    for result in list(cls.lookups.values()):
                        if type(result) is Witness and result.watch.waiting:
                            result.watch.wake()
                    cls.unknown = changed = True
                    solver.opaque = opaque
                    for result in cls.lookups.values():
                        self.add_object(result, self.saturated)
                        added = True
        return added

    def python_method(self, cls, name):
        return self.lookup(cls, name, None, None, _UNLESS_PYTHONS_OWN_METHOD)

    def descriptor_itself(self, cls):
        return self.lookup(cls, "__get__", None, None, _UNLESS_DESCRIPTOR_ITSELF)

    def _may_give_itself(self, cls, name):
        if cls.exhaustive:
            return name not in cls.defines
        for mro in cls.mros:
            for base in mro:
                if isinstance(base, Class):
                    if name in base.defines:
                        break
                elif is_property(base):
                    break
                elif self.outside_member(base, name) != _OUTSIDE_GIVES_INHERITED:
                    return True
            else:
                return True
        return False

    def default_member(self, cls, name):
        return self.lookup(cls, name, None, None, _UNLESS_DEFAULT_MEMBER)

    def outside_member(self, external, name):
        definitions = self.stub_definitions(external)
        if definitions is None:
            return _OUTSIDE_GIVES_OVERRIDE
        found = set()
        for definition in definitions:
            if definition.kind != "class":
                continue
            for path in self.stubs.mro(definition.path):
                if path == BUILTIN_TYPE_PATH:
                    found.add(_OUTSIDE_GIVES_DEFAULT)
                    break
                if path == OBJECT_PATH:
                    break
                owners = {member.owner for member in self.stubs.member(path, name)}
                if path in owners:
                    found.add(_OUTSIDE_GIVES_OVERRIDE)
                    break
        if _OUTSIDE_GIVES_OVERRIDE in found:
            return _OUTSIDE_GIVES_OVERRIDE
        return (
            _OUTSIDE_GIVES_DEFAULT
            if _OUTSIDE_GIVES_DEFAULT in found
            else _OUTSIDE_GIVES_INHERITED
        )

    def outside_overrides(self, external, name):
        return self.outside_member(external, name) == _OUTSIDE_GIVES_OVERRIDE

    def _default_may_answer(self, cls, name):
        if cls.exhaustive:
            return name not in cls.defines
        return any(self._default_first(mro, name) for mro in cls.mros)

    def _default_first(self, mro, name):
        for base in mro:
            if isinstance(base, Class):
                if name in base.defines:
                    return False
            elif base is not None:
                found = self.outside_member(base, name)
                if found != _OUTSIDE_GIVES_INHERITED:
                    return found == _OUTSIDE_GIVES_DEFAULT
        return True

    def relation(self, cls, other, relation):
        return self.lookup(cls, other, None, None, relation)

    def _may_relate(self, cls, other, relation):
        if relation == MAY_LACK_METHOD:
            if cls.exhaustive:
                return other not in cls.defines
            return not all(_defines_method(mro, other) for mro in cls.mros)
        if relation == NOT_NOMINAL:
            return any(
                isinstance(base, External) and not self.nominal_outside(base)
                for mro in cls.mros
                for base in mro
            )
        if isinstance(other, External) and other.name == BUILTIN_OBJECT:
            return relation == MAY_DERIVE
        if relation == MAY_DERIVE:
            return any(self._derives_in(mro, other, True) for mro in cls.mros)
        if cls.exhaustive:
            return other is not cls
        return any(not self._derives_in(mro, other, False) for mro in cls.mros)

    def nominal_outside(self, external):
        if external.name in _GENERIC_CLASSES:
            return True
        paths = [
            definition.path
            for definition in self.stub_definitions(external) or ()
            if definition.kind == "class"
        ]
        return bool(paths) and all(map(_nominal_stub_class, paths))

    def _derives_in(self, mro, other, unknown):
        if isinstance(other, Class):
            return other in mro
        names = {
            outside_name(self.stubs.public_name(definition.path))
            for definition in self.stub_definitions(other) or ()
            if definition.kind == "class"
        }
        for base in mro:
            if isinstance(base, External):
                if self.stub_definitions(base) is None:
                    if unknown:
                        return True
                elif names & self._outside_ancestors(base):
                    return True
        return False

    def _walk_mro(self, cls, attr, receiver, dst, after=None, unless=()):
        if cls.unknown:
            self.add_object(dst, self.saturated)
            return
        explicit = unless == EXPLICIT
        if explicit:
            unless = ()
        if unless == _UNLESS_DESCRIPTOR_ITSELF:
            if self._may_give_itself(cls, attr):
                name = f"{BUILTIN_OBJECT}.{attr}"
                self.add_object(dst, self.external(name, 1))
            return
        if unless == _UNLESS_PYTHONS_OWN_METHOD:
            if _python_may_define(cls, attr):
                name = f"{BUILTIN_OBJECT}.{attr}"
                self.add_object(dst, self.external(name, 1))
            return
        if unless == _UNLESS_DEFAULT_MEMBER:
            if self._default_may_answer(cls, attr):
                name = f"{BUILTIN_OBJECT}.{attr}"
                self.add_object(dst, self.external(name, 1))
            return
        if unless in (MAY_DERIVE, MAY_LACK, MAY_LACK_METHOD, NOT_NOMINAL):
            if self._may_relate(cls, attr, unless):
                self.add_object(dst, self.external(BUILTIN_OBJECT))
            return
        through_class = explicit and receiver is cls and after is None
        if cls.exhaustive:
            self._walk_exhaustive(cls, cls.mros[0], attr, receiver, dst, after, unless)
            if (after is not None and not unless) or (
                explicit and attr not in cls.defines
            ):
                found = self.object_member(cls.mros[0], attr, receiver, dst)
                if not found and through_class:
                    self._metaclass_member(cls, attr, dst)
            return
        for mro in cls.mros:
            if after is not None:
                if after not in mro:
                    continue
                mro = mro[mro.index(after) + 1 :]
            if unless and (_defines(mro, unless) or not _defines(mro, (attr,))):
                continue
            found = self._walk_classes(mro, attr, receiver, dst, True)
            if not found and (explicit or (after is not None and not unless)):
                found = self.object_member(mro, attr, receiver, dst)
            if not found and through_class:
                self._metaclass_member(cls, attr, dst)
            if not found and after is None and not unless:
                self._fallback(mro, attr, receiver, dst)

    def _metaclass_member(self, cls, attr, dst):
        key = (cls.metaclass, attr, dst, "metaclass")
        if key not in self._subscriptions:
            self._subscriptions.add(key)
            member = Each(self._member_of_metaclass, cls, attr, dst, results=(dst,))
            self.solver.attach(cls.metaclass, member)

    def _member_of_metaclass(self, meta, cls, attr, dst):
        if isinstance(meta, Class):
            self.add_edge(self.lookup(meta, attr, cls, None, EXPLICIT), dst)
            return
        for definition in self.stub_definitions(meta) or ():
            if definition.kind == "class":
                self.stub_member(cls, definition.path, meta.name, attr, dst)

    def _walk_exhaustive(self, cls, classes, attr, receiver, dst, after, unless):
        order = cls.mros[0]
        searched_by_all = [cls]
        if after is not None:
            if after not in order:
                return
            classes = [
                base for base in classes if base is not after and base is not cls
            ]
            order = [base for base in order if base is not after and base is not cls]
            searched_by_all = []
        if unless and (
            _defines(searched_by_all, unless) or not _defines(order, (attr,))
        ):
            return
        self._walk_classes(classes, attr, receiver, dst, False)
        if after is None and not unless and attr not in cls.defines:
            for base in classes:
                self._fallback_to(base, attr, receiver, dst)

    def _fallback(self, mro, attr, receiver, dst):
        for base in mro:
            if self._fallback_to(base, attr, receiver, dst):
                return

    def _fallback_to(self, base, attr, receiver, dst):
        if not isinstance(base, Class) or "__getattr__" not in base.defines:
            return False
        instance = isinstance(receiver, Instance) or (
            isinstance(receiver, Class) and not _inherits(receiver, base)
        )
        if instance and attr != "__getattr__":
            if type(dst) is Witness and dst.watch.waiting is not None:
                dst.watch.wake()
            field = self.field(base, "__getattr__")
            key = (field, receiver, dst, "fallback")
            if key not in self._subscriptions:
                self._subscriptions.add(key)
                bind = Each(self._bind_fallback, receiver, dst, results=(dst,))
                self.solver.attach(field, bind)
        return True

    def _bind_fallback(self, obj, receiver, dst):
        key = (receiver, dst)
        if key not in self._fallback_nodes:
            node = self.node()
            self.solver.attach(node, Each(self._wrap_fallback, dst, results=(dst,)))
            self._fallback_nodes[key] = node
        self.bind(obj, receiver, self._fallback_nodes[key], instance=True)

    def _wrap_fallback(self, method, dst):
        self.add_object(dst, self.fallback(method))

    def _walk_classes(self, classes, attr, receiver, dst, first_only):
        found = False
        for base in classes:
            if isinstance(base, External) and self.stub_definitions(base) is not None:
                defines = self.outside_base_member(base, attr, receiver, dst)
            elif isinstance(base, External):
                self.external_attribute(base, attr, dst)
                defines = True
            else:
                field = self.field(base, attr)
                key = (field, receiver, dst)
                if key not in self._subscriptions:
                    self._subscriptions.add(key)
                    instance = isinstance(receiver, Instance) or (
                        isinstance(receiver, Class) and not _inherits(receiver, base)
                    )
                    self.solver.attach(field, _Bind(self, receiver, dst, instance))
                defines = attr in base.defines
            found = found or defines
            if defines and first_only:
                break
        return found

    def bind(self, obj, receiver, dst, instance=None):
        if instance is None:
            instance = isinstance(receiver, Instance)
        match obj:
            case Function() if instance:
                self.add_object(dst, self.bound_method(receiver, obj))
            case Wrapper(kind="staticmethod"):
                self.add_edge(self.field(obj, "__func__"), dst)
            case Wrapper(kind="classmethod"):
                owner = receiver.cls if isinstance(receiver, Instance) else receiver
                function = self.field(obj, "__func__")
                each = Each(self._bind_to, owner, dst, results=(dst,))
                self.solver.attach(function, each)
            case _:
                self.add_object(dst, obj)

    def _bind_to(self, obj, owner, dst):
        if isinstance(obj, Function):
            obj = self.bound_method(owner, obj)
        self.add_object(dst, obj)

    def _keyword_candidate(self, obj, cls):
        if isinstance(obj, UnknownExternal) or not isinstance(obj, (Class, External)):
            obj = None
        obj = self.same_class(obj)
        if obj in cls.keyword:
            return
        cls.keyword[obj] = None
        if isinstance(obj, Class):
            obj.metaclass_candidate_of[cls] = None
        self._update_mros(cls)

    def _decide_metaclasses(self, cls):
        keyword = [None] if cls.keyword is None else list(cls.keyword)
        type_ = self.external(BUILTIN_TYPE)
        slots = [[type_ if meta is None else meta for meta in keyword]] + [
            [meta for base in candidates for meta in self._base_metaclasses(base)]
            for candidates in cls.bases
        ]
        added = False
        for index, slot in enumerate(slots):
            others = slots[:index] + slots[index + 1 :]
            for meta in slot:
                if meta in cls.metaclasses or (
                    isinstance(meta, Class) and not meta.ready
                ):
                    continue
                if all(any(self._derives(meta, o) for o in other) for other in others):
                    cls.metaclasses[meta] = None
                    self.add_object(cls.metaclass, meta)
                    if isinstance(meta, Class):
                        self.add_object(meta.instances, cls)
                        meta.metaclass_users[cls] = None
                    added = True
        self._decide_concrete(cls)
        return added

    def _decide_concrete(self, cls):
        if not cls.concrete and self._concrete(cls):
            cls.concrete = True
            self.add_object(cls.instantiable, cls)
        if cls.concrete and not all(map(self._derives_from_type, cls.mros)):
            self.abstract_instance(cls)

    def class_attribute_stored(self, cls, name):
        if name in cls.stored_names_outside_body:
            return
        cls.stored_names_outside_body.add(name)
        pending, seen = [cls], set()
        while pending:
            current = pending.pop()
            if current in seen:
                continue
            seen.add(current)
            if current.ready and not current.unknown:
                self._decide_concrete(current)
            pending.extend(current.subclasses)

    def _concrete(self, cls):
        if cls.protocol and not any(
            any(
                isinstance(c, Class) and ("__init__" in c.defines or c.uses_namespace)
                for c in mro
            )
            for mro in cls.mros
        ):
            return False
        return not self._abstract_by_abc(cls)

    def _abstract_by_abc(self, cls):
        if not self._made_by_abc(cls):
            return False
        return all(
            self._allocates_with_object(mro)
            and self._has_abstract_name(mro, cls.exhaustive)
            for mro in cls.mros
        )

    def _made_by_abc(self, cls):
        if isinstance(cls, External):
            for definition in self.stub_definitions(cls) or ():
                if definition.kind == "class":
                    path = self.stubs.metaclass(definition.path)
                    return ABC_META in self.stubs.mro(path) or path == ABC_META
            return False
        if not cls.metaclasses:
            return False
        for meta in cls.metaclasses:
            if isinstance(meta, External):
                if not (
                    meta.name == ABC_META or ABC_META in self._outside_ancestors(meta)
                ):
                    return False
            elif meta.exhaustive or not all(
                any(
                    isinstance(base, External)
                    and (
                        base.name == ABC_META
                        or ABC_META in self._outside_ancestors(base)
                    )
                    for base in mro
                )
                for mro in meta.mros
            ):
                return False
        return True

    def _allocates_with_object(self, mro):
        for base in mro:
            if not isinstance(base, External):
                continue
            definitions = self.stub_definitions(base)
            if definitions is None:
                return False
            for definition in definitions:
                if definition.kind != "class":
                    continue
                if any(
                    path.startswith(BUILTIN_STUBS) and path != OBJECT_PATH
                    for path in self.stubs.mro(definition.path)
                ):
                    return False
                for member in self.stubs.member(definition.path, "__new__"):
                    if member.owner != OBJECT_PATH:
                        return False
        return True

    def _has_abstract_name(self, mro, exhaustive):
        abstract, concrete = set(), set()
        for base in mro:
            if isinstance(base, Class) and not base.uses_namespace:
                made = self._made_by_abc(base)
                names = {
                    name: made
                    and name in base.abstract_methods
                    and name not in base.stored_names_outside_body
                    for name in base.defines | base.stored_names_outside_body
                }
            elif isinstance(base, External) and self.stub_definitions(base):
                made = self._made_by_abc(base)
                names = {
                    name: made and is_abstract
                    for name, is_abstract in self._stub_abstract_names(base).items()
                }
            elif exhaustive:
                return False
            else:
                break
            for name, is_abstract in names.items():
                if exhaustive or (name not in abstract and name not in concrete):
                    (abstract if is_abstract else concrete).add(name)
        return bool(abstract - concrete)

    def _stub_abstract_names(self, external):
        names = {}
        for definition in self.stub_definitions(external):
            if definition.kind != "class":
                continue
            for owner in self.stubs.mro(definition.path):
                found = self.stubs.definition(owner)
                for name, member in found.entry["m"].items() if found else ():
                    names.setdefault(name, bool(member.get("x")))
        return names

    def _base_metaclasses(self, base):
        if isinstance(base, Class):
            return list(base.metaclasses)
        if isinstance(base, External):
            for definition in self.stub_definitions(base) or ():
                if definition.kind == "class":
                    path = self.stubs.metaclass(definition.path)
                    return [self.external(outside_name(self.stubs.public_name(path)))]
        return [self.external(BUILTIN_TYPE)]

    def _derives(self, meta, other):
        if meta is other or other.name == BUILTIN_TYPE:
            return True
        if isinstance(meta, Class):
            return any(_named(other, mro) for mro in meta.mros)
        if isinstance(other, External):
            return other.name in self._outside_ancestors(meta)
        return False

    def _derives_from_type(self, mro):
        return any(
            isinstance(base, External)
            and (
                base.name == BUILTIN_TYPE
                or BUILTIN_TYPE in self._outside_ancestors(base)
            )
            for base in mro
        )

    def _outside_ancestors(self, external):
        names = set()
        for definition in self.stub_definitions(external) or ():
            if definition.kind == "class":
                for path in self.stubs.mro(definition.path):
                    names.add(outside_name(self.stubs.public_name(path)))
        return names

    def add_base(self, base, cls, index):
        if isinstance(base, External) and base.name == BUILTIN_OBJECT:
            base = None
        elif not isinstance(base, (Class, External)) or base is cls:
            return
        elif isinstance(base, UnknownExternal):
            return
        elif isinstance(base, External):
            base = self.mro_entry(self.same_class(base))
        if base in cls.bases[index]:
            return
        cls.bases[index][base] = None
        if isinstance(base, Class):
            base.subclasses[cls] = None
            self.add_edge(cls.instances, base.instances)
            if base in self._families:
                self.add_edge(self.family(cls), self._families[base])
            self.members_base(base, cls)
        elif base is not None:
            self.add_outside_base(cls, base)
        self._update_mros(cls)

    def decide_hierarchies(self):
        waiting = [cls for cls in self.classes if not cls.ready and not cls.unknown]
        if not waiting:
            return False
        for cls in waiting:
            for candidates in cls.bases:
                if not candidates:
                    candidates[None] = None
            if cls.keyword is not None and not cls.keyword:
                cls.keyword[None] = None
        for cls in waiting:
            self._update_mros(cls)
        cycles = [cls for cls in waiting if not cls.ready]
        for cls in cycles:
            cls.forced = True
        for cls in cycles:
            self._update_mros(cls)
        return True

    def _update_mros(self, start):
        queue = deque([start])
        while queue:
            cls = queue.popleft()
            if cls.unknown:
                continue
            if not cls.ready:
                if not _resolved(cls):
                    continue
                cls.ready = True
                cls.mros, cls.exhaustive = self._compute_mros(cls)
                for (attr, receiver, after, unless), result in list(
                    cls.lookups.items()
                ):
                    self._walk_mro(cls, attr, receiver, result, after, unless)
                self._decide_metaclasses(cls)
                queue.extend(cls.subclasses)
                queue.extend(cls.metaclass_candidate_of)
                continue
            mros, exhaustive = self._compute_mros(cls)
            if _shape(mros, exhaustive) == _shape(cls.mros, cls.exhaustive):
                if self._decide_metaclasses(cls):
                    queue.extend(cls.subclasses)
                continue
            new = None
            if cls.exhaustive and exhaustive:
                walked = set(cls.mros[0])
                new = [base for base in mros[0] if base not in walked]
            cls.mros, cls.exhaustive = mros, exhaustive
            for (attr, receiver, after, unless), result in list(cls.lookups.items()):
                if new is None or after is not None or unless:
                    self._walk_mro(cls, attr, receiver, result, after, unless)
                else:
                    self._walk_exhaustive(cls, new, attr, receiver, result, None, ())
            self._decide_metaclasses(cls)
            queue.extend(cls.subclasses)
            queue.extend(cls.metaclass_candidate_of)
            queue.extend(cls.metaclass_users)

    def _compute_mros(self, cls):
        slots = [
            sorted(
                (
                    base
                    for base in candidates
                    if cls.forced or not isinstance(base, Class) or base.ready
                ),
                key=base_order,
            )
            for candidates in cls.bases
        ]
        exhaustive = cls.forced or any(
            isinstance(base, Class) and (base.exhaustive or cls in base.ancestors)
            for slot in slots
            for base in slot
        )
        if not exhaustive:
            mros = linearizations(cls, slots, _mros_of, HIERARCHIES_PER_CLASS_MAX)
            if mros is not None:
                return sorted(mros, key=_canonical), False
        return [exhaustive_order(cls, slots, _mros_of)], True


def _resolved(cls):
    expressions = cls.bases if cls.keyword is None else [*cls.bases, cls.keyword]
    return cls.forced or all(
        any(not isinstance(base, Class) or base.ready for base in candidates)
        for candidates in expressions
    )


def opaque(obj):
    if type(obj) is Fallback:
        obj = obj.method
    cls = obj.cls if type(obj) is Instance else obj
    return type(cls) is Saturated or (type(cls) is Class and cls.unknown)


def _inherits(cls, base):
    return base in cls.ancestors


def _named(other, mro):
    if isinstance(other, Class):
        return other in mro
    return any(isinstance(base, External) and base.name == other.name for base in mro)


def _canonical(mro):
    return [base_order(base) for base in mro]


def _shape(mros, exhaustive):
    if exhaustive:
        return True, frozenset(mros[0])
    return False, frozenset(map(tuple, mros))


def _python_may_define(cls, name):
    if cls.exhaustive:
        return name not in cls.defines
    for mro in cls.mros:
        definer = next(
            (c for c in mro if isinstance(c, External) or name in c.defines),
            None,
        )
        if not isinstance(definer, Class):
            return True
    return False


def is_property(obj):
    return isinstance(obj, External) and obj.name == f"{BUILTIN_MODULE}.property"


def _defines_method(classes, name):
    return any(
        name in base.defines
        if isinstance(base, Class)
        else isinstance(base, External) and _outside_defines(base.name, name)
        for base in classes
    )


def _defines(classes, names):
    marked = [DEFINES_MARKERS[name] for name in names if name in DEFINES_MARKERS]
    for base in classes:
        if isinstance(base, Class):
            if any(name in base.defines for name in (*names, *marked)):
                return True
        elif isinstance(base, External):
            final = FINAL_BUILTIN_METHODS.intersection(names)
            if any(_builtin_defines(base.name, name) for name in final):
                return True
            if any(_outside_defines(base.name, name) for name in marked):
                return True
            if TUPLE_STORAGE in names and _derives_from_tuple(base.name):
                return True
    return False


@cache
def _derives_from_tuple(name):
    prefix = f"{BUILTIN_MODULE}."
    if name.startswith(prefix):
        name = f"builtins.{name[len(prefix) :]}"
    return any(
        definition.kind == "class" and "builtins.tuple" in _STUBS.mro(definition.path)
        for definition in _STUBS.find(name)
    )


@cache
def _outside_defines(name, attr):
    prefix = f"{BUILTIN_MODULE}."
    if name.startswith(prefix):
        name = f"builtins.{name[len(prefix) :]}"
    return any(
        definition.kind == "class"
        and any(
            m.owner != "builtins.object" for m in _STUBS.member(definition.path, attr)
        )
        for definition in _STUBS.find(name)
    )


@cache
def _builtin_defines(name, attr):
    prefix = f"{BUILTIN_MODULE}."
    if not name.startswith(prefix):
        return False
    path = f"builtins.{name[len(prefix) :]}"
    definition = _STUBS.definition(path)
    if definition is None or definition.kind != "class":
        return False
    return any(m.owner != "builtins.object" for m in _STUBS.member(path, attr))


@cache
def _nominal_stub_class(path):
    for owner in _STUBS.mro(path):
        definition = _STUBS.definition(owner)
        meta = definition.entry.get("meta") if definition is not None else None
        if meta and class_names(meta) != ["builtins.type"]:
            return False
    for owner in _STUBS.mro(path):
        definition = _STUBS.definition(owner)
        if definition is None or definition.kind != "class":
            return False
        entry = definition.entry
        if entry.get("proto") or entry.get("tco"):
            return False
        if owner.startswith("builtins.") or entry.get("final"):
            return True
        if owner.partition(".")[0] in _MODULES_OF_ABCS or _STUBS.abstract(owner):
            return False
    return True


def _mros_of(base):
    if base is None:
        return [[]]
    return base.mros if isinstance(base, Class) else [[base]]


class _Bases(Constraint):
    __slots__ = ("analysis", "cls", "index")

    def __init__(self, analysis, cls, index):
        self.analysis = analysis
        self.cls = cls
        self.index = index

    def apply(self, obj):
        self.analysis.add_base(obj, self.cls, self.index)

    def captured(self):
        return (self.cls,)


class _Bind(Constraint):
    __slots__ = ("analysis", "receiver", "dst", "instance")

    def __init__(self, analysis, receiver, dst, instance):
        self.analysis = analysis
        self.receiver = receiver
        self.dst = dst
        self.instance = instance

    def apply(self, obj):
        self.analysis.bind(obj, self.receiver, self.dst, self.instance)

    def results(self):
        return (self.dst,)

    def captured(self):
        return (self.receiver,)
