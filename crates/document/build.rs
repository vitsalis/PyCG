use std::env;
use std::fs;
use std::path::PathBuf;

const PACKAGE_INIT: &str = "../../pycg/__init__.py";
const VERSION_ASSIGNMENT: &str = "__version__ = \"";

fn main() {
    let manifest = PathBuf::from(env::var("CARGO_MANIFEST_DIR").expect("CARGO_MANIFEST_DIR"));
    let init = manifest.join(PACKAGE_INIT);
    println!("cargo::rerun-if-changed={}", init.display());
    let text = fs::read_to_string(&init).expect("read pycg/__init__.py");
    let found: Vec<&str> = text
        .lines()
        .filter_map(|line| line.strip_prefix(VERSION_ASSIGNMENT))
        .collect();
    assert_eq!(found.len(), 1, "pycg/__init__.py assigns __version__ once");
    let version = found[0]
        .strip_suffix('"')
        .expect("the version is a string literal on one line");
    assert!(
        !version.is_empty() && version.chars().all(|c| c.is_ascii_digit() || c == '.'),
        "the version {version} is dotted numbers"
    );
    let out = PathBuf::from(env::var("OUT_DIR").expect("OUT_DIR"));
    fs::write(out.join("version.txt"), version).expect("write version.txt");
}
