mod d1;
mod stubs_replay;

use std::process::ExitCode;

const USAGE: &str = "usage: pycg_dump stubs <D2.jsonl> | d1-positions FILE | d1-scopes FILE MODULE";
const EXIT_USAGE: u8 = 2;

fn main() -> ExitCode {
    let arguments: Vec<String> = std::env::args().skip(1).collect();
    match arguments.as_slice() {
        [command, path] if command == "stubs" => stubs_replay::run(path),
        _ => d1::run(&arguments).unwrap_or_else(|| {
            eprintln!("{USAGE}");
            ExitCode::from(EXIT_USAGE)
        }),
    }
}
