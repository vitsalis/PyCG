"""Namespaces read by reflection.

`C.__dict__` and `vars(C)` of an analysed class give its namespace: a dict,
one per class, whose keys are the names that its body binds and that stores
assign on it, and whose element under each name is fed by the class field of
that name, the node that attribute loads read. A name or a value that the
solve adds later is in it. The dict is not exact: Python gives a
`mappingproxy`. Only where the `__dict__` that Python finds on the
metaclass may be the default one, `type`'s: a metaclass that defines its own
(in its body, or in its stubs) hides the namespace. The namespace of an
instance (`obj.__dict__`, `vars(obj)`) stays what the stubs say: code writes
it, and reads it with computed keys.

`inspect.getmembers(x)` of a class or an instance gives a list of (name,
value) pairs: the names of its class and of the candidate bases of each class
on the way up, each with what a load of it through `x` gives (a bound method
through an instance, a descriptor's result), and for an instance also the
names stored on it, with its fields. Only where the default `__dir__` lists
the names: an analysed `__dir__` of the class (the metaclass, for a class) is
not evaluated, and the rule adds nothing. The predicate is not evaluated.

Both keep what the stubs give: these rules add to the result.

`Reflection` is part of `Analysis` (see semantics.py), whose objects, nodes
and constraints it uses.
"""

from .attributes import Load
from .model import Class, Instance, base_order
from .solver import Each


class Reflection:
    def _names(self, obj):
        """The node of the names of the class or instance `obj`, as str
        constants: for a class, the names that its body binds, and for both
        the names that stores assign on it (see `stored_name`)."""
        key = (obj, "names")
        if key not in self._namespace_nodes:
            node = self._namespace_nodes[key] = self.node()
            if isinstance(obj, Class):
                for name in sorted(obj.defines):
                    self.add_object(node, self.const(name))
        return self._namespace_nodes[key]

    def stored_name(self, obj, name):
        """A store assigns `name` on the class or instance `obj`."""
        self.add_object(self._names(obj), self.const(name))

    def namespace(self, obj):
        """The namespace dict of the class `obj`."""
        site = f"{obj.name}.__dict__"
        container = self.container_at("dict", obj, site, "namespace")
        key = ("namespace", obj)
        if key not in self._subscriptions:
            self._subscriptions.add(key)
            names = self._names(obj)
            self.add_edge(names, self.keys(container))
            # A saturated set of names stands for every element.
            unknown = self.unknown(container)
            each = Each(self._namespace_element, obj, container, results=(unknown,))
            self.solver.attach(names, each)
        return container

    def _namespace_element(self, name, obj, container):
        self.add_edge(self.field(obj, name.value), self.element(container, name.value))

    def add_namespace(self, obj, dst):
        """dst ⊇ the namespace of `obj`, if it is a class whose `__dict__`
        is the default one, `type`'s."""
        if isinstance(obj, Class):
            self._default(obj, "__dict__", self._add_namespace, dst, dst)

    def _add_namespace(self, cls, dst):
        self.add_object(dst, self.namespace(cls))

    def _default(self, obj, name, action, arg, result):
        """Call `action(obj, arg)` once the attribute `name` that Python
        finds on a type of the instance or class `obj` (its class, or a
        metaclass of a class) may be the default one, that of `object` or
        `type` (see `default_member` and `outside_member`). What the
        action finds goes to the node `result`."""
        each = Each(
            self._default_type, obj, name, action, arg, result, results=(result,)
        )
        self.solver.attach(self._types(obj), each)

    def _default_type(self, kind, obj, name, action, arg, result):
        if not isinstance(kind, Class):
            if not self.outside_overrides(kind, name):
                action(obj, arg)
            return
        found = Each(self._default_found, obj, action, arg, results=(result,))
        self.solver.attach(self.default_member(kind, name), found)

    def _default_found(self, default, obj, action, arg):
        action(obj, arg)

    def _rule_namespace(self, call, receiver, args):
        """vars(x): the namespace of a class x."""
        key = ("vars", call)
        if call.dst is None or not args.given("object") or key in self._subscriptions:
            return
        self._subscriptions.add(key)
        each = Each(self.add_namespace, call.dst, results=(call.dst,))
        self.solver.attach(args["object"], each)

    def _members(self, cls):
        """The node of the names of `cls` and of the analysed candidate bases
        of each class on the way up: what `dir()` lists for the class and
        its instances, but the names of outside classes. The names of each
        class flow into those of its subclasses; a base that a base
        expression gives later joins (see `Hierarchy.add_base`)."""
        if (cls, "members") not in self._namespace_nodes:
            made, pending = [], [cls]
            while pending:
                member = pending.pop()
                key = (member, "members")
                if key not in self._namespace_nodes:
                    self._namespace_nodes[key] = self.node()
                    self.add_edge(self._names(member), self._namespace_nodes[key])
                    made.append(member)
                    pending.extend(_class_bases(member))
            for member in made:
                for base in _class_bases(member):
                    self.add_edge(
                        self._namespace_nodes[(base, "members")],
                        self._namespace_nodes[(member, "members")],
                    )
        return self._namespace_nodes[(cls, "members")]

    def members_base(self, base, cls):
        """`base` is a new candidate base of `cls`: its members are those of
        `cls` too, once `cls` has a node of members."""
        members = self._namespace_nodes.get((cls, "members"))
        if members is not None:
            self.add_edge(self._members(base), members)

    def _rule_members(self, call, receiver, args):
        """inspect.getmembers(x, predicate): a list of (name, value) pairs of
        the members of the class or instance x (see the module
        docstring)."""
        key = ("getmembers", call)
        if call.dst is None or key in self._subscriptions:
            return
        self._subscriptions.add(key)
        access = _Members(call)
        each = Each(
            self._members_of, access, kinds=(Class, Instance), results=(call.dst,)
        )
        self.solver.attach(args["object"], each)

    def _members_of(self, obj, access):
        """The members of the class or instance `obj`, where the default
        `__dir__` lists them. The list and its pair are made when the first
        such object arrives."""
        dst = access.call.dst
        self._default(obj, "__dir__", self._members_listed, access, dst)

    def _members_listed(self, obj, access):
        key = ("members", obj, access)
        if key in self._subscriptions:
            return
        self._subscriptions.add(key)
        call = access.call
        origin, site = call.origin, call.site
        found = self.container_at("list", origin, site, "members", exact=True)
        pair = self.container_at("tuple", origin, site, "member", 2, exact=True)
        self.add_object(self.unknown(found), pair)
        access.names, access.values = self.element(pair, 0), self.element(pair, 1)
        self.add_object(call.dst, found)
        cls = obj if isinstance(obj, Class) else obj.cls
        members = self._members(cls)
        self.add_edge(members, access.names)
        load = Each(self._load_member, obj, access, results=(access.values,))
        self.solver.attach(members, load)
        if isinstance(obj, Instance):
            names = self._names(obj)
            self.add_edge(names, access.names)
            field = Each(self._member_field, obj, access, results=(access.values,))
            self.solver.attach(names, field)

    def _load_member(self, name, obj, access):
        """A member through the class: an ordinary load of it through
        `obj`."""
        access.loader(self, name.value).apply(obj)

    def _member_field(self, name, obj, access):
        """A name stored on the instance `obj`: its field, which a load
        through the class would also read (a lookup that finds nothing
        there would call `__getattr__`, which Python does not)."""
        self.add_edge(self.field(obj, name.value), access.values)


def _class_bases(cls):
    """The analysed candidate bases of `cls`, in a canonical order."""
    bases = {base for candidates in cls.bases for base in candidates}
    return sorted((base for base in bases if isinstance(base, Class)), key=base_order)


class _Members:
    """A call of `inspect.getmembers`: the nodes of the names and values of
    its pairs, and its load of each name."""

    __slots__ = ("call", "names", "values", "loaders")

    def __init__(self, call):
        self.call = call
        self.names = None
        self.values = None
        self.loaders = {}

    def loader(self, analysis, name):
        if name not in self.loaders:
            call = self.call
            self.loaders[name] = Load(
                analysis, name, self.values, call.caller, call.site
            )
        return self.loaders[name]
