import argparse
import ast
import json
import random
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pycg.analysis import builtin_models, model, mro, stubs  # noqa: E402
from pycg.analysis.builder import NESTING_MAX, nesting  # noqa: E402
from pycg.analysis.builtin_rules import _signature  # noqa: E402

VECTORS_DIRECTORY = ROOT / "crates" / "stubs" / "tests" / "vectors"
MODEL_VECTORS = ROOT / "crates" / "analysis" / "tests" / "vectors" / "model.rs"
MODELS_VECTORS = ROOT / "crates" / "analysis" / "tests" / "vectors" / "models.rs"
NESTING_VECTORS = ROOT / "crates" / "analysis" / "tests" / "vectors" / "nesting.rs"
BUILDER_VECTORS = ROOT / "crates" / "dump" / "tests" / "vectors" / "builder"
DUMP = ROOT / "tools" / "parity" / "dump.py"
BUILDER_FILES = {
    "stubs": {
        "main.pyi": (
            "from typing import Any, List\nimport os.path as p\nAlias = List[int]\n"
            "class Base: ...\nclass C(Base[int], p.Mixin):\n    attr: 'Alias'\n"
            "    def m(self, a: int, b: p.Thing = ...) -> None: ...\n"
            "def g(x: C, *rest: Alias, **kw: str) -> None: ...\nh = g\n"
            "v: List['C']\nw: str\nif flag:\n    z: Base\nelse:\n    y: 'C | None'\n"
        ),
    },
    "linking": {
        "pkg/__init__.py": "__all__ = ['sub', 'x']\nx = 1\n_y = 2\n",
        "pkg/sub.py": "def f():\n    return 1\n",
        "pkg/_hidden.py": "from .sub import f\n",
        "pkg/inner/__init__.py": "",
        "pkg/inner/deep.py": "value = 3\n",
        "chain.py": "from pkg import *\nfrom os.path import *\na = 1\n_b = 2\n",
        "broken.py": "def (:\n",
        "twice.py": "value = 1\n",
        "twice/__init__.py": "value = 2\n",
        "fast.cpython-312-x86_64-linux-gnu.so": "",
    },
}
BUILDER_PROGRAMS = {
    "assignments": "x = 1\ny = x\nfirst, *rest = x\nlast = first = y\ndel x\n",
    "functions": (
        "def f(a, b=2, *args, c, d=4, **kw):\n    return a\n"
        "def g(p, /, q):\n    p = q\n    return p\n"
    ),
    "classes": (
        "class A:\n    x = 1\n    def m(self):\n        return self\n"
        "class B(A):\n    __slots__ = 'p'\n    y = x = 2\n"
    ),
    "branches": (
        "if flag:\n    y = 1\nelif other:\n    y = 2\nelse:\n    y = 3\n"
        "while flag:\n    x = y\n    if other:\n        break\n"
        "    continue\nelse:\n    z = 1\n"
    ),
    "handlers": (
        "try:\n    a = 1\nexcept E as e:\n    a = 2\nelse:\n    b = 1\n"
        "finally:\n    c = a\nwith m as n:\n    d = n\n"
    ),
    "imports": (
        "import os\nimport os.path as p\nfrom os import path\n"
        "from typing import TYPE_CHECKING\nfrom . import sibling\n"
    ),
    "expressions": (
        "import sys\nfrom typing import TYPE_CHECKING\n"
        "def f(a, *args, k=None, **kw):\n    return a\n"
        "x = f(1, *[2], None, k=None, **{'z': 3})\n"
        "y = not x and (x or -5) if x < 3 <= 4 else ~x\n"
        "z = (lambda p: p)(x) + 2 * x % 3 - x.real\n"
        "s = f'a{x!r:>{y}}b{z=}' + '%s-%d' % (x, y) + '{0.real} {k}'.format(x, k=y)\n"
        "u = [x, *s], (x,), {x, *s}, {x: y, **{}}\n"
        "v = x[1:2], x[::2], x[-1:], x[y], sys.modules['os']\n"
        "w = (q := f(x)) is None or q in (1, 2) or q not in [3]\n"
        "if TYPE_CHECKING:\n    pass\n"
        "class C:\n    def m(self):\n        return super().m(), C.__dict__, vars(C)\n"
    ),
    "comprehensions": (
        "def gen(items):\n    yield from items\n    sent = yield items\n"
        "    return [i for i in items if i], {i for i in items}, "
        "{i: j for i, j in items}, (i for i in items), sorted(i for i in items)\n"
        "async def agen(items):\n    return [i async for i in items], await items\n"
    ),
    "surrogates": (
        "def g(x):\n    return '{0.\\ud800}'.format(x), '\\udcff' + str(x)\n"
    ),
    "annotations": (
        "import typing\nfrom typing import TYPE_CHECKING, Optional\n"
        "if TYPE_CHECKING:\n    from collections import OrderedDict\n"
        "    import os.path\n"
        "elif other:\n    import json\nelse:\n    from . import sibling\n"
        "class A:\n    x: int = 1\n    y: 'Optional[A]'\n"
        "    def m(self, a: 'A', *args: int, b: typing.List[int] | None = None,"
        " **kw: 'os.path.sep'):\n"
        "        z: OrderedDict[str, int] = {}\n        return a\n"
        "v: list[int] = []\nAlias = dict[str, int]\nUnion = int | str\n"
        "type T = list[A]\n"
        "def f(p: '  A  ', q: '1 +', r: 'A.B.C', s: \"'A'\", t: '\\x1cA', u: x()):\n"
        "    pass\n"
    ),
    "stubs": (
        "from typing import Any\nclass Base:\n    pass\nclass C(Base):\n"
        "    attr = None\n    def m(self, a, b=1):\n        return a\n"
        "def g(x, *rest, **kw):\n    return x\nh = g\nv = None\nw: int = 2\n"
        "z = y = 3\n"
    ),
    "redefinitions": (
        "def f(a):\n    x = a\n    return x\n"
        "def f(a, b):\n    x = b\n    a = x\n    return a\n"
        "class C:\n    def m(self, c):\n        y = c\n        return y\n"
        "    def m(self, c):\n        y = c\n        return y\n"
    ),
    "matching": (
        "class P:\n    __match_args__ = ('x', 'y')\n"
        "def f(v, kind):\n"
        "    match v:\n"
        "        case 1 | 2 if kind:\n            r = 'small'\n"
        "        case None:\n            r = None\n"
        "        case [first, *rest, last]:\n            r = rest\n"
        "        case (a, b):\n            r = a\n"
        "        case {'k': k, **others}:\n            r = others\n"
        "        case P(px, y=py) as point:\n            r = point\n"
        "        case int(n) | str(n):\n            r = n\n"
        "        case _:\n            r = v\n"
        "    return r\n"
        "match 3:\n    case 3:\n        three = True\n"
        "    case 4:\n        four = True\n"
        "match 'a':\n    case True:\n        t = 1\n    case [x]:\n        t = x\n"
    ),
    "class_tests": (
        "import inspect\nfrom inspect import iscoroutine\n"
        "class A:\n    pass\nclass B(A):\n    pass\n"
        "def f(x, y, t):\n"
        "    if isinstance(x, (A, B)) and not callable(y):\n        r = x\n"
        "    elif issubclass(t, A):\n        r = t\n"
        "    if not (isinstance(x, A) or inspect.iscoroutine(x)):\n        r = x\n"
        "    if iscoroutine(y):\n        r = y\n"
        "    while isinstance(x, B):\n        x = x\n"
        "    assert callable(x)\n"
        "    return isinstance(x, A, B), isinstance(f(x), A), r\n"
    ),
}


def nested_lambdas(depth):
    return "lambda: " * (depth - 2) + "None"


def nested_conditionals(depth):
    return "a if b else " * (depth - 2) + "c"


def else_ifs(count):
    lines = []
    for level in range(count):
        indent = "    " * level
        lines += [f"{indent}if a:", f"{indent}    pass", f"{indent}else:"]
    lines.append("    " * count + "x = 1")
    return "\n".join(lines) + "\n"


BUILDER_PROGRAMS["linking"] = (
    "import pkg.inner.deep\nimport pkg._hidden as hidden\nfrom chain import *\n"
    "from pkg import *\nimport broken\nimport fast\nimport missing.part\n"
    "from . import nothing\nimport twice\n"
)
BUILDER_PROGRAMS["nesting"] = f"x = 1\ny = {nested_lambdas(NESTING_MAX + 1)}\nz = x\n"
NESTING_PROGRAMS = (
    f"x = {nested_lambdas(NESTING_MAX)}\n",
    f"x = {nested_lambdas(NESTING_MAX + 1)}\n",
    f"x = {nested_conditionals(NESTING_MAX)}\n",
    f"x = {nested_conditionals(NESTING_MAX + 1)}\n",
    "x = " + " + ".join(["a"] * (NESTING_MAX + 1)) + "\n",
    "x = " + " + ".join(["a"] * NESTING_MAX) + f" + ({nested_lambdas(NESTING_MAX)})\n",
    "if a:\n    pass\n" + "elif a:\n    pass\n" * (NESTING_MAX + 1),
    "if a:\n    pass\n"
    + "elif a:\n    pass\n" * NESTING_MAX
    + f"elif b:\n    x = {nested_lambdas(NESTING_MAX)}\n",
    else_ifs(64),
    "if a:\n    pass\nelse:\n    x = 1\n    if b:\n        if c:\n            y = 1\n",
    "def f():\n    return 1\n"
    "class A:\n    y = [a for a in b if a]\n"
    "with m as n:\n    del n\n",
)
SEED = 20261126
CASES_PER_FUNCTION = 400
POOL_SIZE = 8
BASES_MAX = 4
MRO_LENGTH_MAX = 6
SLOTS_MAX = 3
SLOT_CANDIDATES_MAX = 3
MROS_PER_CANDIDATE_MAX = 3
LIMIT_MAX = 12


def pool_names(generator):
    return [f"C{index}" for index in range(generator.randint(2, POOL_SIZE))]


def random_mro(generator, name, pool):
    tail = generator.sample(pool, generator.randint(0, min(len(pool), MRO_LENGTH_MAX)))
    return [name] + [item for item in tail if item != name]


def linearize_cases(generator):
    cases = []
    for _ in range(CASES_PER_FUNCTION):
        pool = pool_names(generator)
        cls = generator.choice(pool)
        bases = [generator.choice(pool) for _ in range(generator.randint(0, BASES_MAX))]
        mros = {base: random_mro(generator, base, pool) for base in sorted(set(bases))}
        expected = mro.linearize(cls, bases, mros.__getitem__)
        cases.append({"class": cls, "bases": bases, "mros": mros, "expected": expected})
    return cases


def slots_and_mros(generator):
    pool = pool_names(generator)
    cls = generator.choice(pool)
    slots = []
    for _ in range(generator.randint(0, SLOTS_MAX)):
        slot = []
        for _ in range(generator.randint(0, SLOT_CANDIDATES_MAX)):
            slot.append(None if generator.random() < 0.15 else generator.choice(pool))
        slots.append(slot)
    names = sorted({candidate for slot in slots for candidate in slot if candidate})
    mros = {
        name: [
            random_mro(generator, name, pool)
            for _ in range(generator.randint(0, MROS_PER_CANDIDATE_MAX))
        ]
        for name in names
    }
    return cls, slots, mros


def mros_of(mros):
    return lambda candidate: [[]] if candidate is None else mros[candidate]


def linearizations_cases(generator):
    cases = []
    for _ in range(CASES_PER_FUNCTION):
        cls, slots, mros = slots_and_mros(generator)
        limit = generator.randint(0, LIMIT_MAX)
        expected = mro.linearizations(cls, slots, mros_of(mros), limit)
        cases.append(
            {
                "class": cls,
                "slots": slots,
                "mros": mros,
                "limit": limit,
                "expected": expected,
            }
        )
    return cases


def exhaustive_order_cases(generator):
    cases = []
    for _ in range(CASES_PER_FUNCTION):
        cls, slots, mros = slots_and_mros(generator)
        expected = mro.exhaustive_order(cls, slots, mros_of(mros))
        cases.append({"class": cls, "slots": slots, "mros": mros, "expected": expected})
    return cases


def stub_types(directory):
    found = {}
    files = sorted(directory.glob("*.json")) + sorted(
        (directory / stubs.THIRD_PARTY_DIRECTORY_NAME).glob("*.json")
    )
    for path in files:
        package = json.loads(path.read_text(encoding="utf-8"))
        pending = [
            entry
            for module in package["modules"].values()
            for entry in module["names"].values()
        ]
        while pending:
            entry = pending.pop()
            if entry["k"] != "c":
                continue
            for reduced in [*entry["b"], *([entry["meta"]] if "meta" in entry else [])]:
                found.setdefault(json.dumps(reduced, sort_keys=True), reduced)
            pending.extend(entry["m"].values())
    return [found[key] for key in sorted(found)]


def class_names_cases():
    return [
        {"type": reduced, "expected": stubs.class_names(reduced)}
        for reduced in stub_types(stubs.DATA_DIRECTORY)
        if not isinstance(reduced, str) or not reduced[:1].isalpha()
    ]


def write(name, cases):
    lines = ",\n".join(json.dumps(case, sort_keys=True) for case in cases)
    path = VECTORS_DIRECTORY / name
    path.write_text(f"[\n{lines}\n]\n", encoding="utf-8")


CODE_POINT_POOLS = (
    range(0x20, 0x7F),
    (0x22, 0x27, 0x5C, 0x09, 0x0A, 0x0D, 0x00, 0x1F, 0x7F),
    range(0x80, 0x100),
    range(0x100, 0x2000),
    range(0xD800, 0xE000),
    range(0xE000, 0x10000),
    range(0x10000, 0x110000),
)
TEXT_LENGTH_MAX = 12
CONSTANT_NAME_DIGITS_AROUND = (639, 640, 641, 700)
SIGNATURE_NAMES = ("a", "b", "c", "d", "e")
SIGNATURE_CASES = 300
BINDS_PER_SIGNATURE = 6
PATTERN_CASES = 300
MATCHES_PER_PATTERN = 6
PATTERN_ALPHABET = "aAbB_"
DOTTED_NAMES = (
    "os",
    "os.path",
    "a\u00b7b",
    "\u2118",
    "\u2118.x",
    "\u00e9t\u00e9",
    "x\u0300",
    "\u0300x",
    "1a",
    "a..b",
    "",
    "a.",
    "\u212e",
    "_\u00b7",
)
SITE_CASES = ("main", "main#1", "main#1#2", "#3", "", "a.b:1:2#site")
STEPS_CASES = (("a.b.c", 0), ("a.b.c", 1), ("a.b.c", 2), ("a.b.c", 3), ("a", 1))


def random_code_points(generator):
    return [
        generator.choice(generator.choice(CODE_POINT_POOLS))
        for _ in range(generator.randint(0, TEXT_LENGTH_MAX))
    ]


def random_bytes(generator):
    return bytes(
        generator.choice((generator.randrange(256), 0x22, 0x27, 0x5C))
        for _ in range(generator.randint(0, TEXT_LENGTH_MAX))
    )


def int_values(generator):
    values = [0, 1, -1, 255, -256]
    for digits in CONSTANT_NAME_DIGITS_AROUND:
        values += [10**digits - 1, 10**digits, 10**digits + 1]
    for _ in range(40):
        values.append(generator.randrange(-(10 ** generator.randint(1, 700)), 10**700))
    return values + [-value for value in values if value]


RUST_ESCAPES = {"\\": "\\\\", '"': '\\"'}


def rust_character(character):
    if character in RUST_ESCAPES:
        return RUST_ESCAPES[character]
    if 0x20 <= ord(character) < 0x7F:
        return character
    return f"\\u{{{ord(character):x}}}"


def rust_text(text):
    return '"' + "".join(map(rust_character, text)) + '"'


def rust_texts(texts):
    return "&[" + ", ".join(rust_text(text) for text in texts) + "]"


def rust_option(text):
    return "None" if text is None else f"Some({rust_text(text)})"


def random_signature(generator):
    names = list(SIGNATURE_NAMES)
    generator.shuffle(names)
    positional_count = generator.randint(0, 3)
    positional = names[:positional_count]
    keyword_only = names[positional_count : positional_count + generator.randint(0, 2)]
    vararg = generator.choice((None, "args"))
    kwarg = generator.choice((None, "kwargs"))
    return model.Signature(
        positional,
        generator.randint(0, positional_count),
        keyword_only,
        vararg,
        kwarg,
    )


def signature_line(generator, signature):
    candidates = [*SIGNATURE_NAMES, "args", "kwargs", "z"]
    queries = []
    for _ in range(BINDS_PER_SIGNATURE):
        given = generator.randint(0, 4)
        keywords = generator.sample(candidates, generator.randint(0, 3))
        if keywords and generator.random() < 0.2:
            keywords.append(keywords[0])
        optional = generator.sample(SIGNATURE_NAMES, generator.randint(0, 3))
        bound = signature.binds(given, keywords, optional)
        queries.append(
            f"({given}, {rust_texts(keywords)}, {rust_texts(optional)}, "
            f"{str(bound).lower()})"
        )
    accepted = [name for name in candidates if signature.accepts_keyword(name)]
    return (
        f"    ({rust_texts(signature.positional)}, "
        f"{signature.positional_only_count}, {rust_texts(signature.keyword_only)}, "
        f"{rust_option(signature.vararg)}, {rust_option(signature.kwarg)}, "
        f"{rust_texts(signature.names())}, {rust_texts(accepted)}, "
        f"&[{', '.join(queries)}]),"
    )


def random_affix(generator):
    return "".join(
        generator.choice(PATTERN_ALPHABET) for _ in range(generator.randint(0, 2))
    )


def pattern_line(generator):
    case = generator.choice((None, "lower", "upper"))
    pattern = model.Pattern(random_affix(generator), random_affix(generator), case)
    candidates = [
        pattern.prefix + random_affix(generator) + pattern.suffix,
        random_affix(generator) + random_affix(generator),
        pattern.prefix + "\u00e9" + pattern.suffix,
        pattern.prefix,
        pattern.prefix + pattern.suffix,
        random_affix(generator),
    ]
    matched = ", ".join(
        f"({rust_text(name)}, {rust_option(pattern.matches(name))})"
        for name in candidates[:MATCHES_PER_PATTERN]
    )
    return (
        f"    ({rust_text(pattern.prefix)}, {rust_text(pattern.suffix)}, "
        f"{rust_option(case)}, {rust_text(pattern.name)}, &[{matched}]),"
    )


def model_vectors(generator):
    texts = [random_code_points(generator) for _ in range(CASES_PER_FUNCTION)]
    texts += [[0x27], [0x22], [0x27, 0x22], [], [0xD800], [0x10FFFF]]
    lines = ["pub const STR_NAMES: &[(&[u32], &str)] = &["]
    for points in texts:
        name = model.constant_name("".join(map(chr, points)))
        lines.append(f"    (&{points}, {rust_text(name)}),")
    lines.append("];")
    lines.append("pub const BYTES_NAMES: &[(&[u8], &str)] = &[")
    for value in [random_bytes(generator) for _ in range(CASES_PER_FUNCTION)]:
        lines.append(f"    (&{list(value)}, {rust_text(model.constant_name(value))}),")
    lines.append("];")
    lines.append("pub const INT_NAMES: &[(&str, &str)] = &[")
    for value in int_values(generator):
        lines.append(f'    ("{value}", "{model.constant_name(value)}"),')
    lines.append("];")
    lines.append("pub const DOTTED_IDENTIFIERS: &[(&str, bool)] = &[")
    for name in DOTTED_NAMES:
        dotted = all(part.isidentifier() for part in name.split("."))
        lines.append(f"    ({rust_text(name)}, {str(dotted).lower()}),")
    lines.append("];")
    spaces = [point for point in range(0x110000) if chr(point).isspace()]
    lines.append(f"pub const PYTHON_SPACES: &[u32] = &{spaces};")
    lines.append("pub const SITE_NAMES: &[(&str, &str)] = &[")
    for site in SITE_CASES:
        lines.append(f"    ({rust_text(site)}, {rust_text(model.site_name(site))}),")
    lines.append("];")
    lines.append("pub const STEPS_PAST_ROOT: &[(&str, usize, &[&str])] = &[")
    for name, steps in STEPS_CASES:
        expected = model.External(name, steps).steps_past_root()
        lines.append(f"    ({rust_text(name)}, {steps}, {rust_texts(expected)}),")
    lines.append("];")
    lines.append(
        "pub type Binding = "
        "(usize, &'static [&'static str], &'static [&'static str], bool);"
    )
    lines.append(
        "pub type SignatureCase = (&'static [&'static str], usize, "
        "&'static [&'static str], Option<&'static str>, Option<&'static str>, "
        "&'static [&'static str], &'static [&'static str], &'static [Binding]);"
    )
    lines.append("pub const SIGNATURES: &[SignatureCase] = &[")
    for _ in range(SIGNATURE_CASES):
        lines.append(signature_line(generator, random_signature(generator)))
    lines.append("];")
    lines.append(
        "pub type PatternCase = (&'static str, &'static str, Option<&'static str>, "
        "&'static str, &'static [(&'static str, Option<&'static str>)]);"
    )
    lines.append("pub const PATTERNS: &[PatternCase] = &[")
    for _ in range(PATTERN_CASES):
        lines.append(pattern_line(generator))
    lines.append("];")
    return "\n".join(lines) + "\n"


MODEL_TABLES = ("FUNCTIONS", "SPECIAL_METHOD_CALLS", "REFLECTION_CALLS")
STRING_MAPS = (
    "KEY_WRAPPERS",
    "LIBRARY_VALUES",
    "REPEATS",
    "DEFINES_MARKERS",
    "CALLS_BACK",
    "VARIABLE_TYPES",
    "PROPERTY_ACCESSORS",
    "CLOSURES",
    "VARIABLE_FUNCTIONS",
    "CONCRETE_CLASSES",
    "STUB_RESULTS",
    "CACHED_FUNCTIONS",
)
STRING_SETS = (
    "KEYED_OPERATIONS",
    "READS_TUPLES",
    "NOT_CONSUMING",
    "OPENERS",
    "DECORATING_CLOSURES",
)
STRING_LIST_MAPS = ("KEYED_SEQUENCES", "WRAPPED_ATTRIBUTES_BY_TYPE")
STRING_CONSTANTS = (
    "GROUPER",
    "BUFFER_EXPORTER",
    "TUPLE_STORAGE",
    "ITERABLE",
    "REVERSIBLE",
)
MODE_ALPHABET = "rwaxbt+z"
MODE_LENGTH_MAX = 3
UNKNOWN_KIND = "unknown_kind"
UNKNOWN_METHOD = "unknown_method"


def rust_model(entry):
    text, rule, *arguments = entry
    return f"({rust_text(text)}, {rust_text(rule)}, {rust_texts(arguments)})"


def rust_option_model(entry):
    return "None" if entry is None else f"Some({rust_model(entry)})"


def table_lines(name, item_type, items):
    return [f"pub const {name}: &[{item_type}] = &[", *items, "];"]


def models_tables():
    models = builtin_models
    model_type = "(&str, &str, &[&str])"
    lines = []
    for name in MODEL_TABLES:
        items = [
            f"    ({rust_text(key)}, {rust_model(entry)}),"
            for key, entry in getattr(models, name).items()
        ]
        lines += table_lines(name, f"(&str, {model_type})", items)
    items = [
        f"    ({rust_text(kind)}, {rust_text(method)}, {rust_model(entry)}),"
        for (kind, method), entry in sorted(models.METHODS.items())
    ]
    lines += table_lines("METHODS", f"(&str, &str, {model_type})", items)
    items = [
        f"    ({rust_text(key)}, {rust_text(kind)}, {rust_model(entry)}),"
        for key, (kind, entry) in models.CONTAINER_CLASSES.items()
    ]
    lines += table_lines("CONTAINER_CLASSES", f"(&str, &str, {model_type})", items)
    items = [
        f"    ({rust_text(key)}, {rust_text(mode)}, {rust_texts(roles)}, "
        f"{rust_text(shape)}, {rust_option(kind)}),"
        for key, (mode, roles, shape, kind) in models.LIBRARY_ITERATION.items()
    ]
    lines += table_lines(
        "LIBRARY_ITERATION", "(&str, &str, &[&str], &str, Option<&str>)", items
    )
    for name in STRING_MAPS:
        items = [
            f"    ({rust_text(key)}, {rust_text(value)}),"
            for key, value in getattr(models, name).items()
        ]
        lines += table_lines(name, "(&str, &str)", items)
    for name in STRING_SETS:
        items = [f"    {rust_text(value)}," for value in sorted(getattr(models, name))]
        lines += table_lines(name, "&str", items)
    for name in STRING_LIST_MAPS:
        items = [
            f"    ({rust_text(key)}, {rust_texts(values)}),"
            for key, values in getattr(models, name).items()
        ]
        lines += table_lines(name, "(&str, &[&str])", items)
    items = []
    for key, (parameter, plan, source) in models.LENGTH_HINTS.items():
        steps = ", ".join(
            f"({rust_text(method)}, {rust_texts(needs)})" for method, needs in plan
        )
        items.append(
            f"    ({rust_text(key)}, {rust_text(parameter)}, &[{steps}], "
            f"{rust_text(source)}),"
        )
    lines += table_lines(
        "LENGTH_HINTS", "(&str, &str, &[(&str, &[&str])], &str)", items
    )
    items = [
        f"    ({rust_text(key)}, {rust_text(parameter)}, {str(hashed).lower()}),"
        for key, (parameter, hashed) in models.HASHED_ARGUMENTS.items()
    ]
    lines += table_lines("HASHED_ARGUMENTS", "(&str, &str, bool)", items)
    items = []
    for key, (text, argument, *wrapper) in models.RETURNS_ARGUMENT.items():
        items.append(
            f"    ({rust_text(key)}, {rust_text(text)}, {rust_option(argument)}, "
            f"{rust_option(wrapper[0] if wrapper else None)}),"
        )
    lines += table_lines(
        "RETURNS_ARGUMENT", "(&str, &str, Option<&str>, Option<&str>)", items
    )
    text, argument = models.RETURNED_DECORATOR_SIGNATURE
    lines.append(
        f"pub const RETURNED_DECORATOR_SIGNATURE: (&str, &str) = "
        f"({rust_text(text)}, {rust_text(argument)});"
    )
    lines.append(f"pub const DYNAMIC_NAMES_MAX: usize = {models.DYNAMIC_NAMES_MAX};")
    for name in STRING_CONSTANTS:
        lines.append(f"pub const {name}: &str = {rust_text(getattr(models, name))};")
    return lines


def all_modes():
    modes = [""]
    for length in range(1, MODE_LENGTH_MAX + 1):
        found = [""]
        for _ in range(length):
            found = [mode + letter for mode in found for letter in MODE_ALPHABET]
        modes += found
    return modes


def models_functions():
    models = builtin_models
    items = [
        f"    ({rust_text(mode)}, {str(unbuffered).lower()}, "
        f"{rust_option(models.opened_class(mode, unbuffered))}),"
        for mode in all_modes()
        for unbuffered in (False, True)
    ]
    lines = table_lines("OPENED_CLASSES", "(&str, bool, Option<&str>)", items)
    kinds = sorted(
        {kind for kind, _ in models.METHODS}
        | set(models.CONTAINER_CLASSES)
        | {UNKNOWN_KIND}
    )
    methods = sorted({method for _, method in models.METHODS} | {UNKNOWN_METHOD})
    items = [
        f"    ({rust_text(kind)}, {rust_text(models.builtin_kind(kind))}),"
        for kind in kinds
    ]
    lines += table_lines("BUILTIN_KINDS", "(&str, &str)", items)
    items = [
        f"    ({rust_text(kind)}, {rust_text(method)}, "
        f"{rust_option_model(models.method_model(kind, method))}),"
        for kind in kinds
        for method in methods
    ]
    lines += table_lines(
        "METHOD_MODELS", "(&str, &str, Option<(&str, &str, &[&str])>)", items
    )
    return lines


def signature_texts():
    models = builtin_models
    texts = {
        entry[0] for name in MODEL_TABLES for entry in getattr(models, name).values()
    }
    texts |= {entry[0] for entry in models.METHODS.values()}
    texts |= {entry[0] for _, entry in models.CONTAINER_CLASSES.values()}
    texts |= {entry[0] for entry in models.RETURNS_ARGUMENT.values()}
    texts.add(models.RETURNED_DECORATOR_SIGNATURE[0])
    return sorted(texts)


def rust_constant(value):
    if isinstance(value, str):
        return f"Str({rust_text(value)})"
    return f"Int({value})"


def models_signatures():
    lines = [
        "pub type ParsedSignature = (&'static str, &'static [&'static str], usize, "
        "&'static [&'static str], Option<&'static str>, Option<&'static str>, "
        "&'static [(&'static str, Constant)]);",
        "pub const SIGNATURES: &[ParsedSignature] = &[",
    ]
    for text in signature_texts():
        signature, constants = _signature(text)
        defaults = ", ".join(
            f"({rust_text(name)}, Constant::{rust_constant(value)})"
            for name, value in constants.items()
        )
        lines.append(
            f"    ({rust_text(text)}, {rust_texts(signature.positional)}, "
            f"{signature.positional_only_count}, {rust_texts(signature.keyword_only)}, "
            f"{rust_option(signature.vararg)}, {rust_option(signature.kwarg)}, "
            f"&[{defaults}]),"
        )
    lines.append("];")
    return lines


def models_vectors():
    lines = [
        "#[derive(Debug, PartialEq, Eq)]",
        "pub enum Constant { Str(&'static str), Int(u64) }",
        *models_tables(),
        *models_functions(),
        *models_signatures(),
    ]
    return "\n".join(lines) + "\n"


def nesting_vectors():
    lines = ["pub const NESTING_MAX: usize = " + str(NESTING_MAX) + ";"]
    lines.append("pub const NESTING: &[(&str, &[usize])] = &[")
    for source in NESTING_PROGRAMS:
        depths = [nesting(statement) for statement in ast.parse(source).body]
        lines.append(f"    ({rust_text(source)}, &{depths}),")
    lines.append("];")
    return "\n".join(lines) + "\n"


def builder_vectors():
    if BUILDER_VECTORS.exists():
        shutil.rmtree(BUILDER_VECTORS)
    for name, source in BUILDER_PROGRAMS.items():
        target = BUILDER_VECTORS / name
        target.mkdir(parents=True)
        files = {"main.py": source, **BUILDER_FILES.get(name, {})}
        with tempfile.TemporaryDirectory() as scratch:
            program = Path(scratch) / "program"
            for directory in (target, program):
                for relative, text in files.items():
                    path = directory / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(text, encoding="utf-8")
            out = Path(scratch) / "out"
            subprocess.run(
                [sys.executable, "-I", str(DUMP), "input", "--checkout", str(ROOT)]
                + [
                    "--out",
                    str(out),
                    "--package",
                    str(program),
                    str(program / "main.py"),
                ],
                check=True,
            )
            shutil.copy(out / "D4.jsonl", target / "D4.jsonl")
            document = json.loads((out / "D6.json").read_text(encoding="utf-8"))
            definitions = {
                name: definition
                for name, definition in document["definitions"].items()
                if definition["kind"] == "module"
            }
            for file, section in (
                ("modules.json", document["modules"]),
                ("definitions.json", definitions),
            ):
                text = json.dumps(section, sort_keys=True, separators=(",", ":"))
                (target / file).write_text(text + "\n", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Write the unit vectors of the Rust crates from the Python engine."
    )
    parser.parse_args(argv)
    VECTORS_DIRECTORY.mkdir(parents=True, exist_ok=True)
    generator = random.Random(SEED)
    write("linearize.json", linearize_cases(generator))
    write("linearizations.json", linearizations_cases(generator))
    write("exhaustive_order.json", exhaustive_order_cases(generator))
    write("class_names.json", class_names_cases())
    MODEL_VECTORS.parent.mkdir(parents=True, exist_ok=True)
    MODEL_VECTORS.write_text(model_vectors(random.Random(SEED)), encoding="utf-8")
    MODELS_VECTORS.write_text(models_vectors(), encoding="utf-8")
    NESTING_VECTORS.write_text(nesting_vectors(), encoding="utf-8")
    builder_vectors()


if __name__ == "__main__":
    main()
