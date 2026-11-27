use std::collections::{BTreeMap, BTreeSet};
use std::panic::{self, AssertUnwindSafe};
use std::path::{Path, PathBuf};
use std::process::ExitCode;
use std::sync::Mutex;

use num_bigint::BigUint;
use pycg_analysis::{CAP_DEFAULT_OBJECTS, Cap, Order, Request};
use pycg_document::{ProgramPart, Text, build, dumps};
use pycg_syntax::parse::TARGET_VERSION;
use serde_json::Value;

const CASES: &str = "tests/cases";
const CASE: &str = "case.json";
const EXPECTED: &str = "expected.json";
const PROGRAM: &str = "program";
const PENDING: &str = "tests/cases/pending.txt";
const SNIPPETS: &str = "evaluation/micro-benchmark/snippets";
const MICRO_PREFIX: &str = "micro";
const MICRO_ENTRY: &str = "main.py";
const MICRO_EXPECTED: &str = "callgraph.json";
const MICRO_REQUIRES: &str = "requires-python";
const KNOWN_FAILURES: &str = "tests/known_failures.txt";
const ROOT_IN_WARNINGS: &str = "{root}";

static PANIC: Mutex<Option<String>> = Mutex::new(None);

type Edges = BTreeMap<String, BTreeSet<String>>;

struct Run {
    entry_points: Vec<PathBuf>,
    package: Option<PathBuf>,
    root: PathBuf,
    cap: Option<u32>,
}

struct Expected {
    edges: Edges,
    unresolved: BTreeSet<(String, String, String)>,
    points_to: BTreeMap<String, Vec<String>>,
    warnings: Vec<String>,
    documents: Vec<Requested>,
}

struct Requested {
    package_name: Option<String>,
    package_version: Option<String>,
    document: Value,
}

enum Kind {
    Oracle {
        expected: Expected,
        focus: Vec<String>,
    },
    Micro {
        edges: Edges,
        known_failure: bool,
    },
}

struct Case {
    name: String,
    run: Run,
    kind: Kind,
}

struct Found {
    edges: Edges,
    unresolved: BTreeSet<(String, String, String)>,
    points_to: BTreeMap<String, Vec<String>>,
    documents: Vec<Value>,
    inconsistencies: Vec<String>,
    warnings: Vec<String>,
}

fn main() -> ExitCode {
    let root = Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../..")
        .canonicalize()
        .expect("the root of the repository");
    let mut cases = oracle_cases(&root.join(CASES));
    cases.extend(micro_cases(&root));
    let pending = read_pending(&root.join(PENDING));
    for name in pending.keys() {
        assert!(
            cases.iter().any(|case| &case.name == name),
            "{PENDING} names {name}, which is no case"
        );
    }
    panic::set_hook(Box::new(|info| {
        let payload = info.payload();
        let message = payload
            .downcast_ref::<&str>()
            .map(|text| (*text).to_owned())
            .or_else(|| payload.downcast_ref::<String>().cloned())
            .unwrap_or_default();
        *PANIC.lock().expect("the panic message is free") = Some(message);
    }));
    let mut passed = 0;
    let mut waiting = 0;
    let mut wrong = Vec::new();
    for case in &cases {
        match (problems(case), pending.get(&case.name)) {
            (None, None) => passed += 1,
            (Some(_), Some(_)) => waiting += 1,
            (None, Some(cause)) => wrong.push(format!(
                "{}: passes, but {PENDING} lists it ({cause}): remove its line",
                case.name
            )),
            (Some(problems), None) => wrong.push(format!("{}\t{problems}", case.name)),
        }
    }
    let _ = panic::take_hook();
    for line in &wrong {
        println!("{line}");
    }
    println!(
        "cases: {passed} pass, {waiting} pending, {} fail, of {}",
        wrong.len(),
        cases.len()
    );
    if wrong.is_empty() {
        ExitCode::SUCCESS
    } else {
        ExitCode::FAILURE
    }
}

fn oracle_cases(directory: &Path) -> Vec<Case> {
    let mut cases = Vec::new();
    for family in sorted_directories(directory) {
        for directory in sorted_directories(&family) {
            let case = read_json(&directory.join(CASE));
            let expected = read_json(&directory.join(EXPECTED));
            let program = directory.join(PROGRAM);
            let path = |value: &Value| program.join(text(value));
            let cap = match &case["cap"] {
                Value::Null => None,
                value => Some(
                    u32::try_from(value.as_u64().expect("the cap is a count"))
                        .expect("the cap fits u32"),
                ),
            };
            let run = Run {
                entry_points: list(&case["entry_points"]).iter().map(path).collect(),
                package: (!case["package"].is_null()).then(|| path(&case["package"])),
                root: program.clone(),
                cap,
            };
            let unresolved = list(&expected["unresolved"])
                .iter()
                .map(|entry| (text(&entry[0]), text(&entry[1]), text(&entry[2])))
                .collect();
            let points_to = object(&expected["points_to"])
                .iter()
                .map(|(label, names)| (label.clone(), list(names).iter().map(text).collect()))
                .collect();
            let expected = Expected {
                edges: edges_of(&expected["edges"]),
                unresolved,
                points_to,
                warnings: list(&expected["warnings"]).iter().map(text).collect(),
                documents: list(&expected["documents"])
                    .iter()
                    .map(|requested| Requested {
                        package_name: optional_text(&requested["package_name"]),
                        package_version: optional_text(&requested["package_version"]),
                        document: requested["document"].clone(),
                    })
                    .collect(),
            };
            cases.push(Case {
                name: format!("{}/{}", file_name(&family), file_name(&directory)),
                run,
                kind: Kind::Oracle {
                    expected,
                    focus: list(&case["focus"]).iter().map(text).collect(),
                },
            });
        }
    }
    assert!(!cases.is_empty(), "no case under {}", directory.display());
    cases
}

fn micro_cases(root: &Path) -> Vec<Case> {
    let known_failures = read_known_failures(&root.join(KNOWN_FAILURES));
    let mut cases = Vec::new();
    for category in sorted_directories(&root.join(SNIPPETS)) {
        for snippet in sorted_directories(&category) {
            let id = format!("{}/{}", file_name(&category), file_name(&snippet));
            if needs_a_newer_python(&snippet) {
                continue;
            }
            cases.push(Case {
                name: format!("{MICRO_PREFIX}/{id}"),
                run: Run {
                    entry_points: vec![snippet.join(MICRO_ENTRY)],
                    package: Some(snippet.clone()),
                    root: snippet.clone(),
                    cap: Some(CAP_DEFAULT_OBJECTS),
                },
                kind: Kind::Micro {
                    edges: edges_of(&read_json(&snippet.join(MICRO_EXPECTED))),
                    known_failure: known_failures.contains(&id),
                },
            });
        }
    }
    let ids: BTreeSet<String> = cases
        .iter()
        .map(|case| case.name[MICRO_PREFIX.len() + 1..].to_owned())
        .collect();
    for id in &known_failures {
        assert!(
            ids.contains(id) || needs_a_newer_python(&root.join(SNIPPETS).join(id)),
            "{KNOWN_FAILURES} names {id}, which is no micro case"
        );
    }
    cases
}

fn needs_a_newer_python(snippet: &Path) -> bool {
    let Ok(version) = std::fs::read_to_string(snippet.join(MICRO_REQUIRES)) else {
        return false;
    };
    let parts: Vec<u8> = version
        .trim()
        .split('.')
        .map(|part| part.parse().expect("a version part is a number"))
        .collect();
    let [major, minor] = parts[..] else {
        panic!("{}: {version:?} is not <major>.<minor>", snippet.display());
    };
    (major, minor) > (TARGET_VERSION.major, TARGET_VERSION.minor)
}

fn read_known_failures(path: &Path) -> BTreeSet<String> {
    let text =
        std::fs::read_to_string(path).unwrap_or_else(|error| panic!("{}: {error}", path.display()));
    text.lines()
        .filter(|line| !line.trim().is_empty() && !line.starts_with('#'))
        .map(|line| {
            let (id, _) = line
                .split_once(": ")
                .unwrap_or_else(|| panic!("{KNOWN_FAILURES}: {line:?} has no cause"));
            id.to_owned()
        })
        .collect()
}

fn read_pending(path: &Path) -> BTreeMap<String, String> {
    let text =
        std::fs::read_to_string(path).unwrap_or_else(|error| panic!("{}: {error}", path.display()));
    let mut pending = BTreeMap::new();
    let mut previous: Option<&str> = None;
    for line in text.lines() {
        let (name, cause) = line
            .split_once('\t')
            .unwrap_or_else(|| panic!("{PENDING}: {line:?} is not <case>\\t<cause>"));
        assert!(!cause.is_empty(), "{PENDING}: {name} has no cause");
        assert!(
            previous.is_none_or(|previous| previous < name),
            "{PENDING} is not sorted, or lists {name} twice"
        );
        previous = Some(name);
        pending.insert(name.to_owned(), cause.to_owned());
    }
    pending
}

fn problems(case: &Case) -> Option<String> {
    let found = match panic::catch_unwind(AssertUnwindSafe(|| analyse(case))) {
        Ok(Ok(found)) => found,
        Ok(Err(error)) => return Some(error.to_string()),
        Err(_) => {
            let message = PANIC.lock().expect("the panic message is free").take();
            return Some(format!("panics: {}", message.unwrap_or_default()));
        }
    };
    if !found.inconsistencies.is_empty() {
        return Some(format!(
            "the document is not consistent: {}",
            found.inconsistencies.join("; ")
        ));
    }
    match &case.kind {
        Kind::Micro {
            edges,
            known_failure,
        } => {
            let differences = edge_differences(edges, &found.edges);
            match (*known_failure, differences.is_empty()) {
                (false, true) | (true, false) => None,
                (false, false) => Some(differences.join("; ")),
                (true, true) => Some(format!(
                    "passes, but {KNOWN_FAILURES} lists it: the oracle fails it"
                )),
            }
        }
        Kind::Oracle { expected, focus } => {
            let mut problems = edge_differences(&expected.edges, &found.edges);
            for entry in expected.unresolved.difference(&found.unresolved) {
                problems.push(format!("lost unresolved {entry:?}"));
            }
            for entry in found.unresolved.difference(&expected.unresolved) {
                problems.push(format!("gained unresolved {entry:?}"));
            }
            for (label, names) in &expected.points_to {
                let held = &found.points_to[label];
                if held != names {
                    problems.push(format!("{label} holds {held:?}, not {names:?}"));
                }
            }
            for (requested, document) in expected.documents.iter().zip(&found.documents) {
                if let Some(path) = first_difference(&requested.document, document, "") {
                    problems.push(format!(
                        "the document for package {:?} {:?} differs at {path}",
                        requested.package_name, requested.package_version
                    ));
                }
            }
            if found.warnings != expected.warnings {
                problems.push(format!(
                    "warns {:?}, not {:?}",
                    found.warnings, expected.warnings
                ));
            }
            problems.sort_by_key(|problem| !focus.iter().any(|caller| problem.contains(caller)));
            (!problems.is_empty()).then(|| problems.join("; "))
        }
    }
}

fn edge_differences(expected: &Edges, found: &Edges) -> Vec<String> {
    let mut differences = Vec::new();
    for caller in expected.keys().chain(found.keys()).collect::<BTreeSet<_>>() {
        match (expected.get(caller), found.get(caller)) {
            (Some(_), None) => differences.push(format!("lost caller {caller}")),
            (None, Some(_)) => differences.push(format!("gained caller {caller}")),
            (Some(expected), Some(found)) => {
                for callee in expected.difference(found) {
                    differences.push(format!("lost {caller} -> {callee}"));
                }
                for callee in found.difference(expected) {
                    differences.push(format!("gained {caller} -> {callee}"));
                }
            }
            (None, None) => unreachable!("{caller} is a caller of one side"),
        }
    }
    differences
}

fn analyse(case: &Case) -> Result<Found, pycg_analysis::Error> {
    let run = &case.run;
    let request = Request {
        entry_points: run
            .entry_points
            .iter()
            .map(|path| path.clone().into())
            .collect(),
        package: run.package.as_ref().map(|path| path.clone().into()),
        cap: run
            .cap
            .map_or(Cap::Unbounded, |cap| Cap::Objects(BigUint::from(cap))),
        order: Order::Canonical,
    };
    let root = run.root.to_string_lossy().into_owned();
    let mut warnings = Vec::new();
    let mut warn = |warning: &std::ffi::OsStr| {
        warnings.push(warning.to_string_lossy().replace(&root, ROOT_IN_WARNINGS));
    };
    let analysed = pycg_analysis::analyse(&request, &run.root, &mut warn)?;
    let mut program = analysed.program;
    let analysis = analysed.results;
    let program_part = ProgramPart::from_program(&mut program);
    let as_json = |name: Option<&str>, version: Option<&str>| -> Value {
        let (name, version) = (name.map(Text::from), version.map(Text::from));
        let document = build(&program_part, &analysis, name.as_ref(), version.as_ref());
        serde_json::from_str(&dumps(&document)).expect("the document is JSON")
    };
    let documents = match &case.kind {
        Kind::Oracle { expected, .. } => expected
            .documents
            .iter()
            .map(|requested| {
                as_json(
                    requested.package_name.as_deref(),
                    requested.package_version.as_deref(),
                )
            })
            .collect(),
        Kind::Micro { .. } => Vec::new(),
    };
    let document = as_json(None, None);
    let inconsistencies = inconsistencies(&document);
    let mut edges: Edges = object(&document["definitions"])
        .iter()
        .filter(|(_, definition)| definition["kind"] != "class")
        .map(|(name, _)| (name.clone(), BTreeSet::new()))
        .collect();
    for name in object(&document["outside"]).keys() {
        edges.insert(name.clone(), BTreeSet::new());
    }
    for (caller, sites) in object(&document["calls"]) {
        let callees = edges.entry(caller.clone()).or_default();
        for site in list(sites) {
            callees.extend(list(&site["callees"]).iter().map(text));
        }
    }
    let unresolved = analysis
        .unresolved
        .iter()
        .map(|entry| {
            (
                entry.caller.clone(),
                entry.site.clone(),
                entry.cause.clone(),
            )
        })
        .collect();
    let mut points_to = BTreeMap::new();
    if let Kind::Oracle { expected, .. } = &case.kind {
        let engine = &mut program.analysis;
        let saturated = engine.saturated();
        let mut held: BTreeMap<String, Vec<String>> = BTreeMap::new();
        for node in engine.named_nodes().to_vec() {
            let label = engine
                .label(node)
                .expect("a named node has a label")
                .to_owned();
            let names: Vec<String> = engine
                .held(node)
                .into_iter()
                .filter(|&object| object != saturated)
                .map(|object| engine.object_name(object))
                .collect();
            held.entry(label).or_default().extend(names);
        }
        for label in expected.points_to.keys() {
            let mut names = held.remove(label).unwrap_or_default();
            names.sort_unstable_by(|a, b| a.chars().cmp(b.chars()));
            names.dedup();
            points_to.insert(label.clone(), names);
        }
    }
    Ok(Found {
        edges,
        unresolved,
        points_to,
        documents,
        inconsistencies,
        warnings,
    })
}

fn inconsistencies(document: &Value) -> Vec<String> {
    let definitions = object(&document["definitions"]);
    let nodes: BTreeSet<&String> = definitions
        .iter()
        .filter(|(_, definition)| definition["kind"] != "class")
        .map(|(name, _)| name)
        .collect();
    let outside: BTreeSet<&String> = object(&document["outside"]).keys().collect();
    let mut found = Vec::new();
    for name in nodes.intersection(&outside) {
        found.push(format!("{name} is defined and outside"));
    }
    for (caller, sites) in object(&document["calls"]) {
        if !nodes.contains(caller) {
            found.push(format!("the caller {caller} is no function or module"));
            continue;
        }
        let module = &definitions[caller]["module"];
        let mut keys = Vec::new();
        for site in list(sites) {
            let callees: Vec<String> = list(&site["callees"]).iter().map(text).collect();
            for callee in &callees {
                if !nodes.contains(callee) && !outside.contains(callee) {
                    found.push(format!("{caller} calls {callee}, which is not listed"));
                }
            }
            if !callees.is_sorted_by(|a, b| a < b) {
                found.push(format!("the callees of a site of {caller} are not sorted"));
            }
            if callees.is_empty() && site.get("unresolved").is_none() {
                found.push(format!("a site of {caller} calls nothing and has no cause"));
            }
            if site.get("module") == Some(module) {
                found.push(format!("a site of {caller} names the module of {caller}"));
            }
            let end = list(&site["end"]);
            let number = |value: &Value| value.as_u64().expect("a position is a count");
            keys.push((
                site.get("module").map(text).unwrap_or_default(),
                number(&site["line"]),
                number(&site["col"]),
                number(&end[0]),
                number(&end[1]),
                site.get("implicit").map(text).unwrap_or_default(),
            ));
        }
        if !keys.is_sorted_by(|a, b| a < b) {
            found.push(format!(
                "the sites of {caller} are not sorted or not distinct"
            ));
        }
    }
    found
}

fn first_difference(expected: &Value, found: &Value, path: &str) -> Option<String> {
    match (expected, found) {
        (Value::Object(expected), Value::Object(found)) => {
            for key in expected.keys().chain(found.keys()).collect::<BTreeSet<_>>() {
                let inner = format!("{path}/{key}");
                match (expected.get(key), found.get(key)) {
                    (Some(expected), Some(found)) => {
                        if let Some(difference) = first_difference(expected, found, &inner) {
                            return Some(difference);
                        }
                    }
                    _ => return Some(inner),
                }
            }
            None
        }
        (Value::Array(expected), Value::Array(found)) if expected.len() == found.len() => expected
            .iter()
            .zip(found)
            .enumerate()
            .find_map(|(index, (expected, found))| {
                first_difference(expected, found, &format!("{path}/{index}"))
            }),
        _ => (expected != found).then(|| format!("{path}: {expected} is {found}")),
    }
}

fn optional_text(value: &Value) -> Option<String> {
    (!value.is_null()).then(|| text(value))
}

fn edges_of(value: &Value) -> Edges {
    object(value)
        .iter()
        .map(|(caller, callees)| (caller.clone(), list(callees).iter().map(text).collect()))
        .collect()
}

fn sorted_directories(directory: &Path) -> Vec<PathBuf> {
    let mut found: Vec<PathBuf> = std::fs::read_dir(directory)
        .unwrap_or_else(|error| panic!("{}: {error}", directory.display()))
        .map(|entry| entry.expect("a directory entry").path())
        .filter(|path| path.is_dir())
        .collect();
    found.sort();
    found
}

fn file_name(path: &Path) -> String {
    path.file_name()
        .and_then(|name| name.to_str())
        .expect("a case directory has a UTF-8 name")
        .to_owned()
}

fn read_json(path: &Path) -> Value {
    let text =
        std::fs::read_to_string(path).unwrap_or_else(|error| panic!("{}: {error}", path.display()));
    serde_json::from_str(&text).unwrap_or_else(|error| panic!("{}: {error}", path.display()))
}

fn object(value: &Value) -> &serde_json::Map<String, Value> {
    value
        .as_object()
        .unwrap_or_else(|| panic!("{value} is not an object"))
}

fn list(value: &Value) -> &Vec<Value> {
    value
        .as_array()
        .unwrap_or_else(|| panic!("{value} is not a list"))
}

fn text(value: &Value) -> String {
    value
        .as_str()
        .unwrap_or_else(|| panic!("{value} is not a string"))
        .to_owned()
}
