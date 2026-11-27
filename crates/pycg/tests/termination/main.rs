use std::collections::{BTreeMap, BTreeSet};
use std::ffi::{OsStr, OsString};
use std::path::{Path, PathBuf};

use num_bigint::BigUint;
use pycg_analysis::{CAP_DEFAULT_OBJECTS, Cap, Order, Request, analyse};
use pycg_document::ProgramPart;
use serde_json::Value;

const TERMINATION: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/tests/termination");
const MAX_OBJECTS: usize = 5_000;
const SATURATION_CAP: u32 = 3;
const HIERARCHY_CLASSES: usize = 300;
const TYPE_ALIASES: usize = 1_100;
const GET_FEEDBACK: [&str; 2] = [
    "class_methods_fed_back_through_explicit_get_to_every_owner_kind",
    "property_subclass_fed_its_own_result_through_explicit_get",
];

type Graph = BTreeMap<String, BTreeSet<String>>;

struct Analysed {
    document: String,
    graph: Graph,
    objects: usize,
    tables: Vec<(&'static str, usize)>,
}

fn directories(path: &Path) -> Vec<PathBuf> {
    let mut found: Vec<PathBuf> = std::fs::read_dir(path)
        .unwrap_or_else(|error| panic!("{}: {error}", path.display()))
        .map(|entry| entry.expect("a directory entry").path())
        .filter(|path| path.is_dir())
        .collect();
    found.sort();
    found
}

fn entry_point(directory: &Path) -> PathBuf {
    let main = directory.join("main.py");
    if main.is_file() {
        return main;
    }
    let mut files: Vec<PathBuf> = std::fs::read_dir(directory)
        .expect("a program directory")
        .map(|entry| entry.expect("a directory entry").path())
        .collect();
    assert_eq!(
        files.len(),
        1,
        "{}: one module or main.py",
        directory.display()
    );
    files.remove(0)
}

fn analysed(directory: &Path, order: Order, cap: Cap) -> Analysed {
    let request = Request {
        entry_points: vec![OsString::from(entry_point(directory))],
        package: Some(directory.as_os_str().to_os_string()),
        cap,
        order,
    };
    let mut warnings = Vec::new();
    let mut warn = |warning: &OsStr| warnings.push(warning.to_os_string());
    let mut found = analyse(&request, directory, &mut warn)
        .unwrap_or_else(|error| panic!("{}: {error}", directory.display()));
    let tables = found.program.analysis.table_sizes();
    let part = ProgramPart::from_program(&mut found.program);
    let document = pycg_document::dumps(&pycg_document::build(&part, &found.results, None, None));
    let value: Value = serde_json::from_str(&document).expect("a JSON document");
    let mut graph = Graph::new();
    for (caller, sites) in value["calls"].as_object().expect("calls") {
        let callees = graph.entry(caller.clone()).or_default();
        for site in sites.as_array().expect("sites") {
            for callee in site["callees"].as_array().expect("callees") {
                callees.insert(callee.as_str().expect("a name").to_owned());
            }
        }
    }
    Analysed {
        document: format!("{warnings:?}\n{document}"),
        graph,
        objects: tables.iter().map(|(_, size)| size).sum(),
        tables,
    }
}

fn default_cap() -> Cap {
    Cap::Objects(BigUint::from(CAP_DEFAULT_OBJECTS))
}

fn edges(graph: &Graph) -> BTreeSet<(String, String)> {
    graph
        .iter()
        .flat_map(|(caller, callees)| {
            callees
                .iter()
                .map(move |callee| (caller.clone(), callee.clone()))
        })
        .collect()
}

fn fixed() -> Vec<PathBuf> {
    directories(&Path::new(TERMINATION).join("fixed"))
}

#[test]
fn every_fixed_program_ends_under_the_bound_of_objects() {
    for directory in fixed() {
        let found = analysed(&directory, Order::Canonical, default_cap());
        assert!(
            found.objects < MAX_OBJECTS,
            "{}: {} objects",
            directory.display(),
            found.objects
        );
    }
}

#[test]
fn fed_back_get_results_end_without_a_cap() {
    for name in GET_FEEDBACK {
        let directory = Path::new(TERMINATION).join("fixed").join(name);
        let found = analysed(&directory, Order::Canonical, Cap::Unbounded);
        assert!(
            found.objects < MAX_OBJECTS,
            "{name}: {} objects",
            found.objects
        );
    }
}

#[test]
fn every_fixed_program_gives_one_document_in_either_order() {
    for directory in fixed() {
        let canonical = analysed(&directory, Order::Canonical, default_cap());
        let reversed = analysed(&directory, Order::LastInFirstOut, default_cap());
        assert_eq!(
            canonical.document,
            reversed.document,
            "{}",
            directory.display()
        );
    }
}

#[test]
fn every_fixed_program_at_a_small_cap_ends_alike_in_either_order_with_no_new_edge() {
    for directory in fixed() {
        let full = edges(&analysed(&directory, Order::Canonical, default_cap()).graph);
        let cap = || Cap::Objects(BigUint::from(SATURATION_CAP));
        let canonical = analysed(&directory, Order::Canonical, cap());
        let reversed = analysed(&directory, Order::LastInFirstOut, cap());
        assert_eq!(
            canonical.document,
            reversed.document,
            "{}",
            directory.display()
        );
        for found in [&canonical, &reversed] {
            assert!(
                found.objects < MAX_OBJECTS,
                "{}: {} objects",
                directory.display(),
                found.objects
            );
            let added: Vec<_> = edges(&found.graph).difference(&full).cloned().collect();
            assert!(
                added.is_empty(),
                "{}: the cap adds {added:?}",
                directory.display()
            );
        }
    }
}

#[test]
fn a_program_fills_every_counted_table() {
    let found = analysed(
        &Path::new(TERMINATION).join("filling"),
        Order::Canonical,
        default_cap(),
    );
    let empty: Vec<&str> = found
        .tables
        .iter()
        .filter(|(_, size)| *size == 0)
        .map(|(name, _)| *name)
        .collect();
    assert!(empty.is_empty(), "tables left empty: {empty:?}");
}

fn written(name: &str, source: &str) -> PathBuf {
    let directory = Path::new(env!("CARGO_TARGET_TMPDIR"))
        .join("termination")
        .join(name);
    std::fs::create_dir_all(&directory).expect("a program directory is made");
    std::fs::write(directory.join("main.py"), source).expect("the program is written");
    directory
}

fn long_hierarchies(length: usize) -> String {
    let last = length - 1;
    let mut lines: Vec<String> = [
        "class C0(Exception):",
        "    def run(self): pass",
        "    @staticmethod",
        "    def make(): pass",
        "class M0(type):",
        "    def describe(cls): pass",
    ]
    .map(str::to_owned)
    .to_vec();
    for i in 1..last {
        lines.push(format!("class C{i}(C{}): pass", i - 1));
        lines.push(format!("class M{i}(M{}): pass", i - 1));
    }
    lines.extend([
        format!("class C{last}(C{}):", last - 1),
        "    @staticmethod".to_owned(),
        "    def make(): pass".to_owned(),
        format!("class M{last}(M{}): pass", last - 1),
        format!("class K(metaclass=M{last}): pass"),
        "K.describe()".to_owned(),
        format!("C{last}().run()"),
        "def declared(kind: type[C0], meta: type[M0], value: C0):".to_owned(),
        "    kind.make()".to_owned(),
        "    meta.describe(K)".to_owned(),
        "    value.run()".to_owned(),
        "def handle():".to_owned(),
        "    try:".to_owned(),
        format!("        raise C{last}()"),
        "    except C0 as error:".to_owned(),
        "        error.run()".to_owned(),
        "def check(value):".to_owned(),
        "    match value:".to_owned(),
        "        case C0():".to_owned(),
        "            value.run()".to_owned(),
        format!("check(C{last}())"),
    ]);
    lines.join("\n") + "\n"
}

fn callees<'a>(graph: &'a Graph, caller: &str) -> Vec<&'a str> {
    graph
        .get(caller)
        .map(|callees| callees.iter().map(String::as_str).collect())
        .unwrap_or_default()
}

#[test]
fn a_hierarchy_longer_than_the_stack_is_analysed() {
    let directory = written("long", &long_hierarchies(HIERARCHY_CLASSES));
    let found = analysed(&directory, Order::Canonical, default_cap());
    let last = HIERARCHY_CLASSES - 1;
    let made = format!("main.C{last}.make");
    assert_eq!(
        callees(&found.graph, "main.declared"),
        [
            "main.C0.make",
            "main.C0.run",
            made.as_str(),
            "main.M0.describe"
        ]
    );
    let main = callees(&found.graph, "main");
    for callee in ["main.C0.run", "main.M0.describe", "main.check"] {
        assert!(main.contains(&callee), "{callee}");
    }
    assert_eq!(
        callees(&found.graph, "main.handle"),
        ["<builtin>.Exception.__init__", "main.C0.run"]
    );
    assert_eq!(callees(&found.graph, "main.check"), ["main.C0.run"]);
}

#[test]
fn a_hierarchy_wider_than_the_stack_is_analysed() {
    let width = HIERARCHY_CLASSES;
    let mut lines = vec![
        "class Root:".to_owned(),
        "    def run(self): pass".to_owned(),
    ];
    for i in 0..width {
        lines.extend([
            format!("class Sub{i}(Root): pass"),
            format!("class Base{i}:"),
            format!("    def run{i}(self): pass"),
        ]);
    }
    let bases: Vec<String> = (0..width).map(|i| format!("Base{i}")).collect();
    let last = width - 1;
    lines.extend([
        format!("class Wide({}): pass", bases.join(", ")),
        format!("Wide().run{last}()"),
        format!("Sub{last}().run()"),
        "def declared(kind: type[Root], value: Root):".to_owned(),
        "    kind.run(value)".to_owned(),
        "    value.run()".to_owned(),
    ]);
    let directory = written("wide", &(lines.join("\n") + "\n"));
    let found = analysed(&directory, Order::Canonical, default_cap());
    let run = format!("main.Base{last}.run{last}");
    assert_eq!(
        callees(&found.graph, "main"),
        [run.as_str(), "main.Root.run"]
    );
    assert_eq!(callees(&found.graph, "main.declared"), ["main.Root.run"]);
}

#[test]
fn a_chain_of_type_aliases_longer_than_the_stack_is_analysed() {
    let last = TYPE_ALIASES;
    let mut source = "class C:\n    def f(self): pass\nT0 = C | None\n".to_owned();
    for i in 1..=last {
        source += &format!("T{i} = T{} | None\n", i - 1);
    }
    source += &format!("def value(x: T{last}):\n    x.f()\n");
    source += &format!("def quoted(x: 'T{last}'):\n    x.f()\n");
    source += &format!("def items(xs: list[T{last}]):\n    for x in xs:\n        x.f()\n");
    let directory = written("aliases", &source);
    let found = analysed(&directory, Order::Canonical, default_cap());
    for function in ["value", "quoted", "items"] {
        assert_eq!(
            callees(&found.graph, &format!("main.{function}")),
            ["main.C.f"],
            "{function}"
        );
    }
}
