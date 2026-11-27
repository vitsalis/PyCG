const SPLITMIX_INCREMENT: u64 = 0x9E37_79B9_7F4A_7C15;
const SPLITMIX_FIRST_MULTIPLIER: u64 = 0xBF58_476D_1CE4_E5B9;
const SPLITMIX_SECOND_MULTIPLIER: u64 = 0x94D0_49BB_1331_11EB;
const FRACTION_BITS: u32 = 53;

pub const FAMILIES: usize = 5;

pub struct Random(u64);

impl Random {
    pub fn new(seed: u64) -> Random {
        Random(seed)
    }

    fn next(&mut self) -> u64 {
        self.0 = self.0.wrapping_add(SPLITMIX_INCREMENT);
        let mut mixed = self.0;
        mixed = (mixed ^ (mixed >> 30)).wrapping_mul(SPLITMIX_FIRST_MULTIPLIER);
        mixed = (mixed ^ (mixed >> 27)).wrapping_mul(SPLITMIX_SECOND_MULTIPLIER);
        mixed ^ (mixed >> 31)
    }

    fn random(&mut self) -> f64 {
        (self.next() >> (64 - FRACTION_BITS)) as f64 / (1_u64 << FRACTION_BITS) as f64
    }

    fn below(&mut self, bound: usize) -> usize {
        assert!(bound > 0, "a choice among nothing");
        let bound = u64::try_from(bound).expect("a bound");
        usize::try_from(self.next() % bound).expect("an index")
    }

    fn between(&mut self, minimum: usize, maximum: usize) -> usize {
        minimum + self.below(maximum - minimum + 1)
    }

    fn choice<'a>(&mut self, items: &[&'a str]) -> &'a str {
        items[self.below(items.len())]
    }

    fn sample<'a>(&mut self, items: &[&'a str], count: usize) -> Vec<&'a str> {
        let mut pool = items.to_vec();
        (0..count)
            .map(|_| {
                let index = self.below(pool.len());
                pool.swap_remove(index)
            })
            .collect()
    }
}

const WRAPPER_HEADER: &str = "import functools
class A:
    def f(*args): pass
    def g(self, *args): return self
    @classmethod
    def h(cls, *args): return cls
    @staticmethod
    def s(*args): pass
    @property
    def p(self): return self.f
class B(A):
    pass
a = A()
b = B()
";
const NAMES: [&str; 6] = ["f", "g", "h", "s", "p", "x"];
const OWNERS: [&str; 6] = ["A", "B", "a", "b", "A()", "B()"];
const WRAPPERS: [&str; 5] = [
    "staticmethod",
    "classmethod",
    "classmethod",
    "property",
    "functools.partial",
];

fn wrapped(random: &mut Random, depth: usize, target: &str) -> String {
    if depth == 0 || random.random() < 0.25 {
        let wraps_the_attribute_it_is_stored_to = random.random() < 0.5;
        if wraps_the_attribute_it_is_stored_to {
            return target.to_owned();
        }
        return format!("{}.{}", random.choice(&OWNERS), random.choice(&NAMES));
    }
    let wrapper = random.choice(&WRAPPERS);
    format!("{wrapper}({})", wrapped(random, depth - 1, target))
}

fn wrapper_statements(random: &mut Random) -> Vec<String> {
    let roll = random.random();
    let name = random.choice(&NAMES);
    if roll < 0.6 {
        let target = format!("{}.{name}", random.choice(&["A", "B", "a", "b"]));
        let depth = random.between(1, 4);
        let store = format!("{target} = {}", wrapped(random, depth, &target));
        if random.random() < 0.7 {
            let call = if random.random() < 0.5 {
                target
            } else {
                format!("{}.{name}", random.choice(&OWNERS))
            };
            return vec![store, format!("{call}()")];
        }
        return vec![store];
    }
    let access = format!("{}.{name}", random.choice(&OWNERS));
    if roll < 0.85 {
        let arguments = vec!["1"; random.between(0, 2)];
        return vec![format!("{access}({})", arguments.join(", "))];
    }
    if roll < 0.95 {
        return vec![format!("{access}()()")];
    }
    vec![access]
}

fn wrapper_program(random: &mut Random) -> String {
    let mut statements = Vec::new();
    for _ in 0..random.between(3, 8) {
        statements.extend(wrapper_statements(random));
    }
    format!("{WRAPPER_HEADER}{}\n", statements.join("\n"))
}

const FEEDBACK_HEADER: &str = "class It:
    def __init__(self, *args):
        self.a = self
    def __next__(self):
        return self
    def __getitem__(self, index):
        return self
    def __call__(self, *args):
        return self
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def __eq__(self, other):
        return self
    def __add__(self, other):
        return self
    def __getattr__(self, name):
        return self
class Box:
    pass
class New(It):
    def __new__(cls, *args):
        return super().__new__(cls) if args else x
class Meta(type):
    def make(cls, *args):
        return super().__call__(*args)
class Made(It, metaclass=Meta):
    pass
def make(*args):
    return It()
def gen(value):
    yield from value
async def co(value):
    return await value
async def drive(value):
    global x
    x = await value
x = It()
xs = [It()]
d = {0: It()}
";
const SPECIALS: [&str; 15] = [
    "__iter__",
    "__next__",
    "__call__",
    "__getitem__",
    "__enter__",
    "__eq__",
    "__getattr__",
    "__init__",
    "__add__",
    "__contains__",
    "__getattribute__",
    "__setattr__",
    "__delattr__",
    "__await__",
    "__new__",
];
const CALLABLES: [&str; 19] = [
    "It",
    "Box",
    "New",
    "Made",
    "Made.make",
    "make",
    "gen",
    "co",
    "iter",
    "next",
    "x",
    "xs.append",
    "xs.extend",
    "It.__next__",
    "x.__call__",
    "lambda *args: x",
    "lambda *args: It()",
    "classmethod(It)",
    "staticmethod(make)",
];
const FEEDBACK: [&str; 28] = [
    "xs.extend(x)",
    "xs.append(xs)",
    "xs.append(x)",
    "d[0] = d",
    "d[x] = x",
    "x = x()",
    "x = iter(x)",
    "x = next(x)",
    "x = x[0]",
    "x = xs[0]",
    "x.a = x",
    "x = x.a",
    "x = x + x",
    "x = x == x",
    "x = gen(x)",
    "x = list(x)",
    "x = [y for y in x]",
    "x, *rest = x",
    "x = x in xs",
    "x = getattr(x, 'b')",
    "x = make(x)",
    "xs = xs + [x]",
    "del x.a",
    "x.b = x.a",
    "x = x in [None, x]",
    "x = co(x)",
    "drive(x)",
    "drive(co(x))",
];

fn feedback_statement(random: &mut Random) -> String {
    let roll = random.random();
    if roll < 0.3 {
        let owner = random.choice(&["It", "Box", "x"]);
        return format!(
            "{owner}.{} = {}",
            random.choice(&SPECIALS),
            random.choice(&CALLABLES)
        );
    }
    let statement = random.choice(&FEEDBACK);
    if roll < 0.5 {
        let loop_kind = random.below(3);
        let iterable = random.choice(&["x", "xs", "d", "gen(x)"]);
        return match loop_kind {
            0 => format!("for item in {iterable}:\n    {statement}"),
            1 => format!("with x as item:\n    {statement}"),
            _ => format!("while x:\n    {statement}"),
        };
    }
    statement.to_owned()
}

fn feedback_program(random: &mut Random) -> String {
    let statements: Vec<String> = (0..random.between(3, 10))
        .map(|_| feedback_statement(random))
        .collect();
    let mut body = statements.join("\n");
    let repeated_in_a_called_function = random.random() < 0.3;
    if repeated_in_a_called_function {
        let indented = body.replace('\n', "\n    ");
        body += &format!("\ndef run(x, xs, d):\n    {indented}\n    return x\nx = run(x, xs, d)");
    }
    format!("{FEEDBACK_HEADER}{body}\n")
}

const HIERARCHY_HEADER: &str = "import lib
class Holder:
    pass
class A:
    def method(self):
        return self
class H:
    def __getattr__(self, name):
        return self
def fetch(self, name):
    return self
def put(self, name, value):
    value
holder = Holder()
holder.base = A
attribute = \"base\"
hook_name = \"__getattr__\"
";
const BASES: [&str; 13] = [
    "int",
    "str",
    "list",
    "tuple",
    "dict",
    "set",
    "bytes",
    "Exception",
    "object",
    "lib.Base",
    "A",
    "H",
    "holder.base",
];
const HOOK_NAMES: [&str; 4] = [
    "__getattr__",
    "__getattribute__",
    "__setattr__",
    "__delattr__",
];
const HOOK_VALUES: [&str; 5] = [
    "fetch",
    "put",
    "A().method",
    "lambda self, *args: self",
    "H()",
];
const ACCESSES: [&str; 9] = [
    "{c}().missing",
    "{c}().method()",
    "{c}().attr = 1",
    "del {c}().attr",
    "getattr({c}(), 'missing', None)",
    "getattr({c}(), attribute, None)",
    "setattr({c}(), attribute, 1)",
    "delattr({c}(), 'attr')",
    "{c}().missing.method()",
];

fn hierarchy_program(random: &mut Random) -> String {
    let mut lines = Vec::new();
    let base_from_many_candidates = random.random() < 0.5;
    if base_from_many_candidates {
        let count = random.between(6, BASES.len() - 1);
        let bases = random.sample(&BASES[..BASES.len() - 1], count);
        lines.push(format!(
            "for base in ({},):\n    holder.base = base",
            bases.join(", ")
        ));
    }
    let mut classes: Vec<String> = Vec::new();
    for _ in 0..random.between(4, 12) {
        let roll = random.random();
        if roll < 0.2 {
            lines.push(format!("holder.base = {}", random.choice(&BASES)));
        } else if roll < 0.3 {
            lines.push(format!(
                "setattr(holder, attribute, {})",
                random.choice(&BASES)
            ));
        } else if roll < 0.5 || classes.is_empty() {
            let name = format!("C{}", classes.len());
            let mut candidates: Vec<&str> = BASES.to_vec();
            candidates.extend(classes.iter().map(String::as_str));
            let mut bases: Vec<&str> = (0..random.between(1, 2))
                .map(|_| random.choice(&candidates))
                .collect();
            if bases.len() == 2 && bases[0] == bases[1] {
                bases.truncate(1);
            }
            let mut body = "pass".to_owned();
            if random.random() < 0.3 {
                body = format!(
                    "{} = {}",
                    random.choice(&HOOK_NAMES),
                    random.choice(&HOOK_VALUES)
                );
            }
            lines.push(format!("class {name}({}):\n    {body}", bases.join(", ")));
            classes.push(name);
        } else if roll < 0.65 {
            let names: Vec<&str> = classes.iter().map(String::as_str).collect();
            let target = random.choice(&names);
            let (hook, value) = (random.choice(&HOOK_NAMES), random.choice(&HOOK_VALUES));
            if random.random() < 0.5 {
                lines.push(format!("{target}.{hook} = {value}"));
            } else {
                lines.push(format!("hook_name = '{hook}'"));
                lines.push(format!("setattr({target}, hook_name, {value})"));
            }
        } else {
            let names: Vec<&str> = classes.iter().map(String::as_str).collect();
            let access = random.choice(&ACCESSES);
            lines.push(access.replace("{c}", random.choice(&names)));
        }
    }
    format!("{HIERARCHY_HEADER}{}\n", lines.join("\n"))
}

const TYPED_HEADER: &str = "import collections
import contextlib
import datetime
import functools
import re
import types
def f(*args):
    return args
x = types.SimpleNamespace()
";
const TYPED_VALUES: [&str; 18] = [
    "types.SimpleNamespace()",
    "collections.OrderedDict()",
    "collections.OrderedDict(x)",
    "collections.deque([x])",
    "enumerate([x])",
    "zip([x], [x])",
    "map(f, [x])",
    "map(x, [x], *[[x]])",
    "filter(x, [x])",
    "sorted([x], key=x)",
    "reversed([x])",
    "contextlib.closing(x)",
    "functools.partial(f, x)",
    "datetime.datetime.now()",
    "re.compile('a').match('a')",
    "[x]",
    "(x, x)",
    "{'k': x}",
];
const TYPED_STEPS: [&str; 21] = [
    "x = x.__dict__",
    "x = x.__class__",
    "x = x.copy()",
    "x = x.items()",
    "x = x.values()",
    "x = x.popitem()",
    "x = x.pop()",
    "x = x.group()",
    "x = x.replace()",
    "x = x.__enter__()",
    "x = x.func",
    "x = x.args",
    "x = x(x)",
    "x = next(iter(x))",
    "x = x[0]",
    "x['k'] = x",
    "x.append(x)",
    "x.attr = x",
    "x = x.attr",
    "for x in x:\n    pass",
    "with x as x:\n    pass",
];

fn typed_program(random: &mut Random) -> String {
    let mut statements = vec![format!("x = {}", random.choice(&TYPED_VALUES))];
    for _ in 0..random.between(2, 8) {
        let mut step = random.choice(&TYPED_STEPS).to_owned();
        if random.random() < 0.3 {
            step = format!("x = {}", random.choice(&TYPED_VALUES));
        }
        if random.random() < 0.5 {
            step = format!("for _ in (0,):\n    {}", step.replace('\n', "\n    "));
        }
        statements.push(step);
    }
    format!("{TYPED_HEADER}{}\n", statements.join("\n"))
}

const DISPATCH_HEADER: &str = "class A:
    def m(cls, *args):
        return args
class B:
    pass
class Caller:
    __call__ = map
class Zipper:
    __call__ = staticmethod(zip)
";
const DISPATCH_OWNERS: [&str; 4] = ["A", "B", "Caller", "Zipper"];
const DISPATCH_SLOTS: [&str; 3] = ["__new__", "__call__", "__init__"];
const DISPATCH_VALUES: [&str; 13] = [
    "A",
    "B",
    "Caller()",
    "Zipper()",
    "map",
    "zip",
    "filter",
    "staticmethod(map)",
    "classmethod(map)",
    "classmethod(A.m)",
    "A.m",
    "A().m",
    "lambda *args: sorted(args, key=A)",
];
const DISPATCH_CALLS: [&str; 7] = [
    "A([1])",
    "B([1], [2])",
    "Caller()(A, [1])",
    "Caller()(B, [1], *[[2]])",
    "Zipper()([1], A)",
    "list(map(A, [1], [2]))",
    "sorted([A, B], key=B)",
];

fn dispatch_program(random: &mut Random) -> String {
    let mut statements = Vec::new();
    for _ in 0..random.between(2, 7) {
        let owner = random.choice(&DISPATCH_OWNERS);
        let slot = random.choice(&DISPATCH_SLOTS);
        statements.push(format!(
            "{owner}.{slot} = {}",
            random.choice(&DISPATCH_VALUES)
        ));
    }
    let count = random.between(1, 3);
    statements.extend(
        random
            .sample(&DISPATCH_CALLS, count)
            .into_iter()
            .map(str::to_owned),
    );
    format!("{DISPATCH_HEADER}{}\n", statements.join("\n"))
}

pub fn random_programs(seed: u64, rounds: usize) -> Vec<String> {
    let mut random = Random::new(seed);
    let mut dispatch_random_apart_from_the_other_families = Random::new(seed);
    let mut programs = Vec::with_capacity(rounds * FAMILIES);
    for _ in 0..rounds {
        programs.push(wrapper_program(&mut random));
        programs.push(feedback_program(&mut random));
        programs.push(hierarchy_program(&mut random));
        programs.push(typed_program(&mut random));
        programs.push(dispatch_program(
            &mut dispatch_random_apart_from_the_other_families,
        ));
    }
    programs
}
