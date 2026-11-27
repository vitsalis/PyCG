use std::io::Write;
use std::path::Path;
use std::process::ExitCode;

use pycg_syntax::parse::parse_source;
use pycg_syntax::read::read_file;
use pycg_syntax::tree::{position, walk};
use ruff_source_file::LineIndex;

pub fn run(arguments: &[String]) -> Option<ExitCode> {
    match arguments {
        [command, file] if command == "d1-positions" => {
            let stdout = std::io::stdout();
            let mut out = stdout.lock();
            positions(Path::new(file), &mut out).expect("standard output takes the dump");
            Some(ExitCode::SUCCESS)
        }
        _ => None,
    }
}

fn positions(path: &Path, out: &mut impl Write) -> std::io::Result<()> {
    let source = match read_file(path) {
        Ok(source) => source,
        Err(failure) => return writeln!(out, "{{\"failed\":\"{}\"}}", failure.cause()),
    };
    let parsed = match parse_source(&source) {
        Ok(parsed) => parsed,
        Err(failure) => return writeln!(out, "{{\"failed\":\"{}\"}}", failure.cause()),
    };
    let lines = LineIndex::from_source_text(&source);
    for node in walk(parsed.syntax()) {
        let Some(range) = node.range(parsed.tokens()) else {
            continue;
        };
        let at = position(range, &lines);
        writeln!(
            out,
            "[\"{}\",{},{},{},{}]",
            node.kind(),
            at.lineno,
            at.col_offset,
            at.end_lineno,
            at.end_col_offset
        )?;
    }
    Ok(())
}
