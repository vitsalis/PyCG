use std::path::{Path, PathBuf};
use std::process::{Command, Output};

const VECTORS: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/tests/vectors/engine");

fn vectors() -> Vec<PathBuf> {
    let mut found: Vec<PathBuf> = std::fs::read_dir(VECTORS)
        .expect("the engine vectors exist")
        .map(|entry| entry.expect("a directory entry").path())
        .collect();
    found.sort();
    assert!(!found.is_empty(), "engine vectors");
    for vector in &found {
        for dump in ["D3.jsonl", "D4.jsonl", "D5.jsonl", "D6in.json"] {
            assert!(
                vector.join(dump).exists(),
                "{} has no {dump} of the oracle",
                vector.display()
            );
        }
    }
    found
}

fn replay(vector: &Path) -> (PathBuf, Output) {
    let name = vector.file_name().expect("a vector name");
    let out = Path::new(env!("CARGO_TARGET_TMPDIR"))
        .join("engine")
        .join(name);
    std::fs::create_dir_all(&out).expect("the output directory is made");
    let output = Command::new(env!("CARGO_BIN_EXE_pycg-dump"))
        .arg("engine")
        .arg(vector.join("D4.jsonl"))
        .arg(&out)
        .output()
        .expect("pycg-dump runs");
    (out, output)
}

fn read(path: &Path) -> String {
    std::fs::read_to_string(path).unwrap_or_else(|error| panic!("{}: {error}", path.display()))
}

#[test]
fn the_engine_gives_the_trace_and_points_to_of_the_oracle_on_its_builder_calls() {
    for vector in vectors()
        .into_iter()
        .filter(|vector| !vector.join("not-ported.txt").exists())
    {
        let (out, output) = replay(&vector);
        assert!(
            output.status.success(),
            "{}: {}",
            vector.display(),
            String::from_utf8_lossy(&output.stderr)
        );
        for dump in ["D3.jsonl", "D5.jsonl", "D6in.json"] {
            assert_eq!(
                read(&out.join(dump)),
                read(&vector.join(dump)),
                "{} {dump}",
                vector.display()
            );
        }
    }
}

#[test]
fn the_engine_follows_the_oracle_up_to_the_rule_that_is_not_ported_yet() {
    for vector in vectors()
        .into_iter()
        .filter(|vector| vector.join("not-ported.txt").exists())
    {
        let (out, output) = replay(&vector);
        let expected = read(&vector.join("not-ported.txt"));
        let partial = read(&out.join("D3.partial.jsonl"));
        assert!(
            read(&vector.join("D3.jsonl")).starts_with(&partial),
            "{}: the partial trace leaves the oracle's",
            vector.display()
        );
        assert!(!output.status.success(), "{}", vector.display());
        assert!(
            String::from_utf8_lossy(&output.stderr).contains(expected.trim()),
            "{}: {}",
            vector.display(),
            String::from_utf8_lossy(&output.stderr)
        );
    }
}

#[test]
fn the_builder_into_the_engine_gives_the_trace_and_points_to_of_the_oracle() {
    for vector in vectors()
        .into_iter()
        .filter(|vector| !vector.join("not-ported.txt").exists() && programs(vector).len() == 1)
    {
        let name = vector.file_name().expect("a vector name");
        let out = Path::new(env!("CARGO_TARGET_TMPDIR"))
            .join("engine-build")
            .join(name);
        std::fs::create_dir_all(&out).expect("the output directory is made");
        let program = &programs(&vector)[0];
        let output = Command::new(env!("CARGO_BIN_EXE_pycg-dump"))
            .arg("engine-build")
            .arg(&out)
            .arg("--package")
            .arg(&vector)
            .arg(program)
            .output()
            .expect("pycg-dump runs");
        assert!(
            output.status.success(),
            "{}: {}",
            vector.display(),
            String::from_utf8_lossy(&output.stderr)
        );
        for dump in ["D3.jsonl", "D5.jsonl"] {
            assert_eq!(
                read(&out.join(dump)),
                read(&vector.join(dump)),
                "{} {dump}",
                vector.display()
            );
        }
    }
}

fn programs(vector: &Path) -> Vec<PathBuf> {
    let mut found: Vec<PathBuf> = std::fs::read_dir(vector)
        .expect("a vector directory")
        .map(|entry| entry.expect("a directory entry").path())
        .filter(|path| path.extension().is_some_and(|extension| extension == "py"))
        .collect();
    found.sort();
    found
}
