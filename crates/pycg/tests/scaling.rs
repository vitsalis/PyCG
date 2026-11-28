use std::collections::{BTreeMap, BTreeSet};
use std::ffi::OsString;
use std::path::{Path, PathBuf};

use num_bigint::BigUint;
use pycg_analysis::{CAP_DEFAULT_OBJECTS, Cap, Order, Request, analyse};
use pycg_document::ProgramPart;
use pycg_solver::Work;
use serde_json::Value;

const LINEAR_GROWTH_MAX: f64 = 2.5;
const SHARED_WALK_GROWTH_MAX: f64 = 3.0;
const CLASS_TEST_GROWTH_MAX: f64 = 4.5;
const BUILTIN_CLASSES_CHECKED_BY_MRO: [&str; 16] = [
    "str",
    "bytes",
    "int",
    "float",
    "list",
    "dict",
    "tuple",
    "set",
    "frozenset",
    "bytearray",
    "complex",
    "range",
    "ValueError",
    "KeyError",
    "TypeError",
    "OSError",
];

type Graph = BTreeMap<String, BTreeSet<String>>;

struct Analysed {
    graph: Graph,
    work: Work,
}

fn directory(name: &str) -> PathBuf {
    let directory = Path::new(env!("CARGO_TARGET_TMPDIR"))
        .join("scaling")
        .join(name);
    std::fs::create_dir_all(&directory).expect("the program directory is made");
    directory
}

fn analysed(name: &str, source: &str, order: Order) -> Analysed {
    let directory = directory(name);
    let main = directory.join("main.py");
    std::fs::write(&main, source).expect("the program is written");
    let request = Request {
        entry_points: vec![OsString::from(&main)],
        package: Some(directory.clone().into_os_string()),
        cap: Cap::Objects(BigUint::from(CAP_DEFAULT_OBJECTS)),
        order,
    };
    let mut found = analyse(&request, &directory, &mut |warning| {
        panic!("{}: a warning: {}", main.display(), warning.display())
    })
    .expect("the program is analysed");
    let part = ProgramPart::from_program(&mut found.program);
    let document = pycg_document::build(&part, &found.results, None, None);
    let document: Value =
        serde_json::from_str(&pycg_document::dumps(&document)).expect("a JSON document");
    let mut graph = Graph::new();
    for (caller, sites) in document["calls"].as_object().expect("calls") {
        let callees = graph.entry(caller.clone()).or_default();
        for site in sites.as_array().expect("sites") {
            for callee in site["callees"].as_array().expect("callees") {
                callees.insert(callee.as_str().expect("a name").to_owned());
            }
        }
    }
    Analysed {
        graph,
        work: found.program.analysis.work(),
    }
}

fn callees<'a>(graph: &'a Graph, caller: &str) -> Vec<&'a str> {
    graph
        .get(caller)
        .map(|callees| callees.iter().map(String::as_str).collect())
        .unwrap_or_default()
}

fn total(work: &Work) -> u64 {
    work.copied + work.applied + work.edges
}

fn grows_at_most(costs: &[u64], factor: f64) {
    for pair in costs.windows(2) {
        let (small, large) = (pair[0] as f64, pair[1] as f64);
        assert!(
            large < factor * small,
            "{costs:?} grows past {factor} per doubling"
        );
    }
}

fn lines(parts: Vec<String>) -> String {
    parts.join("\n") + "\n"
}

fn hub(size: usize) -> String {
    let mut parts = vec![
        "def apply(func, *args, **kwargs):".to_owned(),
        "    return func(*args, **kwargs)".to_owned(),
    ];
    for i in 0..size {
        parts.extend([
            format!("class Value{i}:"),
            "    def __init__(self, items):".to_owned(),
            "        self.items = items".to_owned(),
            format!("def f{i}(value, key=None):"),
            format!("    apply(f{}, value, key='k{i}')", (i + 1) % size),
            "    return value".to_owned(),
            format!("apply(f{i}, Value{i}(({i}, 'v{i}')))"),
        ]);
    }
    lines(parts)
}

fn unpacking_hub(size: usize) -> String {
    let mut parts = vec![
        "def apply(func, args):".to_owned(),
        "    return func(*args)".to_owned(),
    ];
    for i in 0..size {
        parts.extend([
            format!("def f{i}(first, second):"),
            "    return first".to_owned(),
            format!("apply(f{i}, (f{i}, 'v{i}'))"),
        ]);
    }
    lines(parts)
}

fn hub_work(name: &str, program: fn(usize) -> String, size: usize) -> u64 {
    let found = analysed(&format!("{name}-{size}"), &program(size), Order::Canonical);
    assert_eq!(callees(&found.graph, "main.apply").len(), size);
    total(&found.work)
}

#[test]
fn work_grows_about_linearly_with_the_size_of_a_hub() {
    let costs: Vec<u64> = [40, 80, 160]
        .into_iter()
        .map(|size| hub_work("hub", hub, size))
        .collect();
    grows_at_most(&costs, LINEAR_GROWTH_MAX);
}

#[test]
fn unpacking_where_many_callables_meet_many_tuples_is_linear() {
    let costs: Vec<u64> = [40, 80, 160]
        .into_iter()
        .map(|size| hub_work("unpacking", unpacking_hub, size))
        .collect();
    grows_at_most(&costs, LINEAR_GROWTH_MAX);
}

fn meeting_paths(size: usize) -> String {
    let mut parts: Vec<String> = [
        "class Box:",
        "    pass",
        "def value():",
        "    pass",
        "box = Box()",
    ]
    .map(str::to_owned)
    .to_vec();
    parts.push("box.s0 = value".to_owned());
    parts.extend((1..size).map(|i| format!("box.s{i} = box.s{}", i - 1)));
    parts.extend((0..size).map(|i| format!("box.meet = box.s{i}")));
    parts.push("box.c0 = box.meet".to_owned());
    parts.extend((1..size).map(|i| format!("box.c{i} = box.c{}", i - 1)));
    parts.push(format!("box.c{}()", size - 1));
    lines(parts)
}

#[test]
fn searches_for_cycles_are_about_linear_in_every_order() {
    let orders = [
        Order::Canonical,
        Order::LastInFirstOut,
        Order::Reversed,
        Order::shuffled(1),
        Order::shuffled(2),
    ];
    for (index, order) in orders.into_iter().enumerate() {
        let costs: Vec<u64> = [100, 200, 400]
            .into_iter()
            .map(|size| {
                let name = format!("meeting-{index}-{size}");
                let found = analysed(&name, &meeting_paths(size), order);
                assert_eq!(callees(&found.graph, "main"), ["main.value"]);
                found.work.searched
            })
            .collect();
        grows_at_most(&costs, LINEAR_GROWTH_MAX);
    }
}

fn metaclass_statements(size: usize) -> String {
    let mut parts: Vec<String> = [
        "class Meta(type):",
        "    def __new__(mcs, name, bases, namespace):",
        "        return super().__new__(mcs, name, bases, namespace)",
        "    def __init__(cls, name, bases, namespace):",
        "        cls.ready()",
    ]
    .map(str::to_owned)
    .to_vec();
    for i in 0..size {
        parts.extend([
            format!("class C{i}(metaclass=Meta):"),
            "    @classmethod".to_owned(),
            "    def ready(cls): pass".to_owned(),
        ]);
    }
    lines(parts)
}

#[test]
fn class_statements_of_one_metaclass_are_about_linear() {
    let costs: Vec<u64> = [40, 80, 160]
        .into_iter()
        .map(|size| {
            let found = analysed(
                &format!("meta-{size}"),
                &metaclass_statements(size),
                Order::Canonical,
            );
            assert_eq!(callees(&found.graph, "main.Meta.__init__").len(), size);
            total(&found.work)
        })
        .collect();
    grows_at_most(&costs, LINEAR_GROWTH_MAX);
}

fn class_tests(values: usize, sites: usize, tested: usize) -> String {
    let kinds = 4;
    let mut parts = Vec::new();
    for i in 0..kinds {
        parts.extend([format!("class C{i}:"), "    def m(self): pass".to_owned()]);
    }
    for j in 0..tested {
        parts.extend([format!("class T{j}:"), "    def m(self): pass".to_owned()]);
    }
    parts.extend((0..values).map(|i| format!("v{i} = C{}()", i % kinds)));
    let items: Vec<String> = (0..values).map(|i| format!("v{i}")).collect();
    parts.push(format!("items = [{}]", items.join(", ")));
    let outside = BUILTIN_CLASSES_CHECKED_BY_MRO[..tested].join(", ");
    let analysed_classes: Vec<String> = (0..tested).map(|j| format!("T{j}")).collect();
    for s in 0..sites {
        parts.extend([
            format!("def site{s}(x):"),
            format!("    if isinstance(x, ({outside},)):"),
            "        x.n()".to_owned(),
            format!(
                "    if not isinstance(x, ({},)):",
                analysed_classes.join(", ")
            ),
            "        x.m()".to_owned(),
            "for item in items:".to_owned(),
            format!("    site{s}(item)"),
        ]);
    }
    lines(parts)
}

fn class_test_work(values: usize, sites: usize, tested: usize) -> u64 {
    let name = format!("class-tests-{values}-{sites}-{tested}");
    let found = analysed(&name, &class_tests(values, sites, tested), Order::Canonical);
    let mut expected = vec!["<builtin>.isinstance".to_owned()];
    expected.extend((0..4).map(|i| format!("main.C{i}.m")));
    for s in [0, sites - 1] {
        assert_eq!(callees(&found.graph, &format!("main.site{s}")), expected);
    }
    total(&found.work)
}

#[test]
fn class_tests_decide_per_class_of_the_values() {
    let small = class_test_work(48, 6, 8);
    let large = class_test_work(96, 12, 16);
    grows_at_most(&[small, large], CLASS_TEST_GROWTH_MAX);
}

fn converted_containers(size: usize) -> String {
    let elements = 40;
    let mut parts = vec![
        "class E:".to_owned(),
        "    def __repr__(self): return 'e'".to_owned(),
    ];
    parts.extend((0..elements).map(|j| format!("e{j} = E()")));
    let items: Vec<String> = (0..elements).map(|j| format!("e{j}")).collect();
    parts.extend((0..size).map(|i| format!("xs{i} = [{}]", items.join(", "))));
    let names: Vec<String> = (0..size).map(|i| format!("xs{i}")).collect();
    parts.push(format!("for v in ({},):", names.join(", ")));
    parts.extend((0..size).map(|_| "    repr(v)".to_owned()));
    lines(parts)
}

#[test]
fn converting_containers_at_many_sites_shares_the_walk_of_their_elements() {
    let costs: Vec<u64> = [10, 20, 40]
        .into_iter()
        .map(|size| {
            let found = analysed(
                &format!("converted-{size}"),
                &converted_containers(size),
                Order::Canonical,
            );
            assert_eq!(
                callees(&found.graph, "main"),
                ["<builtin>.repr", "main.E.__repr__"]
            );
            found.work.applied
        })
        .collect();
    grows_at_most(&costs, SHARED_WALK_GROWTH_MAX);
}

fn compared_containers(size: usize) -> String {
    let mut parts: Vec<String> = [
        "class E:",
        "    def __eq__(self, other): return False",
        "    def __lt__(self, other): return False",
        "e = E()",
    ]
    .map(str::to_owned)
    .to_vec();
    parts.extend((0..size).map(|i| format!("xs{i} = [e, (e, {i})]")));
    parts.extend((0..size).map(|i| format!("ys{i} = (e, [{i}, e])")));
    let names: Vec<String> = (0..size).map(|i| format!("xs{i}, ys{i}")).collect();
    parts.push(format!("values = [{}]", names.join(", ")));
    parts.extend(
        [
            "def compare(a, b):",
            "    return a < b",
            "for a in values:",
            "    for b in values:",
            "        compare(a, b)",
            "sorted(values)",
        ]
        .map(str::to_owned),
    );
    lines(parts)
}

#[test]
fn containers_that_meet_at_one_comparison_cost_their_number() {
    let costs: Vec<u64> = [40, 80, 160]
        .into_iter()
        .map(|size| {
            let found = analysed(
                &format!("compared-{size}"),
                &compared_containers(size),
                Order::Canonical,
            );
            assert_eq!(
                callees(&found.graph, "main.compare"),
                ["main.E.__eq__", "main.E.__lt__"]
            );
            total(&found.work)
        })
        .collect();
    grows_at_most(&costs, LINEAR_GROWTH_MAX);
}

fn reflected_members(size: usize) -> String {
    let inherited = size / 2;
    let mut parts = vec!["import inspect".to_owned(), "class Base:".to_owned()];
    parts.extend((0..inherited).map(|i| format!("    def b{i}(self): pass")));
    parts.push("class Big(Base):".to_owned());
    parts.extend((0..size - inherited).map(|i| format!("    def m{i}(self): pass")));
    parts.extend(
        [
            "def run(rounds):",
            "    for _ in rounds:",
            "        for name, member in inspect.getmembers(Big):",
            "            member(Big())",
            "        for name, member in inspect.getmembers(Big()):",
            "            member()",
            "        for name, member in vars(Big).items():",
            "            member(Big())",
            "run(range(3))",
        ]
        .map(str::to_owned),
    );
    lines(parts)
}

#[test]
fn members_that_reflection_reads_cost_their_number() {
    let costs: Vec<u64> = [40, 80, 160]
        .into_iter()
        .map(|size| {
            let found = analysed(
                &format!("members-{size}"),
                &reflected_members(size),
                Order::Canonical,
            );
            let run = callees(&found.graph, "main.run");
            let inherited = size / 2;
            for i in 0..inherited {
                assert!(run.contains(&format!("main.Base.b{i}").as_str()));
            }
            for i in 0..size - inherited {
                assert!(run.contains(&format!("main.Big.m{i}").as_str()));
            }
            total(&found.work)
        })
        .collect();
    grows_at_most(&costs, LINEAR_GROWTH_MAX);
}

fn reflection_sites(size: usize) -> String {
    let mut parts = vec!["import inspect".to_owned()];
    for i in 0..size {
        parts.extend([
            format!("class K{i}:"),
            "    def a(self): pass".to_owned(),
            "    def b(self): pass".to_owned(),
            format!("def site{i}():"),
            format!("    for name, member in inspect.getmembers(K{i}()):"),
            "        member()".to_owned(),
            format!("site{i}()"),
        ]);
    }
    let instances: Vec<String> = (0..size).map(|i| format!("K{i}()")).collect();
    parts.extend([
        format!("for item in [{}]:", instances.join(", ")),
        "    for name, member in inspect.getmembers(item):".to_owned(),
        "        member()".to_owned(),
    ]);
    lines(parts)
}

#[test]
fn receivers_and_sites_that_reflection_reads_cost_their_number() {
    let costs: Vec<u64> = [40, 80, 160]
        .into_iter()
        .map(|size| {
            let found = analysed(
                &format!("sites-{size}"),
                &reflection_sites(size),
                Order::Canonical,
            );
            let site = callees(&found.graph, "main.site0");
            assert!(site.contains(&"main.K0.a") && site.contains(&"main.K0.b"));
            let last = format!("main.K{}.b", size - 1);
            assert!(callees(&found.graph, "main").contains(&last.as_str()));
            total(&found.work)
        })
        .collect();
    grows_at_most(&costs, LINEAR_GROWTH_MAX);
}

fn dicts_updated_pairwise(size: usize) -> String {
    let mut parts = Vec::new();
    for i in 0..size {
        parts.extend([
            format!("def f{i}(): pass"),
            format!("s{i} = {{'a': f{i}}}"),
            format!("t{i} = {{}}"),
        ]);
    }
    let sources: Vec<String> = (0..size).map(|i| format!("s{i}")).collect();
    let targets: Vec<String> = (0..size).map(|i| format!("t{i}")).collect();
    parts.extend([
        format!("for target in [{}]:", targets.join(", ")),
        format!("    for source in [{}]:", sources.join(", ")),
        "        target.update(source)".to_owned(),
        "t0['a']()".to_owned(),
    ]);
    lines(parts)
}

#[test]
fn dicts_updated_from_many_dicts_at_one_site_cost_their_number() {
    let costs: Vec<u64> = [40, 80, 160]
        .into_iter()
        .map(|size| {
            let found = analysed(
                &format!("pairwise-{size}"),
                &dicts_updated_pairwise(size),
                Order::Canonical,
            );
            let main = callees(&found.graph, "main");
            for i in 0..size {
                assert!(main.contains(&format!("main.f{i}").as_str()));
            }
            found.work.copied + found.work.edges
        })
        .collect();
    grows_at_most(&costs, LINEAR_GROWTH_MAX);
}

fn tuples_read_at_many_sites(size: usize) -> String {
    let mut parts = Vec::new();
    for i in 0..size {
        parts.extend([
            format!("def f{i}(): pass"),
            format!("def read{i}(pair):"),
            "    first, second = pair".to_owned(),
            "    return pair[0], first".to_owned(),
        ]);
    }
    let items: Vec<String> = (0..size).map(|i| format!("(f{i}, {i})")).collect();
    parts.push(format!("for pair in [{}]:", items.join(", ")));
    parts.extend((0..size).map(|i| format!("    read{i}(pair)")));
    lines(parts)
}

#[test]
fn tuples_of_one_node_read_at_many_sites_cost_their_number() {
    let costs: Vec<u64> = [40, 80, 160]
        .into_iter()
        .map(|size| {
            let found = analysed(
                &format!("tuples-{size}"),
                &tuples_read_at_many_sites(size),
                Order::Canonical,
            );
            let main = callees(&found.graph, "main");
            for i in 0..size {
                assert!(main.contains(&format!("main.read{i}").as_str()));
            }
            found.work.copied + found.work.edges
        })
        .collect();
    grows_at_most(&costs, LINEAR_GROWTH_MAX);
}
