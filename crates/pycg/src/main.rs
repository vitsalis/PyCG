use std::ffi::{OsStr, OsString};
use std::io::Write;
use std::panic::{self, PanicHookInfo};
use std::process::ExitCode;

use pycg::{Options, Outcome};
use pycg_analysis::engine::NotPorted;
use pycg_document::{ProgramPart, Text};

const STATUS_FAILURE: u8 = 1;
const STATUS_USAGE: u8 = 2;
const STATUS_NOT_PORTED: u8 = 3;

fn report(program: &[u8], message: &[u8], status: u8) -> ExitCode {
    let line = [program, b": ", message, b"\n"].concat();
    let _ = std::io::stderr().write_all(&pycg::for_stderr(&line));
    ExitCode::from(status)
}

fn internal_error(program: &[u8], info: &PanicHookInfo<'_>) {
    if info.payload().downcast_ref::<NotPorted>().is_some() {
        return;
    }
    let payload = info.payload();
    let message = payload
        .downcast_ref::<&str>()
        .map(|message| (*message).to_owned())
        .or_else(|| payload.downcast_ref::<String>().cloned())
        .unwrap_or_default();
    let location = info.location().map_or_else(String::new, |location| {
        format!(
            " at {}:{}:{}",
            location.file(),
            location.line(),
            location.column()
        )
    });
    let message = format!("internal error{location}: {}", message.replace('\n', "\\n"));
    let _ = report(program, message.as_bytes(), STATUS_FAILURE);
}

fn text(argument: Option<&OsString>) -> Option<Text> {
    argument.map(|argument| Text::from_code_points(&pycg::code_points(argument.as_encoded_bytes())))
}

fn run(program: &[u8], options: Options) -> ExitCode {
    let cwd = match std::env::current_dir() {
        Ok(cwd) => cwd,
        Err(error) => {
            let message = format!("cannot read the working directory: {error}");
            return report(program, message.as_bytes(), STATUS_FAILURE);
        }
    };
    let mut warn = |warning: &OsStr| {
        let line = [warning.as_encoded_bytes(), b"\n"].concat();
        let _ = std::io::stderr().write_all(&pycg::for_stderr(&line));
    };
    let mut analysed = match pycg_analysis::analyse(&options.request, &cwd, &mut warn) {
        Ok(analysed) => analysed,
        Err(error @ pycg_analysis::Error::NotPorted(_)) => {
            return report(program, error.to_string().as_bytes(), STATUS_NOT_PORTED);
        }
        Err(error @ pycg_analysis::Error::Paths(_)) => {
            return report(program, error.to_string().as_bytes(), STATUS_FAILURE);
        }
    };
    let part = ProgramPart::from_program(&mut analysed.program);
    let document = pycg_document::build(
        &part,
        &analysed.results,
        text(options.package_name.as_ref()).as_ref(),
        text(options.package_version.as_ref()).as_ref(),
    );
    let mut written = pycg_document::dumps(&document);
    written.push('\n');
    let outcome = match &options.output {
        Some(path) => std::fs::write(path, written),
        None => std::io::stdout().write_all(written.as_bytes()),
    };
    match (outcome, &options.output) {
        (Ok(()), _) => ExitCode::SUCCESS,
        (Err(error), Some(path)) => {
            let message = [
                b"cannot write ",
                path.as_encoded_bytes(),
                format!(": {error}").as_bytes(),
            ]
            .concat();
            report(program, &message, STATUS_FAILURE)
        }
        (Err(error), None) => {
            let message = format!("cannot write the document: {error}");
            report(program, message.as_bytes(), STATUS_FAILURE)
        }
    }
}

fn main() -> ExitCode {
    let mut arguments = std::env::args_os();
    let program = pycg::program_name(&arguments.next().unwrap_or_default());
    let hooked = program.clone();
    panic::set_hook(Box::new(move |info| internal_error(&hooked, info)));
    let arguments: Vec<OsString> = arguments.collect();
    let columns = std::env::var_os("COLUMNS");
    let width = pycg::width(columns.as_deref(), pycg::stdout_columns());
    match pycg::parse(&program, &arguments, width) {
        Outcome::Run(options) => run(&program, options),
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
