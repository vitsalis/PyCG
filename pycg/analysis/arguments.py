"""Binding the arguments of a call to the parameters of a function.

`Arguments` is part of `Analysis` (see semantics.py), whose objects, nodes
and constraints it uses.

Positional arguments before the first unpacked one bind by position; the
extra ones go to the `*args` tuple of the function, one field per position.
An unpacked list or tuple keeps the positions of its elements; any other
unpacked iterable, and every argument after it, may bind to any later
position. Keyword arguments bind by name, and those that no parameter
accepts go to the `**kwargs` dict. An unpacked dict binds its constant keys
by name; its other elements may bind to any parameter that accepts keywords.
A default flows into its parameter at each call that may omit the argument.

If the function returns a parameter unchanged, or an element of its `*args`
at a constant index, each call's result gets what that call binds to the
parameter or may bind to that element (see `Function.passthrough`).

What the unpacked arguments of a call pass is gathered once per call site
(`_Spread`), and each callee binds the site: a site where many sequences or
dicts meet many callees costs their sum, not their product.
"""

from .containers import SEQUENCES, is_dict
from .model import Container
from .solver import Each


class Arguments:
    def bind_arguments(self, function, call, receiver):
        """Bind the arguments of `call`, and `receiver` if it is not None, to
        the parameters of `function`. Return the parameters that the call
        surely supplies."""
        signature = function.signature
        parameters = function.parameters
        positional = list(signature.positional)
        supplied = set()
        # Positions that the receiver takes in `*args`.
        shift = 0
        if receiver is not None and positional:
            first = positional.pop(0)
            self.add_object(parameters[first], receiver)
            if first in function.passthrough and call.dst is not None:
                self.add_object(call.dst, receiver)
            supplied.add(first)
        elif receiver is not None and function.varargs is not None:
            # A method `def run(*args)`: the receiver is args[0].
            self.add_object(self.element(function.varargs, 0), receiver)
            if (signature.vararg, 0) in function.passthrough and call.dst is not None:
                self.add_object(call.dst, receiver)
            shift = 1
        for index, arg in enumerate(call.args):
            if index < len(positional):
                supplied.add(positional[index])
            if arg is not None:
                self._bind_position(function, positional, index + shift, arg, call)
        if call.star:
            start = len(call.args) + shift
            self._bind_unpacked(function, positional, start, call)
        for name, value in call.keywords:
            if signature.accepts_keyword(name):
                supplied.add(name)
            # An untracked value still gives **kwargs its key.
            if value is None:
                value = self.node()
            self._bind_keyword(function, name, value, call)
        for index, mapping in enumerate(call.double_star):
            if mapping is not None:
                keywords = self._spread(call, ("**", index), mapping)
                self._bind_mapping(keywords, function, call)
        # Unpacked arguments may or may not supply the other parameters.
        for parameter, default in function.defaults.items():
            if parameter not in supplied:
                self._bind_parameter(function, parameter, default, call)
        return supplied

    def _bind_parameter(self, function, name, source, call):
        """Bind the node `source` to the parameter `name`; if the function
        returns the parameter unchanged, the call's result gets `source`."""
        self.add_edge(source, function.parameters[name])
        if name in function.passthrough and call.dst is not None:
            self.add_edge(source, call.dst)

    def _bind_position(self, function, positional, index, source, call):
        """Bind `source` to the positional argument `index`: a parameter or
        a field of `*args`."""
        if index < len(positional):
            self._bind_parameter(function, positional[index], source, call)
        elif function.varargs is not None:
            self._bind_varargs(function, index - len(positional), source, call)

    def _bind_varargs(self, function, index, source, call):
        """Bind `source` to the element `index` of `*args`, or to its unknown
        elements if `index` is None; if the function returns that element
        unchanged (an unknown one may be any), the call's result gets
        `source`."""
        if index is None:
            self.add_edge(source, self.unknown(function.varargs))
        else:
            self.add_edge(source, self.element(function.varargs, index))
        if call.dst is None:
            return
        vararg = function.signature.vararg
        if index is None:
            returned = any(isinstance(entry, tuple) for entry in function.passthrough)
        else:
            returned = (vararg, index) in function.passthrough
        if returned:
            self.add_edge(source, call.dst)

    def _bind_unpacked(self, function, positional, start, call):
        """Bind the arguments from the first unpacked one on, which starts
        at position `start`."""
        first, _ = call.star[0]
        if first is not None:
            spread = self._spread(call, "*", first)

            def bind_field(key, node):
                index = start + key
                if index - len(positional) > key:
                    # A field that would move to a higher index of *args goes
                    # to its unknown elements: moving it up could create new
                    # indexes without end (`def f(*args): f(x, *args)`).
                    if function.varargs is not None:
                        self._bind_varargs(function, None, node, call)
                    return
                self._bind_position(function, positional, index, node, call)

            self.observe(spread, bind_field)
            self._once_gathered(
                spread,
                lambda: self._bind_anywhere(
                    function, positional, start, spread.unknown, call
                ),
            )
        for index, (value, starred) in enumerate(call.star[1:], 1):
            if value is None:
                continue
            if starred:
                value = self._spread(call, index, value).unknown
            self._bind_anywhere(function, positional, start, value, call)

    def _spread(self, call, part, value):
        """The `_Spread` of the unpacked argument `part` of `call`, whose node
        is `value`: "*" for the first `*iterable`, its position for a later
        one, ("**", i) for a mapping."""
        key = (call.origin, part)
        spread = self._unpacked.get(key)
        if spread is None:
            # Only a mapping stores items under class members.
            aliased = self.node() if isinstance(part, tuple) else None
            spread = self._unpacked[key] = _Spread(self.node(), value, aliased)
            if part == "*":
                iteration = self.iteration(
                    spread.unknown, call.caller, call.site, role="arguments"
                )
                gather = Each(
                    self._spread_sequence, spread, iteration, results=(spread.unknown,)
                )
            elif isinstance(part, int):
                gather = self.iteration(
                    spread.unknown, call.caller, call.site, role="for"
                )
            else:
                gather = Each(self._spread_mapping, spread, results=(spread.unknown,))
            self.solver.attach(value, gather)
        # The cache keeps the first node: a call with this origin that
        # unpacked another node would lose what it holds.
        assert spread.source is value, f"{key!r} unpacks another node"
        return spread

    def _spread_sequence(self, obj, spread, iteration):
        """Add the elements of `obj`, unpacked, to `spread`: a list or tuple
        by position, any other iterable at any position."""
        if isinstance(obj, Container) and obj.kind in SEQUENCES:

            def gather_field(key, node):
                if isinstance(key, int) and key >= 0:
                    self.add_edge(node, self._spread_field(spread, key))

            self.observe(obj, gather_field)
            self.add_edge(self.unknown(obj), spread.unknown)
        else:
            iteration.apply(obj)
        self._gathered(spread)

    def _spread_mapping(self, obj, spread):
        """Add the items of the dict `obj`, unpacked with `**`, to
        `spread`."""
        if not (isinstance(obj, Container) and is_dict(obj)):
            return

        def gather_field(key, node):
            if isinstance(key, str):
                self.add_edge(node, self._spread_field(spread, key))

        self.observe(obj, gather_field)
        self.add_edge(self.unknown(obj), spread.unknown)
        self.add_edge(self.aliased(obj), spread.aliased)
        spread.dicts.append(obj)
        if spread.keys is not None:
            self.add_edge(self.keys(obj), spread.keys)
        self._gathered(spread)

    def _once_gathered(self, spread, bind):
        """Call `bind()` once `spread` has gathered something: binding its
        unknown elements creates the nodes of a callee's `*args` and
        `**kwargs` elements, which exist only when something is passed."""
        if spread.waiting is None:
            bind()
        else:
            spread.waiting.append(bind)

    def _gathered(self, spread):
        waiting, spread.waiting = spread.waiting, None
        for bind in waiting or ():
            bind()

    def _spread_field(self, spread, key):
        node = spread.fields.get(key)
        if node is None:
            node = spread.fields[key] = self.node()
            for observer in list(spread.observers):
                self._notify(observer, key, node)
        return node

    def _bind_anywhere(self, function, positional, start, source, call):
        """Bind `source` to every position from `start` on."""
        for parameter in positional[start:]:
            self._bind_parameter(function, parameter, source, call)
        if function.varargs is not None:
            self._bind_varargs(function, None, source, call)

    def _bind_keyword(self, function, name, value, call):
        if function.signature.accepts_keyword(name):
            self._bind_parameter(function, name, value, call)
        elif function.varkeywords is not None:
            self.add_edge(value, self.element(function.varkeywords, name))
            self.add_object(self.keys(function.varkeywords), self.const(name))

    def _bind_mapping(self, spread, function, call):
        """Bind the items that a `**mapping` of `call` gathers in `spread`."""

        def bind_field(key, node):
            self._bind_keyword(function, key, node, call)

        self.observe(spread, bind_field)
        self._once_gathered(
            spread, lambda: self._bind_unknown_keywords(spread, function, call)
        )

    def _bind_unknown_keywords(self, spread, function, call):
        """Bind the items with keys that are not known, and the keys, that
        a `**mapping` gathers in `spread`."""
        signature = function.signature
        unknown = spread.unknown
        for name in signature.positional[signature.positional_only :]:
            self._bind_parameter(function, name, unknown, call)
        for name in signature.keyword_only:
            self._bind_parameter(function, name, unknown, call)
        if function.varkeywords is not None:
            self.add_edge(unknown, self.unknown(function.varkeywords))
            # The items stored under a class member (see
            # `Containers.write_key`) stay apart for a pattern read.
            self.add_edge(spread.aliased, self.aliased(function.varkeywords))
            if spread.keys is None:
                # The keys of the dicts, gathered once a callee takes them.
                spread.keys = self.node()
                for obj in spread.dicts:
                    self.add_edge(self.keys(obj), spread.keys)
            self.add_edge(spread.keys, self.keys(function.varkeywords))


class _Spread:
    """What an unpacked argument of one call site passes, for every callee:
    `fields` by position (`*iterable`) or keyword (`**mapping`), `unknown`
    the elements at other or unknown positions or keys, and for a mapping
    the `keys` of its `dicts`, once a callee takes them, and in `aliased`
    the items that they store under a class member. Callees observe
    the fields like those of a container (`Containers.observe`); `waiting`
    holds the bindings that wait until something is gathered (None after).
    """

    __slots__ = (
        "source",
        "fields",
        "unknown",
        "keys",
        "dicts",
        "aliased",
        "observers",
        "waiting",
    )

    def __init__(self, unknown, source, aliased):
        self.source = source
        self.fields = {}
        self.unknown = unknown
        self.aliased = aliased
        self.keys = None
        self.dicts = []
        self.observers = []
        self.waiting = []
