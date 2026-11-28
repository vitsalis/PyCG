mod canonical;
mod d1;
mod stubs;

use std::path::Path;

use pycg_stubs::Stubs;

const D1_VECTORS: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/../syntax/tests/vectors/d1");
const STUB_QUERIES: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/tests/vectors/stubs.jsonl");

#[test]
fn the_scopes_and_positions_of_each_program_are_its_d1_records() {
    let mut programs: Vec<_> = std::fs::read_dir(D1_VECTORS)
        .expect("the scope and position vectors exist")
        .map(|entry| entry.expect("a directory entry").path())
        .filter(|path| path.extension().is_some_and(|extension| extension == "py"))
        .collect();
    programs.sort();
    assert!(!programs.is_empty(), "scope and position vectors");
    for program in &programs {
        let mut found = Vec::new();
        d1::d1(program, module_of(program), &mut found).expect("the records are written");
        let expected =
            std::fs::read_to_string(program.with_extension("jsonl")).expect("the expected records");
        assert_eq!(
            String::from_utf8(found).expect("the records are UTF-8"),
            expected,
            "{}",
            program.display()
        );
    }
}

#[test]
fn the_stubs_answer_the_recorded_queries() {
    let queries = std::fs::read_to_string(STUB_QUERIES).expect("the stub queries");
    assert!(!queries.is_empty());
    let mut stubs = Stubs::new();
    for (number, query) in queries.lines().enumerate() {
        let record = stubs::replay(&mut stubs, query)
            .unwrap_or_else(|problem| panic!("query {}: {problem}", number + 1));
        assert_eq!(
            canonical::line(&record),
            format!("{query}\n"),
            "query {}",
            number + 1
        );
    }
}

fn module_of(program: &Path) -> &str {
    program
        .file_stem()
        .and_then(|stem| stem.to_str())
        .expect("a vector is named in UTF-8")
}
