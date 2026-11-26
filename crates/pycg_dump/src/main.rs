mod stubs_replay;

use std::process::ExitCode;

const USAGE: &str = "usage: pycg_dump stubs <D2.jsonl>";
const EXIT_USAGE: u8 = 2;

fn main() -> ExitCode {
    let arguments: Vec<String> = std::env::args().skip(1).collect();
    match arguments.as_slice() {
        [command, path] if command == "stubs" => stubs_replay::run(path),
        _ => {
            eprintln!("{USAGE}");
            ExitCode::from(EXIT_USAGE)
        }
    }
}
