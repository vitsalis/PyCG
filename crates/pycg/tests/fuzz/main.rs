mod generator;

use std::collections::BTreeMap;
use std::ffi::{OsStr, OsString};
use std::path::{Path, PathBuf};
use std::sync::Mutex;
use std::sync::atomic::{AtomicU64, Ordering};

use num_bigint::BigUint;
use pycg_analysis::{CAP_DEFAULT_OBJECTS, Cap, Order, Request, analyse};
use pycg_document::ProgramPart;

const SEEDS: u64 = 200;

fn write(seed: u64, files: &BTreeMap<String, String>) -> PathBuf {
    let root = Path::new(env!("CARGO_TARGET_TMPDIR"))
        .join("fuzz")
        .join(seed.to_string());
    if root.exists() {
        std::fs::remove_dir_all(&root).expect("an earlier program is removed");
    }
    for (path, source) in files {
        let file = root.join(path);
        std::fs::create_dir_all(file.parent().expect("a directory")).expect("a directory is made");
        std::fs::write(&file, source).expect("a module is written");
    }
    root
}

fn outcome(root: &Path, order: Order) -> String {
    let request = Request {
        entry_points: vec![OsString::from(root.join("main.py"))],
        package: Some(root.as_os_str().to_os_string()),
        cap: Cap::Objects(BigUint::from(CAP_DEFAULT_OBJECTS)),
        order,
    };
    let mut warnings = Vec::new();
    let mut warn = |warning: &OsStr| warnings.push(warning.to_os_string());
    match analyse(&request, root, &mut warn) {
        Err(error) => format!("error: {error}"),
        Ok(mut analysed) => {
            let part = ProgramPart::from_program(&mut analysed.program);
            let document = pycg_document::build(&part, &analysed.results, None, None);
            format!("{warnings:?}\n{}", pycg_document::dumps(&document))
        }
    }
}

fn report(seed: u64, files: &BTreeMap<String, String>) -> String {
    let sources: Vec<String> = files
        .iter()
        .map(|(path, source)| format!("--- {path}\n{source}"))
        .collect();
    format!("seed {seed}\n{}", sources.join("\n"))
}

fn differences(seed: u64) -> Option<String> {
    let files = generator::program(seed);
    let root = write(seed, &files);
    let first = outcome(&root, Order::Canonical);
    if first != outcome(&root, Order::Canonical) {
        return Some(format!("two runs differ\n{}", report(seed, &files)));
    }
    if first != outcome(&root, Order::LastInFirstOut) {
        return Some(format!("the orders differ\n{}", report(seed, &files)));
    }
    None
}

#[test]
fn a_generated_program_gives_one_document_in_every_run_and_order() {
    let found = Mutex::new(Vec::new());
    let next = AtomicU64::new(0);
    let workers = std::thread::available_parallelism().map_or(1, usize::from);
    std::thread::scope(|scope| {
        for _ in 0..workers {
            scope.spawn(|| {
                loop {
                    let seed = next.fetch_add(1, Ordering::Relaxed);
                    if seed >= SEEDS {
                        break;
                    }
                    if let Some(difference) = differences(seed) {
                        found
                            .lock()
                            .expect("no worker panicked")
                            .push((seed, difference));
                    }
                }
            });
        }
    });
    let mut found = found.into_inner().expect("no worker panicked");
    found.sort();
    let reports: Vec<String> = found.into_iter().map(|(_, report)| report).collect();
    assert!(
        reports.is_empty(),
        "{} of {SEEDS} programs:\n{}",
        reports.len(),
        reports.join("\n")
    );
}
