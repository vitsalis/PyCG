use std::path::Path;
use std::process::Command;

const VECTORS: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/../syntax/tests/vectors/d1");

#[test]
fn the_d1_records_are_those_of_the_oracle() {
    let mut programs: Vec<_> = std::fs::read_dir(VECTORS)
        .expect("the D1 vectors exist")
        .map(|entry| entry.expect("a directory entry").path())
        .filter(|path| path.extension().is_some_and(|extension| extension == "py"))
        .collect();
    programs.sort();
    assert!(!programs.is_empty(), "D1 vectors");
    let listing: String = programs
        .iter()
        .map(|program| format!("{}\t{}\n", module_of(program), path_text(program)))
        .collect();
    let directory = Path::new(env!("CARGO_TARGET_TMPDIR"));
    let modules = directory.join("d1-vectors.tsv");
    let dump = directory.join("d1-vectors.jsonl");
    std::fs::write(&modules, listing).expect("the module list is written");
    let status = Command::new(env!("CARGO_BIN_EXE_pycg-dump"))
        .args(["d1", path_text(&modules), path_text(&dump)])
        .status()
        .expect("pycg-dump runs");
    assert!(status.success(), "pycg-dump d1");
    let found = std::fs::read_to_string(&dump).expect("the dump is UTF-8");
    let expected: String = programs
        .iter()
        .map(|program| std::fs::read_to_string(program.with_extension("jsonl")).expect("expected"))
        .collect();
    assert_eq!(found, expected);
}

fn module_of(program: &Path) -> &str {
    program
        .file_stem()
        .and_then(|stem| stem.to_str())
        .expect("a vector is named in UTF-8")
}

fn path_text(path: &Path) -> &str {
    path.to_str().expect("a vector path is UTF-8")
}
