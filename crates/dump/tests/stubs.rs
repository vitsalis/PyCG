use std::process::Command;

const QUERIES: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/tests/vectors/stubs.jsonl");

#[test]
fn the_stubs_answer_the_queries_of_the_python_unit_tests_as_the_oracle_did() {
    let output = Command::new(env!("CARGO_BIN_EXE_pycg-dump"))
        .args(["stubs", QUERIES])
        .output()
        .expect("pycg-dump runs");
    assert!(
        output.status.success(),
        "pycg-dump stubs: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    let expected = std::fs::read_to_string(QUERIES).expect("the stub queries");
    let found = String::from_utf8(output.stdout).expect("the answers are UTF-8");
    assert!(!expected.is_empty());
    for (number, (expected, found)) in expected.lines().zip(found.lines()).enumerate() {
        assert_eq!(found, expected, "query {}", number + 1);
    }
    assert_eq!(found.lines().count(), expected.lines().count());
}
