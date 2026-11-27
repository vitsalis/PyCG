use std::collections::BTreeSet;

use crate::model::Signature;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Rule {
    Wrap,
    Property,
    PropertyInit,
    PropertyWith,
    PropertyRun,
    Collection,
    Dict,
    Iter,
    Enumerate,
    Zip,
    Reversed,
    Map,
    Filter,
    Next,
    Super,
    Type,
    Convert,
    Pow,
    Print,
    Getattr,
    Setattr,
    Delattr,
    Bind,
    Add,
    Extend,
    AnyElement,
    Copy,
    Update,
    Setdefault,
    Get,
    View,
    Lookup,
    Count,
    Case,
    Advance,
    Defaultdict,
    Counter,
    SpecialMethod,
    Namespace,
    Members,
}

impl Rule {
    pub fn name(self) -> &'static str {
        match self {
            Rule::Wrap => "wrap",
            Rule::Property => "property",
            Rule::PropertyInit => "property_init",
            Rule::PropertyWith => "property_with",
            Rule::PropertyRun => "property_run",
            Rule::Collection => "collection",
            Rule::Dict => "dict",
            Rule::Iter => "iter",
            Rule::Enumerate => "enumerate",
            Rule::Zip => "zip",
            Rule::Reversed => "reversed",
            Rule::Map => "map",
            Rule::Filter => "filter",
            Rule::Next => "next",
            Rule::Super => "super",
            Rule::Type => "type",
            Rule::Convert => "convert",
            Rule::Pow => "pow",
            Rule::Print => "print",
            Rule::Getattr => "getattr",
            Rule::Setattr => "setattr",
            Rule::Delattr => "delattr",
            Rule::Bind => "bind",
            Rule::Add => "add",
            Rule::Extend => "extend",
            Rule::AnyElement => "any_element",
            Rule::Copy => "copy",
            Rule::Update => "update",
            Rule::Setdefault => "setdefault",
            Rule::Get => "get",
            Rule::View => "view",
            Rule::Lookup => "lookup",
            Rule::Count => "count",
            Rule::Case => "case",
            Rule::Advance => "advance",
            Rule::Defaultdict => "defaultdict",
            Rule::Counter => "counter",
            Rule::SpecialMethod => "special_method",
            Rule::Namespace => "namespace",
            Rule::Members => "members",
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Model {
    pub signature: &'static str,
    pub rule: Rule,
    pub arguments: &'static [&'static str],
}

const fn model(signature: &'static str, rule: Rule, arguments: &'static [&'static str]) -> Model {
    Model {
        signature,
        rule,
        arguments,
    }
}

pub const DYNAMIC_NAMES_MAX: usize = 4;

pub static FUNCTIONS: &[(&str, Model)] = &[
    (
        "staticmethod",
        model("(function, /)", Rule::Wrap, &["staticmethod"]),
    ),
    (
        "classmethod",
        model("(function, /)", Rule::Wrap, &["classmethod"]),
    ),
    (
        "property",
        model(
            "(fget=None, fset=None, fdel=None, doc=None)",
            Rule::Property,
            &[],
        ),
    ),
    (
        "property.__init__",
        model(
            "(self, /, fget=None, fset=None, fdel=None, doc=None)",
            Rule::PropertyInit,
            &[],
        ),
    ),
    (
        "property.getter",
        model("(self, function, /)", Rule::PropertyWith, &["fget"]),
    ),
    (
        "property.setter",
        model("(self, function, /)", Rule::PropertyWith, &["fset"]),
    ),
    (
        "property.deleter",
        model("(self, function, /)", Rule::PropertyWith, &["fdel"]),
    ),
    (
        "property.__get__",
        model(
            "(self, instance, owner=None, /)",
            Rule::PropertyRun,
            &["fget"],
        ),
    ),
    (
        "property.__set__",
        model("(self, instance, value, /)", Rule::PropertyRun, &["fset"]),
    ),
    (
        "property.__delete__",
        model("(self, instance, /)", Rule::PropertyRun, &["fdel"]),
    ),
    (
        "list",
        model("(iterable=(), /)", Rule::Collection, &["list"]),
    ),
    (
        "tuple",
        model("(iterable=(), /)", Rule::Collection, &["tuple"]),
    ),
    ("set", model("(iterable=(), /)", Rule::Collection, &["set"])),
    (
        "frozenset",
        model("(iterable=(), /)", Rule::Collection, &["frozenset"]),
    ),
    ("dict", model("(mapping=(), /, **kwargs)", Rule::Dict, &[])),
    ("iter", model("(object, sentinel=None, /)", Rule::Iter, &[])),
    (
        "enumerate",
        model("(iterable, start=0)", Rule::Enumerate, &[]),
    ),
    ("zip", model("(*iterables, strict=False)", Rule::Zip, &[])),
    ("reversed", model("(sequence, /)", Rule::Reversed, &[])),
    (
        "map",
        model(
            "(function, iterable, /, *iterables, strict=False)",
            Rule::Map,
            &[],
        ),
    ),
    (
        "filter",
        model("(function, iterable, /)", Rule::Filter, &[]),
    ),
    (
        "next",
        model("(iterator, default=None, /)", Rule::Next, &[]),
    ),
    (
        "super",
        model("(type=None, object_or_type=None, /)", Rule::Super, &[]),
    ),
    (
        "type",
        model(
            "(object, bases=None, dict=None, /, **kwds)",
            Rule::Type,
            &[],
        ),
    ),
    (
        "str",
        model("(object='')", Rule::Convert, &["str", "object"]),
    ),
    ("repr", model("(obj, /)", Rule::Convert, &["repr", "obj"])),
    (
        "format",
        model(
            "(value, format_spec='', /)",
            Rule::Convert,
            &["format", "value", "format_spec"],
        ),
    ),
    ("pow", model("(base, exp, mod=None)", Rule::Pow, &[])),
    (
        "print",
        model(
            "(*values, sep=None, end=None, file=None, flush=False)",
            Rule::Print,
            &[],
        ),
    ),
    (
        "getattr",
        model(
            "(object, name, default=None, /)",
            Rule::Getattr,
            &["getattr"],
        ),
    ),
    (
        "hasattr",
        model("(obj, name, /)", Rule::Getattr, &["hasattr"]),
    ),
    (
        "setattr",
        model("(obj, name, value, /)", Rule::Setattr, &[]),
    ),
    ("delattr", model("(obj, name, /)", Rule::Delattr, &[])),
];

const ADVANCE: Model = model("()", Rule::Advance, &[]);

pub static METHODS: &[((&str, &str), Model)] = &[
    (
        ("classmethod", "__get__"),
        model("(instance, owner=None, /)", Rule::Bind, &[]),
    ),
    (
        ("staticmethod", "__get__"),
        model("(instance, owner=None, /)", Rule::Bind, &[]),
    ),
    (
        ("list", "append"),
        model("(object, /)", Rule::Add, &["object"]),
    ),
    (
        ("list", "insert"),
        model("(index, object, /)", Rule::Add, &["object"]),
    ),
    (
        ("list", "extend"),
        model("(iterable, /)", Rule::Extend, &[]),
    ),
    (
        ("list", "pop"),
        model("(index=-1, /)", Rule::AnyElement, &[]),
    ),
    (("list", "copy"), model("()", Rule::Copy, &[])),
    (
        ("set", "add"),
        model("(element, /)", Rule::Add, &["element"]),
    ),
    (("set", "update"), model("(*others)", Rule::Extend, &[])),
    (("set", "pop"), model("()", Rule::AnyElement, &[])),
    (("set", "copy"), model("()", Rule::Copy, &[])),
    (("frozenset", "copy"), model("()", Rule::Copy, &[])),
    (
        ("dict", "update"),
        model("(mapping=(), /, **kwargs)", Rule::Update, &[]),
    ),
    (
        ("dict", "setdefault"),
        model("(key, default=None, /)", Rule::Setdefault, &[]),
    ),
    (
        ("dict", "get"),
        model("(key, default=None, /)", Rule::Get, &[]),
    ),
    (
        ("dict", "pop"),
        model("(key, default=None, /)", Rule::Get, &[]),
    ),
    (("dict", "copy"), model("()", Rule::Copy, &[])),
    (("dict", "keys"), model("()", Rule::View, &["dict_keys"])),
    (
        ("dict", "values"),
        model("()", Rule::View, &["dict_values"]),
    ),
    (("dict", "items"), model("()", Rule::View, &["dict_items"])),
    (
        ("collections.OrderedDict", "move_to_end"),
        model("(key, last=True)", Rule::Lookup, &[]),
    ),
    (
        ("collections.deque", "appendleft"),
        model("(x, /)", Rule::Add, &["x"]),
    ),
    (
        ("collections.deque", "extendleft"),
        model("(iterable, /)", Rule::Extend, &[]),
    ),
    (
        ("collections.deque", "popleft"),
        model("()", Rule::AnyElement, &[]),
    ),
    (
        ("collections.Counter", "update"),
        model("(iterable=(), /, **kwargs)", Rule::Count, &[]),
    ),
    (("str", "lower"), model("()", Rule::Case, &["lower"])),
    (("str", "upper"), model("()", Rule::Case, &["upper"])),
    (("str", "casefold"), model("()", Rule::Case, &["lower"])),
    (("generator", "__next__"), ADVANCE),
    (
        ("generator", "send"),
        model("(value, /)", Rule::Advance, &[]),
    ),
    (
        ("generator", "throw"),
        model("(typ=None, val=None, tb=None, /)", Rule::Advance, &[]),
    ),
    (("iterator", "__next__"), ADVANCE),
    (("callable_iterator", "__next__"), ADVANCE),
    (("itertools._grouper", "__next__"), ADVANCE),
    (("itertools._tee", "__next__"), ADVANCE),
    (("itertools.accumulate", "__next__"), ADVANCE),
    (("itertools.batched", "__next__"), ADVANCE),
    (("itertools.chain", "__next__"), ADVANCE),
    (("itertools.combinations", "__next__"), ADVANCE),
    (
        ("itertools.combinations_with_replacement", "__next__"),
        ADVANCE,
    ),
    (("itertools.compress", "__next__"), ADVANCE),
    (("itertools.cycle", "__next__"), ADVANCE),
    (("itertools.dropwhile", "__next__"), ADVANCE),
    (("itertools.filterfalse", "__next__"), ADVANCE),
    (("itertools.groupby", "__next__"), ADVANCE),
    (("itertools.islice", "__next__"), ADVANCE),
    (("itertools.pairwise", "__next__"), ADVANCE),
    (("itertools.permutations", "__next__"), ADVANCE),
    (("itertools.product", "__next__"), ADVANCE),
    (("itertools.repeat", "__next__"), ADVANCE),
    (("itertools.starmap", "__next__"), ADVANCE),
    (("itertools.takewhile", "__next__"), ADVANCE),
    (("itertools.zip_longest", "__next__"), ADVANCE),
];

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum IterationMode {
    Eager,
    Materialize,
    Largest,
    Lazy,
    Tee,
    Starmap,
    Groupby,
    LazyAll,
    LazyOuter,
    Merge,
}

impl IterationMode {
    pub fn name(self) -> &'static str {
        match self {
            IterationMode::Eager => "eager",
            IterationMode::Materialize => "materialize",
            IterationMode::Largest => "largest",
            IterationMode::Lazy => "lazy",
            IterationMode::Tee => "tee",
            IterationMode::Starmap => "starmap",
            IterationMode::Groupby => "groupby",
            IterationMode::LazyAll => "lazy all",
            IterationMode::LazyOuter => "lazy outer",
            IterationMode::Merge => "merge",
        }
    }

    pub fn is_lazy(self) -> bool {
        match self {
            IterationMode::Lazy
            | IterationMode::Tee
            | IterationMode::Starmap
            | IterationMode::Groupby
            | IterationMode::LazyAll
            | IterationMode::LazyOuter
            | IterationMode::Merge => true,
            IterationMode::Eager | IterationMode::Materialize | IterationMode::Largest => false,
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Shape {
    Items,
    First,
    Tuples,
    Positions,
    Nothing,
}

impl Shape {
    pub fn name(self) -> &'static str {
        match self {
            Shape::Items => "items",
            Shape::First => "first",
            Shape::Tuples => "tuples",
            Shape::Positions => "positions",
            Shape::Nothing => "nothing",
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct LibraryOperation {
    pub mode: IterationMode,
    pub roles: &'static [&'static str],
    pub shape: Shape,
    pub kind: Option<&'static str>,
}

const fn operation(
    mode: IterationMode,
    roles: &'static [&'static str],
    shape: Shape,
    kind: Option<&'static str>,
) -> LibraryOperation {
    LibraryOperation {
        mode,
        roles,
        shape,
        kind,
    }
}

use IterationMode::{
    Eager, Groupby, Largest, Lazy, LazyAll, LazyOuter, Materialize, Merge, Starmap, Tee,
};
use Shape::{First, Items, Nothing, Positions, Tuples};

pub static LIBRARY_ITERATION: &[(&str, LibraryOperation)] = &[
    (
        "functools.reduce",
        operation(Eager, &["iterable"], Nothing, None),
    ),
    ("math.sumprod", operation(Eager, &["p", "q"], Nothing, None)),
    ("math.fsum", operation(Eager, &["seq"], Nothing, None)),
    ("math.prod", operation(Eager, &["iterable"], Nothing, None)),
    ("_operator.countOf", operation(Eager, &["a"], Nothing, None)),
    ("_operator.indexOf", operation(Eager, &["a"], Nothing, None)),
    (
        "math.dist",
        operation(Materialize, &["p", "q"], Nothing, None),
    ),
    (
        "itertools.product",
        operation(Materialize, &["*"], Positions, Some("itertools.product")),
    ),
    (
        "itertools.combinations",
        operation(
            Materialize,
            &["iterable"],
            Tuples,
            Some("itertools.combinations"),
        ),
    ),
    (
        "itertools.combinations_with_replacement",
        operation(
            Materialize,
            &["iterable"],
            Tuples,
            Some("itertools.combinations_with_replacement"),
        ),
    ),
    (
        "itertools.permutations",
        operation(
            Materialize,
            &["iterable"],
            Tuples,
            Some("itertools.permutations"),
        ),
    ),
    (
        "heapq.nlargest",
        operation(Largest, &["iterable"], Nothing, None),
    ),
    (
        "heapq.nsmallest",
        operation(Largest, &["iterable"], Nothing, None),
    ),
    (
        "itertools.islice",
        operation(Lazy, &["iterable"], Items, Some("itertools.islice")),
    ),
    (
        "itertools.dropwhile",
        operation(Lazy, &["iterable"], Items, Some("itertools.dropwhile")),
    ),
    (
        "itertools.takewhile",
        operation(Lazy, &["iterable"], Items, Some("itertools.takewhile")),
    ),
    (
        "itertools.filterfalse",
        operation(Lazy, &["iterable"], Items, Some("itertools.filterfalse")),
    ),
    (
        "itertools.compress",
        operation(
            Lazy,
            &["data", "selectors"],
            First,
            Some("itertools.compress"),
        ),
    ),
    (
        "itertools.cycle",
        operation(Lazy, &["iterable"], Items, Some("itertools.cycle")),
    ),
    (
        "itertools.repeat",
        operation(Lazy, &[], Items, Some("itertools.repeat")),
    ),
    (
        "itertools.accumulate",
        operation(Lazy, &["iterable"], Items, Some("itertools.accumulate")),
    ),
    (
        "itertools.pairwise",
        operation(Lazy, &["iterable"], Tuples, Some("itertools.pairwise")),
    ),
    (
        "itertools.batched",
        operation(Lazy, &["iterable"], Tuples, Some("itertools.batched")),
    ),
    (
        "itertools.zip_longest",
        operation(Lazy, &["*"], Positions, Some("itertools.zip_longest")),
    ),
    (
        "itertools.starmap",
        operation(Starmap, &["iterable"], Nothing, Some("itertools.starmap")),
    ),
    (
        "itertools.groupby",
        operation(Groupby, &["iterable"], Nothing, Some("itertools.groupby")),
    ),
    (
        "itertools.tee",
        operation(Tee, &["iterable"], Items, Some("itertools._tee")),
    ),
    (
        "itertools.chain",
        operation(LazyAll, &["iterables"], Items, Some("itertools.chain")),
    ),
    (
        "heapq.merge",
        operation(Merge, &["iterables"], Items, Some("generator")),
    ),
    (
        "itertools.chain.from_iterable",
        operation(LazyOuter, &["iterable"], Items, Some("itertools.chain")),
    ),
];

pub static KEYED_OPERATIONS: &[&str] = &["heapq.nlargest", "heapq.nsmallest", "heapq.merge"];

pub static KEYED_SEQUENCES: &[(&str, &[&str])] = &[
    ("_bisect.bisect_left", &[]),
    ("_bisect.bisect_right", &[]),
    ("_bisect.insort_left", &["x"]),
    ("_bisect.insort_right", &["x"]),
];

pub static KEY_WRAPPERS: &[(&str, &str)] = &[("functools.cmp_to_key", "mycmp")];

pub static LIBRARY_VALUES: &[(&str, &str)] = &[
    ("itertools.zip_longest", "fillvalue"),
    ("itertools.accumulate", "initial"),
    ("itertools.repeat", "object"),
];

pub static READS_TUPLES: &[&str] = &["math.dist"];

pub static REPEATS: &[(&str, &str)] = &[("itertools.product", "repeat")];

pub const GROUPER: &str = "itertools._grouper";

pub static NOT_CONSUMING: &[&str] = &["builtins.iter"];

pub const BUFFER_EXPORTER: &str = "<defines __buffer__>";
pub const TUPLE_STORAGE: &str = "<derives from tuple>";
pub const ITERABLE: &str = "<defines __iter__>";
pub const REVERSIBLE: &str = "<defines __reversed__>";

pub static DEFINES_MARKERS: &[(&str, &str)] = &[
    (BUFFER_EXPORTER, "__buffer__"),
    (ITERABLE, "__iter__"),
    (REVERSIBLE, "__reversed__"),
];

pub type LengthPlan = &'static [(&'static str, &'static [&'static str])];

pub static LENGTH_HINT: LengthPlan = &[("__len__", &[]), ("__length_hint__", &["__len__"])];
pub static BYTES_LENGTH_HINT: LengthPlan = &[
    ("__len__", &["__bytes__", "__index__", BUFFER_EXPORTER]),
    (
        "__length_hint__",
        &["__len__", "__bytes__", "__index__", BUFFER_EXPORTER],
    ),
];
pub static BUFFER_LENGTH_HINT: LengthPlan = &[
    ("__len__", &[BUFFER_EXPORTER]),
    ("__length_hint__", &["__len__", BUFFER_EXPORTER]),
];
pub static SEQUENCE_LENGTH: LengthPlan = &[("__len__", &[ITERABLE])];
pub static REVERSED_LENGTH: LengthPlan = &[("__len__", &[REVERSIBLE])];

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum LengthSource {
    Argument,
    Iterator,
}

impl LengthSource {
    pub fn name(self) -> &'static str {
        match self {
            LengthSource::Argument => "argument",
            LengthSource::Iterator => "iterator",
        }
    }
}

pub static LENGTH_HINTS: &[(&str, (&str, LengthPlan, LengthSource))] = &[
    (
        "builtins.sorted",
        ("iterable", LENGTH_HINT, LengthSource::Argument),
    ),
    (
        "builtins.bytes",
        ("o", BYTES_LENGTH_HINT, LengthSource::Argument),
    ),
    (
        "builtins.bytearray.extend",
        (
            "iterable_of_ints",
            BUFFER_LENGTH_HINT,
            LengthSource::Argument,
        ),
    ),
    (
        "builtins.str.join",
        ("iterable", LENGTH_HINT, LengthSource::Iterator),
    ),
    (
        "builtins.bytes.join",
        ("iterable_of_bytes", LENGTH_HINT, LengthSource::Iterator),
    ),
    (
        "builtins.bytearray.join",
        ("iterable_of_bytes", LENGTH_HINT, LengthSource::Iterator),
    ),
];

pub static HASHED_ARGUMENTS: &[(&str, (&str, bool))] = &[
    ("builtins.set.remove", ("element", false)),
    ("builtins.set.discard", ("element", false)),
    ("builtins.set.union", ("s", true)),
    ("builtins.set.intersection", ("s", true)),
    ("builtins.set.difference", ("s", true)),
    ("builtins.set.symmetric_difference", ("s", true)),
    ("builtins.set.issubset", ("s", true)),
    ("builtins.set.issuperset", ("s", true)),
    ("builtins.set.isdisjoint", ("s", true)),
    ("builtins.frozenset.union", ("s", true)),
    ("builtins.frozenset.intersection", ("s", true)),
    ("builtins.frozenset.difference", ("s", true)),
    ("builtins.frozenset.symmetric_difference", ("s", true)),
    ("builtins.frozenset.issubset", ("s", true)),
    ("builtins.frozenset.issuperset", ("s", true)),
    ("builtins.frozenset.isdisjoint", ("s", true)),
    ("builtins.set.intersection_update", ("s", true)),
    ("builtins.set.difference_update", ("s", true)),
    ("builtins.set.symmetric_difference_update", ("s", true)),
    ("builtins.dict.fromkeys", ("iterable", true)),
];

pub static CONTAINER_CLASSES: &[(&str, (&str, Model))] = &[
    (
        "collections.OrderedDict",
        (
            "dict",
            model(
                "(mapping=(), /, **kwargs)",
                Rule::Dict,
                &["collections.OrderedDict"],
            ),
        ),
    ),
    (
        "collections.defaultdict",
        (
            "dict",
            model(
                "(default_factory=None, mapping=(), /, **kwargs)",
                Rule::Defaultdict,
                &[],
            ),
        ),
    ),
    (
        "collections.Counter",
        (
            "dict",
            model("(iterable=(), /, **kwargs)", Rule::Counter, &[]),
        ),
    ),
    (
        "collections.deque",
        (
            "list",
            model(
                "(iterable=(), maxlen=None)",
                Rule::Collection,
                &["collections.deque"],
            ),
        ),
    ),
];

pub static CALLS_BACK: &[(&str, &str)] = &[
    ("re.sub", "repl"),
    ("re.subn", "repl"),
    ("re.Pattern.sub", "repl"),
    ("re.Pattern.subn", "repl"),
];

pub static VARIABLE_TYPES: &[(&str, &str)] = &[
    ("sys.stdin", "_io.TextIOWrapper"),
    ("sys.stdout", "_io.TextIOWrapper"),
    ("sys.stderr", "_io.TextIOWrapper"),
];

pub static OPENERS: &[&str] = &["builtins.open", "os.fdopen", "pathlib.Path.open"];

pub static PROPERTY_ACCESSORS: &[(&str, &str)] = &[
    ("__get__", "fget"),
    ("__set__", "fset"),
    ("__delete__", "fdel"),
];

pub static WRAPPED_ATTRIBUTES_BY_TYPE: &[(&str, &[&str])] = &[
    ("staticmethod", &["__func__"]),
    ("classmethod", &["__func__"]),
    ("property", &["fget", "fset", "fdel"]),
];

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct ReturnsArgument {
    pub signature: &'static str,
    pub argument: Option<&'static str>,
    pub wrapper: Option<&'static str>,
}

pub static RETURNS_ARGUMENT: &[(&str, ReturnsArgument)] = &[
    (
        "dataclasses.dataclass",
        ReturnsArgument {
            signature: "(cls=None, /, **options)",
            argument: Some("cls"),
            wrapper: Some("dataclasses.dataclass.wrap"),
        },
    ),
    (
        "functools.update_wrapper",
        ReturnsArgument {
            signature: "(wrapper, wrapped, assigned=(), updated=())",
            argument: Some("wrapper"),
            wrapper: None,
        },
    ),
    (
        "functools.wraps",
        ReturnsArgument {
            signature: "(wrapped, assigned=(), updated=())",
            argument: None,
            wrapper: Some("functools.partial.__call__"),
        },
    ),
    (
        "typing.cast",
        ReturnsArgument {
            signature: "(typ, val)",
            argument: Some("val"),
            wrapper: None,
        },
    ),
];

pub static RETURNED_DECORATOR: ReturnsArgument = ReturnsArgument {
    signature: "(argument, /)",
    argument: Some("argument"),
    wrapper: None,
};

pub static CLOSURES: &[(&str, &str)] = &[
    (
        "contextlib.contextmanager",
        "contextlib.contextmanager.helper",
    ),
    (
        "contextlib.asynccontextmanager",
        "contextlib.asynccontextmanager.helper",
    ),
    (
        "functools.lru_cache",
        "functools.lru_cache.decorating_function",
    ),
];

pub static DECORATING_CLOSURES: &[&str] = &["functools.lru_cache.decorating_function"];

pub static VARIABLE_FUNCTIONS: &[(&str, &str)] = &[
    ("timeit.default_timer", "time.perf_counter"),
    ("shutil.rmtree", "shutil.rmtree"),
];

pub static CONCRETE_CLASSES: &[(&str, &str)] =
    &[("ctypes.CDLL.__init__._FuncPtr", "_ctypes.CFuncPtr")];

pub static STUB_RESULTS: &[(&str, &str)] = &[
    ("ctypes.CDLL.__getattr__", "ctypes.CDLL.__init__._FuncPtr"),
    ("ctypes.CDLL.__getitem__", "ctypes.CDLL.__init__._FuncPtr"),
];

pub static CACHED_FUNCTIONS: &[(&str, &str)] =
    &[("urllib.parse.urlsplit", "functools._lru_cache_wrapper")];

pub static SPECIAL_METHOD_CALLS: &[(&str, Model)] = &[(
    "copy.replace",
    model(
        "(obj, /, **changes)",
        Rule::SpecialMethod,
        &["obj", "__replace__"],
    ),
)];

pub static REFLECTION_CALLS: &[(&str, Model)] = &[
    (
        "builtins.vars",
        model("(object=None, /)", Rule::Namespace, &[]),
    ),
    (
        "inspect.getmembers",
        model("(object, predicate=None)", Rule::Members, &[]),
    ),
];

pub fn lookup<K: PartialEq + ?Sized, V>(
    table: &'static [(&'static K, V)],
    key: &K,
) -> Option<&'static V> {
    table
        .iter()
        .find(|(found, _)| *found == key)
        .map(|(_, value)| value)
}

pub fn function_model(name: &str) -> Option<&'static Model> {
    lookup(FUNCTIONS, name)
}

pub fn method(kind: &str, name: &str) -> Option<&'static Model> {
    METHODS
        .iter()
        .find(|((owner, method), _)| *owner == kind && *method == name)
        .map(|(_, found)| found)
}

pub fn builtin_kind(kind: &str) -> &str {
    match lookup(CONTAINER_CLASSES, kind) {
        Some((builtin, _)) => builtin,
        None => kind,
    }
}

pub fn method_model(kind: &str, name: &str) -> Option<&'static Model> {
    method(kind, name).or_else(|| method(builtin_kind(kind), name))
}

const MODE_LETTERS: &str = "rwaxbt+";
const ACTION_LETTERS: &str = "rwax";

pub fn opened_class(mode: &str, unbuffered: bool) -> Option<&'static str> {
    let letters: BTreeSet<char> = mode.chars().collect();
    if letters.len() < mode.chars().count()
        || !letters.iter().all(|letter| MODE_LETTERS.contains(*letter))
    {
        return None;
    }
    let actions = letters
        .iter()
        .filter(|letter| ACTION_LETTERS.contains(**letter))
        .count();
    if actions != 1 || (letters.contains(&'b') && letters.contains(&'t')) {
        return None;
    }
    if !letters.contains(&'b') {
        return if unbuffered {
            None
        } else {
            Some("_io.TextIOWrapper")
        };
    }
    if unbuffered {
        return Some("_io.FileIO");
    }
    if letters.contains(&'+') {
        return Some("_io.BufferedRandom");
    }
    Some(if letters.contains(&'r') {
        "_io.BufferedReader"
    } else {
        "_io.BufferedWriter"
    })
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum DefaultConstant {
    Str(Box<str>),
    Int(u64),
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ModelSignature {
    pub signature: Signature,
    pub constants: Vec<(Box<str>, DefaultConstant)>,
}

pub fn parse_signature(text: &str) -> ModelSignature {
    let inner = text
        .strip_prefix('(')
        .and_then(|rest| rest.strip_suffix(')'))
        .unwrap_or_else(|| panic!("a model signature is parenthesised: {text}"));
    let mut positional = Vec::new();
    let mut positional_only_count = 0;
    let mut keyword_only = Vec::new();
    let mut vararg = None;
    let mut kwarg = None;
    let mut constants = Vec::new();
    let mut after_star = false;
    for part in inner.split(", ").filter(|part| !part.is_empty()) {
        if part == "/" {
            positional_only_count = positional.len();
            continue;
        }
        if let Some(name) = part.strip_prefix("**") {
            kwarg = Some(Box::from(name));
            continue;
        }
        if let Some(name) = part.strip_prefix('*') {
            if !name.is_empty() {
                vararg = Some(Box::from(name));
            }
            after_star = true;
            continue;
        }
        let (name, default) = match part.split_once('=') {
            Some((name, default)) => (name, Some(default)),
            None => (name_of(part), None),
        };
        if let Some(constant) = default.and_then(default_constant) {
            constants.push((Box::from(name), constant));
        }
        if after_star {
            keyword_only.push(Box::from(name));
        } else {
            positional.push(Box::from(name));
        }
    }
    ModelSignature {
        signature: Signature::new(
            positional,
            positional_only_count,
            keyword_only,
            vararg,
            kwarg,
        ),
        constants,
    }
}

fn name_of(part: &str) -> &str {
    assert!(
        part.chars()
            .all(|character| character == '_' || character.is_ascii_alphanumeric()),
        "a model parameter is a name: {part}"
    );
    part
}

fn default_constant(default: &str) -> Option<DefaultConstant> {
    if let Some(text) = default
        .strip_prefix('\'')
        .and_then(|rest| rest.strip_suffix('\''))
    {
        assert!(
            !text.contains(['\'', '\\']),
            "a plain model default: {default}"
        );
        return Some(DefaultConstant::Str(Box::from(text)));
    }
    if default.bytes().all(|byte| byte.is_ascii_digit()) {
        return Some(DefaultConstant::Int(
            default.parse().expect("a decimal default"),
        ));
    }
    assert!(
        matches!(default, "None" | "True" | "False" | "()") || default.starts_with('-'),
        "a model default that is no constant: {default}"
    );
    None
}
