mod canonical;
mod d1;
mod d4;
mod engine_replay;
mod solver_replay;
mod stubs_replay;

use std::process::ExitCode;

const USAGE: &str = "usage: pycg_dump stubs <D2.jsonl> | solver <D3.jsonl> | d1 MODULES OUT \
    | d4 MODULES ENTRIES ORACLE_D4 OUT | engine <D4.jsonl> OUT | engine-build MODULES ENTRIES OUT";
const EXIT_USAGE: u8 = 2;

fn main() -> ExitCode {
    let arguments: Vec<String> = std::env::args().skip(1).collect();
    match arguments.as_slice() {
        [command, path] if command == "stubs" => stubs_replay::run(path),
        [command, path] if command == "solver" => solver_replay::run(path),
        [command, path, out] if command == "engine" => engine_replay::run(path, out),
        _ => d1::run(&arguments)
            .or_else(|| d4::run(&arguments))
            .or_else(|| engine_replay::build(&arguments))
            .unwrap_or_else(|| {
                eprintln!("{USAGE}");
                ExitCode::from(EXIT_USAGE)
            }),
    }
}
