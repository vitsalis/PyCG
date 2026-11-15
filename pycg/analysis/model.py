"""The objects of the analysis: the values that flow through the program.

An object is identified by the place that creates it, never by the name it is
bound to: a function by its definition, an instance by its class and the call
that created it. Objects compare by identity; the analysis interns the ones
that can be created more than once (modules, externals, instances, bound
methods).

Every object has a readable `name` and a dictionary of `fields`, the nodes
that hold its attributes. The fields of a module are its global variables and
the fields of a class are the names bound in its body.
"""

from types import MappingProxyType

BUILTIN_MODULE = "<builtin>"

# The fields of an object that never has any.
_NO_FIELDS = MappingProxyType({})


class Object:
    __slots__ = ("name", "fields")

    def __init__(self, name):
        self.name = name
        self.fields = {}

    def __repr__(self):
        return f"<{type(self).__name__} {self.name}>"


class Module(Object):
    """A module or package under the package root, including namespace
    packages, which have no file. `defines` holds the names that it binds at
    run time: those that its statements may bind at their end (see
    `ModuleBuilder.build`), those that its star imports bring in, its
    submodules."""

    __slots__ = ("defines",)

    def __init__(self, name):
        super().__init__(name)
        self.defines = set()


class External(Object):
    """Anything outside the package root, named by its dotted path, and the
    builtins, named `<builtin>.name`.

    The analysis does not see inside an external. Calling one that no stub
    describes gives the unnamed external (`UnknownExternal`): so
    `ext.Cls().method` names nothing. `steps` counts the attribute loads
    since the root of the name: an import (or a module path that one
    attaches) or a builtin.
    """

    __slots__ = ("steps", "inexact")

    def __init__(self, name, steps, inexact=False):
        super().__init__(name)
        self.steps = steps
        # The class taken from a value whose class is not known
        # (`Outside._class_object`): it names its kind's class for the
        # methods, but the value's class may be any other. A hierarchy holds
        # the external of the same class instead (`Analysis.same_class`).
        self.inexact = inexact

    def steps_past_root(self):
        """The attributes loaded since the root, in order."""
        return self.name.split(".")[-self.steps :] if self.steps else []


class UnknownExternal(External):
    """What a load past the bound of external names gives (see
    `MAX_EXTERNAL_STEPS`), and what calling outside code without stubs
    returns: an external value without a name. Calling it gives no edge and
    gives it again; as a decorator it may also return what it decorates,
    as a named external does. One object stands for all of them, and
    anything loaded from it is itself."""

    __slots__ = ()


class Saturated(Object):
    """What a saturated node holds (see the cap in solver.py): the
    objects that the analysis no longer tracks there. It is not an outside
    value, and it causes no edge, no object and no constraint: calling it,
    loading an attribute of it, subscripting it, iterating over it,
    awaiting it, entering it and operating on it give it again; storing
    into it does nothing; as a base or a metaclass it may define every
    name, and gives none. The document never names it."""

    __slots__ = ()


class Typed(Object):
    """An instance of a class outside the analysed code that the stubs
    describe (see stubs.py): one object per class, whatever its type
    arguments and whoever made it. `cls` is the definition path of the
    class, and the name its public name (`re.Pattern`, `<builtin>.str`).
    The concrete class of an `abstract` one (a protocol, a class with
    abstract methods, a class that exists only in stubs) is not known, so
    its methods give no edges. What the code stores on it is not
    tracked."""

    __slots__ = ("cls", "abstract")

    def __init__(self, cls, name, abstract):
        super().__init__(name)
        self.cls = cls
        self.abstract = abstract


class Signature:
    """The parameter names of a function, by kind.

    `positional` lists the positional-only parameters first and then the
    other positional parameters; `positional_only` is how many of them are
    positional-only.
    """

    __slots__ = ("positional", "positional_only", "keyword_only", "vararg", "kwarg")

    def __init__(
        self,
        positional=(),
        positional_only=0,
        keyword_only=(),
        vararg=None,
        kwarg=None,
    ):
        self.positional = tuple(positional)
        self.positional_only = positional_only
        self.keyword_only = tuple(keyword_only)
        self.vararg = vararg
        self.kwarg = kwarg

    def names(self):
        """All parameter names, in definition order."""
        extra = [name for name in (self.vararg, self.kwarg) if name]
        return list(self.positional) + list(self.keyword_only) + extra

    def accepts_keyword(self, name):
        return (
            name in self.positional[self.positional_only :] or name in self.keyword_only
        )


class Function(Object):
    """A `def`, `async def` or `lambda`.

    `parameters` maps each parameter name to the node of the parameter
    variable, `defaults` maps the parameters that have a default value to
    the node of that value, and `return_node` holds what the function
    returns. A generator function (one with `yield`) also has a `yield_node`
    with the values it yields and a `sent_node` with the values sent to it,
    which are the values of its `yield` expressions; calling it gives its
    `Generator` (an async generator if `is_async`). `is_async` is true for
    an `async def`: without `yield`, calling it gives its `Coroutine`.
    `varargs` and `varkeywords` are the tuple and the dict that its `*args`
    and `**kwargs` parameters hold, or None. `passthrough` holds
    the parameters that a `return` returns unchanged, by name, and the
    elements of `*args` that it returns, as `(name, index)`: each call gets
    its own argument for them as its result. `annotations` maps each annotated
    parameter to the node of its annotation, or is None. `decorated` is
    true for a definition with a decorator other than `staticmethod` and
    `classmethod`, which may give the name another signature. `optional`
    holds the parameters that have a default, whatever its value.
    """

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
    """A class statement.

    `defines` holds the names that the class body binds; an attribute lookup
    stops at the first class in an MRO that defines the name. `bases` holds,
    for each base expression, the classes it may refer to, and None if it may
    refer to no base (`object`). `mros` holds one MRO per hierarchy those
    choices allow, recomputed whenever a choice is added. If there are too
    many, or the class is on a cycle of candidate bases, `mros` holds one
    order with every candidate and `exhaustive` is true: lookups then find
    every definition. `ancestors` holds the classes of all MROs, the class
    included: it is set with them, so whether a class derives from another
    is one look-up. The class is `ready` once it has MROs (see
    hierarchy.py); `forced` if a fixpoint decided its exhaustive order.
    `instances` holds every instance of the class and of its subclasses.
    `index` is its position in the order of creation. `annotations` maps
    each name that the body annotates to the node of its annotation, or is
    None.

    A class is an instance of its metaclass (see hierarchy.py): `keyword`
    holds the candidates of the statement's `metaclass=` expression (None
    for no metaclass known, `type`), or is None without one; `metaclasses`
    holds the metaclasses decided so far, and the node `metaclass` the same
    objects. `protocol` is true for a class that lists `Protocol` among its
    bases, and `abstract_methods` holds the names that its body defines with
    a method decorated with `abstractmethod`; `uses_namespace` is true for
    a body that reads or writes its namespace, which may bind any name (see
    `Hierarchy._has_abstract_name`); `concrete` is true once Python
    may make an object of it, and the node `instantiable` then holds the
    class (see `Hierarchy._concrete`). `ancestry` holds the nodes of its
    base expressions and of its metaclass (the `metaclass=` expression and `metaclass`);
    `unknown` is true once their sets make the class unknown (see
    `Hierarchy.unknown_classes`).
    """

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
        "metaclass_of",
        "protocol",
        "abstract_methods",
        "uses_namespace",
        "stored_names",
        "metaclass_users",
        "concrete",
        "instantiable",
        "ancestry",
        "unknown",
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
        # (attribute, receiver) -> the node that holds the result of looking
        # the attribute up on this class for that receiver. Kept so that the
        # lookups can be redone when the MRO changes.
        self.lookups = {}
        self.instances = None
        self.annotations = None
        self.lineno = None
        self.end_lineno = None
        self.keyword = None
        self.metaclasses = {}
        self.metaclass = None
        # The classes whose `metaclass=` expression may hold this class.
        self.metaclass_of = {}
        self.protocol = False
        self.abstract_methods = frozenset()
        # The names that stores outside the body assign on the class, and
        # the classes whose metaclasses include it (see `Hierarchy`).
        self.uses_namespace = False
        self.stored_names = set()
        self.metaclass_users = {}
        self.concrete = False
        self.instantiable = None
        self.ancestry = ()
        self.unknown = False

    @property
    def mros(self):
        return self._mros

    @mros.setter
    def mros(self, mros):
        self._mros = mros
        self.ancestors = frozenset(base for mro in mros for base in mro)

    @property
    def mro(self):
        """The classes of all MROs, each at its first position. The classes
        of an exhaustive order follow the class in a canonical order, since
        their order does not matter to lookups."""
        if self.exhaustive:
            return [self] + sorted(self.mros[0][1:], key=base_order)
        return list(dict.fromkeys(base for mro in self.mros for base in mro))


def site_name(site):
    """The part of a site that names what a construct creates: a site is
    `module:line:column#end_line:end_column`, where the end tells apart the
    constructs that start at the same place (`a.b.c`, `(a + b) + c`)."""
    return site.partition("#")[0]


def base_order(base):
    """A key that orders candidate bases the same way in every solve: no
    base, then classes by module and, in a module, in order of creation,
    which follows its statements whatever the order in which modules are
    built; then externals by name."""
    if base is None:
        return (0, 0, "")
    if isinstance(base, Class):
        return (1, base.module, base.index)
    return (2, base.steps, base.name)


class Instance(Object):
    """An instance of a class, created by one call site."""

    __slots__ = ("cls",)

    def __init__(self, cls, site):
        super().__init__(f"{cls.name}@{site_name(site)}")
        self.cls = cls


class BoundMethod(Object):
    """A function, or a method of outside code, bound to the object it was
    loaded through: an instance, or a class for a class method, which a
    call passes before its own arguments."""

    __slots__ = ("receiver", "function")

    def __init__(self, receiver, function):
        super().__init__(f"<bound {function.name} of {receiver.name}>")
        self.receiver = receiver
        self.function = function


class ReturnsArgument(Object):
    """The callable that a library callable in `RETURNS_ARGUMENT` returns
    (`functools.wraps(f)`): calling it returns its first argument. Named
    after the library callable, like the result of an external call;
    `analysed` tells whether that callable is an analysed function."""

    __slots__ = ("analysed",)

    def __init__(self, name, analysed):
        super().__init__(name)
        self.analysed = analysed


class Closure(Object):
    """The callable that a library decorator in `CLOSURES` returns, where
    its stub gives a callable type (`contextlib.contextmanager.helper`):
    calling it gives an instance of `result`, the reduced result type of
    that callable (see stubs.py). Named after the closure."""

    __slots__ = ("result",)

    def __init__(self, name, result):
        super().__init__(name)
        self.result = result


class Fallback(Object):
    """The `__getattr__` method, bound to an instance, that a load of an
    attribute no class defines calls (see `Hierarchy.lookup`)."""

    __slots__ = ("method",)

    def __init__(self, method):
        super().__init__(f"<fallback {method.name}>")
        self.method = method


class Wrapper(Object):
    """A `staticmethod`, `classmethod` or `property` object, created by one
    call. `kind` is its type name. Its fields hold what it wraps: `__func__`
    for static and class methods; `fget`, `fset` and `fdel` for properties.
    """

    __slots__ = ("kind",)

    def __init__(self, kind, site):
        super().__init__(f"{kind}@{site_name(site)}")
        self.kind = kind


class BuiltinMethod(Object):
    """A method of a builtin type that the analysis models, bound to the
    object it was loaded from (`prop.setter`). Its name is the callee name,
    through the public name of the type: `<builtin>.property.setter`,
    `types.GeneratorType.send`."""

    __slots__ = ("receiver", "type_name", "method")

    def __init__(self, receiver, type_name, method, name):
        super().__init__(name)
        self.receiver = receiver
        self.type_name = type_name
        self.method = method


class Const(Object):
    """A `str`, `bytes` or `int` constant written in the source. Constants select the
    elements of containers by index or key. `bool` values are not constants:
    `True` is the key `1`.

    A program has many constants (pygments: 84k), so a constant has no
    fields and computes its name when asked."""

    __slots__ = ("value", "exact")

    def __init__(self, value, exact=True):
        self.fields = _NO_FIELDS
        self.value = value
        # Exactly of its builtin class; one more of each value, not exact,
        # stands for an object that Python may make from it (an enum
        # member; see `Containers.inexact`).
        self.exact = exact

    @property
    def name(self):
        return constant_name(self.value)

    @property
    def type_name(self):
        return type(self.value).__name__


# An int below this bound has at most 640 decimal digits, which every Python
# converts to a str whatever its limit (`sys.set_int_max_str_digits`).
_DECIMAL_BOUND = 10**640


def constant_name(value):
    """The name of the constant `value`: `ascii()` of it, which does not
    depend on the Unicode database of the running Python, and an int of more
    than 640 digits in hexadecimal, which no limit of Python refuses."""
    if isinstance(value, int) and abs(value) >= _DECIMAL_BOUND:
        return hex(value)
    return ascii(value)


class Container(Object):
    """A list, tuple, set or dict, or another builtin collection, created by
    one site: a display, a comprehension, or a call that makes one.

    `kind` is its type name. The elements are in nodes: `fields` maps each
    constant index or key to the elements stored under it, `unknown` holds
    the elements stored under other keys, and `keys` the keys of a dict.
    `factory` holds the factories of a `defaultdict`, which a read of a
    missing key calls. `aliased` holds, besides their fields, the elements
    of a dict stored under a key that is an alias of a class member (an
    inexact constant), which a pattern read reads. `length` is the number
    of elements of a display without unpacking, which makes negative
    indexes known; otherwise None.
    `exact` tells that its class is exactly that of `kind`, as for one that
    the analysed code makes (a display, `list(x)`, a slice); one that an
    annotation or a stub result makes stands for any value of its type.
    The analysis creates the nodes
    when they are needed (see containers.py).
    """

    __slots__ = (
        "kind",
        "length",
        "exact",
        "unknown",
        "every",
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
        # Holds every element: those of all fields and of `unknown`.
        self.every = None
        self.keys = None
        self.factory = None
        self.aliased = None
        # Called with (key, node) for each field, now and when it is added.
        self.observers = []
        # What repr() of the container reaches (see `Protocols.repr_reach`).
        self.repr_reach = None


class Super(Object):
    """The result of `super(cls, receiver)`: attributes are looked up in the
    MRO of the receiver's class (or of the receiver, if it is a class),
    after `cls`, and bound to the receiver."""

    __slots__ = ("cls", "receiver")

    def __init__(self, cls, receiver):
        super().__init__(f"super({cls.name}, {receiver.name})")
        self.cls = cls
        self.receiver = receiver


class Generator(Object):
    """The generator that calling a generator function returns. One per
    function: iterating over it gives what the function yields. `kind` is
    its type name: `async_generator` for an `async def`. It is exactly of
    that class; one more, not `exact`, stands for an object that Python may
    make from it (see `Containers.inexact`)."""

    __slots__ = ("function", "exact")

    def __init__(self, function, exact=True):
        super().__init__(f"generator@{function.name}")
        self.function = function
        self.exact = exact

    @property
    def kind(self):
        return "async_generator" if self.function.is_async else "generator"


class Coroutine(Object):
    """The coroutine that calling a coroutine function returns. One per
    function: awaiting it gives what the function returns. `exact` as for a
    `Generator`."""

    __slots__ = ("function", "exact")

    def __init__(self, function, exact=True):
        super().__init__(f"coroutine@{function.name}")
        self.function = function
        self.exact = exact


class TypeForm(Object):
    """A type expression that the analysis reads in annotations (see
    annotations.py): a union `A | B` (`operator` "|") or a subscript
    `X[A, B]` ("[]"). `parts` holds the nodes of the operands, None for one
    without a value: the arms of a union; for a subscript, the subscripted
    value and then the arguments. One per site. It flows like any value (an
    alias `T = A | B` holds it), and no rule but the reading of annotations
    acts on it."""

    __slots__ = ("operator", "parts")

    def __init__(self, operator, parts, site):
        super().__init__(f"type{operator}@{site_name(site)}")
        self.operator = operator
        self.parts = parts


class Pattern(Object):
    """A str that the code builds from a constant `prefix` and `suffix` and
    another value (see patterns.py): `"visit_" + kind`, and its `case`
    conversion, "lower" or "upper" (None for none). One per prefix, suffix
    and case. A `getattr` with it loads the attributes whose names match; it
    flows like a str constant. As for a constant, one more of each, not
    `exact`, stands for an object that Python may make from it (an enum
    member; see `Containers.inexact`)."""

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
        """The part of `name` between the prefix and the suffix, or None if
        `name` does not have both, or cannot be what the case conversion
        gives: an ASCII name that the conversion changes. The case of other
        characters depends on the Unicode database of the running Python,
        so a name with one may be what it gives."""
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
