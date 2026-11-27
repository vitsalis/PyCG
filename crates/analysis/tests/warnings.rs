use std::fs;
use std::path::{Path, PathBuf};

use pycg_analysis::Order;
use pycg_analysis::engine::Engine;
use pycg_analysis::engine::trace::Untraced;
use pycg_analysis::program::Program;

struct Scratch(PathBuf);

impl Drop for Scratch {
    fn drop(&mut self) {
        fs::remove_dir_all(&self.0).expect("the scratch directory is removed");
    }
}

fn scratch(name: &str, files: &[(&str, &str)]) -> Scratch {
    let root = std::env::temp_dir().join(format!("pycg-warnings-{}-{name}", std::process::id()));
    for (path, text) in files {
        let path = root.join(path);
        fs::create_dir_all(path.parent().expect("a file has a directory"))
            .expect("the directory is made");
        fs::write(path, text).expect("the file is written");
    }
    Scratch(root)
}

fn warnings(root: &Path, package: &str, entry_points: &[&str]) -> Vec<String> {
    let entry_points: Vec<PathBuf> = entry_points.iter().map(PathBuf::from).collect();
    let engine = Engine::new(Some(5000), Order::Canonical, Untraced);
    let mut program = Program::new(&entry_points, Some(Path::new(package)), root, engine)
        .expect("the paths are on one drive");
    program.build_modules().expect("the paths are on one drive");
    let root = root.to_str().expect("the scratch path is UTF-8");
    program
        .warnings
        .iter()
        .map(|warning| {
            warning
                .to_str()
                .expect("a warning is UTF-8")
                .replace(root, "{root}")
        })
        .collect()
}

#[test]
fn a_skipped_entry_point_is_warned_as_the_oracle_warns() {
    let files = [
        ("pkg/__init__.py", ""),
        ("pkg/a.py", "def f():\n    pass\n"),
        ("pkg/a.pyi", "x: int\n"),
        ("pkg/sub/m.py", "y = 1\n"),
        ("other/x.py", "z = 1\n"),
    ];
    let scratch = scratch("skipped", &files);
    let found = warnings(
        &scratch.0,
        "pkg",
        &[
            "other/x.py",
            "pkg/a.pyi",
            "pkg/sub",
            "pkg/__init__.py",
            "pkg/a.py",
        ],
    );
    assert_eq!(
        found,
        [
            "Skipping {root}/other/x.py: it is not under the package root {root}/pkg",
            "Skipping {root}/pkg/a.pyi: a stub is not source",
            "Skipping {root}/pkg/sub: a directory is not a module file; give its files",
            "Skipping {root}/pkg/__init__.py: the package root is not a package",
        ]
    );
}

#[test]
fn a_module_nested_too_deep_is_warned_as_the_oracle_warns() {
    let deep = format!("x = 1\ny = 2\nz = {}1\n", "-".repeat(300));
    let scratch = scratch("deep", &[("pkg/deep.py", &deep)]);
    let found = warnings(&scratch.0, "pkg", &["pkg/deep.py"]);
    assert_eq!(
        found,
        ["{root}/pkg/deep.py: line 3 nests deeper than 247 levels; the analysis stops there"]
    );
}

#[test]
fn a_module_that_cannot_be_read_or_parsed_is_warned_with_the_rust_cause() {
    let files = [
        ("pkg/broken.py", "def (\n"),
        ("pkg/latin.py", "# -*- coding: nope -*-\nx = 1\n"),
    ];
    let scratch = scratch("unreadable", &files);
    let found = warnings(
        &scratch.0,
        "pkg",
        &["pkg/broken.py", "pkg/latin.py", "pkg/missing.py"],
    );
    assert_eq!(
        found,
        [
            "Skipping {root}/pkg/broken.py: cannot parse it: SyntaxError (line 1)",
            "Skipping {root}/pkg/latin.py: cannot read it: SyntaxError",
            "Skipping {root}/pkg/missing.py: cannot read it: FileNotFoundError",
        ]
    );
}
