from .containers import SEQUENCES, is_dict
from .model import Container
from .solver import Each


class Arguments:
    def bind_arguments(self, function, call, receiver):
        signature = function.signature
        parameters = function.parameters
        positional = list(signature.positional)
        surely_supplied = set()
        varargs_taken_by_receiver = 0
        if receiver is not None and positional:
            first = positional.pop(0)
            self.add_object(parameters[first], receiver)
            if first in function.passthrough and call.dst is not None:
                self.add_object(call.dst, receiver)
            surely_supplied.add(first)
        elif receiver is not None and function.varargs is not None:
            self.add_object(self.element(function.varargs, 0), receiver)
            if (signature.vararg, 0) in function.passthrough and call.dst is not None:
                self.add_object(call.dst, receiver)
            varargs_taken_by_receiver = 1
        for index, arg in enumerate(call.args):
            if index < len(positional):
                surely_supplied.add(positional[index])
            if arg is not None:
                self._bind_position(
                    function, positional, index + varargs_taken_by_receiver, arg, call
                )
        if call.star:
            start = len(call.args) + varargs_taken_by_receiver
            self._bind_unpacked(function, positional, start, call)
        for name, value in call.keywords:
            if signature.accepts_keyword(name):
                surely_supplied.add(name)
            if value is None:
                value = self.node()
            self._bind_keyword(function, name, value, call)
        for index, mapping in enumerate(call.double_star):
            if mapping is not None:
                keywords = self._spread(call, ("**", index), mapping)
                self._bind_mapping(keywords, function, call)
        for parameter, default in function.defaults.items():
            if parameter not in surely_supplied:
                self._bind_parameter(function, parameter, default, call)
        return surely_supplied

    def _bind_parameter(self, function, name, source, call):
        self.add_edge(source, function.parameters[name])
        if name in function.passthrough and call.dst is not None:
            self.add_edge(source, call.dst)

    def _bind_position(self, function, positional, index, source, call):
        if index < len(positional):
            self._bind_parameter(function, positional[index], source, call)
        elif function.varargs is not None:
            self._bind_varargs(function, index - len(positional), source, call)

    def _bind_varargs(self, function, index, source, call):
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
        first, _ = call.star[0]
        if first is not None:
            spread = self._spread(call, "*", first)

            def bind_field(key, node):
                index = start + key
                if index - len(positional) > key:
                    if function.varargs is not None:
                        self._bind_varargs(function, None, node, call)
                    return
                self._bind_position(function, positional, index, node, call)

            self.observe(spread, bind_field)
            self._bind_once_gathered(
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
        key = (call.origin, part)
        spread = self._unpacked.get(key)
        if spread is None:
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
        assert spread.source is value, f"{key!r} unpacks another node"
        return spread

    def _spread_sequence(self, obj, spread, iteration):
        if isinstance(obj, Container) and obj.kind in SEQUENCES:

            def gather_field(key, node):
                if isinstance(key, int) and key >= 0:
                    self.add_edge(node, self._spread_field(spread, key))

            self.observe(obj, gather_field)
            self.add_edge(self.unknown(obj), spread.unknown)
        else:
            iteration.apply(obj)
        self._wake_bindings_waiting(spread)

    def _spread_mapping(self, obj, spread):
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
        self._wake_bindings_waiting(spread)

    def _bind_once_gathered(self, spread, bind):
        if spread.waiting is None:
            bind()
        else:
            spread.waiting.append(bind)

    def _wake_bindings_waiting(self, spread):
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

        def bind_field(key, node):
            self._bind_keyword(function, key, node, call)

        self.observe(spread, bind_field)
        self._bind_once_gathered(
            spread, lambda: self._bind_unknown_keywords(spread, function, call)
        )

    def _bind_unknown_keywords(self, spread, function, call):
        signature = function.signature
        unknown = spread.unknown
        for name in signature.positional[signature.positional_only_count :]:
            self._bind_parameter(function, name, unknown, call)
        for name in signature.keyword_only:
            self._bind_parameter(function, name, unknown, call)
        if function.varkeywords is not None:
            self.add_edge(unknown, self.unknown(function.varkeywords))
            self.add_edge(spread.aliased, self.aliased(function.varkeywords))
            if spread.keys is None:
                spread.keys = self.node()
                for obj in spread.dicts:
                    self.add_edge(self.keys(obj), spread.keys)
            self.add_edge(spread.keys, self.keys(function.varkeywords))


class _Spread:
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
