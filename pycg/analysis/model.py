from types import MappingProxyType

BUILTIN_MODULE = "<builtin>"

_FIELDS_EMPTY = MappingProxyType({})


class Object:
    __slots__ = ("name", "fields")

    def __init__(self, name):
        self.name = name
        self.fields = {}

    def __repr__(self):
        return f"<{type(self).__name__} {self.name}>"


class Module(Object):
    __slots__ = ("defines",)

    def __init__(self, name):
        super().__init__(name)
        self.defines = set()


class External(Object):
    __slots__ = ("steps", "inexact")

    def __init__(self, name, steps, inexact=False):
        super().__init__(name)
        self.steps = steps
        self.inexact = inexact

    def steps_past_root(self):
        return self.name.split(".")[-self.steps :] if self.steps else []


class UnknownExternal(External):
    __slots__ = ()


class Saturated(Object):
    __slots__ = ()


class Typed(Object):
    __slots__ = ("cls", "abstract")

    def __init__(self, cls, name, abstract):
        super().__init__(name)
        self.cls = cls
        self.abstract = abstract


class Signature:
    __slots__ = (
        "positional",
        "positional_only_count",
        "keyword_only",
        "vararg",
        "kwarg",
        "_names",
    )

    def __init__(
        self,
        positional=(),
        positional_only_count=0,
        keyword_only=(),
        vararg=None,
        kwarg=None,
    ):
        self.positional = tuple(positional)
        assert 0 <= positional_only_count <= len(self.positional)
        self.positional_only_count = positional_only_count
        self.keyword_only = tuple(keyword_only)
        self.vararg = vararg
        self.kwarg = kwarg
        extra = tuple(name for name in (vararg, kwarg) if name)
        self._names = self.positional + self.keyword_only + extra

    def names(self):
        return self._names

    def accepts_keyword(self, name):
        return (
            name in self.positional[self.positional_only_count :]
            or name in self.keyword_only
        )

    def binds(self, given, keywords, optional):
        if given > len(self.positional) and self.vararg is None:
            return False
        filled = set(self.positional[:given])
        for name in keywords:
            if self.accepts_keyword(name):
                if name in filled:
                    return False
                filled.add(name)
            elif self.kwarg is None:
                return False
        required = (*self.positional, *self.keyword_only)
        return all(name in filled for name in required if name not in optional)


class Function(Object):
    __slots__ = (
        "module",
        "signature",
        "parameters",
        "defaults",
        "return_node",
        "yield_node",
        "sent_node",
        "is_async",
        "varargs",
        "varkeywords",
        "passthrough",
        "annotations",
        "decorated",
        "optional",
        "lineno",
        "col_offset",
        "end_lineno",
        "end_col_offset",
    )

    def __init__(self, name, module, signature, parameters, defaults, return_node):
        super().__init__(name)
        self.module = module
        self.signature = signature
        self.parameters = parameters
        self.defaults = defaults
        self.return_node = return_node
        self.yield_node = None
        self.sent_node = None
        self.is_async = False
        self.varargs = None
        self.varkeywords = None
        self.passthrough = set()
        self.annotations = None
        self.decorated = False
        self.optional = frozenset()
        self.lineno = None
        self.col_offset = None
        self.end_lineno = None
        self.end_col_offset = None


class Class(Object):
    __slots__ = (
        "module",
        "defines",
        "bases",
        "_mros",
        "ancestors",
        "exhaustive",
        "ready",
        "forced",
        "index",
        "subclasses",
        "lookups",
        "instances",
        "annotations",
        "lineno",
        "end_lineno",
        "keyword",
        "metaclasses",
        "metaclass",
        "metaclass_candidate_of",
        "protocol",
        "abstract_methods",
        "uses_namespace",
        "stored_names_outside_body",
        "metaclass_users",
        "concrete",
        "instantiable",
        "ancestry",
        "unknown",
        "allocator",
    )

    def __init__(self, name, module, defines, base_count):
        super().__init__(name)
        self.module = module
        self.defines = frozenset(defines)
        self.bases = [{} for _ in range(base_count)]
        self.mros = [[self]]
        self.exhaustive = False
        self.ready = False
        self.forced = False
        self.index = None
        self.subclasses = {}
        self.lookups = {}
        self.instances = None
        self.annotations = None
        self.lineno = None
        self.end_lineno = None
        self.keyword = None
        self.metaclasses = {}
        self.metaclass = None
        self.metaclass_candidate_of = {}
        self.protocol = False
        self.abstract_methods = frozenset()
        self.uses_namespace = False
        self.stored_names_outside_body = set()
        self.metaclass_users = {}
        self.concrete = False
        self.instantiable = None
        self.ancestry = ()
        self.unknown = False
        self.allocator = None

    @property
    def mros(self):
        return self._mros

    @mros.setter
    def mros(self, mros):
        self._mros = mros
        self.ancestors = frozenset(base for mro in mros for base in mro)

    @property
    def mro(self):
        if self.exhaustive:
            return [self] + sorted(self.mros[0][1:], key=base_order)
        return list(dict.fromkeys(base for mro in self.mros for base in mro))


def site_name(site):
    return site.partition("#")[0]


def base_order(base):
    if base is None:
        return (0, 0, "")
    if isinstance(base, Class):
        return (1, base.module, base.index)
    return (2, base.steps, base.name)


class Instance(Object):
    __slots__ = ("cls",)

    def __init__(self, cls, site):
        super().__init__(f"{cls.name}@{site_name(site)}")
        self.cls = cls


class BoundMethod(Object):
    __slots__ = ("receiver", "function")

    def __init__(self, receiver, function):
        super().__init__(f"<bound {function.name} of {receiver.name}>")
        self.receiver = receiver
        self.function = function


class ReturnsArgument(Object):
    __slots__ = ("analysed",)

    def __init__(self, name, analysed):
        super().__init__(name)
        self.analysed = analysed


class Closure(Object):
    __slots__ = ("result",)

    def __init__(self, name, result):
        super().__init__(name)
        self.result = result


class Fallback(Object):
    __slots__ = ("method",)

    def __init__(self, method):
        super().__init__(f"<fallback {method.name}>")
        self.method = method


class Wrapper(Object):
    __slots__ = ("kind",)

    def __init__(self, kind, site):
        super().__init__(f"{kind}@{site_name(site)}")
        self.kind = kind


class BuiltinMethod(Object):
    __slots__ = ("receiver", "type_name", "method")

    def __init__(self, receiver, type_name, method, name):
        super().__init__(name)
        self.receiver = receiver
        self.type_name = type_name
        self.method = method


class Const(Object):
    __slots__ = ("value", "exact")

    def __init__(self, value, exact=True):
        self.fields = _FIELDS_EMPTY
        self.value = value
        self.exact = exact

    @property
    def name(self):
        return constant_name(self.value)

    @property
    def type_name(self):
        return type(self.value).__name__


_CONSTANT_NAME_DECIMAL_LIMIT = 10**640


def constant_name(value):
    if isinstance(value, int) and abs(value) >= _CONSTANT_NAME_DECIMAL_LIMIT:
        return hex(value)
    return ascii(value)


class Container(Object):
    __slots__ = (
        "kind",
        "length",
        "exact",
        "unknown",
        "every_element",
        "keys",
        "factory",
        "aliased",
        "observers",
        "repr_reach",
    )

    def __init__(self, kind, site, length=None, exact=False):
        super().__init__(f"{kind}@{site_name(site)}")
        self.kind = kind
        self.length = length
        self.exact = exact
        self.unknown = None
        self.every_element = None
        self.keys = None
        self.factory = None
        self.aliased = None
        self.observers = []
        self.repr_reach = None


class Super(Object):
    __slots__ = ("cls", "receiver")

    def __init__(self, cls, receiver):
        super().__init__(f"super({cls.name}, {receiver.name})")
        self.cls = cls
        self.receiver = receiver


class Generator(Object):
    __slots__ = ("function", "exact")

    def __init__(self, function, exact=True):
        super().__init__(f"generator@{function.name}")
        self.function = function
        self.exact = exact

    @property
    def kind(self):
        return "async_generator" if self.function.is_async else "generator"


class Coroutine(Object):
    __slots__ = ("function", "exact")

    def __init__(self, function, exact=True):
        super().__init__(f"coroutine@{function.name}")
        self.function = function
        self.exact = exact


class TypeForm(Object):
    __slots__ = ("operator", "parts")

    def __init__(self, operator, parts, site):
        super().__init__(f"type{operator}@{site_name(site)}")
        self.operator = operator
        self.parts = parts


class Pattern(Object):
    __slots__ = ("prefix", "suffix", "case", "exact")

    type_name = "str"

    def __init__(self, prefix, suffix, case=None, exact=True):
        name = f"pattern {ascii(prefix)}*{ascii(suffix)}"
        super().__init__(name if case is None else f"{name} {case}")
        self.prefix = prefix
        self.suffix = suffix
        self.case = case
        self.exact = exact

    def matches(self, name):
        start, end = len(self.prefix), len(name) - len(self.suffix)
        if end < start or not (
            name.startswith(self.prefix) and name.endswith(self.suffix)
        ):
            return None
        if (
            self.case is not None
            and name.isascii()
            and getattr(name, self.case)() != name
        ):
            return None
        return name[start:end]
