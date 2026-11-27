use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

use pycg_analysis::program::imports::ImportManager;
use serde_json::{Value, json};

const VECTORS: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/tests/vectors/imports.json");
const ROOT_IN_PATHS: &str = "{root}";

fn text(value: &Value) -> &str {
    value
        .as_str()
        .unwrap_or_else(|| panic!("{value} is not a string"))
}

fn path_of(value: &Value, root: &Path) -> PathBuf {
    let spelled = text(value);
    let relative = spelled
        .strip_prefix(ROOT_IN_PATHS)
        .unwrap_or_else(|| panic!("{spelled} is not under {ROOT_IN_PATHS}"));
    PathBuf::from(format!("{}{relative}", root.display()))
}

fn spelled(path: &Path, root: &Path) -> String {
    let relative = path
        .strip_prefix(root)
        .unwrap_or_else(|_| panic!("{} is not under {}", path.display(), root.display()));
    if relative.as_os_str().is_empty() {
        return ROOT_IN_PATHS.to_owned();
    }
    format!("{ROOT_IN_PATHS}/{}", relative.display())
}

fn layout(files: &Value, root: &Path) {
    std::fs::create_dir_all(root).expect("the directory of a session");
    for (name, content) in files.as_object().expect("files are an object") {
        let path = root.join(name);
        match content {
            Value::Null => std::fs::create_dir_all(&path).expect("an empty directory"),
            content => {
                std::fs::create_dir_all(path.parent().expect("a file has a directory"))
                    .expect("the directory of a file");
                std::fs::write(&path, text(content)).expect("a file of a session");
            }
        }
    }
}

fn replay(manager: &mut ImportManager, operation: &Value, root: &Path) -> Value {
    let args = operation["args"].as_array().expect("args are a list");
    let name = || text(&args[0]);
    match text(&operation["call"]) {
        "set_pkg" => {
            manager.set_package(&path_of(&args[0], root));
            Value::Null
        }
        "create_node" => {
            manager.create_node(name());
            Value::Null
        }
        "set_filepath" => {
            manager.set_filepath(name(), &path_of(&args[1], root));
            Value::Null
        }
        "set_current_mod" => {
            manager.set_current_mod(name(), &path_of(&args[1], root));
            Value::Null
        }
        "handle_import" => {
            let level = u32::try_from(args[1].as_u64().expect("a level")).expect("a small level");
            let record = args
                .get(2)
                .is_none_or(|record| record.as_bool().expect("a flag"));
            json!(manager.handle_import(name(), level, record))
        }
        "get_imports" => {
            let mut imports: Vec<&String> = manager.imports(name()).collect();
            imports.sort();
            json!(imports)
        }
        "get_filepath" => json!(
            manager
                .filepath(name())
                .map_or_else(String::new, |path| spelled(path, root))
        ),
        "packages" => json!(manager.packages(name())),
        "get_node" => json!(manager.has_node(name())),
        "get_import_graph" => {
            let graph: BTreeMap<&String, Value> = manager
                .import_graph()
                .iter()
                .map(|(module, node)| {
                    let mut imports: Vec<&String> = node.imports.iter().collect();
                    imports.sort();
                    let filename = node
                        .filename
                        .as_deref()
                        .map_or_else(String::new, |path| spelled(path, root));
                    (module, json!({"filename": filename, "imports": imports}))
                })
                .collect();
            json!(graph)
        }
        call => panic!("the vectors call {call}, which this test does not replay"),
    }
}

#[test]
fn the_import_manager_answers_what_the_oracle_answered_in_each_layout() {
    let text = std::fs::read_to_string(VECTORS).expect("the import vectors");
    let sessions: Vec<Value> = serde_json::from_str(&text).expect("the import vectors are JSON");
    assert!(!sessions.is_empty());
    let scratch = std::env::temp_dir().join(format!("pycg-imports-{}", std::process::id()));
    let mut differing = Vec::new();
    for (index, session) in sessions.iter().enumerate() {
        let root = scratch.join(index.to_string());
        layout(&session["files"], &root);
        let mut manager = ImportManager::default();
        for operation in session["operations"]
            .as_array()
            .expect("operations are a list")
        {
            let found = replay(&mut manager, operation, &root);
            if found != operation["result"] {
                differing.push(format!(
                    "{}: {} {} gave {found}, not {}",
                    session["test"], operation["call"], operation["args"], operation["result"]
                ));
            }
        }
    }
    std::fs::remove_dir_all(&scratch).expect("the scratch directory is removed");
    assert!(differing.is_empty(), "{}", differing.join("\n"));
}
