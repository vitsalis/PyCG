import ast
from functools import cache
from typing import NamedTuple

from .builtin_models import (
    DYNAMIC_NAMES_MAX,
    FUNCTIONS,
    LENGTH_HINT,
    RETURNS_ARGUMENT,
    REVERSED_LENGTH,
    SEQUENCE_LENGTH,
    WRAPPED_ATTRIBUTES_BY_TYPE,
    method_model,
)
from .containers import SEQUENCES, hashes_keys, is_dict, keeps_mapping_hashes
from .hierarchy import MAY_DERIVE
from .model import (
    BUILTIN_MODULE,
    Class,
    Const,
    Container,
    External,
    Function,
    Generator,
    Instance,
    Pattern,
    Signature,
    Wrapper,
)
from .solver import Each


class BuiltinRules:
    def builtin_function_rule(self, external):
        name = _builtin_name(external)
        return FUNCTIONS.get(name) if name else None

    def returns_argument(self, callee, call):
        entry = RETURNS_ARGUMENT.get(callee.name)
        if entry is None:
            return False
        analysed = isinstance(callee, Function)
        self.model_edge(callee.name, analysed, call)
        self.return_argument(entry, callee.name, analysed, call)
        return True

    def model_edge(self, name, analysed, call):
        if analysed:
            self._add_call_edge(call, name)
        else:
            self.add_external_call_edge(name, call, "stub")

    def return_argument(self, entry, name, analysed, call):
        if call.dst is None:
            return
        args = self.bind_model(call, entry)
        parameter = entry[1]
        if parameter is not None and args.given(parameter):
            self.add_edge(args[parameter], call.dst)
        if parameter is None or not args.surely(parameter):
            named = entry[2] if len(entry) > 2 else name
            decorator = self.returning_argument(named, analysed)
            self.add_object(call.dst, decorator)

    def apply_rule(self, entry, call, receiver):
        _, name, *parameters = entry
        args = self.bind_model(call, entry)
        getattr(self, f"_rule_{name}")(call, receiver, args, *parameters)

    def bind_model(self, call, entry):
        key = (call, entry)
        if key not in self._model_bindings:
            signature, constants = _signature(entry[0])
            self._model_bindings[key] = self.bind_signature(call, signature, constants)
        return self._model_bindings[key]

    def bind_signature(self, call, signature, constants):
        defaults = {
            name: self.constant(self.const(value)) for name, value in constants.items()
        }
        positional = signature.positional[: len(call.args)]
        keywords = tuple(
            name for name, _ in call.keywords if signature.accepts_keyword(name)
        )
        if not (
            call.star
            or call.double_star
            or signature.vararg
            or signature.kwarg
            or any(name in positional for name in keywords)
            or len(set(keywords)) != len(keywords)
        ):
            supplied = self._interned_name_set(positional + keywords)
            return _LateBound(call, signature, constants, self.solver.phase, supplied)
        parameters = {name: self.node() for name in signature.names()}
        function = Function(None, None, signature, parameters, defaults, None)
        if signature.vararg:
            function.varargs = Container("tuple", call.site)
        if signature.kwarg:
            function.varkeywords = Container("dict", call.site)
        supplied = self.bind_arguments(function, call, None)
        possible = set(supplied)
        if call.star:
            possible.update(signature.positional[len(call.args) :])
        if call.double_star:
            possible.update(
                name for name in signature.names() if signature.accepts_keyword(name)
            )
        return _Bound(
            function,
            self._interned_name_set(supplied),
            self._interned_name_set(possible),
        )

    def _interned_name_set(self, names):
        names = frozenset(names)
        return self._name_sets.setdefault(names, names)

    def late_parameter(self, bound, name):
        call, signature = bound.call, bound.signature
        if name not in signature.names():
            raise KeyError(name)
        source = None
        positional = signature.positional[: len(call.args)]
        if name in positional:
            source = call.args[positional.index(name)]
        elif bound.surely(name):
            source = next(value for keyword, value in call.keywords if keyword == name)
        elif name in bound.constants:
            source = self.constant(self.const(bound.constants[name]))
        if source is None:
            return self.node()
        return self.solver.follower(source, bound.since)

    def load_builtin_attribute(self, obj, type_name, attr, dst):
        if attr in WRAPPED_ATTRIBUTES_BY_TYPE.get(type_name, ()):
            self.add_edge(self.field(obj, attr), dst)
        elif method_model(type_name, attr) is not None:
            self.add_object(dst, self.builtin_method(obj, type_name, attr))
        else:
            self.builtin_member(obj, type_name, attr, dst)

    def _rule_wrap(self, call, receiver, args, kind):
        wrapper = self.wrapper(kind, call)
        self.add_edge(args["function"], self.field(wrapper, "__func__"))
        self._result(call, wrapper)

    def add_implicit_method(self, value, field, kind, site):
        self.solver.attach(
            value, Each(self._implicit_method, field, kind, site, results=(field,))
        )

    def _implicit_method(self, obj, field, kind, site):
        if isinstance(obj, Function):
            key = (kind, field)
            if key not in self._wrappers:
                self._wrappers[key] = Wrapper(kind, site)
            wrapper = self._wrappers[key]
            self.add_object(self.field(wrapper, "__func__"), obj)
            obj = wrapper
        self.add_object(field, obj)

    def _rule_property(self, call, receiver, args):
        prop = self.wrapper("property", call)
        self._store_accessors(prop, args)
        self._result(call, prop)

    def _store_accessors(self, prop, args):
        for name in WRAPPED_ATTRIBUTES_BY_TYPE["property"]:
            if args.given(name):
                self.add_edge(args[name], self.field(prop, name))

    def _properties(self, call, args, rule, *parameters):
        each = Each(
            self._property_receiver,
            rule,
            parameters,
            call.dst,
            kinds=(Wrapper, Instance),
            results=(call.dst,),
        )
        self.solver.attach(args["self"], each)

    def _property_receiver(self, prop, rule, parameters, dst):
        if isinstance(prop, Wrapper):
            if prop.kind == "property":
                rule(prop, *parameters)
            return
        builtin = self.external(f"{BUILTIN_MODULE}.property")
        derives = self.relation(prop.cls, builtin, MAY_DERIVE)
        each = Each(self._derived_property, rule, prop, parameters, results=(dst,))
        self.solver.attach(derives, each)

    def _derived_property(self, derives, rule, prop, parameters):
        rule(prop, *parameters)

    def _rule_property_init(self, call, receiver, args):
        if _may_init_property(call):
            self._properties(call, args, self._store_accessors, args)

    def _rule_property_with(self, call, receiver, args, accessor):
        self._properties(call, args, self._property_with, args, accessor, call)

    def _property_with(self, prop, args, accessor, call):
        self.add_edge(args["function"], self.field(prop, accessor))
        self._result(call, prop)

    def _rule_property_run(self, call, receiver, args, accessor):
        arity = {"fget": (2, 3), "fset": (3, 3), "fdel": (2, 2)}[accessor]
        if not self._positional_call(call, *arity):
            return
        if accessor == "fget" and self.literal_none(call, 1):
            if self.literal_none(call, 2) or not self._supplies(call, 2):
                return
            self._properties(call, args, self._give, call)
            return
        values = [args["instance"]]
        if accessor == "fset":
            values.append(args["value"])
        kind = _ACCESS_KIND_BY_ACCESSOR[accessor]
        dst = call.dst if accessor == "fget" else None
        run = self.site_call(
            call.caller, call.site, ("property", kind, accessor), values, dst=dst
        )
        self._properties(call, args, self._run_property, accessor, run)

    def _give(self, prop, call):
        self._result(call, prop)

    def _run_property(self, prop, accessor, run):
        each = Each(self.call, run, results=(run.dst,))
        self.solver.attach(self.field(prop, accessor), each)

    def _rule_bind(self, call, receiver, args):
        if call.dst is None or not self._positional_call(call, 1, 2):
            return
        no_instance = self.literal_none(call, 0)
        owner_none = self.literal_none(call, 1)
        may_have_owner = self._supplies(call, 1) and not owner_none
        may_lack_owner = len(call.args) < 2 or owner_none
        if no_instance and not may_have_owner:
            return
        if receiver.kind == "staticmethod":
            self.add_edge(self.field(receiver, "__func__"), call.dst)
            return
        if may_have_owner:
            each = Each(
                self._bind_class,
                receiver,
                call.dst,
                kinds=(Class, External),
                results=(call.dst,),
            )
            self.solver.attach(args["owner"], each)
        if may_lack_owner and not no_instance:
            each = Each(
                self._bind_type,
                receiver,
                call.dst,
                kinds=(Instance, Class),
                results=(call.dst,),
            )
            self.solver.attach(args["instance"], each)

    def _bind_class(self, owner, method, dst):
        self.bind(method, owner, dst)

    def _bind_type(self, instance, method, dst):
        if isinstance(instance, Instance):
            self.bind(method, instance, dst)
            return
        each = Each(
            self._bind_class, method, dst, kinds=(Class, External), results=(dst,)
        )
        self.solver.attach(instance.metaclass, each)

    def _positional_call(self, call, least, most):
        if call.keywords or call.double_star:
            return False
        if call.star:
            return len(call.args) <= most
        return least <= len(call.args) <= most

    def _supplies(self, call, index):
        return index < len(call.args) or bool(call.star)

    def _result(self, call, obj):
        if call.dst is not None:
            self.add_object(call.dst, obj)

    def _result_node(self, call):
        return call.dst if call.dst is not None else self.node()

    def _rule_collection(self, call, receiver, args, kind):
        exact = receiver is None
        new = self.container_at(kind, call.origin, call.site, "collection", exact=exact)
        if args.given("iterable"):
            iterable = args["iterable"]
            if hashes_keys(new):
                self.add_keys(new, iterable, args, call.caller, call.site)
            else:
                self.add_elements(new, iterable, call.caller, call.site)
            if kind in ("list", "tuple"):
                self.add_length_hint(iterable, call.caller, call.site)
        self._result(call, new)

    def add_length_hint(self, iterable, caller, site, plan=LENGTH_HINT):
        key = ("length hint", caller, site, iterable, plan)
        if key not in self._subscriptions:
            self._subscriptions.add(key)
            at = _ConstructSite(caller, site)
            hint = Each(self._call_protocol, plan, at, kinds=(Instance, Class))
            self.solver.attach(iterable, hint)
            sequences = Each(self._sequence_length, at, kinds=(Container,))
            self.solver.attach(iterable, sequences)

    def _sequence_length(self, iterator, at):
        plan = {"iterator": SEQUENCE_LENGTH, "reversed": REVERSED_LENGTH}.get(
            iterator.kind
        )
        if plan is not None:
            hint = Each(self._call_protocol, plan, at, kinds=(Instance, Class))
            self.solver.attach(self.iterator_source(iterator), hint)

    def add_iterator_length_hint(self, iterable, caller, site):
        key = ("iterator length hint", caller, site, iterable)
        if key not in self._subscriptions:
            self._subscriptions.add(key)
            iterators = self.node()
            call = self.site_call(caller, site, ("protocol", "__iter__"))
            iteration = self.iteration(self.node(), caller, site, role="length")
            each = Each(
                self._iterator_of,
                call,
                iteration,
                iterators,
                kinds=(Instance, Class, Container),
                results=(iterators,),
            )
            self.solver.attach(iterable, each)
            self.add_length_hint(iterators, caller, site)

    def _iterator_of(self, obj, call, iteration, iterators):
        if isinstance(obj, Container):
            self.add_object(iterators, obj)
            return
        self.call_dunder(obj, "__iter__", call, iterators)
        sequence = Each(
            self._sequence_type, obj, iteration, iterators, results=(iterators,)
        )
        self.solver.attach(self._types(obj), sequence)

    def _rule_dict(self, call, receiver, args, kind="dict"):
        exact = receiver is None
        new = self.container_at(kind, call.origin, call.site, "dict", exact=exact)
        self._rule_update(call, new, args)
        self._result(call, new)

    def _rule_defaultdict(self, call, receiver, args):
        kind = "collections.defaultdict"
        exact = receiver is None
        new = self.container_at(
            kind, call.origin, call.site, "defaultdict", exact=exact
        )
        self._rule_update(call, new, args)
        if args.given("default_factory"):
            self.add_edge(args["default_factory"], self.factory(new))
        self._result(call, new)

    def _rule_counter(self, call, receiver, args):
        kind = "collections.Counter"
        exact = receiver is None
        new = self.container_at(kind, call.origin, call.site, "counter", exact=exact)
        self._rule_count(call, new, args)
        self._result(call, new)

    def _rule_count(self, call, receiver, args):
        if args.given("iterable"):
            iterable, caller, site = args["iterable"], call.caller, call.site
            keeps = keeps_mapping_hashes
            self.add_keys(receiver, iterable, args, caller, site, keeps)
        self.add_edge(self.keys(args.varkeywords), self.keys(receiver))

    def _rule_add(self, call, receiver, args, parameter):
        self.add_edge(args[parameter], self.unknown(receiver))
        if hashes_keys(receiver):
            stored = self.elements(receiver)
            self.add_hash(args[parameter], call.caller, call.site, stored)

    def _rule_extend(self, call, receiver, args):
        if args.varargs is None:
            iterables = args["iterable"]
        else:
            iterables = self.every(args.varargs)
        if hashes_keys(receiver):
            self.add_keys(receiver, iterables, args, call.caller, call.site)
            return
        elements = self.iterated(iterables, args, call.caller, call.site)
        self.add_edge(elements, self.unknown(receiver))
        if receiver.kind == "list":
            self.add_length_hint(iterables, call.caller, call.site)

    def _rule_any_element(self, call, receiver, args):
        if call.dst is not None:
            self.add_edge(self.every(receiver), call.dst)

    def _rule_copy(self, call, receiver, args):
        kind, exact = receiver.kind, receiver.exact
        new = self.container_at(kind, call.origin, call.site, "copy", exact=exact)
        if receiver.kind in SEQUENCES:
            self.copy_range(receiver, new, (0, None))
        elif is_dict(receiver):
            self.copy_items(receiver, new)
            if receiver.factory is not None:
                self.add_edge(receiver.factory, self.factory(new))
        else:
            self.add_edge(self.every(receiver), self.unknown(new))
        self._result(call, new)

    def _rule_update(self, call, receiver, args):
        if args.given("mapping"):
            self.add_dict_items(receiver, args["mapping"], call.caller, call.site)
        self.copy_items(args.varkeywords, receiver)

    def _rule_setdefault(self, call, receiver, args):
        self._rule_lookup(call, receiver, args)
        self.write_keyed(receiver, args["key"], args["default"])
        self.read_keyed(receiver, args["key"], call.dst)

    def _rule_get(self, call, receiver, args):
        self._rule_lookup(call, receiver, args)
        self.read_keyed(receiver, args["key"], call.dst)
        if call.dst is not None:
            self.add_edge(args["default"], call.dst)

    def _rule_lookup(self, call, receiver, args):
        self.add_hash(args["key"], call.caller, call.site, self.keys(receiver))

    def _rule_view(self, call, receiver, args, kind):
        view = self.container_at(kind, call.origin, call.site, "view")
        if kind == "dict_keys":
            self.add_edge(self.keys(receiver), self.unknown(view))
        elif kind == "dict_values":
            self.add_edge(self.every(receiver), self.unknown(view))
        else:
            origin, site, exact = call.origin, call.site, receiver.exact
            pair = self.container_at("tuple", origin, site, "pair", 2, exact=exact)
            self.add_edge(self.keys(receiver), self.element(pair, 0))
            self.add_edge(self.every(receiver), self.element(pair, 1))
            self.add_object(self.unknown(view), pair)
        self._result(call, view)

    def _rule_convert(self, call, receiver, args, kind, parameter, spec=None):
        spec = args[spec] if spec else None
        self.add_conversion(args[parameter], kind, call.caller, call.site, spec)
        self._result(call, self.typed("builtins.str"))

    def _rule_pow(self, call, receiver, args):
        extra = (args["mod"],) if args.given("mod") else ()
        self.add_operator(
            args["base"],
            args["exp"],
            "__pow__",
            "__rpow__",
            False,
            self._result_node(call),
            call.caller,
            call.site,
            extra=extra,
        )

    def _rule_print(self, call, receiver, args):
        values = self.every(args.varargs)
        self.add_conversion(values, "str", call.caller, call.site)

    def _rule_getattr(self, call, receiver, args, builtin):
        if builtin == "getattr":
            dst = self._result_node(call)
            self.add_edge(args["default"], dst)
            obj = args["object"]
        else:
            dst = self.node()
            obj = args["obj"]
        self._named_access(obj, args["name"], dst, None, call)

    def _rule_setattr(self, call, receiver, args):
        self._named_access(args["obj"], args["name"], None, args["value"], call)

    def _rule_delattr(self, call, receiver, args):
        self._named_access(args["obj"], args["name"], None, None, call, True)

    def add_named_load(self, obj, name, dst, caller, site):
        call = self.site_call(caller, site, ("named load",))
        access = _DynamicAccess(name, obj, dst, None, call, False)
        self._dynamic_accesses.append(access)

    def _named_access(self, obj, name, dst, src, call, delete=False):
        literal = None
        if len(call.args) > 1 and call.args[1] is not None:
            literal = self._literal(call.args[1])
        if literal is not None:
            self._access(literal, obj, dst, src, call, delete)
        else:
            access = _DynamicAccess(name, obj, dst, src, call, delete)
            self._dynamic_accesses.append(access)
            if src is None and not delete:
                load = Each(self.load_by_pattern, access, kinds=(Pattern,))
                self.solver.attach(name, load)

    def _literal(self, node):
        objects = self.solver.objects(node)
        if len(objects) == 1:
            (obj,) = objects
            if isinstance(obj, Const) and isinstance(obj.value, str):
                if self._constants.get(obj) is node:
                    return obj.value
        return None

    def _access(self, attr, obj, dst, src, call, delete):
        if dst is not None:
            self.add_load(obj, attr, dst, call.caller, call.site)
        if src is not None:
            self.add_store(obj, attr, src, call.caller, call.site)
        if delete:
            self.add_delete(obj, attr, call.caller, call.site)

    def names_known(self, access):
        names = self.solver.objects(access.name)
        return (
            not access.dynamic
            and bool(names)
            and all(isinstance(n, Const) and isinstance(n.value, str) for n in names)
        )

    def complete_dynamic_accesses(self):
        added = False
        for access in self._dynamic_accesses:
            if access.dynamic:
                continue
            names = dict.fromkeys(
                name.value
                for name in self.solver.objects(access.name)
                if isinstance(name, Const) and isinstance(name.value, str)
            )
            counted = names
            if access.src is None and not access.delete:
                counted = [n for n in names if n not in self._namespace_names_read]
            if len(counted) > DYNAMIC_NAMES_MAX:
                access.dynamic = True
                continue
            for name in names:
                if name not in access.done:
                    access.done.add(name)
                    self._access(
                        name,
                        access.obj,
                        access.dst,
                        access.src,
                        access.call,
                        access.delete,
                    )
                    added = True
        return added

    def _rule_super(self, call, receiver, args):
        if call.dst is None:
            return
        cls, obj = args["type"], args["object_or_type"]
        explicit = call.site not in self.zero_argument_super
        each = Each(self._super_class, obj, call, explicit, results=(call.dst,))
        self.solver.attach(cls, each)

    def _super_class(self, cls, obj, call, explicit):
        if isinstance(cls, External) and explicit:
            each = Each(self._super_after_outside, cls, call.dst, results=(call.dst,))
            self.solver.attach(obj, each)
            return
        if not isinstance(cls, Class):
            return
        if explicit:
            self._super_with_arguments(cls, obj, call)
        else:
            each = Each(self._super_object, cls, call.dst, results=(call.dst,))
            self.solver.attach(obj, each)

    def _super_after_outside(self, obj, cls, dst):
        owner = obj.cls if isinstance(obj, Instance) else obj
        if isinstance(owner, Class) and any(cls in mro for mro in owner.mros):
            self.add_object(dst, self.super_object(cls, obj))

    def _super_object(self, obj, cls, dst):
        if isinstance(obj, (Instance, Class)):
            self.add_object(dst, self.super_object(cls, obj))

    def _super_with_arguments(self, cls, obj, call):
        key = (call, cls)
        if key in self._super_pairs:
            return
        self._super_pairs.add(key)
        self._super_accepted.setdefault(cls, set())
        dst = call.dst
        given = Each(
            self._super_given, cls, dst, kinds=(Instance, Class), results=(dst,)
        )
        self.solver.attach(obj, given)
        for node in (cls.instances, self.family(cls)):
            accepted = Each(self._super_accepted_by, cls, obj, dst, results=(dst,))
            self.solver.attach(node, accepted)

    def _super_given(self, obj, cls, dst):
        if obj in self._super_accepted[cls]:
            self.add_object(dst, self.super_object(cls, obj))

    def _super_accepted_by(self, obj, cls, given, dst):
        self._super_accepted[cls].add(obj)
        if obj in self.solver.objects(given):
            self.add_object(dst, self.super_object(cls, obj))

    def _rule_type(self, call, receiver, args):
        if call.dst is None:
            return
        self.add_object(call.dst, self.typed("builtins.type"))
        written = len(call.args) == 3 and not (
            call.keywords or call.star or call.double_star
        )
        if written:
            made = [args["object"], args["bases"], args["dict"]]
            each = Each(self._type_bases, call, made, kinds=(Container,))
            self.solver.attach(args["bases"], each)

    def _type_bases(self, bases, call, made):
        if bases.kind == "tuple" and bases.length == 1:
            each = Each(self._type_base, call, made, kinds=(Class,))
            self.solver.attach(self.element(bases, 0), each)

    def _call_type_metaclass(self, meta, call):
        self.call(meta, call)

    def _type_base(self, base, call, made):
        metaclass = self.site_call(call.caller, call.site, ("type", "metaclass"), made)
        each = Each(self._call_type_metaclass, metaclass, kinds=(Class,))
        self.solver.attach(base.metaclass, each)

    def _rule_iter(self, call, receiver, args):
        dst = self._result_node(call)
        if not args.surely("sentinel"):
            self.add_iter(args["object"], dst, call.caller, call.site)
        if args.given("sentinel"):
            kind = "callable_iterator"
            iterator = self.container_at(kind, call.origin, call.site, "iter")
            self.add_edge(args["object"], self.iterator_source(iterator))
            self.add_object(dst, iterator)

    def _rule_enumerate(self, call, receiver, args):
        result = self.container_at("enumerate", call.origin, call.site, "enumerate")
        origin, site = call.origin, call.site
        pair = self.container_at("tuple", origin, site, "enumerate", 2, exact=True)
        construct = ("enumerate", call)
        elements = self.iterated(args["iterable"], construct, call.caller, call.site)
        self.add_edge(elements, self.element(pair, 1))
        self.add_object(self.unknown(result), pair)
        self._result(call, result)

    def _rule_zip(self, call, receiver, args):
        result = self.container_at("zip", call.origin, call.site, "zip")
        length = None if call.star else len(call.args)
        rule = ("zip", length)
        origin, site = call.origin, call.site
        items = self.container_at("tuple", origin, site, rule, length, exact=True)
        if call.star:
            construct = ("zip", call)
            iterables = self.every(args.varargs)
            elements = self.iterated(iterables, construct, call.caller, call.site)
            self.add_edge(elements, self.unknown(items))
        else:
            for index, node in enumerate(call.args):
                if node is not None:
                    construct = ("zip", call, index)
                    elements = self.iterated(node, construct, call.caller, call.site)
                    self.add_edge(elements, self.element(items, index))
        self.add_object(self.unknown(result), items)
        self._result(call, result)

    def _rule_reversed(self, call, receiver, args):
        dst = self._result_node(call)
        result = self.container_at("reversed", call.origin, call.site, "reversed")
        iteration = self.iteration(self.unknown(result), call.caller, call.site)
        reversing = Each(self._reversed, call, dst, result, iteration, results=(dst,))
        self.solver.attach(args["sequence"], reversing)

    def _reversed(self, obj, call, dst, result, iteration):
        if isinstance(obj, (Instance, Class)):
            reverse = self.site_call(call.caller, call.site, ("reversed",))
            self.call_dunder(obj, "__reversed__", reverse, dst)
            items = self.unknown(result)
            sequence = Each(
                self._reversed_sequence, obj, call, result, results=(items,)
            )
            self.solver.attach(self._types(obj), sequence)
        else:
            iteration.apply(obj)
        self.add_object(dst, result)

    def _reversed_sequence(self, cls, obj, call, result):
        if not isinstance(cls, Class):
            return
        unless = ("__reversed__",)
        lengths = self.lookup(cls, "__len__", obj, None, unless)
        getters = self.lookup(cls, "__getitem__", obj, None, unless)
        length = self.site_call(call.caller, call.site, ("reversed", "len"))
        index = self.site_call(call.caller, call.site, ("reversed", "item"), [None])
        length = self._implicit_call(obj, "__len__", length, None, unless)
        items = self.unknown(result)
        index = self._implicit_call(obj, "__getitem__", index, items, unless)
        source = self.iterator_source(result)
        for other, methods, implicit, reversing in (
            (getters, lengths, length, source),
            (lengths, getters, index, None),
        ):
            each = Each(
                self._reverse_sequence,
                obj,
                methods,
                implicit,
                reversing,
                results=(implicit.dst,),
            )
            self.solver.attach(other, each)

    def _reverse_sequence(self, method, obj, methods, implicit, reversing):
        key = ("reverse sequence", obj, methods, implicit)
        if key not in self._subscriptions:
            self._subscriptions.add(key)
            self.solver.attach(methods, implicit)
            if reversing is not None:
                self.add_object(reversing, obj)

    def _rule_map(self, call, receiver, args):
        result = self.container_at("map", call.origin, call.site, "map")
        base = self._prefixes.get(call, (call, ()))[0]
        elements, surplus = [], []
        for index, node in enumerate(call.args[1:]):
            construct = ("map", call, index)
            if node is not None:
                node = self.iterated(node, construct, call.caller, call.site)
            (elements if index + 1 < len(base.args) else surplus).append(node)
        rest = None
        if call.star or surplus:
            rest = self.node()
            for node in surplus:
                if node is not None:
                    self.add_edge(node, rest)
        if call.star:
            iterables = [self.every(args.varargs)]
            if len(call.args) < 2:
                iterables.append(args["iterable"])
            for part, node in enumerate(iterables):
                construct = ("map", call, "*", part)
                found = self.iterated(node, construct, call.caller, call.site)
                self.add_edge(found, rest)
        role = ("map", len(elements), rest is not None)
        back = self.site_call(
            call.caller, call.site, role, elements, dst=self.unknown(result), rest=rest
        )
        self.add_edge(args["function"], self._callee(back))
        self._result(call, result)

    def _rule_filter(self, call, receiver, args):
        result = self.container_at("filter", call.origin, call.site, "filter")
        construct = ("filter", call)
        elements = self.iterated(args["iterable"], construct, call.caller, call.site)
        self.add_edge(elements, self.unknown(result))
        verdict = self.node()
        back = self.site_call(
            call.caller, call.site, ("filter",), [elements], dst=verdict
        )
        self.add_edge(args["function"], self._callee(back))
        self.add_truth(verdict, call.caller, call.site)
        self._result(call, result)

    def _rule_next(self, call, receiver, args):
        dst = self._result_node(call)
        self.add_next(args["iterator"], dst, call.caller, call.site)
        self.add_edge(args["default"], dst)

    def _rule_advance(self, call, receiver, args):
        if isinstance(receiver, Generator) and "value" in args:
            self.add_edge(args["value"], receiver.function.sent_node)
        iteration = self.iteration(
            self._result_node(call), call.caller, call.site, role="advance"
        )
        self.next_element(receiver, iteration)


def _may_init_property(call):
    names = WRAPPED_ATTRIBUTES_BY_TYPE["property"] + ("doc",)
    given = len(call.args)
    if given > len(names) + 1 or (given == 0 and not call.star):
        return False
    taken = set(names[: max(given - 1, 0)])
    for name, _ in call.keywords:
        if name not in names or name in taken:
            return False
        taken.add(name)
    return True


_ACCESS_KIND_BY_ACCESSOR = {"fget": "Load", "fset": "Store", "fdel": "Delete"}


def _builtin_name(external):
    module, _, name = external.name.partition(".")
    if module == BUILTIN_MODULE and external.steps <= 1:
        return name
    return None


class _ConstructSite(NamedTuple):
    caller: str
    site: str


class _DynamicAccess:
    __slots__ = (
        "name",
        "obj",
        "dst",
        "src",
        "call",
        "delete",
        "done",
        "dynamic",
        "loaded",
        "loaders",
    )

    def __init__(self, name, obj, dst, src, call, delete):
        self.name = name
        self.obj = obj
        self.dst = dst
        self.src = src
        self.call = call
        self.delete = delete
        self.done = set()
        self.dynamic = False
        self.loaded = set()
        self.loaders = {}


class _Bound:
    __slots__ = ("parameters", "varargs", "varkeywords", "_supplied", "_possible")

    def __init__(self, function, supplied, possible):
        self.parameters = function.parameters
        self.varargs = function.varargs
        self.varkeywords = function.varkeywords
        self._supplied = supplied
        self._possible = possible

    def __getitem__(self, name):
        return self.parameters[name]

    def __contains__(self, name):
        return name in self.parameters

    def given(self, name):
        return name in self._possible

    def surely(self, name):
        return name in self._supplied


class _LateBound:
    __slots__ = ("call", "signature", "constants", "since", "_nodes", "_supplied")

    varargs = varkeywords = None

    def __init__(self, call, signature, constants, since, supplied):
        self.call = call
        self.signature = signature
        self.constants = constants
        self.since = since
        self._nodes = None
        self._supplied = supplied

    def __getitem__(self, name):
        if self._nodes is None:
            self._nodes = {}
        node = self._nodes.get(name)
        if node is None:
            node = self._nodes[name] = self.call.analysis.late_parameter(self, name)
        return node

    def __contains__(self, name):
        return name in self.signature.names()

    def given(self, name):
        return name in self._supplied

    surely = given


@cache
def _signature(text):
    arguments = ast.parse(f"def f{text}: pass").body[0].args
    positional = [arg.arg for arg in arguments.posonlyargs + arguments.args]
    keyword_only = [arg.arg for arg in arguments.kwonlyargs]
    signature = Signature(
        positional=positional,
        positional_only_count=len(arguments.posonlyargs),
        keyword_only=keyword_only,
        vararg=arguments.vararg.arg if arguments.vararg else None,
        kwarg=arguments.kwarg.arg if arguments.kwarg else None,
    )
    with_defaults = positional[len(positional) - len(arguments.defaults) :]
    pairs = list(zip(with_defaults, arguments.defaults))
    pairs += zip(keyword_only, arguments.kw_defaults)
    constants = {}
    for name, default in pairs:
        value = getattr(default, "value", None)
        if isinstance(value, (str, int)) and not isinstance(value, bool):
            constants[name] = value
    return signature, constants
