use std::path::{Path, PathBuf};
use std::process::Command;

fn vectors() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/vectors/builder")
}

fn replay(case: &Path, scratch: &Path) -> (String, String, String) {
    let out = scratch.join("out");
    let status = Command::new(env!("CARGO_BIN_EXE_pycg-dump"))
        .current_dir(case)
        .arg("d4")
        .arg(case.join("D4.jsonl"))
        .arg(&out)
        .arg("--package")
        .arg(".")
        .arg("main.py")
        .status()
        .expect("pycg-dump runs");
    assert!(status.success(), "{}", case.display());
    let read = |name: &str| std::fs::read_to_string(out.join(name)).expect("a replayed dump");
    (
        read("D4.jsonl"),
        read("modules.json"),
        read("definitions.json"),
    )
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
        let read = |name: &str| std::fs::read_to_string(case.join(name)).expect("an oracle dump");
        let expected = read("D4.jsonl");
        let (found, modules, definitions) = replay(case, &scratch);
        if modules != read("modules.json") {
            differing.push(format!("{}: the modules differ", case.display()));
        }
        if definitions != read("definitions.json") {
            differing.push(format!("{}: the module definitions differ", case.display()));
        }
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
