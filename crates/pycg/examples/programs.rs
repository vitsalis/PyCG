#[path = "../tests/fuzz/generator.rs"]
mod generator;

use std::path::PathBuf;
use std::process::ExitCode;

const USAGE: &str = "usage: programs FIRST COUNT OUT";

fn main() -> ExitCode {
    let arguments: Vec<String> = std::env::args().skip(1).collect();
    let [first, count, out] = arguments.as_slice() else {
        eprintln!("{USAGE}");
        return ExitCode::from(2);
    };
    let (Ok(first), Ok(count)) = (first.parse::<u64>(), count.parse::<u64>()) else {
        eprintln!("{USAGE}");
        return ExitCode::from(2);
    };
    let out = PathBuf::from(out);
    for seed in first..first + count {
        let root = out.join(seed.to_string());
        for (path, source) in generator::program(seed) {
            let file = root.join(path);
            std::fs::create_dir_all(file.parent().expect("a directory"))
                .expect("a directory is made");
            std::fs::write(&file, source).expect("a module is written");
        }
    }
    ExitCode::SUCCESS
}
