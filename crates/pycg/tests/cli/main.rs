#![cfg(unix)]

mod vectors;
mod view_vectors;

use std::ffi::{OsStr, OsString};
use std::os::unix::ffi::OsStrExt;
use std::os::unix::process::CommandExt;
use std::path::{Path, PathBuf};
use std::process::Command;

use num_bigint::BigUint;
use pycg_analysis::Cap;

const PARSED_WIDTH: i64 = 78;

struct Case {
    program: &'static [u8],
    arguments: &'static [&'static [u8]],
    columns: Option<&'static [u8]>,
    outcome: Outcome,
}

enum Outcome {
    Parsed(Parsed),
    Viewed(Viewed),
    Exit {
        status: i32,
        stdout: &'static [u8],
        stderr: &'static [u8],
    },
}

struct Viewed {
    document: &'static [u8],
    output: Option<&'static [u8]>,
}

struct DocumentCase {
    files: &'static [(&'static [u8], &'static [u8])],
    arguments: &'static [&'static [u8]],
    status: i32,
    written: Option<(&'static [u8], &'static [u8])>,
}

struct Parsed {
    entry_points: &'static [&'static [u8]],
    package: Option<&'static [u8]>,
    package_name: Option<&'static [u8]>,
    package_version: Option<&'static [u8]>,
    output: Option<&'static [u8]>,
    cap: Option<&'static [u8]>,
}

fn os_string(bytes: &[u8]) -> OsString {
    OsStr::from_bytes(bytes).to_os_string()
}

fn optional(bytes: Option<&[u8]>) -> Option<OsString> {
    bytes.map(os_string)
}

fn shown(bytes: &[u8]) -> String {
    String::from_utf8_lossy(bytes).into_owned()
}

fn describe(case: &Case) -> String {
    let arguments: Vec<String> = case.arguments.iter().map(|a| shown(a)).collect();
    format!(
        "program {:?}, COLUMNS {:?}, arguments {:?}",
        shown(case.program),
        case.columns.map(shown),
        arguments
    )
}

fn run_binary(case: &Case) -> (i32, Vec<u8>, Vec<u8>) {
    let mut command = Command::new(env!("CARGO_BIN_EXE_pycg"));
    command
        .arg0(OsStr::from_bytes(case.program))
        .args(case.arguments.iter().map(|a| OsStr::from_bytes(a)))
        .env_remove("COLUMNS")
        .env_remove("LINES");
    if let Some(columns) = case.columns {
        command.env("COLUMNS", OsStr::from_bytes(columns));
    }
    let output = command.output().expect("run pycg");
    let status = output.status.code().expect("an exit status");
    (status, output.stdout, output.stderr)
}

fn expected_cap(cap: Option<&[u8]>) -> Cap {
    match cap {
        None => Cap::Unbounded,
        Some(digits) => Cap::Objects(BigUint::parse_bytes(digits, 10).expect("digits")),
    }
}

fn check_parsed(case: &Case, parsed: &Parsed) -> Result<(), String> {
    let program = pycg::program_name(OsStr::from_bytes(case.program));
    let arguments: Vec<OsString> = case.arguments.iter().map(|a| os_string(a)).collect();
    let pycg::Outcome::Run(options) = pycg::parse(&program, &arguments, PARSED_WIDTH) else {
        return Err("the oracle parsed the arguments, the port did not".to_owned());
    };
    let entry_points: Vec<OsString> = parsed.entry_points.iter().map(|a| os_string(a)).collect();
    let expected = (
        entry_points,
        optional(parsed.package),
        expected_cap(parsed.cap),
        optional(parsed.package_name),
        optional(parsed.package_version),
        optional(parsed.output),
    );
    let actual = (
        options.request.entry_points,
        options.request.package,
        options.request.cap,
        options.package_name,
        options.package_version,
        options.output,
    );
    if actual != expected {
        return Err(format!("parsed {actual:?}, the oracle {expected:?}"));
    }
    Ok(())
}

fn check_viewed(case: &Case, viewed: &Viewed) -> Result<(), String> {
    let program = pycg::program_name(OsStr::from_bytes(case.program));
    let arguments: Vec<OsString> = case.arguments.iter().map(|a| os_string(a)).collect();
    let expected = pycg::Outcome::View(pycg::ViewOptions {
        document: os_string(viewed.document),
        output: optional(viewed.output),
    });
    let actual = pycg::parse(&program, &arguments, PARSED_WIDTH);
    if actual != expected {
        return Err(format!("parsed {actual:?}, the oracle {expected:?}"));
    }
    Ok(())
}

fn check_exit(case: &Case, status: i32, stdout: &[u8], stderr: &[u8]) -> Result<(), String> {
    let (ran_status, ran_stdout, ran_stderr) = run_binary(case);
    let mut differences = Vec::new();
    if ran_status != status {
        differences.push(format!("status {ran_status}, the oracle {status}"));
    }
    if ran_stdout != stdout {
        differences.push(format!(
            "stdout\n{}\nthe oracle\n{}",
            shown(&ran_stdout),
            shown(stdout)
        ));
    }
    if ran_stderr != stderr {
        differences.push(format!(
            "stderr\n{}\nthe oracle\n{}",
            shown(&ran_stderr),
            shown(stderr)
        ));
    }
    if differences.is_empty() {
        Ok(())
    } else {
        Err(differences.join("\n"))
    }
}

fn check(case: &Case) -> Result<(), String> {
    match &case.outcome {
        Outcome::Parsed(parsed) => check_parsed(case, parsed),
        Outcome::Viewed(viewed) => check_viewed(case, viewed),
        Outcome::Exit {
            status,
            stdout,
            stderr,
        } => check_exit(case, *status, stdout, stderr),
    }
}

#[test]
fn every_case_gives_what_python_gives() {
    let mut failures = Vec::new();
    for case in vectors::CASES {
        if let Err(difference) = check(case) {
            failures.push(format!("{}\n{difference}", describe(case)));
        }
    }
    assert!(
        failures.is_empty(),
        "{} of {} cases differ from the oracle:\n\n{}",
        failures.len(),
        vectors::CASES.len(),
        failures.join("\n\n")
    );
}

const TEMPLATE: &str = include_str!("../../src/template.html");
const MARKER: &str = "@@PYCG_DOCUMENT@@";

fn files_under(root: &Path) -> Vec<PathBuf> {
    let mut found = Vec::new();
    let mut directories = vec![root.to_path_buf()];
    while let Some(directory) = directories.pop() {
        for entry in std::fs::read_dir(&directory).expect("read a case directory") {
            let path = entry.expect("a directory entry").path();
            if path.is_dir() {
                directories.push(path);
            } else {
                found.push(path);
            }
        }
    }
    found.sort();
    found
}

fn check_document(index: usize, case: &DocumentCase) -> Result<(), String> {
    let root = Path::new(env!("CARGO_TARGET_TMPDIR")).join(format!("view-{index}"));
    if root.exists() {
        std::fs::remove_dir_all(&root).expect("remove an old case directory");
    }
    for (name, data) in case.files {
        let path = root.join(OsStr::from_bytes(name));
        std::fs::create_dir_all(path.parent().expect("a parent")).expect("make a directory");
        std::fs::write(&path, data).expect("write an input");
    }
    let output = Command::new(env!("CARGO_BIN_EXE_pycg"))
        .arg("view")
        .args(case.arguments.iter().map(|a| OsStr::from_bytes(a)))
        .current_dir(&root)
        .output()
        .expect("run pycg view");
    let status = output.status.code().expect("an exit status");
    let mut differences = Vec::new();
    if status != case.status {
        differences.push(format!("status {status}, the oracle {}", case.status));
    }
    let lines = output.stderr.iter().filter(|byte| **byte == b'\n').count();
    let reported = output.stderr.starts_with(b"pycg view: ") && lines == 1;
    if !output.stdout.is_empty() || (case.status == 0) != output.stderr.is_empty() {
        differences.push(format!(
            "stdout {:?}, stderr {:?}",
            shown(&output.stdout),
            shown(&output.stderr)
        ));
    } else if case.status == 1 && !reported {
        differences.push(format!(
            "stderr {:?} is not one line of pycg view",
            shown(&output.stderr)
        ));
    }
    let inputs: Vec<(PathBuf, &[u8])> = case
        .files
        .iter()
        .map(|(name, data)| (root.join(OsStr::from_bytes(name)), *data))
        .collect();
    let written: Vec<PathBuf> = files_under(&root)
        .into_iter()
        .filter(|path| {
            let data = std::fs::read(path).expect("read a file");
            !inputs
                .iter()
                .any(|(input, original)| input == path && *original == data)
        })
        .collect();
    let (head, tail) = TEMPLATE
        .split_once(MARKER)
        .expect("the template has the marker");
    match (case.written, written.as_slice()) {
        (None, []) => {}
        (Some((name, block)), [path]) if *path == root.join(OsStr::from_bytes(name)) => {
            let page = std::fs::read(path).expect("read the page");
            if page != [head.as_bytes(), block, tail.as_bytes()].concat() {
                differences.push(format!("the page {} differs", path.display()));
            }
        }
        (expected, found) => differences.push(format!(
            "wrote {found:?}, the oracle {:?}",
            expected.map(|(name, _)| shown(name))
        )),
    }
    if differences.is_empty() {
        Ok(())
    } else {
        Err(differences.join("\n"))
    }
}

#[test]
fn every_document_case_gives_what_python_gives() {
    let mut failures = Vec::new();
    for (index, case) in view_vectors::DOCUMENT_CASES.iter().enumerate() {
        if let Err(difference) = check_document(index, case) {
            let arguments: Vec<String> = case.arguments.iter().map(|a| shown(a)).collect();
            failures.push(format!(
                "case {index}, arguments {arguments:?}\n{difference}"
            ));
        }
    }
    assert!(
        failures.is_empty(),
        "{} of {} document cases differ from the oracle:\n\n{}",
        failures.len(),
        view_vectors::DOCUMENT_CASES.len(),
        failures.join("\n\n")
    );
}

const MINIMAL: &str = concat!(
    r#"{"calls":{},"definitions":{},"exports":{},"format":"pycg/1","modules":{},"#,
    r#""outside":{},"package":{"name":null,"version":null},"#,
    r#""tool":{"name":"pycg","typeshed":"abc","version":"1.0.0"}}"#
);
const NESTING_PAST_PYTHON: usize = 100_000;
const DIGITS_PAST_PYTHON: usize = 5_000;

#[test]
fn documents_that_python_fails_on_give_their_page() {
    let nested = format!(
        "{}{}",
        "[".repeat(NESTING_PAST_PYTHON),
        "]".repeat(NESTING_PAST_PYTHON)
    );
    let digits = format!("[{}]", "7".repeat(DIGITS_PAST_PYTHON));
    for exports in [nested, digits] {
        let text = MINIMAL.replace(
            r#""exports":{}"#,
            &format!(r#""exports":{{"a":{exports}}}"#),
        );
        let root = Path::new(env!("CARGO_TARGET_TMPDIR")).join("view-past-python");
        if root.exists() {
            std::fs::remove_dir_all(&root).expect("remove an old case directory");
        }
        std::fs::create_dir_all(&root).expect("make a directory");
        std::fs::write(root.join("d.json"), &text).expect("write an input");
        let output = Command::new(env!("CARGO_BIN_EXE_pycg"))
            .args(["view", "d.json"])
            .current_dir(&root)
            .output()
            .expect("run pycg view");
        assert_eq!(output.status.code(), Some(0), "{}", shown(&output.stderr));
        let (head, tail) = TEMPLATE
            .split_once(MARKER)
            .expect("the template has the marker");
        let page = std::fs::read_to_string(root.join("d.html")).expect("read the page");
        assert_eq!(page, [head, text.as_str(), tail].concat());
    }
}
