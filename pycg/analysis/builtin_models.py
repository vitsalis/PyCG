"""The rules of builtin functions and methods of builtin types that track
more than their stubs say: elements of containers, what a descriptor
wraps, the special methods a builtin calls, attributes by name.

Every other builtin is described by the stubs (see outside.py). A modelled
builtin gives the edge, and its rule (in `builtin_rules.py`) decides the
result; it never calls its arguments. An entry is a tuple: the signature of
the builtin in Python syntax, the rule name, then the parameters of the
rule. A call binds its arguments to the signature like a call of a
function, so unpacked and keyword arguments reach the rule, and so do
defaults that are str or int constants (`format_spec=''`).
"""

# Builtin functions and classes, by their name in `builtins`, and methods of
# builtin classes, by the class's name and theirs.
FUNCTIONS = {
    "staticmethod": ("(function, /)", "wrap", "staticmethod"),
    "classmethod": ("(function, /)", "wrap", "classmethod"),
    "property": ("(fget=None, fset=None, fdel=None, doc=None)", "property"),
    # The methods of `property`, whose receiver is the engine's own property
    # or an instance of an analysed subclass of `property`.
    "property.__init__": (
        "(self, /, fget=None, fset=None, fdel=None, doc=None)",
        "property_init",
    ),
    "property.getter": ("(self, function, /)", "property_with", "fget"),
    "property.setter": ("(self, function, /)", "property_with", "fset"),
    "property.deleter": ("(self, function, /)", "property_with", "fdel"),
    "property.__get__": ("(self, instance, owner=None, /)", "property_run", "fget"),
    "property.__set__": ("(self, instance, value, /)", "property_run", "fset"),
    "property.__delete__": ("(self, instance, /)", "property_run", "fdel"),
    "list": ("(iterable=(), /)", "collection", "list"),
    "tuple": ("(iterable=(), /)", "collection", "tuple"),
    "set": ("(iterable=(), /)", "collection", "set"),
    "frozenset": ("(iterable=(), /)", "collection", "frozenset"),
    "dict": ("(mapping=(), /, **kwargs)", "dict"),
    "iter": ("(object, sentinel=None, /)", "iter"),
    "enumerate": ("(iterable, start=0)", "enumerate"),
    "zip": ("(*iterables, strict=False)", "zip"),
    "reversed": ("(sequence, /)", "reversed"),
    "map": ("(function, iterable, /, *iterables, strict=False)", "map"),
    "filter": ("(function, iterable, /)", "filter"),
    "next": ("(iterator, default=None, /)", "next"),
    "super": ("(type=None, object_or_type=None, /)", "super"),
    "type": ("(object, bases=None, dict=None, /, **kwds)", "type"),
    "str": ("(object='')", "convert", "str", "object"),
    "repr": ("(obj, /)", "convert", "repr", "obj"),
    "format": (
        "(value, format_spec='', /)",
        "convert",
        "format",
        "value",
        "format_spec",
    ),
    "print": ("(*values, sep=None, end=None, file=None, flush=False)", "print"),
    "getattr": ("(object, name, default=None, /)", "getattr", "getattr"),
    "hasattr": ("(obj, name, /)", "getattr", "hasattr"),
    "setattr": ("(obj, name, value, /)", "setattr"),
    "delattr": ("(obj, name, /)", "delattr"),
}

# getattr, hasattr, setattr and delattr whose name is a str literal are a
# load, a store or a deletion. With any other name, they are one of each str
# constant it holds at each fixpoint, whatever else it holds, while it holds
# at most this many; beyond that, the access is dynamic and gets no more names.
MAX_DYNAMIC_NAMES = 4

# Methods of builtin types, by type name and method name.
METHODS = {
    ("classmethod", "__get__"): ("(instance, owner=None, /)", "bind"),
    ("staticmethod", "__get__"): ("(instance, owner=None, /)", "bind"),
    ("list", "append"): ("(object, /)", "add", "object"),
    ("list", "insert"): ("(index, object, /)", "add", "object"),
    ("list", "extend"): ("(iterable, /)", "extend"),
    ("list", "pop"): ("(index=-1, /)", "any_element"),
    ("list", "copy"): ("()", "copy"),
    ("set", "add"): ("(element, /)", "add", "element"),
    ("set", "update"): ("(*others)", "extend"),
    ("set", "pop"): ("()", "any_element"),
    ("set", "copy"): ("()", "copy"),
    ("frozenset", "copy"): ("()", "copy"),
    ("dict", "update"): ("(mapping=(), /, **kwargs)", "update"),
    ("dict", "setdefault"): ("(key, default=None, /)", "setdefault"),
    ("dict", "get"): ("(key, default=None, /)", "get"),
    ("dict", "pop"): ("(key, default=None, /)", "get"),
    ("dict", "copy"): ("()", "copy"),
    ("dict", "keys"): ("()", "view", "dict_keys"),
    ("dict", "values"): ("()", "view", "dict_values"),
    ("dict", "items"): ("()", "view", "dict_items"),
    ("collections.OrderedDict", "move_to_end"): ("(key, last=True)", "lookup"),
    ("collections.deque", "appendleft"): ("(x, /)", "add", "x"),
    ("collections.deque", "extendleft"): ("(iterable, /)", "extend"),
    ("collections.deque", "popleft"): ("()", "any_element"),
    ("collections.Counter", "update"): ("(iterable=(), /, **kwargs)", "count"),
    ("str", "lower"): ("()", "case", "lower"),
    ("str", "upper"): ("()", "case", "upper"),
    ("str", "casefold"): ("()", "case", "lower"),
    ("generator", "__next__"): ("()", "advance"),
    ("generator", "send"): ("(value, /)", "advance"),
    ("generator", "throw"): ("(typ=None, val=None, tb=None, /)", "advance"),
    ("iterator", "__next__"): ("()", "advance"),
    ("callable_iterator", "__next__"): ("()", "advance"),
}

# Selected operations of the standard library that iterate what they get
# (design.md, "Selected standard-library operations"), by the canonical
# stub definition path: how (below), the parameters whose arguments they
# iterate ("*": every parameter that the overload types as an abstract
# iterable, by position), what the lazy objects give, and the class of the
# lazy object (its methods' names). By probes of CPython 3.12.12, 3.13.12,
# 3.14.9 and 3.15.2 with an iterable apart from its iterator:
# - EAGER: iterate at the call (`functools.reduce`, `math.sumprod`, ...);
# - MATERIALIZE: make a tuple of each at the call, which asks its length
#   (on 3.12 and 3.13; every version counts), and give tuples of items;
# - LARGEST: `heapq.nlargest`/`nsmallest`: `len()`, `iter()`, `iter()` of
#   that iterator again, and advance it, at the call;
# - LAZY: `iter()` at the call, the advancing where the object is advanced;
# - TEE: as LAZY, with `iter()` of the iterator again at the call;
# - STARMAP: as LAZY; each argument bundle is made a tuple when advanced;
# - GROUPBY: as LAZY; a group advances the same source;
# - LAZY_ALL: `iter()` and the advancing where the object is advanced
#   (`chain`);
# - MERGE: as LAZY_ALL, and `iter()` of an iterator again (`heapq.merge`
#   delegates to its last source with `yield from`);
# - LAZY_OUTER: `iter()` of the outer iterable at the call; each inner
#   iterable is taken and iterated where the object is advanced.
EAGER, MATERIALIZE, LARGEST = "eager", "materialize", "largest"
LAZY, TEE, STARMAP, GROUPBY = "lazy", "tee", "starmap", "groupby"
LAZY_ALL, LAZY_OUTER, MERGE = "lazy all", "lazy outer", "merge"
LAZY_MODES = frozenset({LAZY, TEE, STARMAP, GROUPBY, LAZY_ALL, LAZY_OUTER, MERGE})
# What advancing a lazy object gives: the items (of every argument, or of
# the first only), tuples of items, a tuple per position, or nothing.
ITEMS, FIRST, TUPLES, POSITIONS, NOTHING = (
    "items",
    "first",
    "tuples",
    "positions",
    "nothing",
)
LIBRARY_ITERATION = {
    "functools.reduce": (EAGER, ("iterable",), NOTHING, None),
    "math.sumprod": (EAGER, ("p", "q"), NOTHING, None),
    "math.fsum": (EAGER, ("seq",), NOTHING, None),
    "math.prod": (EAGER, ("iterable",), NOTHING, None),
    "_operator.countOf": (EAGER, ("a",), NOTHING, None),
    "_operator.indexOf": (EAGER, ("a",), NOTHING, None),
    "math.dist": (MATERIALIZE, ("p", "q"), NOTHING, None),
    "itertools.product": (MATERIALIZE, ("*",), POSITIONS, "itertools.product"),
    "itertools.combinations": (
        MATERIALIZE,
        ("iterable",),
        TUPLES,
        "itertools.combinations",
    ),
    "itertools.combinations_with_replacement": (
        MATERIALIZE,
        ("iterable",),
        TUPLES,
        "itertools.combinations_with_replacement",
    ),
    "itertools.permutations": (
        MATERIALIZE,
        ("iterable",),
        TUPLES,
        "itertools.permutations",
    ),
    "heapq.nlargest": (LARGEST, ("iterable",), NOTHING, None),
    "heapq.nsmallest": (LARGEST, ("iterable",), NOTHING, None),
    "itertools.islice": (LAZY, ("iterable",), ITEMS, "itertools.islice"),
    "itertools.dropwhile": (LAZY, ("iterable",), ITEMS, "itertools.dropwhile"),
    "itertools.takewhile": (LAZY, ("iterable",), ITEMS, "itertools.takewhile"),
    "itertools.filterfalse": (LAZY, ("iterable",), ITEMS, "itertools.filterfalse"),
    "itertools.compress": (LAZY, ("data", "selectors"), FIRST, "itertools.compress"),
    "itertools.cycle": (LAZY, ("iterable",), ITEMS, "itertools.cycle"),
    "itertools.accumulate": (LAZY, ("iterable",), ITEMS, "itertools.accumulate"),
    "itertools.pairwise": (LAZY, ("iterable",), TUPLES, "itertools.pairwise"),
    "itertools.batched": (LAZY, ("iterable",), TUPLES, "itertools.batched"),
    "itertools.zip_longest": (LAZY, ("*",), POSITIONS, "itertools.zip_longest"),
    "itertools.starmap": (STARMAP, ("iterable",), NOTHING, "itertools.starmap"),
    "itertools.groupby": (GROUPBY, ("iterable",), NOTHING, "itertools.groupby"),
    "itertools.tee": (TEE, ("iterable",), ITEMS, "itertools._tee"),
    "itertools.chain": (LAZY_ALL, ("iterables",), ITEMS, "itertools.chain"),
    "heapq.merge": (MERGE, ("iterables",), ITEMS, "generator"),
    "itertools.chain.from_iterable": (
        LAZY_OUTER,
        ("iterable",),
        ITEMS,
        "itertools.chain",
    ),
}
# The operations whose result gets an argument as a value, without
# iterating it: `zip_longest`'s fill value, `accumulate`'s first value.
LIBRARY_VALUES = {
    "itertools.zip_longest": "fillvalue",
    "itertools.accumulate": "initial",
}
# The operations that read a tuple, also of a subclass, without iterating
# it (`PyTuple_Check`): `math.dist`.
READS_TUPLES = frozenset({"math.dist"})
# A parameter of an operation that repeats its iterables (`product`): the
# positions of the items are not known where it is given.
REPEATS = {"itertools.product": "repeat"}
# The class of the groups of `groupby`.
GROUPER = "itertools._grouper"
# The builtins of the stubs that take an iterable and do not consume it.
NOT_CONSUMING = frozenset({"builtins.iter"})
# `next()` on a lazy object of the table advances it, as `next(x)` does.
for _kind in {entry[3] for entry in LIBRARY_ITERATION.values()} | {GROUPER}:
    if _kind is not None and (_kind, "__next__") not in METHODS:
        METHODS[(_kind, "__next__")] = ("()", "advance")

# What a builtin that asks the length of what it iterates calls on it
# before it iterates it (CPython's `PyObject_LengthHint`): its `__len__`,
# else its `__length_hint__`. An entry of a protocol plan: the method and
# the methods whose definition makes Python skip it. The fallback to
# `__length_hint__` after a `__len__` that raises `TypeError` is not
# modelled. Every supported version counts: `tuple(x)` and a call that
# unpacks one argument alone, `f(*x)`, ask on 3.12 and 3.13 only; `list(x)`,
# `list.extend`, `+=` on a list, `sorted`, the unpacking in a list or tuple
# display and in any other call ask on every version.
LENGTH_HINT = (("__len__", ()), ("__length_hint__", ("__len__",)))
# Markers in the `unless` of a length hint: a class of the MRO defines the
# method, an analysed class or an outside class whose stubs define it (see
# `hierarchy._defines`). A buffer exporter defines `__buffer__` (`bytes`,
# `bytearray`, `memoryview`, `array.array`); an iterable, `__iter__`
# (`collections.abc.Sequence`). Only these plans test the outside classes:
# another plan that lists `__buffer__` (the overloads of `int` and `float`
# put `Buffer` first, where CPython calls `__int__` and `__float__` first)
# sees analysed definitions only.
BUFFER_EXPORTER = "<defines __buffer__>"
# In the `unless` of an iteration: a class that derives from `tuple`, whose
# storage `math.dist` reads (see `hierarchy._defines`).
TUPLE_STORAGE = "<derives from tuple>"
ITERABLE = "<defines __iter__>"
REVERSIBLE = "<defines __reversed__>"
DEFINES_MARKERS = {
    BUFFER_EXPORTER: "__buffer__",
    ITERABLE: "__iter__",
    REVERSIBLE: "__reversed__",
}
# `bytes(x)` takes `__bytes__`, then `__index__`, then a buffer, before it
# iterates x; `bytearray.extend(x)` takes a buffer first.
BYTES_LENGTH_HINT = (
    ("__len__", ("__bytes__", "__index__", BUFFER_EXPORTER)),
    ("__length_hint__", ("__len__", "__bytes__", "__index__", BUFFER_EXPORTER)),
)
BUFFER_LENGTH_HINT = (
    ("__len__", (BUFFER_EXPORTER,)),
    ("__length_hint__", ("__len__", BUFFER_EXPORTER)),
)
# What the iterator that the sequence protocol makes asks of its sequence
# when its length is asked (CPython's `iter_len`): `__len__` only. Where an
# outside base defines `__iter__` (the mixin of `Sequence`, a generator),
# Python iterates through it, not through the sequence protocol.
SEQUENCE_LENGTH = (("__len__", (ITERABLE,)),)
# What a `reversed` object asks of its sequence when its length is asked
# (`reversed_len`): `__len__` again, where `reversed()` made one; where a
# class of the MRO defines `__reversed__` (also the mixin of `Sequence`),
# `reversed()` returns what that returns.
REVERSED_LENGTH = (("__len__", (REVERSIBLE,)),)
# The builtins of the stubs that ask the length of an argument, by
# definition path: the parameter and the plan. With `ITERATOR`, they ask the
# iterator that `iter()` of the argument gives: `str.join` makes a list of
# `iter(x)` (CPython's `PySequence_Fast`), so it asks x itself only where
# `x.__iter__` returns x.
ARGUMENT, ITERATOR = "argument", "iterator"
LENGTH_HINTS = {
    "builtins.sorted": ("iterable", LENGTH_HINT, ARGUMENT),
    "builtins.bytes": ("o", BYTES_LENGTH_HINT, ARGUMENT),
    "builtins.bytearray.extend": ("iterable_of_ints", BUFFER_LENGTH_HINT, ARGUMENT),
    "builtins.str.join": ("iterable", LENGTH_HINT, ITERATOR),
    "builtins.bytes.join": ("iterable_of_bytes", LENGTH_HINT, ITERATOR),
    "builtins.bytearray.join": ("iterable_of_bytes", LENGTH_HINT, ITERATOR),
}

# The methods of the builtin sets, and `dict.fromkeys`, that the stubs
# describe and that hash what they get (see `Containers.add_hash`), by stub
# path: the parameter, and whether its argument is an iterable of keys
# (else one key).
_SET_OPERATIONS = (
    "union",
    "intersection",
    "difference",
    "symmetric_difference",
    "issubset",
    "issuperset",
    "isdisjoint",
)
HASHED_ARGUMENTS = {
    "builtins.set.remove": ("element", False),
    "builtins.set.discard": ("element", False),
    **{
        f"builtins.{kind}.{name}": ("s", True)
        for kind in ("set", "frozenset")
        for name in _SET_OPERATIONS
    },
    **{
        f"builtins.set.{name}_update": ("s", True)
        for name in ("intersection", "difference", "symmetric_difference")
    },
    "builtins.dict.fromkeys": ("iterable", True),
}

# The classes of `collections` whose instances are containers, by stub
# class: the builtin container whose elements they keep in the same way, and
# whose modelled methods (`METHODS`) they share where the table lists none
# of their own; then their constructor, as an entry of `FUNCTIONS`.
CONTAINER_CLASSES = {
    "collections.OrderedDict": (
        "dict",
        ("(mapping=(), /, **kwargs)", "dict", "collections.OrderedDict"),
    ),
    "collections.defaultdict": (
        "dict",
        ("(default_factory=None, mapping=(), /, **kwargs)", "defaultdict"),
    ),
    "collections.Counter": ("dict", ("(iterable=(), /, **kwargs)", "counter")),
    "collections.deque": (
        "list",
        ("(iterable=(), maxlen=None)", "collection", "collections.deque"),
    ),
}


def builtin_kind(kind):
    """The builtin container whose elements a container of `kind` keeps:
    `dict` for `collections.OrderedDict`, the kind itself for the others."""
    entry = CONTAINER_CLASSES.get(kind)
    return kind if entry is None else entry[0]


def method_model(kind, method):
    """The entry of the modelled method `method` of an object of `kind`: its
    own, else that of its builtin container; None if it has none."""
    return METHODS.get((kind, method)) or METHODS.get((builtin_kind(kind), method))


# The library functions other than the builtins that call what they are
# given, by stub path: the parameter whose callable they call, with one
# argument. They are C code with a documented call: `re.sub` and `re.subn`
# call a callable replacement with each match.
CALLS_BACK = {
    "re.sub": "repl",
    "re.subn": "repl",
    "re.Pattern.sub": "repl",
    "re.Pattern.subn": "repl",
}

# Variables of the standard library whose values have a concrete class that
# the stubs do not give, by stub path: the class. The interpreter makes the
# standard streams `io.TextIOWrapper` objects; the stubs type them as the
# abstract `TextIO`.
VARIABLE_TYPES = {
    "sys.stdin": "_io.TextIOWrapper",
    "sys.stdout": "_io.TextIOWrapper",
    "sys.stderr": "_io.TextIOWrapper",
}

# The functions that open a file as `io.open` does, by stub path (`io.open`
# is `builtins.open`). Their stubs give an overload per kind of mode, whose
# `Literal` modes the stub data reduces to `str`; `opened_class` decides.
OPENERS = frozenset({"builtins.open", "os.fdopen", "pathlib.Path.open"})


def opened_class(mode, unbuffered):
    """The stub class of the file object that `io.open` makes for the str
    `mode`, with `buffering=0` if `unbuffered`; None where it raises
    `ValueError`: a mode of other letters than `rwaxbt+`, with a repeated
    one, without exactly one of `rwax`, or with both `b` and `t`, and
    unbuffered text."""
    letters = set(mode)
    if len(letters) < len(mode) or not letters <= set("rwaxbt+"):
        return None
    if len(letters & set("rwax")) != 1 or {"b", "t"} <= letters:
        return None
    if "b" not in letters:
        return None if unbuffered else "_io.TextIOWrapper"
    if unbuffered:
        return "_io.FileIO"
    if "+" in letters:
        return "_io.BufferedRandom"
    return "_io.BufferedReader" if "r" in letters else "_io.BufferedWriter"


# The accessor of a property for each descriptor method.
PROPERTY_ACCESSORS = {"__get__": "fget", "__set__": "fset", "__delete__": "fdel"}

# The attributes of a builtin object that hold what it wraps, by type name.
WRAPPED = {
    "staticmethod": ("__func__",),
    "classmethod": ("__func__",),
    "property": ("fget", "fset", "fdel"),
}

# Library callables that return one of their arguments where their stubs do
# not say so (`dataclass(frozen=True)` returns a callable; `update_wrapper`
# a stub-only type; `typing.cast` the declared type), by qualified name,
# whether the analysis analyses them or not: their signature, the parameter
# that the call returns, and the name of the decorator it returns
# otherwise. Stubs of the form `(x: T) -> T` (`typing.final`,
# `abc.abstractmethod`) say it for the others.
# If the call may omit that parameter, or there is none, the call returns a
# decorator: a callable that returns its argument, named as it runs
# (`@dataclass(frozen=True)` applies the closure `dataclasses.dataclass.wrap`,
# `functools.wraps(f)` a `functools.partial` of `update_wrapper`), or after
# the callable if the entry names none.
RETURNS_ARGUMENT = {
    "dataclasses.dataclass": (
        "(cls=None, /, **options)",
        "cls",
        "dataclasses.dataclass.wrap",
    ),
    "functools.update_wrapper": (
        "(wrapper, wrapped, assigned=(), updated=())",
        "wrapper",
    ),
    "functools.wraps": (
        "(wrapped, assigned=(), updated=())",
        None,
        "functools.partial.__call__",
    ),
    "typing.cast": ("(typ, val)", "val"),
}

# The signature of the decorator that such a callable returns.
DECORATOR = ("(argument, /)", "argument")

# Library decorators whose stubs return a callable type where CPython returns
# a closure that it defines inside the decorator, by stub path: the closure's
# name (micro-benchmark README, "Functions without an attribute path"). A call
# of the decorated function calls that closure first (Lib/contextlib.py and
# Lib/functools.py of CPython 3.12 to 3.15):
# - `contextmanager` and `asynccontextmanager` return `helper`
#   (`@wraps(func) def helper(*args, **kwds)`), which makes the
#   `_GeneratorContextManager` or `_AsyncGeneratorContextManager`;
# - `lru_cache` given an int or None returns `decorating_function`, which
#   makes the `_lru_cache_wrapper` (given a function, it makes the wrapper at
#   once, as the stub's other overload says; so does `cache`).
CLOSURES = {
    "contextlib.contextmanager": "contextlib.contextmanager.helper",
    "contextlib.asynccontextmanager": "contextlib.asynccontextmanager.helper",
    "functools.lru_cache": "functools.lru_cache.decorating_function",
}

# Outside callables that read a namespace by reflection, by stub path: the
# signature that binds their arguments and the rule, which adds to what the
# stubs give (see reflection.py).
REFLECTION_CALLS = {
    "builtins.vars": ("(object=None, /)", "namespace"),
    "inspect.getmembers": ("(object, predicate=None)", "members"),
}
