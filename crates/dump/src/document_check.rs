use std::path::{Path, PathBuf};
use std::process::ExitCode;

use crate::canonical::document;

const EXIT_FAILURE: u8 = 1;
const DOCUMENT: &str = "D6.json";

pub fn run(root: &str) -> ExitCode {
    let documents = match documents(Path::new(root)) {
        Ok(documents) => documents,
        Err(error) => {
            eprintln!("pycg-dump: cannot list {root}: {error}");
            return ExitCode::from(EXIT_FAILURE);
        }
    };
    if documents.is_empty() {
        eprintln!("pycg-dump: no {DOCUMENT} under {root}");
        return ExitCode::from(EXIT_FAILURE);
    }
    let mut different = Vec::new();
    for path in &documents {
        if let Err(problem) = check(path) {
            different.push((path, problem));
        }
    }
    println!(
        "document: {} documents, {} identical, {} different",
        documents.len(),
        documents.len() - different.len(),
        different.len()
    );
    for (path, problem) in &different {
        let shown = path
            .strip_prefix(root)
            .expect("a listed document is under the root");
        println!("  {}: {problem}", shown.display());
    }
    if different.is_empty() {
        ExitCode::SUCCESS
    } else {
        ExitCode::from(EXIT_FAILURE)
    }
}

fn check(path: &Path) -> Result<(), String> {
    let text = std::fs::read_to_string(path).map_err(|error| error.to_string())?;
    let parsed: serde_json::Value =
        serde_json::from_str(&text).map_err(|error| error.to_string())?;
    let written = pycg_document::dumps(&document(&parsed)?);
    match text.bytes().zip(written.bytes()).position(|(a, b)| a != b) {
        Some(offset) => Err(format!("differs at byte {offset}")),
        None if text.len() != written.len() => Err(format!(
            "{} bytes written for {} read",
            written.len(),
            text.len()
        )),
        None => Ok(()),
    }
}

fn documents(root: &Path) -> std::io::Result<Vec<PathBuf>> {
    let mut found = Vec::new();
    let mut pending = vec![root.to_path_buf()];
    while let Some(directory) = pending.pop() {
        for entry in std::fs::read_dir(&directory)? {
            let path = entry?.path();
            if path.is_dir() {
                pending.push(path);
            } else if path.file_name().is_some_and(|name| name == DOCUMENT) {
                found.push(path);
            }
        }
    }
    found.sort();
    Ok(found)
}
