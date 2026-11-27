use std::path::{Path, PathBuf};
use std::process::Command;

fn vectors() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/vectors/builder")
}

fn replay(case: &Path, scratch: &Path) -> String {
    let modules = scratch.join("modules.tsv");
    let main = case.join("main.py");
    std::fs::write(&modules, format!("main\t{}\n", main.display())).expect("the module list");
    let out = scratch.join("D4.jsonl");
    let status = Command::new(env!("CARGO_BIN_EXE_pycg_dump"))
        .arg("d4")
        .arg(&modules)
        .arg(case.join("entries.txt"))
        .arg(case.join("D4.jsonl"))
        .arg(&out)
        .status()
        .expect("pycg_dump runs");
    assert!(status.success(), "{}", case.display());
    std::fs::read_to_string(out).expect("the replayed D4")
}

#[test]
fn the_builder_makes_the_oracles_calls_on_statement_programs() {
    let mut cases: Vec<PathBuf> = std::fs::read_dir(vectors())
        .expect("the builder vectors")
        .map(|entry| entry.expect("a vector").path())
        .collect();
    cases.sort();
    assert!(!cases.is_empty());
    let scratch = std::env::temp_dir().join(format!("pycg-builder-{}", std::process::id()));
    std::fs::create_dir_all(&scratch).expect("a scratch directory");
    let mut differing = Vec::new();
    for case in &cases {
        let expected = std::fs::read_to_string(case.join("D4.jsonl")).expect("the oracle's D4");
        let found = replay(case, &scratch);
        if found != expected {
            let line = expected
                .lines()
                .zip(found.lines())
                .position(|(a, b)| a != b)
                .unwrap_or(expected.lines().count().min(found.lines().count()));
            differing.push(format!(
                "{}: first difference at record {}",
                case.display(),
                line + 1
            ));
        }
    }
    std::fs::remove_dir_all(&scratch).expect("the scratch directory is removed");
    assert!(differing.is_empty(), "{differing:#?}");
}
