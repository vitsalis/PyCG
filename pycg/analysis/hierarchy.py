"""Class hierarchies: base classes, MROs, attribute lookups on classes, and
what a class attribute becomes when it is loaded through a receiver.

`Hierarchy` is part of `Analysis` (see semantics.py), whose objects, nodes
and constraints it uses.

Results do not depend on the order in which bases arrive. A class gets its
MROs (it is ready) only when each of its base expressions holds a ready
candidate or no base (`object`, an expression the analysis does not track,
or one that a fixpoint decided holds nothing); lookups on it wait until
then. After that, a new candidate only adds alternative MROs, and the
exhaustive order that stands for many alternatives finds what every one of
them would, so no lookup keeps a result that a complete hierarchy would not
give. Classes on a cycle of candidate bases get the exhaustive order.
"""

from collections import deque
from functools import cache

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
from .mro import linearizations, merged_order
from .outside import outside_name
from .solver import Constraint, Each, Node, Watch, Witness
from .stubs import Stubs, class_names

# The stub data, for what the builtin classes define (see `_builtin_defines`).
_STUBS = Stubs()

BUILTIN_OBJECT = f"{BUILTIN_MODULE}.object"
BUILTIN_TYPE = f"{BUILTIN_MODULE}.type"
# The stub path of `object`, whose `__new__` refuses an abstract class.
OBJECT_PATH = "builtins.object"
BUILTIN_STUBS = "builtins."
BUILTIN_TYPE_PATH = "builtins.type"
ABC_META = "abc.ABCMeta"

# A class has at most this many alternative MROs; beyond that, one order with
# every candidate base stands for all of them.
MAX_HIERARCHIES = 8

# The `unless` of the lookup that tells whether Python's own special method
# may run (see `python_method`).
_PYTHONS_OWN = ("<python's own>",)

# The `unless` of the lookup that tells whether the attribute that Python
# finds may be the default one, that of `object` or `type` (see
# `default_member`).
_DEFAULT_MEMBER = ("<the default>",)

# What an outside class gives for a member when the MRO walk of
# `default_member` reaches it: `type`'s own (the default), another
# definition, or neither (the walk goes on).
_DEFAULT, _OVERRIDE, _INHERITED = "default", "override", "inherited"

# The `unless` of the lookups that tell whether a class may derive from
# another class, or may not (see `relation`).
MAY_DERIVE = ("<may derive>",)
MAY_LACK = ("<may lack>",)
# The `unless` of the lookup that tells whether an outside class of some
# MRO of a class may test instances otherwise than by MRO (see `relation`).
NOT_NOMINAL = ("<not nominal>",)

# The modules whose classes are ABCs or protocols at run time, whatever
# metaclass their stubs declare.
_ABC_MODULES = frozenset({"abc", "typing", "typing_extensions", "_collections_abc"})

# `Generic` adds no instance check: its subclasses are tested by MRO.
_GENERIC = frozenset({"typing.Generic", "typing_extensions.Generic"})

# The `unless` of the lookup of an attribute that the code loads by name
# (`self.x`, `C.x`, `super().x`): it also finds what `object` defines (see
# `Outside.object_member`). Implicit lookups (special methods that the
# interpreter calls, `__init__` when a class is instantiated) do not, but
# for a lookup after a class (`__init_subclass__` of the nearest base): an
# instance whose `__init__` is object's gets no call.
EXPLICIT = ("<explicit>",)

# Special methods whose builtin implementations never call what Python falls
# back to without them: a subclass of list that defines `__getitem__`
# iterates with `list.__iter__`, and tests `in` with `list.__contains__`.
# Not so for conversions: `int.__format__` calls `__str__` for an empty spec.
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
        """Create a class whose base expressions have the nodes `base_nodes`
        (None for an expression without a value), and whose `metaclass=`
        expression has the node `metaclass` (None without one). It lists
        `Protocol` among its bases if `protocol`, and its body defines the
        names `abstract_methods` with an abstract method; its body reads or
        writes its namespace if `uses_namespace`. A class has one
        instance that stands for "an object of this class", unless Python
        makes no object of it (see `_concrete`) or it is a metaclass, whose
        objects are classes. That is decided when the class is ready (see
        `_decide_metaclasses`)."""
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
        """Return the node that holds the attribute `attr` of `cls`, bound to
        `receiver` (`cls` itself or one of its instances).

        If `after` is a class, the lookup starts after it in the MRO, as
        `super()` does. If `unless` names attributes, the lookup only uses
        the MROs in which no analysed class defines any of them, and only
        the definitions in class bodies: it finds the special method that
        Python falls back to (`__repr__` for `str()` without `__str__`).

        A lookup through an instance in an MRO where no class defines `attr`
        also gives the `__getattr__` that the MRO defines, as a `Fallback`.

        Every load of that attribute through that receiver shares the node.
        The lookup waits until `cls` is ready, and is redone when its MROs
        change.
        """
        key = (attr, receiver, after, unless)
        if key not in cls.lookups:
            watched = (cls, attr, after, unless)
            if type(receiver) is Instance and watched not in self._watches:
                # The first lookup of the name through an instance of the
                # class: it tells when the class may answer (see `later`).
                self._watches[watched] = watch = Watch()
                cls.lookups[key] = Witness(watch)
            else:
                cls.lookups[key] = Node()
            if cls.ready or cls.unknown:
                self._walk_mro(cls, attr, receiver, cls.lookups[key], after, unless)
        return cls.lookups[key]

    def later(self, cls, attr, receiver, after, unless, rule, *args):
        """Run `rule(receiver, *args)`, a rule that looks `attr` up on `cls`
        through its instance `receiver` (see `lookup` for `after` and
        `unless`) and acts only through what that lookup finds: now if the
        class may answer the name, else when it first may.

        The lookups of one name on one class through its instances differ
        only in the receiver that they bind, and each gets its first object
        in the same round as the others. So the first one, the witness,
        stands for all, and the rule waits, as an entry in a list, until the
        witness gets an object or an edge (`Solver.add_object`, `add_edge`).
        Then it runs and makes the lookup and the constraints that it would
        have made at once, which had nothing to act on before (see *Records
        on demand* in docs/design.md)."""
        watched = (cls, attr, after, unless)
        if watched not in self._watches:
            self.lookup(cls, attr, receiver, after, unless)
        watch = self._watches[watched]
        if watch.waiting is None:
            rule(receiver, *args)
        else:
            watch.waiting.setdefault((rule, *args), []).append(receiver)

    def unknown_classes(self):
        """Between rounds (see `Solver.between_rounds`): decide which classes
        are unknown, from the sets that the last propagation left. A class
        is unknown when the set of one of its base expressions or of its
        metaclass (written or inferred) holds the saturated value or an
        unknown class. Nothing about an unknown class is known, its own
        members included: it and its instances are opaque to every rule,
        which sees them as the saturated value (`opaque`), and every lookup
        on it gives the saturated value. What earlier rounds found stays.
        Return whether a lookup got the saturated value, which then
        propagates before the constraints apply."""
        solver = self.solver
        if not solver.absorbed_sets:
            # No node saturated yet.
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
                    # The rules that wait for the class to answer run first,
                    # while its instances are not opaque, and make what the
                    # saturated value then reaches, as if made at once (see
                    # `later`).
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
        """A node that gets an object (`<builtin>.object.name`) once Python's
        own special method `name`, or an external class's, may run for an
        instance of `cls`: in some MRO no analysed class body defines `name`
        before an external class or the end; in an exhaustive order, unless
        `cls` itself defines it. Like a lookup, it waits until `cls` is
        ready and is redone when its MROs grow, which can only turn the
        answer from no to yes."""
        return self.lookup(cls, name, None, None, _PYTHONS_OWN)

    def default_member(self, cls, name):
        """A node that gets an object once the attribute `name` (`__dir__`
        or `__dict__`) that Python finds for an instance of `cls` may be the
        default one: `type`'s for a class (`cls` is then a metaclass),
        `object`'s for another object. In some MRO, the first class that
        defines `name` is `type`, or none is (`object` ends every MRO): an
        analysed class defines it by its body; an outside class by its
        stubs, walking its stub MRO up to `type` (see `outside_member`). As
        for any lookup, one candidate MRO that reaches the default is
        enough: the answer only turns from no to yes as MROs are added. In
        an exhaustive order, unless `cls` itself defines it. It waits until
        `cls` is ready and is redone when its MROs grow."""
        return self.lookup(cls, name, None, None, _DEFAULT_MEMBER)

    def outside_member(self, external, name):
        """What the outside class `external` gives for `name` by its stubs:
        the default (`_DEFAULT`) if its stub MRO reaches `type` before a
        class that defines `name`, another definition (`_OVERRIDE`) if a
        class defines it first, else `_INHERITED`: `object`'s, which comes
        last in Python's MRO, so the walk goes on. A class without stubs
        may define any name."""
        definitions = self.stub_definitions(external)
        if definitions is None:
            return _OVERRIDE
        found = set()
        for definition in definitions:
            if definition.kind != "class":
                continue
            for path in self.stubs.mro(definition.path):
                if path == BUILTIN_TYPE_PATH:
                    found.add(_DEFAULT)
                    break
                if path == OBJECT_PATH:
                    break
                owners = {member.owner for member in self.stubs.member(path, name)}
                if path in owners:
                    found.add(_OVERRIDE)
                    break
        if _OVERRIDE in found:
            return _OVERRIDE
        return _DEFAULT if _DEFAULT in found else _INHERITED

    def outside_overrides(self, external, name):
        """Whether the `name` that Python finds on the outside class
        `external` is not the default one (see `outside_member`)."""
        return self.outside_member(external, name) == _OVERRIDE

    def _default_may_answer(self, cls, name):
        """See `default_member`."""
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
                if found != _INHERITED:
                    return found == _DEFAULT
        return True

    def relation(self, cls, other, relation):
        """A node that gets an object once some hierarchy of `cls` may make
        it derive from the class `other` (`MAY_DERIVE`), or not derive from
        it (`MAY_LACK`), or once an outside class of some MRO of `cls` may
        test its instances otherwise than by MRO (`NOT_NOMINAL`, `other`
        None; see `nominal_outside`). Every class derives from `object`; an
        outside class derives from the classes of its stub MRO, and one
        without stubs may derive from any class. Like a lookup, it waits
        until `cls` is ready and is redone when its MROs grow, which can
        only turn the answer from no to yes: an MRO is added, or an
        exhaustive order, which stands for every hierarchy, gains
        classes."""
        return self.lookup(cls, other, None, None, relation)

    def _may_relate(self, cls, other, relation):
        """See `relation`."""
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
        """Whether `isinstance` and `issubclass` against the outside class
        `external` follow MROs alone: its metaclass is known to be `type`.
        That holds for `Generic`, and for a class of the stubs whose stub
        MRO has no class that declares a metaclass other than `type`, and,
        up to the first class of `builtins` (or from the start, for a class
        of `builtins`), no protocol, no class of the stubs only, no abstract
        class and no class of the modules of ABCs. Not for a class without
        stubs, whose metaclass is not known."""
        if external.name in _GENERIC:
            return True
        paths = [
            definition.path
            for definition in self.stub_definitions(external) or ()
            if definition.kind == "class"
        ]
        return bool(paths) and all(map(_nominal_stub_class, paths))

    def _derives_in(self, mro, other, unknown):
        """Whether a class of `mro` is `other` or, if outside, derives from
        it; a class without stubs counts as `unknown`."""
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
        """Subscribe `dst` to `attr` in every MRO of `cls`, up to the first
        class that defines it. See `lookup` for `after` and `unless`,
        `python_method` and `EXPLICIT`."""
        if cls.unknown:
            # Nothing about the class is known (see `unknown_classes`).
            self.add_object(dst, self.saturated)
            return
        explicit = unless == EXPLICIT
        if explicit:
            unless = ()
        if unless == _PYTHONS_OWN:
            if _python_may_define(cls, attr):
                name = f"{BUILTIN_OBJECT}.{attr}"
                self.add_object(dst, self.external(name, 1))
            return
        if unless == _DEFAULT_MEMBER:
            if self._default_may_answer(cls, attr):
                name = f"{BUILTIN_OBJECT}.{attr}"
                self.add_object(dst, self.external(name, 1))
            return
        if unless in (MAY_DERIVE, MAY_LACK, NOT_NOMINAL):
            if self._may_relate(cls, attr, unless):
                self.add_object(dst, self.external(BUILTIN_OBJECT))
            return
        # A load through the class itself that its MROs do not answer
        # finds the attribute in the metaclass (see `_metaclass_member`).
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
                # `object` ends every MRO, but no MRO holds it.
                found = self.object_member(mro, attr, receiver, dst)
            if not found and through_class:
                self._metaclass_member(cls, attr, dst)
            if not found and after is None and not unless:
                self._fallback(mro, attr, receiver, dst)

    def _metaclass_member(self, cls, attr, dst):
        """dst ⊇ the attribute `attr` that the metaclasses of `cls` give,
        bound to `cls`, for a load through `cls` that no class of an MRO of
        `cls`, nor `object`, answers: an analysed metaclass's, by a lookup
        through `cls` (see `bind`), or the stubs' member of an outside one
        (`type.mro`)."""
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
        """Subscribe `dst` to `attr` in `classes`, which are the exhaustive
        order of `cls` or the classes an update added to it, finding what
        every hierarchy the order stands for would: every definition; after
        `after`, every class but `after` and `cls`; with `unless`, nothing
        only if a class that every one of those hierarchies searches (`cls`,
        when the lookup does not start after a class) defines one of the
        names, or no class defines `attr`; and the `__getattr__` of every
        class unless `cls` itself defines `attr`."""
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
        """Subscribe `dst` to the `__getattr__` of `mro`, as a `Fallback`,
        for a load of `attr` through an instance that no class defines: the
        first that a class body of `mro` defines."""
        for base in mro:
            if self._fallback_to(base, attr, receiver, dst):
                return

    def _fallback_to(self, base, attr, receiver, dst):
        """Subscribe `dst` to the `__getattr__` of `base`, if `base` is an
        analysed class whose body defines it; return whether it does. What
        an external class in the MRO defines is not seen. The receiver is
        an instance of `base`: an instance, or a class whose metaclass it
        is (see `_metaclass_member`)."""
        if not isinstance(base, Class) or "__getattr__" not in base.defines:
            return False
        instance = isinstance(receiver, Instance) or (
            isinstance(receiver, Class) and not _inherits(receiver, base)
        )
        if instance and attr != "__getattr__":
            # The fallback reaches `dst` through a node of its own per
            # receiver, a round after the walk: the waiting rules run now, so
            # that their lookups get it in the same round (see `later`).
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
        """`obj` is a `__getattr__` that a class attribute holds: bind it to
        `receiver` as any class attribute is bound (see `bind`), and give
        what that makes as a `Fallback`, which the load calls."""
        key = (receiver, dst)
        if key not in self._fallback_nodes:
            node = self.node()
            self.solver.attach(node, Each(self._wrap_fallback, dst, results=(dst,)))
            self._fallback_nodes[key] = node
        self.bind(obj, receiver, self._fallback_nodes[key], instance=True)

    def _wrap_fallback(self, method, dst):
        self.add_object(dst, self.fallback(method))

    def _walk_classes(self, classes, attr, receiver, dst, first_only):
        """Subscribe `dst` to `attr` in `classes`, in order; if `first_only`,
        up to the first class that defines it. Return whether a class
        defines it; an external class may."""
        found = False
        for base in classes:
            if isinstance(base, External) and self.stub_definitions(base) is not None:
                defines = self.outside_base_member(base, attr, receiver, dst)
            elif isinstance(base, External):
                # Outside code without stubs may define any name: the member
                # is named through the outside base.
                self.external_attribute(base, attr, dst)
                defines = True
            else:
                field = self.field(base, attr)
                key = (field, receiver, dst)
                if key not in self._subscriptions:
                    self._subscriptions.add(key)
                    # A class that does not derive from `base` is an
                    # instance of it: `base` is one of its metaclasses.
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
        """Add to `dst` what `obj`, found on a class, becomes when it is
        loaded through `receiver` (the class itself or one of its
        instances, which may be a class whose metaclass it is: `instance`).

        A function binds to an instance. A static method is the function it
        wraps, unbound; a class method binds the class of the receiver.
        """
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
        """Bind what a class method wraps to its class if it is a function;
        give any other callable as it is."""
        if isinstance(obj, Function):
            obj = self.bound_method(owner, obj)
        self.add_object(dst, obj)

    def _keyword_candidate(self, obj, cls):
        """`obj` reaches the `metaclass=` expression of `cls`: a class, or
        anything else, which Python calls to make the class (its type is
        then taken to be `type`)."""
        if isinstance(obj, UnknownExternal) or not isinstance(obj, (Class, External)):
            obj = None
        obj = self.same_class(obj)
        if obj in cls.keyword:
            return
        cls.keyword[obj] = None
        if isinstance(obj, Class):
            obj.metaclass_of[cls] = None
        self._update_mros(cls)

    def _decide_metaclasses(self, cls):
        """Add the metaclasses of the ready class `cls`, decide whether
        Python may make an object of it (see `_concrete`), and if so give it
        its abstract instance if some MRO of it does not derive from `type`;
        return whether a metaclass was added.

        A class is an instance of its metaclass, the most derived of the
        classes that its `metaclass=` expression holds (`type` without
        one) and the metaclasses of its bases (`type` for an outside base
        that the stubs do not describe). Each expression may hold several
        candidates, so a candidate is a metaclass of `cls` if, for each
        other expression, it derives from one of that expression's
        candidates: it is the most derived in some choice of them. The
        candidates only grow, so the metaclasses only grow, and do not
        depend on the order in which they arrive. A class among the
        candidates that is not ready yet waits (see `_resolved`)."""
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
        """Open the gate of the ready class `cls` once Python may make an
        object of it (see `_concrete`), and give it its abstract instance
        unless it is a metaclass. Evidence of one concrete alternative keeps
        it concrete for good: the decision only turns from "no instance yet"
        to "instance"."""
        if not cls.concrete and self._concrete(cls):
            cls.concrete = True
            self.add_object(cls.instantiable, cls)
        if cls.concrete and not all(map(self._derives_from_type, cls.mros)):
            self.abstract_instance(cls)

    def class_attribute_stored(self, cls, name):
        """A store outside the body assigns `name` on the class `cls`: an
        abstract method that it replaces no longer counts, for `cls` and its
        subclasses (see `_concrete`)."""
        if name in cls.stored_names:
            return
        cls.stored_names.add(name)
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
        """Whether Python may make an object of the ready class `cls`. Only
        `object.__new__` and the initializer of `Protocol` refuse a class:
        the class is refused when, for every alternative, it lists
        `Protocol` and no class body of an MRO defines `__init__` or uses
        its namespace (which may bind any name), or it is
        certainly abstract by `abc` (see `_abstract_by_abc`). Anything else
        may be made, and the answer only turns from no to yes as MROs,
        metaclasses and stores are added."""
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
        """Whether `object.__new__` certainly refuses `cls`: `cls` is made by
        `ABCMeta` (see `_made_by_abc`), and in every MRO an outside class
        that allocates otherwise (`list`) is absent and some name is
        abstract (see `_has_abstract_name`)."""
        if not self._made_by_abc(cls):
            return False
        return all(
            self._allocates_with_object(mro)
            and self._has_abstract_name(mro, cls.exhaustive)
            for mro in cls.mros
        )

    def _made_by_abc(self, cls):
        """Whether every metaclass of the analysed or outside class `cls`
        derives from `ABCMeta` in every hierarchy: then the class has
        `__abstractmethods__`. An exhaustive metaclass, or none yet, is not
        certain."""
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
        """Whether the outside classes of `mro` leave `object.__new__` as
        the allocator: each is described by the stubs, derives from no
        builtin type but `object` (a builtin type allocates in C: `list`,
        `Exception`), and its `__new__`, if any, is object's. Special forms
        (`Protocol`, `Generic`) allocate nothing."""
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
        """Whether a name is abstract in `mro`, as `ABCMeta` decides it: the
        first class that defines the name there is made by `ABCMeta` and its
        final binding of the name is an abstract method (an analysed class
        body, not replaced by a store outside it), or it is a stub member
        marked abstract. An outside class without stubs may define any
        name, and so may a class body that uses its namespace. In an
        exhaustive order, a name is abstract where every class
        of the order that defines it defines it so."""
        abstract, concrete = set(), set()
        for base in mro:
            if isinstance(base, Class) and not base.uses_namespace:
                made = self._made_by_abc(base)
                names = {
                    name: made
                    and name in base.abstract_methods
                    and name not in base.stored_names
                    for name in base.defines | base.stored_names
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
        """The names that the outside class `external` has, through its
        stub MRO, each with whether its first definition is abstract."""
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
        """The metaclasses of a candidate base: those of an analysed class,
        the one that the stubs give an outside class, else `type`."""
        if isinstance(base, Class):
            return list(base.metaclasses)
        if isinstance(base, External):
            for definition in self.stub_definitions(base) or ():
                if definition.kind == "class":
                    path = self.stubs.metaclass(definition.path)
                    return [self.external(outside_name(self.stubs.public_name(path)))]
        return [self.external(BUILTIN_TYPE)]

    def _derives(self, meta, other):
        """Whether the metaclass `meta` is `other` or derives from it, as
        far as its MROs (or for an outside class, its stubs) say. Every
        metaclass derives from `type`."""
        if meta is other or other.name == BUILTIN_TYPE:
            return True
        if isinstance(meta, Class):
            return any(_named(other, mro) for mro in meta.mros)
        if isinstance(other, External):
            return other.name in self._outside_ancestors(meta)
        return False

    def _derives_from_type(self, mro):
        """Whether the MRO is that of a metaclass: it holds `type`, or an
        outside class that derives from it."""
        return any(
            isinstance(base, External)
            and (
                base.name == BUILTIN_TYPE
                or BUILTIN_TYPE in self._outside_ancestors(base)
            )
            for base in mro
        )

    def _outside_ancestors(self, external):
        """The names of the classes of the stub MRO of an outside class."""
        names = set()
        for definition in self.stub_definitions(external) or ():
            if definition.kind == "class":
                for path in self.stubs.mro(definition.path):
                    names.add(outside_name(self.stubs.public_name(path)))
        return names

    def add_base(self, base, cls, index):
        """Add `base` as a candidate of the base expression `index` of
        `cls`, and update the MROs if it is new. `object` is no base: the
        implicit root of every class."""
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
        """At a fixpoint, decide the classes that still wait: a base
        expression that holds nothing holds no base, and classes that still
        wait after that are on (or below) a cycle of candidate bases and get
        the exhaustive order. An unknown class is not decided: nothing about
        it is known. Return whether any class waited."""
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
        """Give `start` its MROs if it can have them, or recompute them, and
        do the same for its subclasses; walk the lookups that waited or
        redo those that changed.

        MROs only grow: a recomputation adds alternative MROs, or classes to
        an exhaustive order, so the update ends. An exhaustive lookup finds
        the attribute in every class of the order, so when an exhaustive
        order grows, only its new classes are walked.
        """
        queue = deque([start])
        while queue:
            cls = queue.popleft()
            if cls.unknown:
                # Nothing about it is known (see `unknown_classes`).
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
                queue.extend(cls.metaclass_of)
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
            queue.extend(cls.metaclass_of)
            # Whether the classes of this metaclass are made by ABCMeta may
            # change (see `_made_by_abc`).
            queue.extend(cls.metaclass_users)

    def _compute_mros(self, cls):
        """Return the MROs of `cls`, one per hierarchy its ready candidate
        bases allow, and whether they are exhaustive (see `Class`): with
        more than `MAX_HIERARCHIES`, when a base is exhaustive, or when `cls`
        is on a cycle of candidate bases."""
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
            mros = linearizations(cls, slots, _mros_of, MAX_HIERARCHIES)
            if mros is not None:
                return sorted(mros, key=_canonical), False
        return [merged_order(cls, slots, _mros_of)], True


def _resolved(cls):
    """Whether each base expression of `cls`, and its `metaclass=`
    expression, holds no class or a candidate that is ready, or a fixpoint
    decided `cls`."""
    expressions = cls.bases if cls.keyword is None else [*cls.bases, cls.keyword]
    return cls.forced or all(
        any(not isinstance(base, Class) or base.ready for base in candidates)
        for candidates in expressions
    )


def opaque(obj):
    """Whether `obj` is the saturated value, an unknown class or an instance
    of one, or the `__getattr__` that a load calls (a `Fallback`) when its
    method is: what no rule sees (see `Hierarchy.unknown_classes`)."""
    if type(obj) is Fallback:
        obj = obj.method
    cls = obj.cls if type(obj) is Instance else obj
    return type(cls) is Saturated or (type(cls) is Class and cls.unknown)


def _inherits(cls, base):
    """Whether the class `cls` is `base` or derives from it."""
    return base in cls.ancestors


def _named(other, mro):
    """Whether the MRO holds the class `other` (an outside one by name)."""
    if isinstance(other, Class):
        return other in mro
    return any(isinstance(base, External) and base.name == other.name for base in mro)


def _canonical(mro):
    """A key that orders the alternative MROs of a class the same way in
    every solve, whatever order its candidate bases arrived in."""
    return [base_order(base) for base in mro]


def _shape(mros, exhaustive):
    """What lookups depend on: the alternative MROs, or the classes of an
    exhaustive order, in any order."""
    if exhaustive:
        return True, frozenset(mros[0])
    return False, frozenset(map(tuple, mros))


def _python_may_define(cls, name):
    """See `Hierarchy.python_method`."""
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


def _defines(classes, names):
    """Whether a class among `classes` defines one of `names`: an analysed
    class, or a builtin class that defines one of `FINAL_BUILTIN_METHODS`
    among them."""
    for base in classes:
        if isinstance(base, Class):
            if any(name in base.defines for name in names):
                return True
        elif isinstance(base, External):
            final = FINAL_BUILTIN_METHODS.intersection(names)
            if any(_builtin_defines(base.name, name) for name in final):
                return True
    return False


@cache
def _builtin_defines(name, attr):
    """Whether the builtin class named `name` (`<builtin>.list`) or one of
    its bases other than `object` defines `attr`, as the stubs say (in some
    version)."""
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
    """See `Hierarchy.nominal_outside`: the stub class `path`."""
    # A metaclass that a class of the whole stub MRO declares, also after a
    # builtin class (`IntEnum`: `int`, then `Enum` of `EnumMeta`).
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
        if owner.startswith("builtins."):
            # The stubs give builtin classes protocol bases that they do not
            # have at run time.
            return True
        if owner.partition(".")[0] in _ABC_MODULES or _STUBS.abstract(owner):
            return False
    return True


def _mros_of(base):
    if base is None:
        return [[]]
    return base.mros if isinstance(base, Class) else [[base]]


class _Bases(Constraint):
    """Adds the candidate bases that reach a base expression of `cls`."""

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
    """Adds what the class attribute becomes when loaded through
    `receiver`, an instance of the class if `instance`."""

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
