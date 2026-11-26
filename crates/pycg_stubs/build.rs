use std::env;
use std::fmt::Write as _;
use std::fs;
use std::path::{Path, PathBuf};

const STUB_DATA_DIRECTORY: &str = "../../pycg/analysis/stub_data";
const THIRD_PARTY_DIRECTORY_NAME: &str = "third_party";
const README_NAME: &str = "README.md";
const TYPESHED_COMMIT_MARKER: &str = "at commit";
const STUB_SUFFIX: &str = ".json";

fn main() {
    let manifest = PathBuf::from(env::var("CARGO_MANIFEST_DIR").expect("CARGO_MANIFEST_DIR"));
    let directory = manifest.join(STUB_DATA_DIRECTORY);
    println!("cargo::rerun-if-changed={}", directory.display());
    let mut source = String::new();
    write_table(&mut source, "STANDARD_LIBRARY", &directory);
    write_table(
        &mut source,
        "THIRD_PARTY",
        &directory.join(THIRD_PARTY_DIRECTORY_NAME),
    );
    let commit = typeshed_commit(&directory.join(README_NAME));
    writeln!(source, "pub const TYPESHED_COMMIT: &str = {commit:?};").expect("write");
    let out = PathBuf::from(env::var("OUT_DIR").expect("OUT_DIR"));
    fs::write(out.join("stub_files.rs"), source).expect("write stub_files.rs");
}

fn write_table(source: &mut String, name: &str, directory: &Path) {
    let mut files: Vec<(String, PathBuf)> = fs::read_dir(directory)
        .expect("read the stub data directory")
        .map(|item| item.expect("read a stub data entry").path())
        .filter(|path| path.is_file())
        .filter_map(|path| {
            let file = path.file_name()?.to_str()?.to_owned();
            let top = file.strip_suffix(STUB_SUFFIX)?.to_owned();
            Some((top, path))
        })
        .collect();
    files.sort();
    assert!(
        !files.is_empty(),
        "no stub files in {}",
        directory.display()
    );
    writeln!(source, "pub static {name}: &[(&str, &[u8])] = &[").expect("write");
    for (top, path) in &files {
        let path = path.canonicalize().expect("canonical stub path");
        let path = path.to_str().expect("a UTF-8 stub path");
        writeln!(source, "    ({top:?}, include_bytes!({path:?})),").expect("write");
    }
    writeln!(source, "];").expect("write");
}

fn typeshed_commit(readme: &Path) -> String {
    let text = fs::read_to_string(readme).expect("read the stub data README");
    let after = text
        .split_once(TYPESHED_COMMIT_MARKER)
        .expect("the README names the typeshed commit")
        .1;
    let commit = after
        .split('`')
        .nth(1)
        .expect("the typeshed commit in backquotes");
    assert!(
        commit.len() == 40 && commit.bytes().all(|byte| byte.is_ascii_hexdigit()),
        "the typeshed commit is a full hexadecimal hash: {commit}"
    );
    commit.to_owned()
}
