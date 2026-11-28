#![cfg(unix)]

mod vectors;

use std::ffi::{OsStr, OsString};
use std::os::unix::ffi::OsStrExt;
use std::os::unix::process::CommandExt;
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
    Exit {
        status: i32,
        stdout: &'static [u8],
        stderr: &'static [u8],
    },
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
