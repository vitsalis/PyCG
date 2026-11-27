use std::collections::{BTreeMap, BTreeSet};
use std::path::{Path, PathBuf};
use std::process::{Command, ExitCode};
use std::sync::Mutex;
use std::sync::atomic::{AtomicUsize, Ordering};

use serde_json::Value;

const ROOT: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/../..");
const NOT_PORTED_PREFIX: &str = "pycg: not ported: ";
const PENDING: &str = "tests/cases/pending.txt";
const CASE_KEYS: [&str; 8] = [
    "statement",
    "design",
    "entry_points",
    "package",
    "cap",
    "warnings",
    "present",
    "absent",
];

type Edges = BTreeMap<String, BTreeSet<String>>;
type Unresolved = BTreeMap<String, BTreeMap<String, String>>;

enum Expected {
    Case {
        edges: Edges,
        unresolved: Unresolved,
        warnings: Vec<String>,
        document: Option<Value>,
    },
    Micro {
        edges: Edges,
        known_failure: bool,
    },
}

struct Case {
    id: String,
    directory: PathBuf,
    entry_points: Vec<String>,
    package: bool,
    cap: Option<String>,
    expected: Expected,
}

enum Outcome {
    Document {
        document: Value,
        warnings: Vec<String>,
    },
    NotPorted(String),
    Failed(String),
}

#[derive(Clone, Debug, PartialEq)]
enum Toml {
    String(String),
    Integer(i64),
    Boolean(bool),
    Array(Vec<Toml>),
}

struct Reader<'a> {
    text: &'a [u8],
    at: usize,
}

impl Reader<'_> {
    fn blank(&mut self) {
        while self.at < self.text.len() {
            match self.text[self.at] {
                b' ' | b'\t' | b'\n' | b'\r' => self.at += 1,
                b'#' => {
                    while self.at < self.text.len() && self.text[self.at] != b'\n' {
                        self.at += 1;
                    }
                }
                _ => break,
            }
        }
    }

    fn eat(&mut self, byte: u8) -> bool {
        self.blank();
        let found = self.text.get(self.at) == Some(&byte);
        if found {
            self.at += 1;
        }
        found
    }

    fn word(&mut self) -> String {
        self.blank();
        let start = self.at;
        while self.at < self.text.len()
            && (self.text[self.at].is_ascii_alphanumeric() || b"_-".contains(&self.text[self.at]))
        {
            self.at += 1;
        }
        String::from_utf8(self.text[start..self.at].to_vec()).expect("an ASCII word")
    }

    fn string(&mut self) -> String {
        let mut bytes = Vec::new();
        loop {
            let byte = *self.text.get(self.at).expect("a closed string");
            self.at += 1;
            match byte {
                b'"' => break,
                b'\\' => {
                    let escape = self.text[self.at];
                    self.at += 1;
                    match escape {
                        b'"' | b'\\' | b'/' => bytes.push(escape),
                        b'n' => bytes.push(b'\n'),
                        b't' => bytes.push(b'\t'),
                        b'u' => {
                            let hex = std::str::from_utf8(&self.text[self.at..self.at + 4])
                                .expect("an ASCII escape");
                            self.at += 4;
                            let code = u32::from_str_radix(hex, 16).expect("a hex escape");
                            let character = char::from_u32(code).expect("a scalar value");
                            let mut buffer = [0; 4];
                            bytes.extend(character.encode_utf8(&mut buffer).as_bytes());
                        }
                        other => panic!("the escape \\{}", other as char),
                    }
                }
                other => bytes.push(other),
            }
        }
        String::from_utf8(bytes).expect("a UTF-8 string")
    }

    fn value(&mut self) -> Toml {
        if self.eat(b'"') {
            return Toml::String(self.string());
        }
        if self.eat(b'[') {
            let mut items = Vec::new();
            while !self.eat(b']') {
                items.push(self.value());
                if !self.eat(b',') {
                    assert!(self.eat(b']'), "an array ends with ]");
                    break;
                }
            }
            return Toml::Array(items);
        }
        match self.word().as_str() {
            "true" => Toml::Boolean(true),
            "false" => Toml::Boolean(false),
            word => Toml::Integer(word.parse().unwrap_or_else(|_| panic!("a value: {word}"))),
        }
    }
}

fn read_toml(text: &str) -> BTreeMap<String, Toml> {
    let mut reader = Reader {
        text: text.as_bytes(),
        at: 0,
    };
    let mut table = BTreeMap::new();
    loop {
        reader.blank();
        if reader.at == reader.text.len() {
            return table;
        }
        let key = reader.word();
        assert!(reader.eat(b'='), "{key} = value");
        let value = reader.value();
        assert!(table.insert(key.clone(), value).is_none(), "{key} twice");
    }
}

fn text(table: &BTreeMap<String, Toml>, key: &str) -> String {
    match table.get(key) {
        Some(Toml::String(value)) => value.clone(),
        other => panic!("{key} is a string, not {other:?}"),
    }
}

fn strings(table: &BTreeMap<String, Toml>, key: &str) -> Vec<String> {
    let Some(Toml::Array(items)) = table.get(key) else {
        panic!("{key} is an array");
    };
    items
        .iter()
        .map(|item| match item {
            Toml::String(item) => item.clone(),
            other => panic!("{key}: a string, not {other:?}"),
        })
        .collect()
}

fn pairs(table: &BTreeMap<String, Toml>, key: &str) -> Vec<(String, String)> {
    let Some(Toml::Array(items)) = table.get(key) else {
        panic!("{key} is an array");
    };
    items
        .iter()
        .map(|item| match item {
            Toml::Array(pair) => match pair.as_slice() {
                [Toml::String(caller), Toml::String(callee)] => (caller.clone(), callee.clone()),
                _ => panic!("{key}: [caller, callee]"),
            },
            _ => panic!("{key}: [caller, callee]"),
        })
        .collect()
}

fn read(path: &Path) -> String {
    std::fs::read_to_string(path).unwrap_or_else(|error| panic!("{}: {error}", path.display()))
}

fn edges_of(value: &Value) -> Edges {
    value
        .as_object()
        .expect("edges are an object")
        .iter()
        .map(|(caller, callees)| {
            let callees = callees.as_array().expect("callees are an array");
            let names = callees
                .iter()
                .map(|callee| callee.as_str().expect("a name").to_owned());
            (caller.clone(), names.collect())
        })
        .collect()
}

fn unresolved_of(value: &Value) -> Unresolved {
    value
        .as_object()
        .expect("unresolved is an object")
        .iter()
        .map(|(caller, sites)| {
            let sites = sites.as_object().expect("sites are an object");
            let causes = sites
                .iter()
                .map(|(site, cause)| (site.clone(), cause.as_str().expect("a cause").to_owned()));
            (caller.clone(), causes.collect())
        })
        .collect()
}

fn headings() -> BTreeSet<String> {
    read(&Path::new(ROOT).join("docs/design.md"))
        .lines()
        .filter(|line| line.starts_with('#'))
        .map(|line| line.trim_start_matches('#').trim().to_owned())
        .collect()
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

fn read_case(directory: PathBuf, headings: &BTreeSet<String>) -> Case {
    let family = directory
        .parent()
        .and_then(Path::file_name)
        .expect("a family");
    let name = directory.file_name().expect("a case name");
    let id = format!(
        "cases/{}/{}",
        family.to_string_lossy(),
        name.to_string_lossy()
    );
    let table = read_toml(&read(&directory.join("case.toml")));
    for key in table.keys() {
        assert!(CASE_KEYS.contains(&key.as_str()), "{id}: the key {key}");
    }
    assert!(!text(&table, "statement").is_empty(), "{id}: a statement");
    let design = text(&table, "design");
    assert!(
        headings.contains(&design),
        "{id}: {design:?} is not a heading of docs/design.md"
    );
    let entry_points = strings(&table, "entry_points");
    let package = table.get("package") == Some(&Toml::Boolean(true));
    assert!(
        package || table.get("package") == Some(&Toml::Boolean(false)),
        "{id}: package is true or false"
    );
    let cap = match table.get("cap") {
        None => None,
        Some(Toml::Integer(cap)) => Some(cap.to_string()),
        Some(Toml::String(cap)) if cap == "none" => Some(cap.clone()),
        Some(other) => panic!("{id}: cap is a number or \"none\", not {other:?}"),
    };
    let expected: Value = serde_json::from_str(&read(&directory.join("expected.json")))
        .unwrap_or_else(|error| panic!("{id}: expected.json: {error}"));
    let edges = edges_of(&expected["edges"]);
    for (caller, callee) in &pairs(&table, "present") {
        assert!(
            edges
                .get(caller)
                .is_some_and(|callees| callees.contains(callee)),
            "{id}: the present edge {caller} -> {callee} is not expected"
        );
    }
    for (caller, callee) in &pairs(&table, "absent") {
        assert!(
            !edges
                .get(caller)
                .is_some_and(|callees| callees.contains(callee)),
            "{id}: the absent edge {caller} -> {callee} is expected"
        );
    }
    let document_path = directory.join("expected-document.json");
    let document = document_path.is_file().then(|| {
        serde_json::from_str(&read(&document_path))
            .unwrap_or_else(|error| panic!("{id}: expected-document.json: {error}"))
    });
    Case {
        id,
        directory,
        entry_points,
        package,
        cap,
        expected: Expected::Case {
            edges,
            unresolved: unresolved_of(&expected["unresolved"]),
            warnings: strings(&table, "warnings"),
            document,
        },
    }
}

fn known_failures() -> BTreeSet<String> {
    read(&Path::new(ROOT).join("tests/known_failures.txt"))
        .lines()
        .filter(|line| !line.trim().is_empty() && !line.starts_with('#'))
        .map(|line| {
            line.split_once(": ")
                .expect("<case>: <reason>")
                .0
                .to_owned()
        })
        .collect()
}

fn skip_reason(directory: &Path) -> Option<String> {
    let path = directory.join("requires-python");
    if !path.is_file() {
        return None;
    }
    let version = read(&path);
    let (major, minor) = version.trim().split_once('.').expect("major.minor");
    let needed = (
        major.parse::<u8>().expect("a major"),
        minor.parse::<u8>().expect("a minor"),
    );
    let target = pycg_syntax::parse::TARGET_VERSION;
    (needed > (target.major, target.minor)).then(|| {
        format!(
            "needs Python {}, the parser reads {}.{}",
            version.trim(),
            target.major,
            target.minor
        )
    })
}

fn micro_cases(skipped: &mut Vec<String>) -> Vec<Case> {
    let known = known_failures();
    let snippets = Path::new(ROOT).join("evaluation/micro-benchmark/snippets");
    let mut cases = Vec::new();
    for category in directories(&snippets) {
        for directory in directories(&category) {
            let name = format!(
                "{}/{}",
                category.file_name().expect("a category").to_string_lossy(),
                directory.file_name().expect("a case").to_string_lossy()
            );
            if let Some(reason) = skip_reason(&directory) {
                skipped.push(format!("micro/{name}: skipped: {reason}"));
                continue;
            }
            let graph: Value = serde_json::from_str(&read(&directory.join("callgraph.json")))
                .unwrap_or_else(|error| panic!("{name}: callgraph.json: {error}"));
            cases.push(Case {
                id: format!("micro/{name}"),
                directory,
                entry_points: vec!["main.py".to_owned()],
                package: true,
                cap: None,
                expected: Expected::Micro {
                    edges: edges_of(&graph),
                    known_failure: known.contains(&name),
                },
            });
        }
    }
    cases
}

fn document_of(value: &Value) -> (Edges, Unresolved) {
    let mut edges = Edges::new();
    for (name, definition) in value["definitions"].as_object().expect("definitions") {
        if definition["kind"] != "class" {
            edges.insert(name.clone(), BTreeSet::new());
        }
    }
    for name in value["outside"].as_object().expect("outside").keys() {
        edges.insert(name.clone(), BTreeSet::new());
    }
    let mut unresolved = Unresolved::new();
    for (caller, sites) in value["calls"].as_object().expect("calls") {
        for site in sites.as_array().expect("sites") {
            let callees = site["callees"].as_array().expect("callees");
            let names = callees
                .iter()
                .map(|callee| callee.as_str().expect("a callee").to_owned());
            edges
                .get_mut(caller)
                .expect("a caller is a node")
                .extend(names);
            if let Some(cause) = site.get("unresolved") {
                let key = format!("{}:{}", site["line"], site["col"]);
                let cause = cause.as_str().expect("a cause").to_owned();
                unresolved
                    .entry(caller.clone())
                    .or_default()
                    .insert(key, cause);
            }
        }
    }
    (edges, unresolved)
}

fn run(case: &Case, output: &Path) -> Outcome {
    let directory = std::fs::canonicalize(&case.directory).expect("the case directory");
    let mut command = Command::new(env!("CARGO_BIN_EXE_pycg"));
    if case.package {
        command.arg("--package").arg(&directory);
    }
    if let Some(cap) = &case.cap {
        command.arg("--cap").arg(cap);
    }
    for entry in &case.entry_points {
        command.arg(directory.join(entry));
    }
    let done = command
        .arg("-o")
        .arg(output)
        .env_clear()
        .output()
        .expect("pycg runs");
    let stderr = String::from_utf8_lossy(&done.stderr);
    let last = stderr.lines().last().unwrap_or("").to_owned();
    if !done.status.success() {
        return match last.strip_prefix(NOT_PORTED_PREFIX) {
            Some(rule) => Outcome::NotPorted(rule.to_owned()),
            None => Outcome::Failed(format!("{}: {last}", done.status)),
        };
    }
    let prefix = format!("{}/", directory.display());
    let warnings = stderr
        .lines()
        .map(|line| line.replace(&prefix, ""))
        .collect();
    let document = serde_json::from_str(&read(output)).expect("a JSON document");
    Outcome::Document { document, warnings }
}

fn difference(expected: &Edges, found: &Edges) -> Vec<String> {
    let flat = |edges: &Edges| -> BTreeSet<(String, String)> {
        edges
            .iter()
            .flat_map(|(caller, callees)| {
                callees
                    .iter()
                    .map(move |callee| (caller.clone(), callee.clone()))
            })
            .collect()
    };
    let (expected_edges, found_edges) = (flat(expected), flat(found));
    let mut lines = Vec::new();
    for (caller, callee) in found_edges.difference(&expected_edges) {
        lines.push(format!("  gained {caller} -> {callee}"));
    }
    for (caller, callee) in expected_edges.difference(&found_edges) {
        lines.push(format!("  lost {caller} -> {callee}"));
    }
    let expected_nodes: BTreeSet<&String> = expected.keys().collect();
    let found_nodes: BTreeSet<&String> = found.keys().collect();
    for node in found_nodes.difference(&expected_nodes) {
        lines.push(format!("  gained node {node}"));
    }
    for node in expected_nodes.difference(&found_nodes) {
        lines.push(format!("  lost node {node}"));
    }
    lines
}

fn problem(case: &Case, outcome: &Outcome) -> Option<(String, Vec<String>)> {
    let (document, warnings) = match outcome {
        Outcome::NotPorted(rule) => return Some((format!("not ported: {rule}"), Vec::new())),
        Outcome::Failed(error) => return Some((format!("failed: {error}"), Vec::new())),
        Outcome::Document { document, warnings } => (document, warnings),
    };
    match &case.expected {
        Expected::Case {
            edges: expected,
            unresolved: expected_unresolved,
            warnings: expected_warnings,
            document: expected_document,
        } => {
            let (edges, unresolved) = document_of(document);
            let mut lines = difference(expected, &edges);
            if &unresolved != expected_unresolved {
                lines.push(format!(
                    "  unresolved {unresolved:?}, expected {expected_unresolved:?}"
                ));
            }
            if warnings != expected_warnings {
                lines.push(format!(
                    "  warnings {warnings:?}, expected {expected_warnings:?}"
                ));
            }
            if expected_document
                .as_ref()
                .is_some_and(|expected| expected != document)
            {
                lines.push("  the document differs from expected-document.json".to_owned());
            }
            (!lines.is_empty()).then(|| ("differs from expected.json".to_owned(), lines))
        }
        Expected::Micro {
            edges: expected,
            known_failure,
        } => {
            let lines = difference(expected, &document_of(document).0);
            match (lines.is_empty(), known_failure) {
                (true, false) | (false, true) => None,
                (true, true) => Some(("a known failure passes".to_owned(), Vec::new())),
                (false, false) => Some(("differs from callgraph.json".to_owned(), lines)),
            }
        }
    }
}

fn check(case: &Case, found: Option<&(String, Vec<String>)>, listed: bool) -> Vec<String> {
    let id = &case.id;
    match (found, listed) {
        (None, false) | (Some(_), true) => Vec::new(),
        (None, true) => vec![format!("{id}: passes, but {PENDING} lists it")],
        (Some((cause, lines)), false) => [vec![format!("{id}: {cause}")], lines.clone()].concat(),
    }
}

fn pending(path: &Path) -> BTreeMap<String, String> {
    read(path)
        .lines()
        .filter(|line| !line.is_empty())
        .map(|line| {
            let (id, rule) = line.split_once(": ").expect("<case>: <cause>");
            (id.to_owned(), rule.to_owned())
        })
        .collect()
}

fn main() -> ExitCode {
    let headings = headings();
    let mut cases: Vec<Case> = Vec::new();
    for family in directories(&Path::new(ROOT).join("tests/cases")) {
        cases.extend(
            directories(&family)
                .into_iter()
                .map(|case| read_case(case, &headings)),
        );
    }
    assert!(!cases.is_empty(), "tests/cases holds cases");
    let mut skipped = Vec::new();
    cases.extend(micro_cases(&mut skipped));
    let listed = pending(&Path::new(ROOT).join(PENDING));
    let ids: BTreeSet<&String> = cases.iter().map(|case| &case.id).collect();
    for id in listed.keys() {
        assert!(ids.contains(id), "{PENDING} names {id}, which is no case");
    }
    let outputs = Path::new(env!("CARGO_TARGET_TMPDIR")).join("cases");
    std::fs::create_dir_all(&outputs).expect("the output directory is made");
    let outcomes: Mutex<Vec<Option<Outcome>>> = Mutex::new(cases.iter().map(|_| None).collect());
    let next = AtomicUsize::new(0);
    let workers = std::thread::available_parallelism().map_or(1, usize::from);
    std::thread::scope(|scope| {
        for _ in 0..workers {
            scope.spawn(|| {
                loop {
                    let index = next.fetch_add(1, Ordering::Relaxed);
                    let Some(case) = cases.get(index) else { break };
                    let outcome = run(case, &outputs.join(format!("{index}.json")));
                    outcomes.lock().expect("no worker panicked")[index] = Some(outcome);
                }
            });
        }
    });
    let outcomes = outcomes.into_inner().expect("no worker panicked");
    let mut errors = Vec::new();
    let mut failing = BTreeMap::new();
    let mut counts = BTreeMap::<&str, usize>::new();
    for (case, outcome) in cases.iter().zip(&outcomes) {
        let outcome = outcome.as_ref().expect("every case ran");
        let found = problem(case, outcome);
        let kind = match (&found, outcome) {
            (None, _) => "passed",
            (Some(_), Outcome::NotPorted(_)) => "not ported",
            (Some(_), Outcome::Failed(_)) => "failed",
            (Some(_), Outcome::Document { .. }) => "differ",
        };
        *counts.entry(kind).or_default() += 1;
        errors.extend(check(case, found.as_ref(), listed.contains_key(&case.id)));
        if let Some((cause, _)) = found {
            failing.insert(case.id.clone(), cause);
        }
    }
    let summary: Vec<String> = counts
        .iter()
        .map(|(kind, count)| format!("{count} {kind}"))
        .collect();
    println!(
        "{} cases: {}, {} skipped",
        cases.len(),
        summary.join(", "),
        skipped.len()
    );
    for line in &skipped {
        println!("{line}");
    }
    if errors.is_empty() {
        return ExitCode::SUCCESS;
    }
    for line in &errors {
        println!("{line}");
    }
    if failing.keys().ne(listed.keys()) {
        println!("{PENDING} for this build:");
        for (id, cause) in &failing {
            println!("{id}: {cause}");
        }
    }
    ExitCode::FAILURE
}
