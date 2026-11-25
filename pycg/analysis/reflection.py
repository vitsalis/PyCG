from .attributes import Load
from .model import Class, Instance, base_order
from .solver import Each


class Reflection:
    def _namespace_names(self, obj):
        key = (obj, "names")
        if key not in self._namespace_nodes:
            node = self._namespace_nodes[key] = self.node()
            if isinstance(obj, Class):
                for name in sorted(obj.defines):
                    self.add_object(node, self.const(name))
        return self._namespace_nodes[key]

    def stored_name(self, obj, name):
        self.add_object(self._namespace_names(obj), self.const(name))

    def namespace(self, obj):
        site = f"{obj.name}.__dict__"
        container = self.container_at("dict", obj, site, "namespace")
        key = ("namespace", obj)
        if key not in self._subscriptions:
            self._subscriptions.add(key)
            names = self._namespace_names(obj)
            self.add_edge(names, self.keys(container))
            unknown = self.unknown(container)
            each = Each(self._namespace_element, obj, container, results=(unknown,))
            self.solver.attach(names, each)
        return container

    def _namespace_element(self, name, obj, container):
        self.add_edge(self.field(obj, name.value), self.element(container, name.value))

    def add_namespace(self, obj, dst):
        if isinstance(obj, Class):
            self._when_default_member(obj, "__dict__", self._add_namespace, dst, dst)

    def _add_namespace(self, cls, dst):
        self.add_object(dst, self.namespace(cls))

    def _when_default_member(self, obj, name, action, arg, result):
        each = Each(
            self._when_default_member_on_type,
            obj,
            name,
            action,
            arg,
            result,
            results=(result,),
        )
        self.solver.attach(self._types(obj), each)

    def _when_default_member_on_type(self, kind, obj, name, action, arg, result):
        if not isinstance(kind, Class):
            if not self.outside_overrides(kind, name):
                action(obj, arg)
            return
        found = Each(self._run_default_action, obj, action, arg, results=(result,))
        self.solver.attach(self.default_member(kind, name), found)

    def _run_default_action(self, default, obj, action, arg):
        action(obj, arg)

    def _rule_namespace(self, call, receiver, args):
        key = ("vars", call)
        if call.dst is None or not args.given("object") or key in self._subscriptions:
            return
        self._subscriptions.add(key)
        each = Each(self.add_namespace, call.dst, results=(call.dst,))
        self.solver.attach(args["object"], each)

    def _member_names(self, cls):
        if (cls, "members") not in self._namespace_nodes:
            made, pending = [], [cls]
            while pending:
                member = pending.pop()
                key = (member, "members")
                if key not in self._namespace_nodes:
                    self._namespace_nodes[key] = self.node()
                    self.add_edge(
                        self._namespace_names(member), self._namespace_nodes[key]
                    )
                    made.append(member)
                    pending.extend(_analysed_candidate_bases(member))
            for member in made:
                for base in _analysed_candidate_bases(member):
                    self.add_edge(
                        self._namespace_nodes[(base, "members")],
                        self._namespace_nodes[(member, "members")],
                    )
        return self._namespace_nodes[(cls, "members")]

    def members_base(self, base, cls):
        members = self._namespace_nodes.get((cls, "members"))
        if members is not None:
            self.add_edge(self._member_names(base), members)

    def _rule_members(self, call, receiver, args):
        key = ("getmembers", call)
        if call.dst is None or key in self._subscriptions:
            return
        self._subscriptions.add(key)
        access = _GetmembersAccess(call)
        each = Each(
            self._members_of, access, kinds=(Class, Instance), results=(call.dst,)
        )
        self.solver.attach(args["object"], each)

    def _members_of(self, obj, access):
        dst = access.call.dst
        self._when_default_member(obj, "__dir__", self._members_listed, access, dst)

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
        members = self._member_names(cls)
        self.add_edge(members, access.names)
        load = Each(self._load_member, obj, access, results=(access.values,))
        self.solver.attach(members, load)
        if isinstance(obj, Instance):
            names = self._namespace_names(obj)
            self.add_edge(names, access.names)
            field = Each(self._member_field, obj, access, results=(access.values,))
            self.solver.attach(names, field)

    def _load_member(self, name, obj, access):
        access.loader(self, name.value).apply(obj)

    def _member_field(self, name, obj, access):
        self.add_edge(self.field(obj, name.value), access.values)


def _analysed_candidate_bases(cls):
    bases = {base for candidates in cls.bases for base in candidates}
    return sorted((base for base in bases if isinstance(base, Class)), key=base_order)


class _GetmembersAccess:
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
