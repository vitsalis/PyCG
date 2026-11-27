use std::collections::BTreeSet;
use std::ffi::{OsStr, OsString};
use std::path::{Path, PathBuf};
use std::sync::Mutex;
use std::sync::atomic::{AtomicUsize, Ordering};

use num_bigint::BigUint;
use pycg_analysis::{Cap, Order, Request, analyse};
use pycg_document::{ProgramPart, Value};

const ROOT: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/../..");
const SEEDS: [u64; 2] = [1, 2];
const SMALL_CAPS: [u32; 3] = [1, 2, 3];
const SUBSET_CAPS: [u32; 3] = [2, 3, 10];

struct Input {
    id: String,
    directory: PathBuf,
    entry_points: Vec<String>,
    modules: Vec<String>,
}

fn read(path: &Path) -> String {
    std::fs::read_to_string(path).unwrap_or_else(|error| panic!("{}: {error}", path.display()))
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

fn python_files(directory: &Path, relative: &Path, found: &mut Vec<String>) {
    for entry in std::fs::read_dir(directory.join(relative)).expect("a case directory") {
        let path = entry.expect("a directory entry").path();
        let name = relative.join(path.file_name().expect("a file name"));
        if path.is_dir() {
            python_files(directory, &name, found);
        } else if path.extension().is_some_and(|extension| extension == "py") {
            found.push(name.to_string_lossy().into_owned());
        }
    }
}

fn parses(directory: &Path) -> bool {
    let path = directory.join("requires-python");
    if !path.is_file() {
        return true;
    }
    let version = read(&path);
    let (major, minor) = version.trim().split_once('.').expect("major.minor");
    let needed = (
        major.parse::<u8>().expect("a major"),
        minor.parse::<u8>().expect("a minor"),
    );
    let target = pycg_syntax::parse::TARGET_VERSION;
    needed <= (target.major, target.minor)
}

fn micro_inputs() -> Vec<Input> {
    let snippets = Path::new(ROOT).join("evaluation/micro-benchmark/snippets");
    let mut inputs = Vec::new();
    for category in directories(&snippets) {
        for directory in directories(&category) {
            if !parses(&directory) {
                continue;
            }
            let mut modules = Vec::new();
            python_files(&directory, Path::new(""), &mut modules);
            modules.sort();
            inputs.push(Input {
                id: format!(
                    "micro/{}",
                    directory.strip_prefix(&snippets).expect("a case").display()
                ),
                directory,
                entry_points: vec!["main.py".to_owned()],
                modules,
            });
        }
    }
    inputs
}

fn default_cap() -> Cap {
    Cap::Objects(BigUint::from(pycg_analysis::CAP_DEFAULT_OBJECTS))
}

fn document(
    input: &Input,
    entry_points: &[String],
    order: Order,
    cap: Cap,
) -> Result<(Value, Vec<OsString>), String> {
    let request = Request {
        entry_points: entry_points
            .iter()
            .map(|entry| OsString::from(input.directory.join(entry)))
            .collect(),
        package: Some(input.directory.clone().into_os_string()),
        cap,
        order,
    };
    let mut warnings = Vec::new();
    let mut warn = |warning: &OsStr| warnings.push(warning.to_os_string());
    let mut analysed =
        analyse(&request, &input.directory, &mut warn).map_err(|error| error.to_string())?;
    let part = ProgramPart::from_program(&mut analysed.program);
    Ok((
        pycg_document::build(&part, &analysed.results, None, None),
        warnings,
    ))
}

fn outcome(input: &Input, entry_points: &[String], order: Order, cap: Cap) -> String {
    match document(input, entry_points, order, cap) {
        Err(error) => format!("error: {error}"),
        Ok((document, warnings)) => format!("{warnings:?}\n{}", pycg_document::dumps(&document)),
    }
}

fn edges(document: &Value) -> BTreeSet<(String, String)> {
    let Value::Object(document) = document else {
        panic!("a document is an object");
    };
    let Some(Value::Object(calls)) = document.get("calls") else {
        panic!("a document has calls");
    };
    let mut found = BTreeSet::new();
    for (caller, sites) in calls {
        let Value::Array(sites) = sites else {
            panic!("the sites of a caller are an array");
        };
        for site in sites {
            let Value::Object(site) = site else {
                panic!("a site is an object");
            };
            let Some(Value::Array(callees)) = site.get("callees") else {
                panic!("a site has callees");
            };
            for callee in callees {
                found.insert((caller.clone(), format!("{callee:?}")));
            }
        }
    }
    found
}

fn orders() -> Vec<Order> {
    let mut orders = vec![Order::LastInFirstOut, Order::Reversed];
    orders.extend(SEEDS.map(Order::shuffled));
    orders
}

fn differences(input: &Input) -> Vec<String> {
    let canonical = outcome(input, &input.entry_points, Order::Canonical, default_cap());
    let mut found = Vec::new();
    for order in orders() {
        if outcome(input, &input.entry_points, order, default_cap()) != canonical {
            found.push(format!("{}: {order:?} gives another result", input.id));
        }
    }
    if input.modules.len() > 1 {
        let mut reversed = input.modules.clone();
        reversed.reverse();
        let forward = outcome(input, &input.modules, Order::Canonical, default_cap());
        if outcome(input, &reversed, Order::Canonical, default_cap()) != forward {
            found.push(format!(
                "{}: its modules in reverse give another result",
                input.id
            ));
        }
    }
    found
}

fn small_cap_differences(input: &Input) -> Vec<String> {
    let mut found = Vec::new();
    for cap in SMALL_CAPS {
        let capped = || Cap::Objects(BigUint::from(cap));
        let canonical = outcome(input, &input.entry_points, Order::Canonical, capped());
        for order in orders() {
            if outcome(input, &input.entry_points, order, capped()) != canonical {
                found.push(format!(
                    "{}: {order:?} at cap {cap} gives another result",
                    input.id
                ));
            }
        }
    }
    found
}

fn added_edges(input: &Input) -> Vec<String> {
    let Ok((full, _)) = document(input, &input.entry_points, Order::Canonical, default_cap())
    else {
        return Vec::new();
    };
    let full = edges(&full);
    let mut found = Vec::new();
    for cap in SUBSET_CAPS {
        let capped = Cap::Objects(BigUint::from(cap));
        if let Ok((capped, _)) = document(input, &input.entry_points, Order::Canonical, capped) {
            for (caller, callee) in edges(&capped).difference(&full) {
                found.push(format!("{}: cap {cap} adds {caller} -> {callee}", input.id));
            }
        }
    }
    found
}

fn everywhere(check: fn(&Input) -> Vec<String>) {
    let inputs = micro_inputs();
    assert!(!inputs.is_empty(), "inputs");
    let found = Mutex::new(Vec::new());
    let next = AtomicUsize::new(0);
    let workers = std::thread::available_parallelism().map_or(1, usize::from);
    std::thread::scope(|scope| {
        for _ in 0..workers {
            scope.spawn(|| {
                loop {
                    let index = next.fetch_add(1, Ordering::Relaxed);
                    let Some(input) = inputs.get(index) else {
                        break;
                    };
                    let lines = check(input);
                    found.lock().expect("no worker panicked").extend(lines);
                }
            });
        }
    });
    let mut found = found.into_inner().expect("no worker panicked");
    found.sort();
    assert!(
        found.is_empty(),
        "{} findings over {} inputs:\n{}",
        found.len(),
        inputs.len(),
        found.join("\n")
    );
}

#[test]
fn every_micro_case_gives_one_result_in_every_order() {
    everywhere(differences);
}

#[test]
fn every_micro_case_gives_one_result_in_every_order_at_small_caps() {
    everywhere(small_cap_differences);
}

#[test]
fn a_small_cap_adds_no_edge_to_a_micro_case() {
    everywhere(added_edges);
}
