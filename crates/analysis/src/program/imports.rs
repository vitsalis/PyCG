use std::collections::BTreeSet;
use std::ffi::{OsStr, OsString};
use std::path::{Path, PathBuf};
use std::sync::Arc;

use indexmap::IndexMap;
use pycg_syntax::names::is_identifier;
use rustc_hash::{FxHashMap, FxHashSet};

use crate::program::paths::{basename, normpath};

const INITIALIZER: &str = "__init__.py";

const BUILTIN_OR_FROZEN_MODULES: [&str; 63] = [
    "__hello__",
    "__hello_alias__",
    "__hello_only__",
    "__phello__",
    "__phello__.__init__",
    "__phello__.ham",
    "__phello__.ham.__init__",
    "__phello__.ham.eggs",
    "__phello__.spam",
    "__phello_alias__",
    "__phello_alias__.spam",
    "_abc",
    "_ast",
    "_asyncio",
    "_codecs",
    "_collections",
    "_collections_abc",
    "_contextvars",
    "_datetime",
    "_frozen_importlib",
    "_frozen_importlib_external",
    "_functools",
    "_imp",
    "_io",
    "_locale",
    "_opcode",
    "_operator",
    "_signal",
    "_sitebuiltins",
    "_sre",
    "_stat",
    "_string",
    "_symtable",
    "_thread",
    "_tokenize",
    "_tracemalloc",
    "_typing",
    "_warnings",
    "_weakref",
    "abc",
    "atexit",
    "builtins",
    "codecs",
    "errno",
    "faulthandler",
    "gc",
    "genericpath",
    "importlib.machinery",
    "importlib.util",
    "io",
    "itertools",
    "marshal",
    "ntpath",
    "os",
    "posix",
    "posixpath",
    "pwd",
    "runpy",
    "site",
    "stat",
    "sys",
    "time",
    "zipimport",
];

pub fn extension_name(filename: &OsStr) -> Option<&str> {
    let filename = filename.to_str()?;
    let (stem, suffix) = filename.rsplit_once('.')?;
    let (name, tag) = stem.split_once('.').unwrap_or((stem, ""));
    (matches!(suffix, "so" | "pyd") && !name.is_empty() && !tag.contains('.')).then_some(name)
}

#[derive(Debug, Default)]
pub struct ImportNode {
    pub filename: Option<PathBuf>,
    pub imports: BTreeSet<String>,
}

#[derive(Debug, Default)]
pub struct ImportManager {
    import_graph: IndexMap<String, ImportNode>,
    pub extension_modules: IndexMap<String, PathBuf>,
    current_module: String,
    input_file: PathBuf,
    mod_dir: PathBuf,
    directory_entries_by_path: FxHashMap<PathBuf, Arc<FxHashSet<OsString>>>,
}

type Found = Vec<(String, Option<PathBuf>)>;

fn absolute(path: &Path) -> PathBuf {
    assert!(
        path.is_absolute(),
        "the import manager takes absolute paths"
    );
    normpath(path)
}

impl ImportManager {
    pub fn set_package(&mut self, package: &Path) {
        self.mod_dir = absolute(package);
    }

    pub fn has_node(&self, name: &str) -> bool {
        self.import_graph.contains_key(name)
    }

    pub fn create_node(&mut self, name: &str) {
        assert!(!name.is_empty(), "a node has a name");
        assert!(!self.has_node(name), "a node is created once");
        self.import_graph
            .insert(name.to_owned(), ImportNode::default());
    }

    fn create_edge(&mut self, destination: &str) {
        assert!(!destination.is_empty(), "an edge has a destination");
        self.import_graph
            .get_mut(&self.current_module)
            .expect("an edge starts at an existing node")
            .imports
            .insert(destination.to_owned());
    }

    pub fn set_current_mod(&mut self, name: &str, file: &Path) {
        self.current_module = name.to_owned();
        self.input_file = absolute(file);
    }

    pub fn filepath(&self, name: &str) -> Option<&Path> {
        self.import_graph
            .get(name)
            .expect("a module of the import graph")
            .filename
            .as_deref()
    }

    pub fn set_filepath(&mut self, name: &str, file: &Path) {
        assert!(!file.as_os_str().is_empty(), "a module file has a path");
        let file = absolute(file);
        self.import_graph
            .get_mut(name)
            .expect("the node exists")
            .filename = Some(file);
    }

    pub fn imports(&self, name: &str) -> impl Iterator<Item = &String> {
        self.import_graph
            .get(name)
            .into_iter()
            .flat_map(|node| node.imports.iter())
    }

    pub fn import_graph(&self) -> &IndexMap<String, ImportNode> {
        &self.import_graph
    }

    pub fn handle_import(&mut self, name: &str, level: u32, record: bool) -> Option<String> {
        let mut parts = self.base_package(level)?;
        parts.extend(name.split('.').map(str::to_owned));
        let (modules, reached_frozen) = self.find_modules(&parts, level == 0, true);
        if record {
            for (module, filename) in &modules {
                if !self.has_node(module) {
                    self.create_node(module);
                    if let Some(filename) = filename {
                        self.set_filepath(module, filename);
                    }
                }
                if *module != self.current_module {
                    self.create_edge(module);
                }
            }
        }
        if reached_frozen {
            return None;
        }
        match modules.last() {
            Some((module, _)) if modules.len() + 1 >= parts.len() => Some(module.clone()),
            _ => None,
        }
    }

    pub fn module_files(&mut self, name: &str) -> Vec<PathBuf> {
        assert!(
            self.mod_dir.is_absolute(),
            "the package root is set before a search"
        );
        let (packages, last) = name.rsplit_once('.').unwrap_or(("", name));
        let mut directory = self.mod_dir.clone();
        for package in packages.split('.').filter(|part| !part.is_empty()) {
            directory.push(package);
        }
        self.candidates(&directory, last)
    }

    pub fn locate(&mut self, name: &str) -> Option<(String, Option<String>)> {
        let parts: Vec<String> = name.split('.').map(str::to_owned).collect();
        let (modules, reached_frozen) = self.find_modules(&parts, true, false);
        if reached_frozen {
            return None;
        }
        let (module, _) = modules.last()?;
        if modules.len() == parts.len() {
            return Some((module.clone(), None));
        }
        if modules.len() + 1 == parts.len() {
            return Some((module.clone(), parts.last().cloned()));
        }
        None
    }

    pub fn packages(&mut self, name: &str) -> Vec<String> {
        let mut parts: Vec<String> = name.split('.').map(str::to_owned).collect();
        parts.pop();
        let (found, _) = self.find_modules(&parts, true, false);
        let mut packages = Vec::new();
        for (package, filename) in found {
            let mut initializer = self.mod_dir.clone();
            for part in package.split('.') {
                initializer.push(part);
            }
            initializer.push(INITIALIZER);
            if filename
                .as_ref()
                .is_some_and(|filename| *filename != initializer)
            {
                break;
            }
            packages.push(package);
        }
        packages
    }

    fn base_package(&self, level: u32) -> Option<Vec<String>> {
        if level == 0 {
            return Some(Vec::new());
        }
        let mut package: Vec<String> = self.current_module.split('.').map(str::to_owned).collect();
        if basename(&self.input_file) != INITIALIZER {
            package.pop();
        }
        let level = usize::try_from(level).expect("a level fits usize");
        if level > package.len() {
            return None;
        }
        package.truncate(package.len() - level + 1);
        Some(package)
    }

    fn find_modules(&mut self, parts: &[String], absolute: bool, record: bool) -> (Found, bool) {
        assert!(
            self.mod_dir.is_absolute(),
            "the package root is set before a search"
        );
        let mut found = Vec::new();
        let mut directory = self.mod_dir.clone();
        for (index, part) in parts.iter().enumerate() {
            if !is_identifier(part) {
                break;
            }
            let name = parts[..=index].join(".");
            if absolute && BUILTIN_OR_FROZEN_MODULES.contains(&name.as_str()) {
                return (found, true);
            }
            let path = directory.join(part);
            let files = self.candidates(&directory, part);
            match files.first() {
                Some(first) if basename(first) == INITIALIZER => {
                    found.push((name, Some(first.clone())));
                }
                Some(first) if first.as_os_str().as_encoded_bytes().ends_with(b".py") => {
                    found.push((name, Some(first.clone())));
                    break;
                }
                Some(first) => {
                    if record {
                        self.extension_modules.insert(name, first.clone());
                    }
                    break;
                }
                None => {
                    if self.list_dir(&directory).contains(OsStr::new(part)) && path.is_dir() {
                        found.push((name, None));
                    } else {
                        break;
                    }
                }
            }
            directory = path;
        }
        (found, false)
    }

    fn candidates(&mut self, directory: &Path, part: &str) -> Vec<PathBuf> {
        let entries = self.list_dir(directory);
        let path = directory.join(part);
        let mut found = Vec::new();
        let initializer = path.join(INITIALIZER);
        if entries.contains(OsStr::new(part))
            && self.list_dir(&path).contains(OsStr::new(INITIALIZER))
            && initializer.is_file()
        {
            found.push(initializer);
        }
        let module = directory.join(format!("{part}.py"));
        if entries.contains(OsStr::new(&format!("{part}.py"))) && module.is_file() {
            found.push(module);
        }
        let prefix = format!("{part}.");
        let mut extensions: Vec<&OsString> = entries
            .iter()
            .filter(|entry| entry.as_encoded_bytes().starts_with(prefix.as_bytes()))
            .collect();
        extensions.sort();
        for entry in extensions {
            if extension_name(entry) == Some(part) {
                let file = directory.join(entry);
                if file.is_file() {
                    found.push(file);
                }
            }
        }
        found
    }

    fn list_dir(&mut self, path: &Path) -> Arc<FxHashSet<OsString>> {
        if let Some(entries) = self.directory_entries_by_path.get(path) {
            return Arc::clone(entries);
        }
        let entries: FxHashSet<OsString> = std::fs::read_dir(path)
            .and_then(|entries| {
                entries
                    .map(|entry| entry.map(|entry| entry.file_name()))
                    .collect()
            })
            .unwrap_or_default();
        let entries = Arc::new(entries);
        self.directory_entries_by_path
            .insert(path.to_owned(), Arc::clone(&entries));
        entries
    }
}
