"""The rules of the modelled builtins listed in builtin_models.py.

`BuiltinRules` is part of `Analysis` (see semantics.py). A rule named `name`
in the table is the method `_rule_name`. It receives the call, the object
that the method was loaded from (None for a builtin function), the
arguments bound to the signature of the entry (`_Bound`) and the parameters
of the rule, and it decides the result of the call.
"""

import ast
from functools import cache
from typing import NamedTuple

from .builtin_models import (
    FUNCTIONS,
    LENGTH_HINT,
    MAX_DYNAMIC_NAMES,
    RETURNS_ARGUMENT,
    REVERSED_LENGTH,
    SEQUENCE_LENGTH,
    WRAPPED,
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
        """The rule of the modelled builtin function `external`, or None."""
        name = _builtin_name(external)
        return FUNCTIONS.get(name) if name else None

    def returns_argument(self, callee, call):
        """Apply the model of `callee`, an analysed function or an external,
        if it returns one of its arguments (see `RETURNS_ARGUMENT`): emit the
        edge and give the result. The model replaces the body of an analysed
        function, but not its edge (see `model_edge`). Return whether
        `callee` has such a model."""
        entry = RETURNS_ARGUMENT.get(callee.name)
        if entry is None:
            return False
        analysed = isinstance(callee, Function)
        self.model_edge(callee.name, analysed, call)
        self.return_argument(entry, callee.name, analysed, call)
        return True

    def model_edge(self, name, analysed, call):
        """The edge to the modelled callable `name`. An analysed function is
        never outside code: its edge stays for an implicit call, and it is
        no external callee."""
        if analysed:
            self._add_call_edge(call, name)
        else:
            self.add_external_call_edge(name, call, "stub")

    def return_argument(self, entry, name, analysed, call):
        """The result of a call that returns the argument named in `entry`
        (see `RETURNS_ARGUMENT` and `DECORATOR`): that argument where the
        call may supply it, and a decorator where it may omit it."""
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
        """Bind the arguments of `call` to the signature of `entry`, once per
        call and entry, like the arguments of a call of a function."""
        key = (call, entry)
        if key not in self._model_bindings:
            signature, constants = _signature(entry[0])
            self._model_bindings[key] = self.bind_signature(call, signature, constants)
        return self._model_bindings[key]

    def bind_signature(self, call, signature, constants):
        """The arguments of `call` bound to `signature`, like the arguments
        of a call of a function; `constants` maps the parameters that have
        a constant default to its value.

        Most bindings are of plain calls to plain signatures, and no rule
        reads most of their parameters (sphinx: 1.2 million bindings, 12 %
        of the parameters read). Such a binding makes the node of a
        parameter when a rule reads it (`_Late`). With `*` or `**` in the
        call or in the signature, or an argument passed twice, the binding
        is made at once: it has effects of its own (it unpacks and
        iterates), or a parameter with two sources."""
        # The constants exist from now on in both cases: the solver numbers
        # the objects in the order in which their nodes are made.
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
            supplied = self._name_set(positional + keywords)
            return _Late(call, signature, constants, self.solver.phase, supplied)
        parameters = {name: self.node() for name in signature.names()}
        function = Function(None, None, signature, parameters, defaults, None)
        # The rules read `*args` and `**kwargs` from the containers.
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
        return _Bound(function, self._name_set(supplied), self._name_set(possible))

    def _name_set(self, names):
        """The one copy of the set of parameter names `names`: the calls of
        a signature supply few different sets, and most calls may supply
        exactly what they surely supply."""
        names = frozenset(names)
        return self._name_sets.setdefault(names, names)

    def late_parameter(self, bound, name):
        """The node of the parameter `name` of the binding `bound`, made
        now, in the state that it would have if the binding had made it
        (`Solver.follower`): it holds what its one source gives it, the
        argument at its position or of its name, else its default."""
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
        """dst ⊇ obj.attr for an object of the builtin type `type_name`: what
        it wraps, a modelled method, or else what the stubs say (see
        `Outside.builtin_member`)."""
        if attr in WRAPPED.get(type_name, ()):
            self.add_edge(self.field(obj, attr), dst)
        elif method_model(type_name, attr) is not None:
            self.add_object(dst, self.builtin_method(obj, type_name, attr))
        else:
            self.builtin_member(obj, type_name, attr, dst)

    # Descriptors

    def _rule_wrap(self, call, receiver, args, kind):
        """staticmethod(f), classmethod(f)"""
        wrapper = self.wrapper(kind, call)
        self.add_edge(args["function"], self.field(wrapper, "__func__"))
        self._result(call, wrapper)

    def add_implicit_method(self, value, field, kind, site):
        """The class attribute `field`, of the class statement at `site`,
        gets `value`, in which a function is made a `kind` method (see
        `IMPLICIT_METHODS` in the builder), as `type.__new__` does; anything
        else stays as it is."""
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
        """property(fget, fset, fdel, doc)"""
        prop = self.wrapper("property", call)
        self._store_accessors(prop, args)
        self._result(call, prop)

    def _store_accessors(self, prop, args):
        for name in WRAPPED["property"]:
            if args.given(name):
                self.add_edge(args[name], self.field(prop, name))

    def _properties(self, call, args, rule, *parameters):
        """Apply `rule(prop, *parameters)` to each property that `self`
        holds: the engine's own, or an instance whose class may derive from
        the builtin `property` (once it may: its bases may come late). The
        rule may give the result of `call`."""
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
        """property.__init__(self, /, fget, fset, fdel, doc), resolved for
        an instance of a subclass of `property` (or called with one), in a
        call that may be valid: `self` keeps the accessors. It calls none of
        them."""
        if _may_init_property(call):
            self._properties(call, args, self._store_accessors, args)

    def _rule_property_with(self, call, receiver, args, accessor):
        """prop.getter(f), prop.setter(f), prop.deleter(f): `prop` itself,
        with `f` as that accessor too. Python returns a copy (for a
        subclass, a call of its class); flow-insensitively, the copy and
        `prop` hold the same accessors."""
        self._properties(call, args, self._property_with, args, accessor, call)

    def _property_with(self, prop, args, accessor, call):
        self.add_edge(args["function"], self.field(prop, accessor))
        self._result(call, prop)

    def _rule_property_run(self, call, receiver, args, accessor):
        """prop.__get__(instance, owner), prop.__set__(instance, value),
        prop.__delete__(instance), for a valid call: call the accessor that
        `prop` holds with the instance (and the value). `__get__` gives
        what the getter returns, or `prop` itself for the literal None as
        the instance with an owner that is not; `__set__` and `__delete__`
        give None."""
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
        kind = _ACCESS_KINDS[accessor]
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
        """sm.__get__(instance, owner) and cm.__get__(instance, owner) of a
        static method and a class method, for a valid call (the literal None
        for both, or for the instance without an owner, raises): the
        function that a static method wraps; a class method's function
        bound to each owner that the call may pass, and, where it may pass
        none or the literal None, to the type of the instance (see
        `Hierarchy.bind`)."""
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
        """Bind the class method `method` to the type of `instance`: its
        class, or the metaclasses of a class."""
        if isinstance(instance, Instance):
            self.bind(method, instance, dst)
            return
        each = Each(
            self._bind_class, method, dst, kinds=(Class, External), results=(dst,)
        )
        self.solver.attach(instance.metaclass, each)

    def _positional_call(self, call, least, most):
        """Whether `call` may pass between `least` and `most` arguments by
        position and none by keyword, as a method whose parameters are
        positional-only takes them. A call with `**` is not, even `**{}`: a
        restriction of the analysis."""
        if call.keywords or call.double_star:
            return False
        if call.star:
            return len(call.args) <= most
        return least <= len(call.args) <= most

    def _supplies(self, call, index):
        """Whether `call` may pass an argument at the position `index`."""
        return index < len(call.args) or bool(call.star)

    # Containers

    def _result(self, call, obj):
        if call.dst is not None:
            self.add_object(call.dst, obj)

    def _result_node(self, call):
        """The node of the result of `call`, even if the call's value is not
        used: the rule may make implicit calls that need it."""
        return call.dst if call.dst is not None else self.node()

    def _rule_collection(self, call, receiver, args, kind):
        """list(x), tuple(x), set(x), frozenset(x): a new container with the
        elements of x, exactly of its class unless the class called may be
        another (`receiver`, see `Outside.call_outside`), which a set hashes
        (see `add_keys`); list(x) asks the length of x."""
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
        """The construct at `site`, in the scope `caller`, asks the length
        of what the node `iterable` holds before it iterates it: `__len__`,
        else `__length_hint__` (`LENGTH_HINT`), implicit calls from that
        scope. Once per construct, node and plan.

        The node is an argument (`list(x)`, `sorted`, `f(*x)`, a display,
        `bytes`, `extend`, `+=`; see `LENGTH_HINTS`) or the iterators that
        `iter()` of one gives (`add_iterator_length_hint`, a starred
        target). What it may hold, and what Python asks:

        - an instance of an analysed class: `plan`, by its class;
        - an analysed class: `plan`, by its metaclass;
        - the sequence protocol's iterator (`Container` "iterator"): the
          `__len__` of each sequence it iterates, instance or class
          (`SEQUENCE_LENGTH`);
        - a `reversed` object (`Container` "reversed"): the `__len__` of
          its sequence, instance or class (`REVERSED_LENGTH`);
        - any other engine container (lists, tuples, sets, dicts, views,
          their iterators, `enumerate`, `zip`, `map`, `filter`,
          `callable_iterator`), a generator, a coroutine, a constant, an
          outside value, a function, the saturated value: nothing that the
          program defines (a builtin length, or none)."""
        key = ("length hint", caller, site, iterable, plan)
        if key not in self._subscriptions:
            self._subscriptions.add(key)
            at = _At(caller, site)
            hint = Each(self._call_protocol, plan, at, kinds=(Instance, Class))
            self.solver.attach(iterable, hint)
            # The iterators of the sequence protocol and `reversed` objects
            # ask their sequences.
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
        """The construct at `site` asks the length of the iterator that
        `iter()` gives for what `iterable` holds (`str.join`): the result of
        the `__iter__` that its protocol calls there, which is the object
        itself where `__iter__` returns it."""
        key = ("iterator length hint", caller, site, iterable)
        if key not in self._subscriptions:
            self._subscriptions.add(key)
            iterators = self.node()
            call = self.site_call(caller, site, ("protocol", "__iter__"))
            # For the sequence protocol's iterator (see `_sequence_type`).
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
        """`iter(obj)` for the length hint of `str.join`: what the
        `__iter__` that its protocol calls returns (a class's metaclass's),
        or the sequence protocol's iterator where its type has `__getitem__`
        only. An engine container goes on as it is: an iterator is its own,
        and the others have no analysed length (see `add_length_hint`)."""
        if isinstance(obj, Container):
            self.add_object(iterators, obj)
            return
        self.call_dunder(obj, "__iter__", call, iterators)
        sequence = Each(
            self._sequence_type, obj, iteration, iterators, results=(iterators,)
        )
        self.solver.attach(self._types(obj), sequence)

    def _rule_dict(self, call, receiver, args, kind="dict"):
        """dict(mapping_or_pairs, **keywords), and the dict of `collections`
        of `kind` (`collections.OrderedDict`); exact as for `collection`."""
        exact = receiver is None
        new = self.container_at(kind, call.origin, call.site, "dict", exact=exact)
        self._rule_update(call, new, args)
        self._result(call, new)

    def _rule_defaultdict(self, call, receiver, args):
        """collections.defaultdict(default_factory, mapping_or_pairs,
        **keywords): a dict that keeps its factory, which a read of a
        missing key calls (see `Containers.call_factory`)."""
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
        """collections.Counter(iterable, **keywords): a dict whose keys are
        what it counts (see `_rule_count`)."""
        kind = "collections.Counter"
        exact = receiver is None
        new = self.container_at(kind, call.origin, call.site, "counter", exact=exact)
        self._rule_count(call, new, args)
        self._result(call, new)

    def _rule_count(self, call, receiver, args):
        """Counter.update(iterable, **keywords): the elements of the
        iterable (the keys of a mapping, which iteration gives) and the
        keywords are keys of the counter; its values are counts, which are
        not tracked."""
        if args.given("iterable"):
            iterable, caller, site = args["iterable"], call.caller, call.site
            keeps = keeps_mapping_hashes
            self.add_keys(receiver, iterable, args, caller, site, keeps)
        self.add_edge(self.keys(args.varkeywords), self.keys(receiver))

    def _rule_add(self, call, receiver, args, parameter):
        """list.append(x), list.insert(i, x), set.add(x): x is the
        argument of `parameter`, which a set hashes."""
        self.add_edge(args[parameter], self.unknown(receiver))
        if hashes_keys(receiver):
            stored = self.elements(receiver)
            self.add_hash(args[parameter], call.caller, call.site, stored)

    def _rule_extend(self, call, receiver, args):
        """list.extend(xs), set.update(*xss): list.extend asks the length
        of xs, and set.update hashes the elements."""
        if args.varargs is None:
            iterables = args["iterable"]
        else:
            iterables = self.every(args.varargs)
        # The same nodes for every receiver that the call binds to this
        # model (list.extend or set.update): iterated once.
        if hashes_keys(receiver):
            # set.update hashes the elements.
            self.add_keys(receiver, iterables, args, call.caller, call.site)
            return
        elements = self.iterated(iterables, args, call.caller, call.site)
        self.add_edge(elements, self.unknown(receiver))
        if receiver.kind == "list":
            self.add_length_hint(iterables, call.caller, call.site)

    def _rule_any_element(self, call, receiver, args):
        """list.pop(i), set.pop()"""
        if call.dst is not None:
            self.add_edge(self.every(receiver), call.dst)

    def _rule_copy(self, call, receiver, args):
        """list.copy(), dict.copy(), set.copy(): a new container of the
        class of the receiver, exactly so if the receiver's class is
        exactly known (a subclass of dict may copy itself to its own
        class)."""
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
        """dict.update(mapping_or_pairs, **keywords): the keywords are the
        items of the **kwargs dict of the signature."""
        if args.given("mapping"):
            self.add_dict_items(receiver, args["mapping"], call.caller, call.site)
        self.copy_items(args.varkeywords, receiver)

    def _rule_setdefault(self, call, receiver, args):
        """dict.setdefault(key, default): looks the key up, and stores it,
        with the default if there is one."""
        self._rule_lookup(call, receiver, args)
        self.write_keyed(receiver, args["key"], args["default"])
        self.read_keyed(receiver, args["key"], call.dst)

    def _rule_get(self, call, receiver, args):
        """dict.get(key, default), dict.pop(key, default): a lookup."""
        self._rule_lookup(call, receiver, args)
        self.read_keyed(receiver, args["key"], call.dst)
        if call.dst is not None:
            self.add_edge(args["default"], call.dst)

    def _rule_lookup(self, call, receiver, args):
        """A lookup of the key in the dict `receiver`, as a subscript read
        makes it (`OrderedDict.move_to_end(key)`): it hashes the key and
        compares it with the stored keys."""
        self.add_hash(args["key"], call.caller, call.site, self.keys(receiver))

    def _rule_view(self, call, receiver, args, kind):
        """dict.keys(), dict.values(), dict.items(): a container whose
        elements are the keys, the values, or (key, value) pairs."""
        view = self.container_at(kind, call.origin, call.site, "view")
        if kind == "dict_keys":
            self.add_edge(self.keys(receiver), self.unknown(view))
        elif kind == "dict_values":
            self.add_edge(self.every(receiver), self.unknown(view))
        else:
            # A subclass of dict may override `items`.
            origin, site, exact = call.origin, call.site, receiver.exact
            pair = self.container_at("tuple", origin, site, "pair", 2, exact=exact)
            self.add_edge(self.keys(receiver), self.element(pair, 0))
            self.add_edge(self.every(receiver), self.element(pair, 1))
            self.add_object(self.unknown(view), pair)
        self._result(call, view)

    # Special methods

    def _rule_convert(self, call, receiver, args, kind, parameter, spec=None):
        """str(x), repr(x), format(x, spec)"""
        spec = args[spec] if spec else None
        self.add_conversion(args[parameter], kind, call.caller, call.site, spec)
        self._result(call, self.typed("builtins.str"))

    def _rule_print(self, call, receiver, args):
        """print(*values): converts each value to str."""
        values = self.every(args.varargs)
        self.add_conversion(values, "str", call.caller, call.site)

    # Attributes by name

    def _rule_getattr(self, call, receiver, args, builtin):
        """getattr(obj, name, default), hasattr(obj, name): a load, whose
        result hasattr discards."""
        if builtin == "getattr":
            dst = self._result_node(call)
            self.add_edge(args["default"], dst)
            obj = args["object"]
        else:
            dst = self.node()
            obj = args["obj"]
        self._named_access(obj, args["name"], dst, None, call)

    def _rule_setattr(self, call, receiver, args):
        """setattr(obj, name, value): a store."""
        self._named_access(args["obj"], args["name"], None, args["value"], call)

    def _rule_delattr(self, call, receiver, args):
        """delattr(obj, name): a deletion."""
        self._named_access(args["obj"], args["name"], None, None, call, True)

    def add_named_load(self, obj, name, dst, caller, site):
        """dst ⊇ the attribute of `obj` that the node `name` names, loaded
        as `getattr` loads it (see `MAX_DYNAMIC_NAMES`), without a call:
        the attribute that a positional class pattern of `match` reads."""
        call = self.site_call(caller, site, ("named load",))
        access = _DynamicAccess(name, obj, dst, None, call, False)
        self._dynamic_accesses.append(access)

    def _named_access(self, obj, name, dst, src, call, delete=False):
        """A load into `dst` or a store from `src` of the attribute that the
        node `name` names (see `MAX_DYNAMIC_NAMES`). A str literal written as
        the second argument is a load or store at once."""
        literal = None
        if len(call.args) > 1 and call.args[1] is not None:
            literal = self._literal(call.args[1])
        if literal is not None:
            self._access(literal, obj, dst, src, call, delete)
        else:
            access = _DynamicAccess(name, obj, dst, src, call, delete)
            self._dynamic_accesses.append(access)
            if src is None and not delete:
                # A load by pattern (patterns.py); a store or a deletion by
                # pattern goes to no known name.
                load = Each(self.load_by_pattern, access, kinds=(Pattern,))
                self.solver.attach(name, load)

    def _literal(self, node):
        """The str that `node` holds if it is the node of a str literal."""
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
        """Whether every name that the dynamic `access` may use is known
        after the solve: its name holds str constants and nothing else, no
        more than `MAX_DYNAMIC_NAMES` of them."""
        names = self.solver.objects(access.name)
        return (
            not access.dynamic
            and bool(names)
            and all(isinstance(n, Const) and isinstance(n.value, str) for n in names)
        )

    def complete_dynamic_accesses(self):
        """At a fixpoint, extend each access by the names it holds now: a
        load or store of each str constant that the name holds, whatever
        else it holds, while it holds at most `MAX_DYNAMIC_NAMES` str
        constants. Once it holds more, the access is dynamic and gets no
        more names. Names that a later round supplies are added then. Return
        whether anything was added."""
        added = False
        for access in self._dynamic_accesses:
            if access.dynamic:
                continue
            # What else the name holds names nothing: a str of unknown value,
            # an outside value; a pattern is loaded by itself (patterns.py).
            # By value: a constant and its alias (`Containers.inexact`)
            # are one name.
            names = dict.fromkeys(
                name.value
                for name in self.solver.objects(access.name)
                if isinstance(name, Const) and isinstance(name.value, str)
            )
            if len(names) > MAX_DYNAMIC_NAMES:
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

    # super

    def _rule_super(self, call, receiver, args):
        """super(cls, receiver). The builder passes the class and the first
        parameter for `super()` without arguments, which pairs the class
        with each of them. With arguments, Python accepts only a receiver
        that is an instance of the class or of a subclass, or the class or
        a subclass (see `_super_with_arguments`)."""
        if call.dst is None:
            return
        cls, obj = args["type"], args["object_or_type"]
        explicit = call.site not in self.zero_argument_super
        each = Each(self._super_class, obj, call, explicit, results=(call.dst,))
        self.solver.attach(cls, each)

    def _super_class(self, cls, obj, call, explicit):
        if not isinstance(cls, Class):
            return
        if explicit:
            self._super_with_arguments(cls, obj, call)
        else:
            each = Each(self._super_object, cls, call.dst, results=(call.dst,))
            self.solver.attach(obj, each)

    def _super_object(self, obj, cls, dst):
        if isinstance(obj, (Instance, Class)):
            self.add_object(dst, self.super_object(cls, obj))

    def _super_with_arguments(self, cls, obj, call):
        """`super(cls, x)` for each object of `obj` that is also among the
        instances of `cls` and of its subclasses (a class whose metaclass
        derives from `cls` among them) or the classes of its family: the
        receivers that Python accepts; for any other, it raises TypeError.
        Both sides only grow, in any order. The receivers that `cls`
        accepts are kept once per class, for all its sites."""
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

    # type

    def _rule_type(self, call, receiver, args):
        """type(object) and type(name, bases, dict) give a typed `type`, as
        the stubs say; the class of an object is not followed (see the
        design, "Open problems"). A call with exactly three positional
        arguments, without keywords or unpacking, calls the metaclass of
        its one written base, as `type.__new__` does."""
        if call.dst is None:
            return
        self.add_object(call.dst, self.typed("builtins.type"))
        written = len(call.args) == 3 and not (
            call.keywords or call.star or call.double_star
        )
        if written:
            # What `type.__new__` calls for the class that it makes.
            made = [args["object"], args["bases"], args["dict"]]
            each = Each(self._type_bases, call, made, kinds=(Container,))
            self.solver.attach(args["bases"], each)

    def _type_bases(self, bases, call, made):
        """The bases of `type(name, bases, dict)`, where they are a tuple of
        one element: that base's metaclass is the winner. With several
        bases, the winning metaclass depends on the class that the call
        makes, which the analysis does not make: no call."""
        if bases.kind == "tuple" and bases.length == 1:
            each = Each(self._type_base, call, made, kinds=(Class,))
            self.solver.attach(self.element(bases, 0), each)

    def _call_type_metaclass(self, meta, call):
        self.call(meta, call)

    def _type_base(self, base, call, made):
        """Call each analysed metaclass of `base` (the winner, for each
        hierarchy of `base`) with the arguments of `type(name, bases,
        dict)`: its `__new__` and `__init__`, implicitly from the caller.
        The new class's `__init_subclass__` is not called: the analysis
        does not make that class."""
        metaclass = self.site_call(call.caller, call.site, ("type", "metaclass"), made)
        each = Each(self._call_type_metaclass, metaclass, kinds=(Class,))
        self.solver.attach(base.metaclass, each)

    # Iteration

    def _rule_iter(self, call, receiver, args):
        """iter(iterable), and iter(callable, sentinel): an iterator whose
        next() calls the callable (see `next_element`)."""
        dst = self._result_node(call)
        if not args.surely("sentinel"):
            self.add_iter(args["object"], dst, call.caller, call.site)
        if args.given("sentinel"):
            kind = "callable_iterator"
            iterator = self.container_at(kind, call.origin, call.site, "iter")
            self.add_edge(args["object"], self.iterator_source(iterator))
            self.add_object(dst, iterator)

    def _rule_enumerate(self, call, receiver, args):
        """enumerate(iterable): an iterator of (index, element) pairs."""
        result = self.container_at("enumerate", call.origin, call.site, "enumerate")
        origin, site = call.origin, call.site
        pair = self.container_at("tuple", origin, site, "enumerate", 2, exact=True)
        construct = ("enumerate", call)
        elements = self.iterated(args["iterable"], construct, call.caller, call.site)
        self.add_edge(elements, self.element(pair, 1))
        self.add_object(self.unknown(result), pair)
        self._result(call, result)

    def _rule_zip(self, call, receiver, args):
        """zip(*iterables): an iterator of tuples whose i-th element is an
        element of the i-th iterable."""
        result = self.container_at("zip", call.origin, call.site, "zip")
        length = None if call.star else len(call.args)
        # A call that adds receivers keeps the origin and passes more
        # iterables: the length is part of the key.
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
        """reversed(sequence): what `__reversed__` of an instance returns;
        else an iterator over the elements, which for an instance are what
        `__getitem__` returns (after `__len__`), where no class defines
        `__reversed__`."""
        dst = self._result_node(call)
        result = self.container_at("reversed", call.origin, call.site, "reversed")
        iteration = self.iteration(self.unknown(result), call.caller, call.site)
        reversing = Each(self._reversed, call, dst, result, iteration, results=(dst,))
        self.solver.attach(args["sequence"], reversing)

    def _reversed(self, obj, call, dst, result, iteration):
        # A class's special methods are its metaclass's (see `call_dunder`).
        if isinstance(obj, (Instance, Class)):
            reverse = self.site_call(call.caller, call.site, ("reversed",))
            self.call_dunder(obj, "__reversed__", reverse, dst)
            unless = ("__reversed__",)
            length = self.site_call(call.caller, call.site, ("reversed", "len"))
            self.call_dunder(obj, "__len__", length, None, unless)
            index = self.site_call(call.caller, call.site, ("reversed", "item"), [None])
            self.call_dunder(obj, "__getitem__", index, self.unknown(result), unless)
            # Its length hint asks the sequence again (`REVERSED_LENGTH`).
            self.add_object(self.iterator_source(result), obj)
        else:
            iteration.apply(obj)
        self.add_object(dst, result)

    def _rule_map(self, call, receiver, args):
        """map(function, *iterables): calls the function with an element of
        each iterable at its position, from the scope of the call (a class
        is instantiated), and gives an iterator over what it returns. After
        an unpacked argument the positions are not known: the elements of
        the iterables bound to `*iterables`, and to `iterable` if it is not
        explicit, go to any position after the explicit ones. So do those of
        the positional arguments past the number that the call has without
        the receivers that bound methods add: the call back is a new root,
        and its arity must not grow with receivers (see *Termination*)."""
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
        # One call of a site may pass more arguments than another (a call
        # with `*args` and its copies): the arity is part of the role.
        role = ("map", len(elements), rest is not None)
        back = self.site_call(
            call.caller, call.site, role, elements, dst=self.unknown(result), rest=rest
        )
        # Through the one callee node of the back call, which may itself
        # reach this rule (`map(map, ...)`): each application adds an edge,
        # not a constraint that applies the rule again.
        self.add_edge(args["function"], self._callee(back))
        self._result(call, result)

    def _rule_filter(self, call, receiver, args):
        """filter(function, iterable): calls the function with each element,
        from the scope of the call (a class is instantiated), tests the
        truth of what it returns, and gives an iterator over the elements.
        The call back passes one argument, whatever receivers reached the
        call (see *Termination*)."""
        result = self.container_at("filter", call.origin, call.site, "filter")
        construct = ("filter", call)
        elements = self.iterated(args["iterable"], construct, call.caller, call.site)
        self.add_edge(elements, self.unknown(result))
        verdict = self.node()
        back = self.site_call(
            call.caller, call.site, ("filter",), [elements], dst=verdict
        )
        # Through the one callee node of the back call, as for map.
        self.add_edge(args["function"], self._callee(back))
        self.add_truth(verdict, call.caller, call.site)
        self._result(call, result)

    def _rule_next(self, call, receiver, args):
        """next(iterator, default)"""
        dst = self._result_node(call)
        self.add_next(args["iterator"], dst, call.caller, call.site)
        self.add_edge(args["default"], dst)

    def _rule_advance(self, call, receiver, args):
        """it.__next__() on an iterator that iter() makes, a generator or a
        generator expression, and generator.send(value) and throw(...): what
        next() on it gives, from the scope of the call (see
        `next_element`)."""
        if isinstance(receiver, Generator) and "value" in args:
            self.add_edge(args["value"], receiver.function.sent_node)
        iteration = self.iteration(
            self._result_node(call), call.caller, call.site, role="advance"
        )
        self.next_element(receiver, iteration)


def _may_init_property(call):
    """Whether `call` may be a valid call of `property.__init__(self, /,
    fget=None, fset=None, fdel=None, doc=None)`: `self` by position, at most
    five positional arguments, and no other keyword nor one given twice
    (`**` may pass any)."""
    names = WRAPPED["property"] + ("doc",)
    given = len(call.args)
    if given > len(names) + 1 or (given == 0 and not call.star):
        return False
    taken = set(names[: max(given - 1, 0)])
    for name, _ in call.keywords:
        if name not in names or name in taken:
            return False
        taken.add(name)
    return True


# The kind of access that runs each accessor of a property.
_ACCESS_KINDS = {"fget": "Load", "fset": "Store", "fdel": "Delete"}


def _builtin_name(external):
    """The name in `builtins` of the builtin `external` (`len`), or of a
    method of a builtin class (`object.__new__`); else None."""
    module, _, name = external.name.partition(".")
    if module == BUILTIN_MODULE and external.steps <= 1:
        return name
    return None


class _At(NamedTuple):
    """A construct that makes implicit calls: its scope and its site."""

    caller: str
    site: str


class _DynamicAccess:
    """A getattr, hasattr, setattr or delattr whose name is not a literal:
    the node of the name, the access, the names it reaches so far, and
    whether it has become dynamic; for loads by pattern, what it loaded and
    its load of each name."""

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
    """The arguments of a call of a modelled builtin, bound to its
    signature: `args[name]` is the node of a parameter, `varargs` and
    `varkeywords` the containers of `*args` and `**kwargs`. `given(name)` is
    true if the call may supply the parameter, `surely(name)` if it does."""

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


class _Late:
    """A `_Bound` of a plain call to a plain signature (no `*`, no `**`,
    no argument passed twice), which makes the node of a parameter when a
    rule reads it (see `BuiltinRules.bind_signature`). `since` is the
    solver's phase when the call was bound. Such a call surely supplies
    what it may supply, and the signature has no `*args` or `**kwargs`."""

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
    """The `Signature` of a signature written in Python syntax, and the
    defaults that are constants the analysis tracks (str and int), by
    parameter name."""
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
