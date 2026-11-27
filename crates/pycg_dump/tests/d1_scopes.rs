use std::path::Path;
use std::process::Command;

const VECTORS: &str = concat!(
    env!("CARGO_MANIFEST_DIR"),
    "/../pycg_syntax/tests/vectors/scopes"
);
const MODULE: &str = "m";

#[test]
fn the_scopes_dump_is_that_of_the_oracle() {
    let mut programs: Vec<_> = std::fs::read_dir(VECTORS)
        .expect("the scope vectors exist")
        .map(|entry| entry.expect("a directory entry").path())
        .filter(|path| path.extension().is_some_and(|extension| extension == "py"))
        .collect();
    programs.sort();
    assert!(!programs.is_empty(), "scope vectors");
    for program in programs {
        let output = Command::new(env!("CARGO_BIN_EXE_pycg_dump"))
            .args(["d1-scopes", path_text(&program), MODULE])
            .output()
            .expect("pycg_dump runs");
        assert!(
            output.status.success(),
            "pycg_dump on {}",
            program.display()
        );
        let found = String::from_utf8(output.stdout).expect("the dump is UTF-8");
        let expected = std::fs::read_to_string(program.with_extension("txt")).expect("expected");
        assert_eq!(found, expected, "{}", program.display());
    }
}

fn path_text(path: &Path) -> &str {
    path.to_str().expect("a vector path is UTF-8")
}
