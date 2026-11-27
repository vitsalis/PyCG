use std::ffi::OsString;
use std::io::Write;
use std::process::ExitCode;

use pycg::{Options, Outcome};

const STATUS_FAILURE: u8 = 1;
const STATUS_USAGE: u8 = 2;

fn report(program: &[u8], message: &[u8]) -> ExitCode {
    let line = [program, b": ", message, b"\n"].concat();
    let _ = std::io::stderr().write_all(&pycg::for_stderr(&line));
    ExitCode::from(STATUS_FAILURE)
}

fn run(program: &[u8], options: Options) -> ExitCode {
    match pycg_analysis::analyse(&options.request) {
        Err(error) => report(program, error.to_string().as_bytes()),
        Ok(analysis) => match analysis {},
    }
}

fn main() -> ExitCode {
    let mut arguments = std::env::args_os();
    let program = pycg::program_name(&arguments.next().unwrap_or_default());
    let arguments: Vec<OsString> = arguments.collect();
    let columns = std::env::var_os("COLUMNS");
    let width = pycg::width(columns.as_deref(), pycg::stdout_columns());
    match pycg::parse(&program, &arguments, width) {
        Outcome::Run(options) => run(&program, options),
        Outcome::View(options) => match pycg::view(&options) {
            Ok(()) => ExitCode::SUCCESS,
            Err(error) => report(&pycg::view_program(&program), &error.message()),
        },
        Outcome::Help(text) => {
            let _ = std::io::stdout().write_all(&text);
            ExitCode::SUCCESS
        }
        Outcome::Usage(text) => {
            let _ = std::io::stderr().write_all(&pycg::for_stderr(&text));
            ExitCode::from(STATUS_USAGE)
        }
    }
}
