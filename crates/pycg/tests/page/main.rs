mod generate;

use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::OnceLock;
use std::sync::atomic::{AtomicUsize, Ordering};

use serde_json::{Value, json};

const DOCUMENT_OPEN: &str = "<script type=\"application/json\" id=\"pycg-document\">";
const SCRIPT_CLOSE: &str = "</script>";
const LARGE_DEFINITIONS: usize = 20000;
const LARGE_SITES: usize = 100000;
const LARGE_SEED: u64 = 1;
const HOSTILE: [&str; 14] = [
    "</script><script>alert(1)</script>",
    "</SCRIPT >",
    "<!--<script>",
    "<script>",
    "-->",
    "]]>",
    "<\\/script>",
    "&lt;b&gt;",
    "\"'`",
    "  ",
    "constructor",
    "__proto__",
    "toString",
    "ünïcödé.名前",
];

static SCRATCH: AtomicUsize = AtomicUsize::new(0);

fn root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("../..")
}

fn sample() -> PathBuf {
    root().join("tests/data/view/sample.json")
}

fn fake_dom() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/page/view_dom.js")
}

struct Scratch(PathBuf);

impl Scratch {
    fn new() -> Scratch {
        let number = SCRATCH.fetch_add(1, Ordering::Relaxed);
        let path = std::env::temp_dir().join(format!("pycg-page-{}-{number}", std::process::id()));
        fs::create_dir_all(&path).expect("the scratch directory is made");
        Scratch(path)
    }

    fn path(&self, name: &str) -> PathBuf {
        self.0.join(name)
    }
}

impl Drop for Scratch {
    fn drop(&mut self) {
        fs::remove_dir_all(&self.0).expect("the scratch directory is removed");
    }
}

fn all() -> Value {
    json!({"outside": true, "implicit": true, "unresolved": true})
}

fn without(filter: &str) -> Value {
    let mut filters = all();
    filters[filter] = json!(false);
    filters
}

fn quoted(value: Value) -> String {
    serde_json::to_string(&value).expect("a value is JSON")
}

fn run_node(scratch: &Scratch, program: &str) -> Value {
    let path = scratch.path("program.js");
    fs::write(&path, program).expect("the program is written");
    let output = Command::new("node")
        .arg(&path)
        .output()
        .expect("node runs: the page tests need node on the PATH");
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    serde_json::from_slice(&output.stdout).expect("node writes JSON")
}

fn view(document: &Path, page: &Path) {
    let output = Command::new(env!("CARGO_BIN_EXE_pycg"))
        .arg("view")
        .arg(document)
        .arg("-o")
        .arg(page)
        .output()
        .expect("pycg view runs");
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
}

fn written_page(scratch: &Scratch, source: &Path) -> String {
    let page = scratch.path("page.html");
    view(source, &page);
    fs::read_to_string(page).expect("the page is UTF-8")
}

fn script(html: &str, name: &str) -> String {
    let open = format!("<script id=\"{name}\">");
    let start = html.find(&open).expect("the page has the script") + open.len();
    let end = start + html[start..].find(SCRIPT_CLOSE).expect("the script ends");
    html[start..end].to_owned()
}

fn logic_of(scratch: &Scratch, expression: &str, source: &Path) -> Value {
    let html = written_page(scratch, &sample());
    let program = format!(
        "{}\nconst fs = require('fs');\nconst doc = JSON.parse(fs.readFileSync({}, 'utf8'));\nconst index = PyCG.buildIndex(doc);\nconst ALL = {};\nprocess.stdout.write(JSON.stringify({expression}));\n",
        script(&html, "pycg-logic"),
        quoted(json!(source.to_str().expect("a UTF-8 path"))),
        quoted(all()),
    );
    run_node(scratch, &program)
}

fn logic(expression: &str) -> Value {
    logic_of(&Scratch::new(), expression, &sample())
}

fn rows(function: &str, name: &str, filters: &Value) -> Value {
    logic(&format!(
        "PyCG.{function}(index, {}, {}).map(r => [r.name, r.sites.map(s => [s.line, s.col, s.implicit || null])])",
        quoted(json!(name)),
        quoted(filters.clone())
    ))
}

fn run_page(scratch: &Scratch, html: &str, steps: &str, hash: &str) -> Value {
    let html_path = scratch.path("shown.html");
    fs::write(&html_path, html).expect("the page is written");
    let program = format!(
        "const {{loadPage, Event}} = require({});\nconst fs = require('fs');\nconst html = fs.readFileSync({}, 'utf8');\nconst page = loadPage(html, {{hash: {}}});\nconst out = {{}};\n{steps}\nprocess.stdout.write(JSON.stringify(out));\n",
        quoted(json!(fake_dom().to_str().expect("a UTF-8 path"))),
        quoted(json!(html_path.to_str().expect("a UTF-8 path"))),
        quoted(json!(hash)),
    );
    run_node(scratch, &program)
}

fn page_of(scratch: &Scratch, steps: &str, source: &Path, hash: &str) -> Value {
    let html = written_page(scratch, source);
    run_page(scratch, &html, steps, hash)
}

fn page(steps: &str, hash: &str) -> Value {
    page_of(&Scratch::new(), steps, &sample(), hash)
}

fn write_json(scratch: &Scratch, name: &str, value: &Value) -> PathBuf {
    let path = scratch.path(name);
    fs::write(&path, quoted(value.clone())).expect("the document is written");
    path
}

fn document(parts: Value) -> Value {
    let mut base = json!({
        "format": "pycg/1",
        "tool": {"name": "pycg", "version": "1.0.0", "typeshed": "abc"},
        "package": {"name": null, "version": null},
        "modules": {},
        "definitions": {},
        "exports": {},
        "outside": {},
        "calls": {},
    });
    for (key, value) in parts.as_object().expect("the parts are an object") {
        base[key] = value.clone();
    }
    base
}

fn hostile_document() -> Value {
    let mut modules = serde_json::Map::new();
    let mut definitions = serde_json::Map::new();
    let mut outside = serde_json::Map::new();
    let mut calls = serde_json::Map::new();
    for (i, text) in HOSTILE.iter().enumerate() {
        let module = format!("m{i}.{text}");
        modules.insert(
            module.clone(),
            json!({"file": format!("{text}.py"), "kind": "source", "status": "analysed"}),
        );
        definitions.insert(
            module.clone(),
            json!({"kind": "module", "module": module, "lines": [1, 2]}),
        );
        outside.insert(format!("x.{text}"), json!({"known": "name"}));
        calls.insert(
            module,
            json!([
                {"line": 1, "col": 0, "end": [1, 4], "callees": [format!("x.{text}")]},
                {"line": 2, "col": 0, "end": [2, 4], "callees": [], "unresolved": text},
            ]),
        );
    }
    modules.insert(
        "broken".to_owned(),
        json!({"file": "broken.py", "kind": "source", "status": "failed", "cause": HOSTILE[0]}),
    );
    document(json!({
        "package": {"name": HOSTILE[0], "version": HOSTILE[2]},
        "modules": modules,
        "definitions": definitions,
        "outside": outside,
        "calls": calls,
    }))
}

fn percent_encoded(text: &str) -> String {
    text.bytes()
        .map(|byte| match byte {
            b'A'..=b'Z' | b'a'..=b'z' | b'0'..=b'9' | b'_' | b'.' | b'-' | b'~' => {
                char::from(byte).to_string()
            }
            _ => format!("%{byte:02X}"),
        })
        .collect()
}

fn edges(document: &Value) -> BTreeMap<String, BTreeSet<String>> {
    let mut graph: BTreeMap<String, BTreeSet<String>> = BTreeMap::new();
    for (name, definition) in document["definitions"].as_object().expect("definitions") {
        if definition["kind"] != "class" {
            graph.entry(name.clone()).or_default();
        }
    }
    for name in document["outside"].as_object().expect("outside").keys() {
        graph.entry(name.clone()).or_default();
    }
    for (caller, sites) in document["calls"].as_object().expect("calls") {
        for site in sites.as_array().expect("sites") {
            for callee in site["callees"].as_array().expect("callees") {
                graph
                    .get_mut(caller)
                    .expect("a caller is a definition")
                    .insert(callee.as_str().expect("a callee name").to_owned());
            }
        }
    }
    graph
}

fn text<'v>(value: &'v Value, key: &str) -> &'v str {
    value[key].as_str().expect("a text")
}

fn texts(value: &Value, key: &str) -> Vec<String> {
    value[key]
        .as_array()
        .expect("a list")
        .iter()
        .map(|item| item.as_str().expect("a text").to_owned())
        .collect()
}

fn one_with<'t>(items: &'t [String], part: &str) -> &'t str {
    items
        .iter()
        .find(|item| item.contains(part))
        .unwrap_or_else(|| panic!("no item has {part:?} in {items:?}"))
}

fn site(line: u64, col: u64, end: [u64; 2], callees: &[&str], extra: Value) -> Value {
    let mut site = json!({"line": line, "col": col, "end": end, "callees": callees});
    for (key, value) in extra.as_object().expect("the extra parts are an object") {
        site[key] = value.clone();
    }
    site
}

fn labels_of(expression: &str, source: &Path, scratch: &Scratch) -> Value {
    logic_of(
        scratch,
        &format!("{expression}.map(r => [r.name, r.sites.map(s => PyCG.siteLabel(index, s))])"),
        source,
    )
}

struct Real {
    path: PathBuf,
    document: Value,
    _scratch: Scratch,
}

fn real() -> &'static Real {
    static REAL: OnceLock<Real> = OnceLock::new();
    REAL.get_or_init(|| {
        let scratch = Scratch::new();
        let package = root().join("evaluation/common");
        let mut files: Vec<PathBuf> = fs::read_dir(&package)
            .expect("the package is read")
            .map(|entry| entry.expect("an entry").path())
            .filter(|path| path.extension().is_some_and(|suffix| suffix == "py"))
            .collect();
        files.sort();
        let path = scratch.path("common.json");
        let output = Command::new(env!("CARGO_BIN_EXE_pycg"))
            .arg("--package")
            .arg(&package)
            .args(&files)
            .arg("--package-name")
            .arg("common")
            .arg("-o")
            .arg(&path)
            .output()
            .expect("pycg runs");
        assert!(
            output.status.success(),
            "{}",
            String::from_utf8_lossy(&output.stderr)
        );
        let document = serde_json::from_slice(&fs::read(&path).expect("the document is read"))
            .expect("the document is JSON");
        Real {
            path,
            document,
            _scratch: scratch,
        }
    })
}

fn large() -> &'static (PathBuf, Scratch) {
    static LARGE: OnceLock<(PathBuf, Scratch)> = OnceLock::new();
    LARGE.get_or_init(|| {
        let scratch = Scratch::new();
        let document = generate::generate(LARGE_DEFINITIONS, LARGE_SITES, LARGE_SEED);
        let path = write_json(&scratch, "large.json", &document);
        (path, scratch)
    })
}

#[test]
fn counts() {
    assert_eq!(
        logic("index.counts"),
        json!({"modules": 9, "definitions": 40, "sites": 47, "edges": 46, "outside": 16, "unresolved": 3})
    );
}

#[test]
fn callees_are_in_the_order_of_their_first_site() {
    assert_eq!(
        rows("callees", "shop.cli.main", &all()),
        json!([
            ["shop.cart.Cart.__init__", [[15, 11, null]]],
            ["shop.cli.Session.__enter__", [[16, 9, "with"]]],
            ["shop.cli.Session.__exit__", [[16, 9, "with"]]],
            ["shop.cart.Cart.add", [[17, 8, null]]],
            ["json.loads", [[17, 17, null]]],
            ["requests.get", [[18, 11, null]]],
            ["requests.Response.json", [[18, 11, null]]],
            ["<builtin>.print", [[19, 4, null]]],
            ["shop._speedups.escape", [[19, 10, null]]],
            ["<builtin>.str.__new__", [[19, 17, null]]],
            ["shop.cart.Cart.__str__", [[19, 17, null]]],
            ["shop.util.load", [[20, 11, null]]],
        ])
    );
}

#[test]
fn a_site_shows_its_end_only_to_tell_it_from_another() {
    let scratch = Scratch::new();
    let labels = labels_of(
        r#"PyCG.callees(index, "shop.cli.main", ALL)"#,
        &sample(),
        &scratch,
    );
    let labels: BTreeMap<String, Value> = labels
        .as_array()
        .expect("rows")
        .iter()
        .map(|row| (row[0].as_str().expect("a name").to_owned(), row[1].clone()))
        .collect();
    assert_eq!(labels["requests.get"], json!(["18:11–32"]));
    assert_eq!(labels["requests.Response.json"], json!(["18:11–39"]));
    assert_eq!(labels["shop.cart.Cart.__init__"], json!(["15:11"]));
    assert_eq!(labels["shop.cli.Session.__enter__"], json!(["16:9"]));
}

#[test]
fn a_site_in_another_module_shows_its_file() {
    let scratch = Scratch::new();
    assert_eq!(
        labels_of(
            r#"PyCG.callees(index, "shop.check", ALL)"#,
            &sample(),
            &scratch
        ),
        json!([
            ["shop.check.report", ["10:0"]],
            ["shop.cli.main", ["shop/__init__.py 7:11"]],
            ["<builtin>.str.__new__", ["shop/__init__.py 7:17"]],
            ["shop.cart.Cart.__str__", ["shop/__init__.py 7:17"]],
        ])
    );
    assert_eq!(
        labels_of(
            r#"PyCG.callers(index, "shop.cli.main", ALL)"#,
            &sample(),
            &scratch
        ),
        json!([
            ["shop.check", ["shop/__init__.py 7:11"]],
            ["shop.cli", ["23:4"]]
        ])
    );
    let check = logic(r#"PyCG.describe(index, "shop.check")"#);
    assert_eq!(
        (&check["file"], &check["lines"]),
        (&json!("shop/check.py"), &json!([1, 10]))
    );
    assert_eq!(check["otherModules"], json!(["shop"]));
}

#[test]
fn the_links_of_a_comparison_chain_are_two_sites() {
    assert_eq!(
        logic(
            r#"PyCG.callees(index, "shop.check.report", ALL).map(r => [r.name, r.sites.map(s => [PyCG.siteLabel(index, s), s.implicit])])"#
        ),
        json!([[
            "shop.check.Level.__lt__",
            [["8:11", "operator"], ["8:17", "operator"]]
        ]])
    );
}

#[test]
fn sites_in_other_modules_come_last_and_keep_their_own_position() {
    let scratch = Scratch::new();
    let outside: BTreeMap<String, Value> = "abcde"
        .chars()
        .map(|name| (name.to_string(), json!({"known": "name"})))
        .collect();
    let source = write_json(
        &scratch,
        "graph.json",
        &document(json!({
            "modules": {
                "m": {"file": "m.py", "kind": "source", "status": "analysed"},
                "n": {"file": "n.py", "kind": "source", "status": "analysed"},
            },
            "definitions": {"m": {"kind": "module", "module": "m", "lines": [1, 3]}},
            "outside": outside,
            "calls": {"m": [
                site(1, 0, [1, 7], &["e"], json!({})),
                site(2, 0, [2, 3], &["c"], json!({})),
                site(1, 0, [1, 5], &["a"], json!({"module": "n"})),
                site(1, 0, [1, 9], &["b"], json!({"module": "n"})),
                site(1, 0, [1, 5], &["d"], json!({"module": "o"})),
            ]},
        })),
    );
    assert_eq!(
        labels_of(r#"PyCG.callees(index, "m", ALL)"#, &source, &scratch),
        json!([
            ["e", ["1:0"]],
            ["c", ["2:0"]],
            ["a", ["n.py 1:0–5"]],
            ["b", ["n.py 1:0–9"]],
            ["d", ["o 1:0"]],
        ])
    );
}

#[test]
fn sites_with_the_same_start_are_ordered_by_their_end() {
    let scratch = Scratch::new();
    let outside: BTreeMap<String, Value> = "abcd"
        .chars()
        .map(|name| (name.to_string(), json!({"known": "name"})))
        .collect();
    let source = write_json(
        &scratch,
        "graph.json",
        &document(json!({
            "modules": {"m": {"file": "m.py", "kind": "source", "status": "analysed"}},
            "definitions": {"m": {"kind": "module", "module": "m", "lines": [1, 3]}},
            "outside": outside,
            "calls": {"m": [
                site(1, 0, [1, 5], &["b"], json!({})),
                site(1, 0, [3, 1], &["a"], json!({})),
                site(2, 4, [2, 9], &["c"], json!({})),
                site(2, 4, [2, 9], &["d"], json!({"implicit": "with"})),
            ]},
        })),
    );
    assert_eq!(
        labels_of(r#"PyCG.callees(index, "m", ALL)"#, &source, &scratch),
        json!([
            ["b", ["1:0–5"]],
            ["a", ["1:0–3:1"]],
            ["c", ["2:4"]],
            ["d", ["2:4"]]
        ])
    );
}

fn names(rows: &Value) -> Vec<String> {
    rows.as_array()
        .expect("rows")
        .iter()
        .map(|row| row[0].as_str().expect("a name").to_owned())
        .collect()
}

#[test]
fn callees_without_outside_callees() {
    assert_eq!(
        names(&rows("callees", "shop.cli.main", &without("outside"))),
        [
            "shop.cart.Cart.__init__",
            "shop.cli.Session.__enter__",
            "shop.cli.Session.__exit__",
            "shop.cart.Cart.add",
            "shop.cart.Cart.__str__",
            "shop.util.load",
        ]
    );
}

#[test]
fn callees_without_implicit_calls() {
    let found = names(&rows("callees", "shop.cli.main", &without("implicit")));
    assert!(!found.contains(&"shop.cli.Session.__enter__".to_owned()));
    assert!(!found.contains(&"shop.cli.Session.__exit__".to_owned()));
    assert!(found.contains(&"shop.cart.Cart.__init__".to_owned()));
    assert_eq!(
        rows("callees", "shop.cart.Cart.total", &without("implicit")),
        json!([])
    );
}

#[test]
fn callees_of_a_name_without_calls() {
    assert_eq!(rows("callees", "shop.util.<lambda1>", &all()), json!([]));
    assert_eq!(rows("callees", "json.loads", &all()), json!([]));
    assert_eq!(rows("callees", "no.such.name", &all()), json!([]));
}

#[test]
fn callers_group_the_sites_of_each_caller() {
    assert_eq!(
        rows("callers", "shop.util.fmt", &all()),
        json!([
            ["shop.base.Base.describe", [[8, 15, null], [8, 32, null]]],
            ["shop.cart.Cart.__str__", [[28, 15, null]]],
            ["shop.check.Level.__lt__", [[5, 15, null], [5, 27, null]]],
            ["shop.deep.build", [[4, 11, null]]],
            ["shop.util.apply", [[24, 16, null]]],
        ])
    );
}

#[test]
fn callers_follow_the_filters() {
    assert_eq!(
        rows("callers", "json.loads", &all()),
        json!([["shop.cli.main", [[17, 17, null]]]])
    );
    assert_eq!(
        rows("callers", "json.loads", &without("outside")),
        json!([])
    );
    assert_eq!(
        rows(
            "callers",
            "shop.cli.Session.__enter__",
            &without("implicit")
        ),
        json!([])
    );
    assert_eq!(
        rows("callers", "shop.cli.main", &all()),
        json!([
            ["shop.check", [[7, 11, null]]],
            ["shop.cli", [[23, 4, null]]]
        ])
    );
}

#[test]
fn a_callback_is_a_callee_of_the_library_call() {
    assert_eq!(
        rows("callees", "shop.util.apply", &all()),
        json!([
            ["<builtin>.list.__init__", [[24, 11, null]]],
            ["<builtin>.map.__init__", [[24, 16, null]]],
            ["shop.util.<lambda1>", [[24, 16, null]]],
            ["shop.util.fmt", [[24, 16, null]]],
        ])
    );
}

fn unresolved(name: &str, filters: &str) -> Value {
    logic(&format!(
        "PyCG.unresolved(index, {}, {filters}).map(s => [s.line, s.col, s.unresolved])",
        quoted(json!(name))
    ))
}

#[test]
fn unresolved_sites_and_their_cause() {
    for (name, causes) in [
        ("shop.util.call_by_name", json!([[31, 11, "computed name"]])),
        (
            "shop.util.run_hook",
            json!([[39, 11, "no value"], [40, 11, "outside value"]]),
        ),
    ] {
        assert_eq!(unresolved(name, &quoted(all())), causes);
        assert_eq!(unresolved(name, &quoted(without("unresolved"))), json!([]));
    }
    assert_eq!(unresolved("shop.cli.main", "ALL"), json!([]));
}

fn expand(name: &str, direction: &str, path: &[&str], filters: &Value) -> Value {
    logic(&format!(
        "PyCG.expand(index, {}, {}, {}, {}).map(r => [r.name, r.recursive, r.expandable])",
        quoted(json!(name)),
        quoted(json!(direction)),
        quoted(filters.clone()),
        quoted(json!(path))
    ))
}

#[test]
fn expanding_marks_direct_recursion() {
    let walk = "shop.util.walk";
    assert_eq!(
        expand(walk, "callees", &[walk], &all()),
        json!([[walk, true, false]])
    );
    assert_eq!(
        expand(walk, "callers", &[walk], &all()),
        json!([["shop.cart.Cart.tree", false, false], [walk, true, false]])
    );
}

#[test]
fn expanding_marks_mutual_recursion_on_the_path() {
    let (even, odd) = ("shop.util.is_even", "shop.util.is_odd");
    assert_eq!(
        expand(even, "callees", &[even], &all()),
        json!([[odd, false, true]])
    );
    assert_eq!(
        expand(odd, "callees", &[even, odd], &all()),
        json!([[even, true, false]])
    );
}

#[test]
fn a_row_is_expandable_only_with_visible_children() {
    let name = "shop.cart.Cart.__str__";
    let total: Vec<Value> = expand(name, "callees", &[name], &all())
        .as_array()
        .expect("rows")
        .iter()
        .filter(|row| row[0].as_str().expect("a name").contains("total"))
        .cloned()
        .collect();
    assert_eq!(total, [json!(["shop.cart.Cart.total", false, true])]);
    let hidden = expand(name, "callees", &[name], &without("implicit"));
    assert!(hidden.as_array().expect("rows").contains(&json!([
        "shop.cart.Cart.total",
        false,
        false
    ])));
    assert_eq!(
        expand("shop.util.fmt", "callees", &["shop.util.fmt"], &all()),
        json!([["<builtin>.str.format", false, false]])
    );
}

fn search_in(query: &str, limit: usize, source: &Path) -> Value {
    logic_of(
        &Scratch::new(),
        &format!(
            "(r => [r.total, r.entries.map(e => [e.name, e.kind, e.target])])(PyCG.search(index, {}, {limit}))",
            quoted(json!(query))
        ),
        source,
    )
}

fn search(query: &str) -> Value {
    search_in(query, 10, &sample())
}

#[test]
fn search_ranks_an_exact_last_name_first() {
    assert_eq!(
        search("walk")[1][0],
        json!(["shop.util.walk", "function", "shop.util.walk"])
    );
    assert_eq!(search("  WALK ")[1][0][0], json!("shop.util.walk"));
}

#[test]
fn search_ranks_definitions_before_exports_and_outside_names() {
    let entries = search("cart")[1].clone();
    let first: Vec<&Value> = entries.as_array().expect("entries")[..3]
        .iter()
        .map(|entry| &entry[0])
        .collect();
    assert_eq!(
        first,
        [
            &json!("shop.cart.Cart"),
            &json!("shop.cart"),
            &json!("shop.Cart")
        ]
    );
    assert_eq!(entries[2], json!(["shop.Cart", "export", "shop.cart.Cart"]));
}

#[test]
fn search_matches_a_dotted_suffix() {
    assert_eq!(search("Cart.add")[1][0][0], json!("shop.cart.Cart.add"));
}

#[test]
fn search_finds_outside_names_exports_and_modules_without_definitions() {
    assert_eq!(
        search("safe_load")[1][0],
        json!(["yaml.safe_load", "outside", "yaml.safe_load"])
    );
    assert_eq!(
        search("shop.escape")[1][0],
        json!(["shop.escape", "export", "shop._speedups.escape"])
    );
    assert_eq!(
        search("broken")[1],
        json!([["shop.broken", "module", "shop.broken"]])
    );
    assert_eq!(
        search("speedups")[1][0],
        json!(["shop._speedups", "module", "shop._speedups"])
    );
}

#[test]
fn search_limits_the_entries_and_counts_every_match() {
    let found = search_in("s", 5, &sample());
    assert_eq!(found[1].as_array().expect("entries").len(), 5);
    assert!(found[0].as_u64().expect("a total") > 40);
    assert_eq!(search(""), json!([0, []]));
    assert_eq!(search("   "), json!([0, []]));
    assert_eq!(search("zzz"), json!([0, []]));
}

fn module_map(filters: &Value) -> BTreeMap<String, Value> {
    let rows = logic(&format!(
        "PyCG.moduleMap(index, {})",
        quoted(filters.clone())
    ));
    let rows = rows.as_array().expect("rows");
    let listed: Vec<&str> = rows
        .iter()
        .map(|row| row["name"].as_str().expect("a name"))
        .collect();
    let mut sorted = listed.clone();
    sorted.sort_unstable();
    assert_eq!(listed, sorted);
    rows.iter()
        .map(|row| {
            (
                row["name"].as_str().expect("a name").to_owned(),
                row.clone(),
            )
        })
        .collect()
}

#[test]
fn module_map_counts_edges_between_modules() {
    let modules = module_map(&all());
    let cli = &modules["shop.cli"];
    assert_eq!(
        cli["out"],
        json!([["shop.cart", 3], ["shop._speedups", 1], ["shop.util", 1]])
    );
    assert_eq!(
        (&cli["within"], &cli["outside"], &cli["callsOut"]),
        (&json!(3), &json!(5), &json!(5))
    );
    assert_eq!(
        modules["shop.util"]["in"],
        json!([
            ["shop.cart", 2],
            ["shop.base", 1],
            ["shop.check", 1],
            ["shop.cli", 1],
            ["shop.deep", 1]
        ])
    );
    let (shop, check) = (&modules["shop"], &modules["shop.check"]);
    assert_eq!(shop["out"], json!([["shop.cart", 1], ["shop.cli", 1]]));
    assert_eq!(shop["outside"], json!(1));
    assert_eq!(check["out"], json!([["shop.util", 1]]));
    assert_eq!(check["within"], json!(2));
    assert_eq!(modules["shop.util"]["within"], json!(9));
    assert_eq!(modules["shop.util"]["definitions"], json!(12));
    assert_eq!(modules["shop.base"]["outside"], json!(1));
}

#[test]
fn module_map_marks_failed_and_extension_modules() {
    let modules = module_map(&all());
    let broken = &modules["shop.broken"];
    assert_eq!(
        (&broken["status"], &broken["cause"]),
        (&json!("failed"), &json!("SyntaxError (line 3)"))
    );
    assert_eq!(broken["definitions"], json!(0));
    let deep = &modules["shop.deep"];
    assert_eq!(
        (&deep["status"], &deep["cause"]),
        (&json!("partial"), &json!("DeepNesting (line 5)"))
    );
    assert_eq!(deep["definitions"], json!(1));
    let speedups = &modules["shop._speedups"];
    assert_eq!(speedups["kind"], json!("extension"));
    assert_eq!(speedups["in"], json!([["shop.cli", 1]]));
    assert_eq!(speedups["definitions"], json!(1));
}

#[test]
fn module_map_and_describe_give_the_files_that_a_module_shadows() {
    let modules = module_map(&all());
    assert_eq!(
        modules["shop.util"]["shadows"],
        json!(["shop/util.abi3.so", "shop/util.cpython-312-darwin.so"])
    );
    assert_eq!(modules["shop.cart"]["shadows"], json!([]));
    assert_eq!(
        logic(r#"PyCG.describe(index, "shop")"#)["shadows"],
        json!(["shop.py"])
    );
    assert_eq!(
        logic(r#"PyCG.describe(index, "shop.util.fmt")"#)["shadows"],
        json!([])
    );
}

#[test]
fn module_map_follows_the_filters() {
    let cli = module_map(&without("outside"))["shop.cli"].clone();
    assert_eq!(cli["out"], json!([["shop.cart", 3], ["shop.util", 1]]));
    assert_eq!(cli["outside"], json!(0));
    let modules = module_map(&without("implicit"));
    assert_eq!(modules["shop.cli"]["within"], json!(1));
    assert_eq!(modules["shop.util"]["within"], json!(8));
    let total: u64 = module_map(&all())
        .values()
        .map(|row| {
            ["within", "outside", "callsOut"]
                .iter()
                .map(|key| row[*key].as_u64().expect("a count"))
                .sum::<u64>()
        })
        .sum();
    assert_eq!(total, 46);
}

#[test]
fn module_members_are_in_line_order() {
    let members = logic(r#"PyCG.members(index, "shop.cart")"#);
    assert_eq!(
        members.as_array().expect("members")[..3],
        [
            json!("shop.cart.Cart"),
            json!("shop.cart.Cart.__init__"),
            json!("shop.cart.Cart.add")
        ]
    );
    assert_eq!(
        logic(r#"PyCG.members(index, "shop._speedups")"#),
        json!(["shop._speedups.escape"])
    );
    assert_eq!(logic(r#"PyCG.members(index, "shop.broken")"#), json!([]));
}

#[test]
fn tree_nests_modules_classes_and_functions() {
    assert_eq!(logic("PyCG.children(index, null)"), json!(["shop"]));
    assert_eq!(
        logic(r#"PyCG.children(index, "shop")"#),
        json!([
            "shop._speedups",
            "shop.base",
            "shop.broken",
            "shop.cart",
            "shop.check",
            "shop.cli",
            "shop.deep",
            "shop.util",
        ])
    );
    let util = logic(r#"PyCG.children(index, "shop.util")"#);
    let util = util.as_array().expect("children");
    assert_eq!(util[0], json!("shop.util.register"));
    assert_eq!(util[util.len() - 1], json!("shop.util.<lambda1>"));
    assert!(!util.contains(&json!("shop.util.outer.inner")));
    assert_eq!(
        logic(r#"PyCG.children(index, "shop.util.outer")"#),
        json!(["shop.util.outer.inner"])
    );
    assert_eq!(
        logic(r#"PyCG.children(index, "shop._speedups")"#),
        json!(["shop._speedups.escape"])
    );
}

#[test]
fn describe() {
    let cart = logic(r#"PyCG.describe(index, "shop.cart.Cart")"#);
    assert_eq!(cart["kind"], json!("class"));
    assert_eq!(
        (&cart["file"], &cart["lines"]),
        (&json!("shop/cart.py"), &json!([4, 31]))
    );
    assert_eq!(
        cart["mro"],
        json!(["shop.cart.Cart", "shop.base.Base", "<builtin>.object"])
    );
    assert_eq!(cart["exportedAs"], json!(["shop.Cart", "shop.cli.Cart"]));
    let error = logic(r#"PyCG.describe(index, "shop.cart.CartError")"#);
    assert_eq!(
        error["mro"],
        json!(["shop.cart.CartError", "<builtin>.ValueError"])
    );
    let broken = logic(r#"PyCG.describe(index, "shop.broken")"#);
    assert_eq!(
        (&broken["kind"], &broken["status"]),
        (&json!("module"), &json!("failed"))
    );
    assert_eq!(broken["lines"], json!([0, 0]));
    assert_eq!(broken["cause"], json!("SyntaxError (line 3)"));
    let escape = logic(r#"PyCG.describe(index, "shop._speedups.escape")"#);
    assert_eq!(
        (&escape["kind"], &escape["known"]),
        (&json!("outside"), &json!("extension"))
    );
    assert_eq!(
        (&escape["module"], &escape["file"]),
        (
            &json!("shop._speedups"),
            &json!("shop/_speedups.cpython-312-darwin.so")
        )
    );
    assert_eq!(
        escape["exportedAs"],
        json!(["shop.cli.escape", "shop.escape"])
    );
    let loads = logic(r#"PyCG.describe(index, "yaml.safe_load")"#);
    assert_eq!(
        (&loads["known"], &loads["module"], &loads["file"]),
        (&json!("name"), &Value::Null, &Value::Null)
    );
    assert_eq!(
        logic(r#"PyCG.describe(index, "no.such.name")"#),
        Value::Null
    );
    let json_module = logic(r#"PyCG.describe(index, "json")"#);
    assert_eq!(
        (&json_module["kind"], &json_module["known"]),
        (&json!("outside"), &Value::Null)
    );
    assert_eq!(json_module["exportedAs"], json!(["shop.cli.json"]));
}

#[test]
fn names_of_object_properties_are_plain_names() {
    let scratch = Scratch::new();
    let names = ["constructor", "__proto__", "toString", "hasOwnProperty"];
    let source = write_json(
        &scratch,
        "graph.json",
        &document(json!({
            "modules": {"constructor": {"file": "c.py", "kind": "source", "status": "analysed"}},
            "definitions": {
                "constructor": {"kind": "module", "module": "constructor", "lines": [1, 3]},
                "constructor.__proto__": {"kind": "function", "module": "constructor", "lines": [2, 3]},
            },
            "outside": {"toString": {"known": "name"}},
            "calls": {"constructor": [
                {"line": 1, "col": 0, "end": [1, 9], "callees": ["constructor.__proto__", "toString"]},
            ]},
        })),
    );
    let described: Vec<String> = names
        .iter()
        .map(|name| format!(r#"PyCG.describe(index, "{name}")"#))
        .collect();
    let result = logic_of(
        &scratch,
        &format!(
            r#"[index.counts, {}, PyCG.callees(index, "constructor", ALL).map(r => r.name), PyCG.callers(index, "toString", ALL).map(r => r.name), PyCG.callees(index, "hasOwnProperty", ALL), PyCG.search(index, "proto", 5).entries.map(e => e.name)]"#,
            described.join(", ")
        ),
        &source,
    );
    let counts = &result[0];
    assert!(counts["definitions"] == json!(2) && counts["edges"] == json!(2));
    assert_eq!(result[1]["kind"], json!("module"));
    assert_eq!(result[2], Value::Null);
    assert_eq!(result[3]["kind"], json!("outside"));
    assert_eq!(result[4], Value::Null);
    assert_eq!(result[5], json!(["constructor.__proto__", "toString"]));
    assert_eq!(result[6], json!(["constructor"]));
    assert_eq!(result[7], json!([]));
    assert_eq!(result[8], json!(["constructor.__proto__"]));
}

#[test]
fn header_shows_the_package_tool_and_counts() {
    let out = page(
        "out.title = page.document.title;out.header = page.text(page.first('top'));",
        "",
    );
    assert_eq!(out["title"], json!("shop 2.1.0 call graph"));
    let header = text(&out, "header");
    for part in [
        "shop",
        "2.1.0",
        "pycg 0.1.0.dev0",
        "9 modules",
        "40 definitions",
        "47 call sites",
        "46 edges",
        "16 outside callees",
        "3 unresolved sites",
    ] {
        assert!(header.contains(part), "{part} not in {header}");
    }
}

#[test]
fn search_with_keys_opens_the_function() {
    let out = page(
        r#"
        const search = page.byId('search');
        page.key(page.document.body, '/');
        out.focused = page.document.activeElement === search;
        page.type(search, 'is_');
        out.results = page.all('result').map(r => page.text(r.firstChild));
        page.key(search, 'ArrowDown');
        out.selected = page.all('result').map(r => r.getAttribute('aria-selected'));
        out.activedescendant = search.getAttribute('aria-activedescendant');
        page.key(search, 'Enter');
        out.hash = page.location.hash;
        page.settle();
        out.node = page.text(page.first('node-name'));
        out.card = page.text(page.first('card'));
        out.callees = page.all('row', page.byId('callees')).map(r => page.text(r));
        "#,
        "",
    );
    assert_eq!(out["focused"], json!(true));
    assert_eq!(
        out["results"],
        json!(["shop.util.is_odd", "shop.util.is_even"])
    );
    assert_eq!(out["selected"], json!(["false", "true"]));
    assert_eq!(out["activedescendant"], json!("result-1"));
    assert_eq!(out["hash"], json!("#shop.util.is_even"));
    assert_eq!(out["node"], json!("shop.util.is_even"));
    assert!(text(&out, "card").contains("shop/util.py, lines 17–18"));
    let callees = texts(&out, "callees");
    assert!(callees.len() == 1 && callees[0].contains("shop.util.is_odd"));
}

#[test]
fn expanding_a_callee_in_place_marks_recursion() {
    let out = page(
        r#"
        const callees = page.byId('callees');
        page.first('toggle', callees).click();
        out.rows = page.all('row', callees).map(r => page.text(r));
        out.recursive = page.all('recursive', callees).length;
        out.toggles = page.all('toggle', callees)
          .filter(t => t.tagName === 'BUTTON').length;
        page.first('toggle', callees).click();
        out.collapsed = page.all('row', callees).length;
        "#,
        "#shop.util.is_even",
    );
    let rows = texts(&out, "rows");
    assert_eq!(rows.len(), 2);
    assert!(rows[0].contains("shop.util.is_odd"));
    assert!(rows[1].contains("shop.util.is_even"));
    assert!(out["recursive"].as_u64().expect("a count") >= 1);
    assert_eq!(out["toggles"], json!(1));
    assert_eq!(out["collapsed"], json!(1));
}

#[test]
fn expanded_rows_stay_expanded_when_a_filter_changes() {
    let out = page(
        r#"
        const callees = page.byId('callees');
        page.first('toggle', callees).click();
        out.before = page.all('row', callees).length;
        page.byId('filter-outside').click();
        out.after = page.all('row', callees).length;
        page.location.hash = '#shop.util.is_odd';
        page.settle();
        out.other = page.all('row', page.byId('callees')).length;
        "#,
        "#shop.util.is_even",
    );
    assert_eq!(
        (&out["before"], &out["after"], &out["other"]),
        (&json!(2), &json!(2), &json!(1))
    );
}

#[test]
fn callee_rows_show_sites_constructs_and_how_outside_names_are_known() {
    let out = page(
        r#"
        const callees = () =>
          page.all('row', page.byId('callees')).map(r => page.text(r));
        out.main = callees();
        page.location.hash = '#shop.util.load';
        page.settle();
        out.load = callees();
        "#,
        "#shop.cli.main",
    );
    let main = texts(&out, "main");
    assert!(main[1].contains("16:9 with"));
    assert!(one_with(&main, "requests.get").contains("18:11–32"));
    let json_loads = one_with(&main, "json.loads");
    assert!(json_loads.contains("stub") && json_loads.contains("17:17"));
    assert!(one_with(&main, "escape").contains("extension"));
    assert!(one_with(&main, "Cart.add").contains("17:8"));
    let load = texts(&out, "load");
    assert!(load.len() == 1 && load[0].replace("yaml", "").contains("name"));
}

#[test]
fn filters_apply_to_the_hierarchy() {
    let out = page(
        r#"
        const count = () => page.all('row', page.byId('callees')).length;
        out.all = count();
        page.byId('filter-outside').click();
        out.noOutside = count();
        page.byId('filter-implicit').click();
        out.noImplicit = count();
        page.location.hash = '#shop.util.call_by_name';
        page.settle();
        out.unresolved = page.text(page.byId('unresolved'));
        page.byId('filter-unresolved').click();
        out.hidden = page.byId('unresolved').hidden;
        "#,
        "#shop.cli.main",
    );
    assert_eq!(
        (&out["all"], &out["noOutside"], &out["noImplicit"]),
        (&json!(12), &json!(6), &json!(4))
    );
    let shown = text(&out, "unresolved");
    assert!(shown.contains("31:11") && shown.contains("computed name"));
    assert_eq!(out["hidden"], json!(true));
}

#[test]
fn callers_and_the_card_of_an_outside_name() {
    let out = page(
        r#"
        out.card = page.text(page.first('card'));
        out.callers = page.all('row', page.byId('callers')).map(r => page.text(r));
        "#,
        "#shop._speedups.escape",
    );
    assert!(text(&out, "card").contains("extension"));
    assert!(text(&out, "card").contains("shop.escape"));
    let callers = texts(&out, "callers");
    assert!(callers.len() == 1 && callers[0].contains("shop.cli.main"));
}

#[test]
fn card_and_rows_of_a_name_with_sites_in_two_modules() {
    let out = page(
        r#"
        out.card = page.text(page.first('card'));
        out.callees = page.all('row', page.byId('callees')).map(r => page.text(r));
        page.location.hash = '#shop.check.report';
        page.settle();
        out.chain = page.all('site', page.byId('callees')).map(s => page.text(s));
        "#,
        "#shop.check",
    );
    assert!(text(&out, "card").contains("shop/check.py, lines 1–10"));
    assert!(text(&out, "card").contains("shop/__init__.py"));
    assert!(one_with(&texts(&out, "callees"), "shop.cli.main").contains("shop/__init__.py 7:11"));
    assert_eq!(out["chain"], json!(["8:11 operator", "8:17 operator"]));
}

#[test]
fn card_of_an_outside_module_that_the_package_exports() {
    let out = page("out.card = page.text(page.first('card'));", "#json");
    let card = text(&out, "card");
    assert!(card.contains("outside"));
    assert!(card.contains("shop.cli.json"));
    assert!(!card.contains("No module"));
}

#[test]
fn failed_module_card_shows_the_cause() {
    let out = page("out.card = page.text(page.first('card'));", "#shop.broken");
    let card = text(&out, "card");
    assert!(card.contains("failed"));
    assert!(card.contains("failed: SyntaxError (line 3)"));
    assert!(card.contains("shop/broken.py") && !card.contains("lines"));
}

#[test]
fn partial_module_is_marked_incomplete() {
    let out = page(
        r#"
        out.card = page.text(page.first('card'));
        const tree = page.byId('tree');
        page.first('toggle', tree).click();
        out.tree = page.all('tree-item', tree).map(i => page.text(i.firstChild));
        page.byId('tab-modules').click();
        out.row = page.text(page.byId('module-shop.deep'));
        "#,
        "#shop.deep",
    );
    assert!(text(&out, "card").contains("partial: DeepNesting (line 5)"));
    assert!(text(&out, "card").contains("may call less"));
    assert!(one_with(&texts(&out, "tree"), "partial").contains("deep"));
    let row = text(&out, "row");
    assert!(row.contains("partial") && row.contains("DeepNesting"));
}

#[test]
fn shadowed_files_are_marked_on_the_card_tree_and_module_map() {
    let out = page(
        r#"
        out.card = page.text(page.first('card'));
        const tree = page.byId('tree');
        out.root = page.text(page.first('tree-item', tree).firstChild);
        page.byId('tab-modules').click();
        out.util = page.text(page.byId('module-shop.util'));
        out.cart = page.text(page.byId('module-shop.cart'));
        "#,
        "#shop.util",
    );
    let shadows = "shadows shop/util.abi3.so, shop/util.cpython-312-darwin.so: not analysed";
    assert!(text(&out, "card").contains(shadows));
    assert!(text(&out, "util").contains(shadows));
    assert!(!text(&out, "cart").contains("shadows"));
    assert!(text(&out, "root").contains("shadows"));
}

#[test]
fn constructs_and_causes_have_their_description_as_tooltip() {
    let out = page(
        r#"
        const chip = page.withText('site', '16:9 with', page.byId('callees'));
        out.chip = chip.getAttribute('title');
        page.location.hash = '#shop.util.run_hook';
        page.settle();
        const items = page.byId('unresolved').children[1].children;
        out.unresolved = items.map(i => [page.text(i), i.getAttribute('title')]);
        "#,
        "#shop.cli.main",
    );
    let chip = text(&out, "chip");
    assert!(chip.starts_with("with: "));
    assert!(chip.contains("__enter__"));
    assert_eq!(out["unresolved"][0][0], json!("39:11 no value"));
    assert_eq!(out["unresolved"][1][0], json!("40:11–54 outside value"));
    assert!(
        out["unresolved"][1][1]
            .as_str()
            .expect("a title")
            .starts_with("outside value: ")
    );
}

#[test]
fn unknown_name_in_the_address() {
    let out = page("out.card = page.text(page.first('card'));", "#no.such");
    assert!(text(&out, "card").contains("no.such"));
    let out = page("out.card = page.text(page.first('card'));", "#%E0%A4%A");
    assert!(text(&out, "card").contains("%E0%A4%A"));
}

#[test]
fn tree_opens_lazily_and_selects() {
    let out = page(
        r#"
        const tree = page.byId('tree');
        out.before = page.all('tree-item', tree).length;
        page.first('toggle', tree).click();
        out.after = page.all('tree-item', tree).map(i => page.text(i.firstChild));
        page.withText('label', 'util', tree).click();
        out.hash = page.location.hash;
        "#,
        "",
    );
    assert_eq!(out["before"], json!(1));
    let after = texts(&out, "after");
    assert_eq!(after.len(), 9);
    assert!(after.iter().any(|item| item.contains("failed")));
    assert!(after.iter().any(|item| item.contains("extension")));
    assert_eq!(out["hash"], json!("#shop.util"));
}

#[test]
fn module_map_opens_a_function_in_the_hierarchy() {
    let out = page(
        r#"
        page.byId('tab-modules').click();
        out.hierarchyHidden = page.byId('hierarchy').hidden;
        const table = page.byId('module-table');
        out.rows = page.all('module-row', table).map(r => page.text(r));
        page.withText('module-name', 'shop.cli', table).click();
        out.detail = page.text(page.first('module-detail', table));
        const detail = page.first('module-detail', table);
        page.withText('label', 'shop.cli.main', detail).click();
        out.hash = page.location.hash;
        page.settle();
        out.modulesHidden = page.byId('modules').hidden;
        out.node = page.text(page.first('node-name'));
        "#,
        "",
    );
    assert_eq!(out["hierarchyHidden"], json!(true));
    let rows = texts(&out, "rows");
    assert_eq!(rows.len(), 9);
    let broken = rows
        .iter()
        .find(|row| row.starts_with("shop.broken"))
        .expect("a row of shop.broken");
    assert!(broken.contains("failed") && broken.contains("SyntaxError"));
    let speedups = rows
        .iter()
        .find(|row| row.starts_with("shop._speedups"))
        .expect("a row of shop._speedups");
    assert!(speedups.contains("extension"));
    let detail = text(&out, "detail");
    assert!(detail.contains("shop.cart") && detail.contains('3'));
    assert_eq!(out["hash"], json!("#shop.cli.main"));
    assert_eq!(out["modulesHidden"], json!(true));
    assert_eq!(out["node"], json!("shop.cli.main"));
}

#[test]
fn module_map_follows_the_filters_on_the_page() {
    let out = page(
        r#"
        page.byId('tab-modules').click();
        const cells = () =>
          page.byId('module-shop.cli').children.map(td => page.text(td));
        out.before = cells();
        page.byId('filter-outside').click();
        out.after = cells();
        "#,
        "",
    );
    assert_eq!(
        out["before"],
        json!(["shop.cli", "analysed", "4", "5", "1", "3", "5"])
    );
    assert_eq!(
        out["after"],
        json!(["shop.cli", "analysed", "4", "4", "1", "3", "–"])
    );
}

#[test]
fn hostile_names_are_shown_as_text() {
    let scratch = Scratch::new();
    let source = write_json(&scratch, "hostile.json", &hostile_document());
    let module = format!("m0.{}", HOSTILE[0]);
    let out = page_of(
        &scratch,
        r#"
        out.title = page.document.title;
        out.header = page.text(page.first('top'));
        out.node = page.text(page.first('node-name'));
        out.card = page.text(page.first('card'));
        out.callees = page.text(page.byId('callees'));
        page.type(page.byId('search'), 'script');
        out.results = page.all('result').length;
        page.byId('tab-modules').click();
        out.modules = page.text(page.byId('module-table'));
        out.scripts = page.tags().filter(tag => tag === 'SCRIPT').length;
        "#,
        &source,
        &format!("#{}", percent_encoded(&module)),
    );
    assert!(text(&out, "title").contains(HOSTILE[0]));
    assert!(text(&out, "header").contains(HOSTILE[0]));
    assert_eq!(out["node"], json!(module));
    assert!(text(&out, "callees").contains(&format!("x.{}", HOSTILE[0])));
    assert!(text(&out, "card").contains(HOSTILE[0]));
    assert!(out["results"].as_u64().expect("a count") >= 4);
    assert!(text(&out, "modules").contains(HOSTILE[0]));
    assert_eq!(out["scripts"], json!(1));
}

#[test]
fn page_refuses_an_unknown_format() {
    let scratch = Scratch::new();
    let html = written_page(&scratch, &sample());
    let start = html
        .find(DOCUMENT_OPEN)
        .expect("the page embeds the document")
        + DOCUMENT_OPEN.len();
    let end = start + html[start..].find(SCRIPT_CLOSE).expect("the document ends");
    let other = quoted(document(json!({"format": "pycg/9"}))).replace('<', "\\u003c");
    let html = format!("{}{other}{}", &html[..start], &html[end..]);
    let out = run_page(
        &scratch,
        &html,
        "out.text = page.text(page.byId('app'));",
        "",
    );
    assert!(text(&out, "text").contains("pycg/9"));
}

#[test]
fn page_reports_a_malformed_document() {
    let scratch = Scratch::new();
    let source = write_json(
        &scratch,
        "graph.json",
        &document(json!({"calls": {"m": [{"line": 1, "col": 0, "end": [1, 3]}]}})),
    );
    let out = page_of(
        &scratch,
        "out.text = page.text(page.byId('app'));",
        &source,
        "",
    );
    assert!(text(&out, "text").contains("cannot be read"));
}

#[test]
fn callers_and_callees_are_the_edges_of_a_real_document() {
    let real = real();
    let expected = edges(&real.document);
    let mut callers: BTreeMap<String, BTreeSet<String>> = expected
        .keys()
        .map(|name| (name.clone(), BTreeSet::new()))
        .collect();
    for (caller, callees) in &expected {
        for callee in callees {
            callers
                .get_mut(callee)
                .expect("a callee is a name of the graph")
                .insert(caller.clone());
        }
    }
    let names: Vec<&String> = expected.keys().collect();
    let result = logic_of(
        &Scratch::new(),
        &format!(
            "(() => {{
              const names = {};
              const sorted = (rows) => rows.map((row) => row.name).sort();
              return {{
                counts: index.counts,
                callees: Object.fromEntries(
                  names.map((n) => [n, sorted(PyCG.callees(index, n, ALL))])),
                callers: Object.fromEntries(
                  names.map((n) => [n, sorted(PyCG.callers(index, n, ALL))])),
              }};
            }})()",
            quoted(json!(names))
        ),
        &real.path,
    );
    assert_eq!(result["callees"], json!(expected));
    assert_eq!(result["callers"], json!(callers));
    let counts = &result["counts"];
    let definitions = real.document["definitions"]
        .as_object()
        .expect("definitions")
        .len();
    let sites: usize = real.document["calls"]
        .as_object()
        .expect("calls")
        .values()
        .map(|sites| sites.as_array().expect("sites").len())
        .sum();
    let edge_count: usize = expected.values().map(BTreeSet::len).sum();
    assert_eq!(counts["definitions"], json!(definitions));
    assert_eq!(counts["edges"], json!(edge_count));
    assert_eq!(counts["sites"], json!(sites));
}

#[test]
fn page_of_a_real_document() {
    let real = real();
    let caller = "loop.main";
    let graph = edges(&real.document);
    let expected: Vec<&String> = graph[caller].iter().collect();
    assert!(!expected.is_empty());
    let scratch = Scratch::new();
    let out = page_of(
        &scratch,
        r#"
        out.header = page.text(page.first('top'));
        out.callees = page.all('row', page.byId('callees'))
          .map(r => page.text(page.first('label', r)));
        page.byId('tab-modules').click();
        out.modules = page.all('module-row').length;
        "#,
        &real.path,
        &format!("#{caller}"),
    );
    let modules = real.document["modules"].as_object().expect("modules").len();
    assert!(text(&out, "header").contains(&format!("{modules} modules")));
    let mut callees = texts(&out, "callees");
    callees.sort();
    assert_eq!(callees.iter().collect::<Vec<_>>(), expected);
    assert_eq!(out["modules"], json!(modules));
}

#[test]
fn large_document_has_the_stated_size() {
    let (path, _) = large();
    let counts = logic_of(&Scratch::new(), "index.counts", path);
    assert!(counts["definitions"].as_u64().expect("a count") >= LARGE_DEFINITIONS as u64);
    assert!(counts["sites"].as_u64().expect("a count") >= LARGE_SITES as u64);
}

#[test]
fn logic_is_fast_on_a_large_document() {
    let (path, _) = large();
    let timings = logic_of(
        &Scratch::new(),
        &format!(
            "(() => {{
              const t = {{}};
              const time = (name, f) => {{
                const start = process.hrtime.bigint();
                const value = f();
                t[name] = Number(process.hrtime.bigint() - start) / 1e6;
                return value;
              }};
              const text = fs.readFileSync({}, 'utf8');
              const parsed = time('parse', () => JSON.parse(text));
              time('index', () => PyCG.buildIndex(parsed));
              for (const query of ['a', 'f1', 'hub', 'm001.f', 'zzzz'])
                time('search ' + query, () => PyCG.search(index, query, 50));
              const hub = PyCG.search(index, 'hub', 1).entries[0].name;
              t.hubCallers = time('callers', () => PyCG.callers(index, hub, ALL)).length;
              time('expand', () => PyCG.expand(index, hub, 'callers', ALL, [hub]));
              time('modules', () => PyCG.moduleMap(index, ALL));
              return t;
            }})()",
            quoted(json!(path.to_str().expect("a UTF-8 path")))
        ),
        path,
    );
    println!("{timings}");
    let number = |key: &str| timings[key].as_f64().expect("a number");
    assert!(number("hubCallers") >= 1000.0);
    assert!(number("index") < 3000.0);
    let search = timings
        .as_object()
        .expect("timings")
        .iter()
        .filter(|(key, _)| key.starts_with("search"))
        .map(|(_, value)| value.as_f64().expect("a number"))
        .fold(0.0, f64::max);
    assert!(search < 200.0);
    assert!(number("expand") < 500.0);
    assert!(number("modules") < 2000.0);
}

#[test]
fn page_renders_only_what_is_visible_on_a_large_document() {
    let (path, _) = large();
    let out = page_of(
        &Scratch::new(),
        r#"
        out.load = page.created();
        page.type(page.byId('search'), 'hub');
        page.key(page.byId('search'), 'Enter');
        page.settle();
        out.callers = page.all('row', page.byId('callers')).length;
        out.more = page.all('more', page.byId('callers')).length;
        out.hub = page.created();
        page.byId('tab-modules').click();
        out.modules = page.all('module-row').length;
        out.total = page.created();
        "#,
        path,
        "",
    );
    println!("{out}");
    assert!(out["callers"].as_u64().expect("a count") <= 200);
    assert_eq!(out["more"], json!(1));
    assert!(out["load"].as_u64().expect("a count") < 5000);
    assert!(out["total"].as_u64().expect("a count") < 20000);
}
