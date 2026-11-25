FUNCTIONS = {
    "staticmethod": ("(function, /)", "wrap", "staticmethod"),
    "classmethod": ("(function, /)", "wrap", "classmethod"),
    "property": ("(fget=None, fset=None, fdel=None, doc=None)", "property"),
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

DYNAMIC_NAMES_MAX = 4

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

EAGER, MATERIALIZE, LARGEST = "eager", "materialize", "largest"
LAZY, TEE, STARMAP, GROUPBY = "lazy", "tee", "starmap", "groupby"
LAZY_ALL, LAZY_OUTER, MERGE = "lazy all", "lazy outer", "merge"
LAZY_MODES = frozenset({LAZY, TEE, STARMAP, GROUPBY, LAZY_ALL, LAZY_OUTER, MERGE})
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
    "itertools.repeat": (LAZY, (), ITEMS, "itertools.repeat"),
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
LIBRARY_VALUES = {
    "itertools.zip_longest": "fillvalue",
    "itertools.accumulate": "initial",
    "itertools.repeat": "object",
}
READS_TUPLES = frozenset({"math.dist"})
REPEATS = {"itertools.product": "repeat"}
GROUPER = "itertools._grouper"
NOT_CONSUMING = frozenset({"builtins.iter"})
for _kind in {entry[3] for entry in LIBRARY_ITERATION.values()} | {GROUPER}:
    if _kind is not None and (_kind, "__next__") not in METHODS:
        METHODS[(_kind, "__next__")] = ("()", "advance")

LENGTH_HINT = (("__len__", ()), ("__length_hint__", ("__len__",)))
BUFFER_EXPORTER = "<defines __buffer__>"
TUPLE_STORAGE = "<derives from tuple>"
ITERABLE = "<defines __iter__>"
REVERSIBLE = "<defines __reversed__>"
DEFINES_MARKERS = {
    BUFFER_EXPORTER: "__buffer__",
    ITERABLE: "__iter__",
    REVERSIBLE: "__reversed__",
}
BYTES_LENGTH_HINT = (
    ("__len__", ("__bytes__", "__index__", BUFFER_EXPORTER)),
    ("__length_hint__", ("__len__", "__bytes__", "__index__", BUFFER_EXPORTER)),
)
BUFFER_LENGTH_HINT = (
    ("__len__", (BUFFER_EXPORTER,)),
    ("__length_hint__", ("__len__", BUFFER_EXPORTER)),
)
SEQUENCE_LENGTH = (("__len__", (ITERABLE,)),)
REVERSED_LENGTH = (("__len__", (REVERSIBLE,)),)
ARGUMENT, ITERATOR = "argument", "iterator"
LENGTH_HINTS = {
    "builtins.sorted": ("iterable", LENGTH_HINT, ARGUMENT),
    "builtins.bytes": ("o", BYTES_LENGTH_HINT, ARGUMENT),
    "builtins.bytearray.extend": ("iterable_of_ints", BUFFER_LENGTH_HINT, ARGUMENT),
    "builtins.str.join": ("iterable", LENGTH_HINT, ITERATOR),
    "builtins.bytes.join": ("iterable_of_bytes", LENGTH_HINT, ITERATOR),
    "builtins.bytearray.join": ("iterable_of_bytes", LENGTH_HINT, ITERATOR),
}

_HASHING_SET_OPERATIONS = (
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
        for name in _HASHING_SET_OPERATIONS
    },
    **{
        f"builtins.set.{name}_update": ("s", True)
        for name in ("intersection", "difference", "symmetric_difference")
    },
    "builtins.dict.fromkeys": ("iterable", True),
}

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
    entry = CONTAINER_CLASSES.get(kind)
    return kind if entry is None else entry[0]


def method_model(kind, method):
    return METHODS.get((kind, method)) or METHODS.get((builtin_kind(kind), method))


CALLS_BACK = {
    "re.sub": "repl",
    "re.subn": "repl",
    "re.Pattern.sub": "repl",
    "re.Pattern.subn": "repl",
}

VARIABLE_TYPES = {
    "sys.stdin": "_io.TextIOWrapper",
    "sys.stdout": "_io.TextIOWrapper",
    "sys.stderr": "_io.TextIOWrapper",
}

OPENERS = frozenset({"builtins.open", "os.fdopen", "pathlib.Path.open"})


def opened_class(mode, unbuffered):
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


PROPERTY_ACCESSORS = {"__get__": "fget", "__set__": "fset", "__delete__": "fdel"}

WRAPPED_ATTRIBUTES_BY_TYPE = {
    "staticmethod": ("__func__",),
    "classmethod": ("__func__",),
    "property": ("fget", "fset", "fdel"),
}

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

RETURNED_DECORATOR_SIGNATURE = ("(argument, /)", "argument")

CLOSURES = {
    "contextlib.contextmanager": "contextlib.contextmanager.helper",
    "contextlib.asynccontextmanager": "contextlib.asynccontextmanager.helper",
    "functools.lru_cache": "functools.lru_cache.decorating_function",
}

DECORATING_CLOSURES = frozenset({"functools.lru_cache.decorating_function"})

VARIABLE_FUNCTIONS = {
    "timeit.default_timer": "time.perf_counter",
    "shutil.rmtree": "shutil.rmtree",
}

REFLECTION_CALLS = {
    "builtins.vars": ("(object=None, /)", "namespace"),
    "inspect.getmembers": ("(object, predicate=None)", "members"),
}
