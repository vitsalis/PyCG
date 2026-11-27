pub mod imports;
pub mod paths;

use std::collections::VecDeque;
use std::path::{Path, PathBuf};

use indexmap::{IndexMap, IndexSet};
use pycg_solver::ObjId;
use pycg_stubs::Stubs;
use pycg_syntax::parse::with_parsed_and_stub;
use pycg_syntax::read::read_file;
use pycg_syntax::scopes::{analyse_scopes, literal_assignment, mentions};
use pycg_syntax::tree::Node;
use ruff_python_ast::{ModModule, Stmt};
use ruff_source_file::LineIndex;
use rustc_hash::{FxHashMap, FxHashSet};

use crate::builder::calls::Analysis;
use crate::builder::{ModuleBuilder, Source};
use crate::program::imports::extension_name;
use crate::program::paths::{abspath, basename, commonpath, dirname, relpath, splitext};

const INITIALIZER: &str = "__init__.py";

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Status {
    Analysed,
    Partial,
    Failed,
}

impl Status {
    pub fn name(&self) -> &'static str {
        match self {
            Status::Analysed => "analysed",
            Status::Partial => "partial",
            Status::Failed => "failed",
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct SourceModule {
    pub name: String,
    pub file: PathBuf,
    pub line_count: usize,
    pub status: Status,
    pub cause: Option<String>,
}

struct Built {
    star_imported_modules: Vec<String>,
    outside_star_imported_modules: Vec<String>,
    names_bound_at_run_time: Vec<String>,
    declared: Option<Vec<String>>,
    too_deep: Option<usize>,
}

pub struct Program<A: Analysis> {
    pub root: PathBuf,
    cwd: PathBuf,
    entry_points: Vec<PathBuf>,
    pub analysis: A,
    pub modules: IndexMap<String, SourceModule>,
    pub extension_modules: IndexMap<String, PathBuf>,
    entry_module_names: FxHashSet<String>,
    entry_only_files_by_name: FxHashMap<String, Vec<PathBuf>>,
    star_imported_modules_by_importer: IndexMap<String, Vec<String>>,
    outside_star_imported_modules_by_importer: IndexMap<String, Vec<String>>,
    exports_by_module: FxHashMap<String, IndexSet<String>>,
    modules_declaring_all: FxHashSet<String>,
    stubs: Stubs,
}

fn own_stub_source(path: &Path) -> Option<String> {
    let stub = path.with_extension("pyi");
    if path.extension().is_none_or(|suffix| suffix != "py") || !stub.is_file() {
        return None;
    }
    read_file(&stub).ok()
}

fn declares_global_or_nonlocal(tree: &ModModule) -> bool {
    let mut pending: Vec<Node<'_>> = tree.body.iter().map(Node::Stmt).collect();
    while let Some(node) = pending.pop() {
        if matches!(node, Node::Stmt(Stmt::Global(_) | Stmt::Nonlocal(_))) {
            return true;
        }
        pending.extend(node.children());
    }
    false
}

fn line_count(source: &str) -> usize {
    if source.is_empty() {
        return 0;
    }
    source.matches('\n').count() + usize::from(!source.ends_with('\n'))
}

fn declared_all_names(body: &[Stmt], source: &str) -> Option<Vec<String>> {
    let mut names = None;
    for statement in body {
        if matches!(statement, Stmt::FunctionDef(_) | Stmt::ClassDef(_)) {
            continue;
        }
        if !mentions(statement, "__all__") {
            continue;
        }
        names = Some(literal_assignment(statement, "__all__", source)?);
    }
    names
}

impl<A: Analysis + Send> Program<A> {
    pub fn new(entry_points: &[PathBuf], package: Option<&Path>, cwd: &Path, analysis: A) -> Self {
        let entry_points: Vec<PathBuf> =
            entry_points.iter().map(|path| abspath(path, cwd)).collect();
        let root = match package {
            Some(package) => abspath(package, cwd),
            None if entry_points.is_empty() => abspath(Path::new("."), cwd),
            None => {
                let directories: Vec<PathBuf> =
                    entry_points.iter().map(|path| dirname(path)).collect();
                commonpath(&directories)
            }
        };
        let mut program = Program {
            root,
            cwd: cwd.to_owned(),
            entry_points,
            analysis,
            modules: IndexMap::new(),
            extension_modules: IndexMap::new(),
            entry_module_names: FxHashSet::default(),
            entry_only_files_by_name: FxHashMap::default(),
            star_imported_modules_by_importer: IndexMap::new(),
            outside_star_imported_modules_by_importer: IndexMap::new(),
            exports_by_module: FxHashMap::default(),
            modules_declaring_all: FxHashSet::default(),
            stubs: Stubs::new(),
        };
        let root = program.root.clone();
        program.analysis.imports().set_package(&root);
        program
    }

    pub fn shadowed(&mut self, name: &str, file: &Path) -> Vec<PathBuf> {
        let mut files = self.analysis.imports().module_files(name);
        files.extend(
            self.entry_only_files_by_name
                .get(name)
                .into_iter()
                .flatten()
                .cloned(),
        );
        files.into_iter().filter(|other| other != file).collect()
    }

    pub fn relative(&self, path: &Path) -> String {
        relpath(path, &self.root, &self.cwd)
            .to_str()
            .expect("a module path is UTF-8")
            .to_owned()
    }

    pub fn build_modules(&mut self) {
        let mut named: IndexMap<String, IndexSet<PathBuf>> = IndexMap::new();
        for path in self.entry_points.clone() {
            if let Some(name) = self.module_name(&path) {
                named.entry(name).or_default().insert(path);
            }
        }
        let mut queue: VecDeque<(String, PathBuf)> = VecDeque::new();
        for (name, paths) in named {
            self.entry_module_names.insert(name.clone());
            let found = self.analysis.imports().module_files(&name);
            let mut others: Vec<PathBuf> = paths
                .into_iter()
                .filter(|path| !found.contains(path))
                .collect();
            others.sort_by_key(|path| relpath(path, &self.root, &self.cwd));
            self.entry_only_files_by_name
                .insert(name.clone(), others.clone());
            let first = found
                .into_iter()
                .chain(others)
                .next()
                .expect("an entry module has a file");
            if extension_name(basename(&first)).is_some() {
                self.analysis
                    .imports()
                    .extension_modules
                    .insert(name, first);
            } else {
                queue.push_back((name, first));
            }
        }
        let mut pending_stars: Vec<(String, String)> = Vec::new();
        while let Some((name, path)) = queue.pop_front() {
            if self.modules.contains_key(&name) {
                continue;
            }
            self.build(&name, &path);
            for holder in self
                .star_imported_modules_by_importer
                .get(&name)
                .into_iter()
                .flatten()
            {
                pending_stars.push((name.clone(), holder.clone()));
            }
            let mut importers = vec![name];
            importers.extend(self.import_listed_submodules(&mut pending_stars));
            for importer in importers {
                let imported: Vec<String> = self
                    .analysis
                    .imports()
                    .imports(&importer)
                    .cloned()
                    .collect();
                for imported in imported {
                    let path = self
                        .analysis
                        .imports()
                        .filepath(&imported)
                        .map(Path::to_owned);
                    if let Some(path) = path
                        && !self.modules.contains_key(&imported)
                    {
                        queue.push_back((imported, path));
                    }
                }
            }
        }
        let mut extensions: Vec<(String, PathBuf)> = self
            .analysis
            .imports()
            .extension_modules
            .iter()
            .map(|(name, path)| (name.clone(), path.clone()))
            .collect();
        extensions.sort_by(|a, b| a.0.cmp(&b.0));
        self.extension_modules = extensions.into_iter().collect();
        self.link_submodules();
        self.link_star_imports();
    }

    fn module_name(&self, path: &Path) -> Option<String> {
        let relative = relpath(path, &self.root, &self.cwd);
        let relative = relative
            .to_str()
            .expect("an entry point's path is UTF-8")
            .to_owned();
        if relative == ".." || relative.starts_with("../") {
            return None;
        }
        if relative.ends_with(".pyi") || path.is_dir() {
            return None;
        }
        let (directory, filename) = match relative.rsplit_once('/') {
            Some((directory, filename)) => (directory, filename),
            None => ("", relative.as_str()),
        };
        let stem = extension_name(std::ffi::OsStr::new(filename)).unwrap_or(splitext(filename).0);
        let joined = if directory.is_empty() {
            stem.to_owned()
        } else {
            format!("{directory}/{stem}")
        };
        let name = joined.replace('/', ".");
        if name == "__init__" {
            return None;
        }
        Some(name.strip_suffix(".__init__").unwrap_or(&name).to_owned())
    }

    fn build(&mut self, name: &str, path: &Path) {
        self.analysis.begin_module(name);
        self.build_module(name, path);
        let analysed = self.modules[name].status != Status::Failed;
        self.analysis.end_module(name, analysed);
    }

    fn build_module(&mut self, name: &str, path: &Path) {
        let imports = self.analysis.imports();
        if !imports.has_node(name) {
            imports.create_node(name);
            imports.set_filepath(name, path);
        }
        imports.set_current_mod(name, path);
        let source = match read_file(path) {
            Ok(source) => source,
            Err(failure) => {
                self.failed(name, path, failure.cause());
                return;
            }
        };
        let is_package = basename(path) == INITIALIZER;
        let is_entry = self.entry_module_names.contains(name);
        let stub = own_stub_source(path);
        let analysis = &mut self.analysis;
        let built = with_parsed_and_stub(&source, stub.as_deref(), |parsed, stub_parsed| {
            let parsed = parsed.map_err(|failure| failure.cause())?;
            let lines = LineIndex::from_source_text(&source);
            let tokens = parsed.tokens();
            let body = &parsed.syntax().body;
            let scopes = analyse_scopes(parsed.syntax(), name, tokens, &lines, &source);
            let stub_lines = stub.as_deref().map(LineIndex::from_source_text);
            let own_stub = match (stub_parsed, stub.as_deref(), stub_lines.as_ref()) {
                (Some(Ok(stub_parsed)), Some(text), Some(stub_lines))
                    if !declares_global_or_nonlocal(stub_parsed.syntax()) =>
                {
                    Some((
                        stub_parsed.syntax(),
                        Source {
                            text,
                            tokens: stub_parsed.tokens(),
                            lines: stub_lines,
                        },
                    ))
                }
                _ => None,
            };
            let module = analysis.module(name);
            let mut builder = ModuleBuilder::new(
                analysis,
                name,
                module,
                Source {
                    text: &source,
                    tokens,
                    lines: &lines,
                },
                &scopes,
                is_package,
                is_entry,
            );
            if let Some((tree, source)) = own_stub {
                builder = builder.with_own_stub(tree, source);
            }
            let too_deep = builder.build(body);
            Ok(Built {
                star_imported_modules: builder.star_imported_modules.clone(),
                outside_star_imported_modules: builder.outside_star_imported_modules.clone(),
                names_bound_at_run_time: builder.names_bound_at_run_time.clone(),
                declared: declared_all_names(body, &source),
                too_deep,
            })
        });
        let built = match built {
            Ok(built) => built,
            Err(cause) => {
                self.failed(name, path, cause);
                return;
            }
        };
        let (status, cause) = match built.too_deep {
            Some(line) => (Status::Partial, Some(format!("DeepNesting (line {line})"))),
            None => (Status::Analysed, None),
        };
        self.modules.insert(
            name.to_owned(),
            SourceModule {
                name: name.to_owned(),
                file: path.to_owned(),
                line_count: line_count(&source),
                status,
                cause,
            },
        );
        self.star_imported_modules_by_importer
            .insert(name.to_owned(), built.star_imported_modules);
        self.outside_star_imported_modules_by_importer
            .insert(name.to_owned(), built.outside_star_imported_modules);
        match built.declared {
            None => {
                let public = built
                    .names_bound_at_run_time
                    .into_iter()
                    .filter(|bound| !bound.starts_with('_'));
                self.exports_by_module
                    .insert(name.to_owned(), public.collect());
            }
            Some(declared) => {
                self.exports_by_module
                    .insert(name.to_owned(), declared.into_iter().collect());
                self.modules_declaring_all.insert(name.to_owned());
            }
        }
    }

    fn failed(&mut self, name: &str, path: &Path, cause: String) {
        self.modules.insert(
            name.to_owned(),
            SourceModule {
                name: name.to_owned(),
                file: path.to_owned(),
                line_count: 0,
                status: Status::Failed,
                cause: Some(cause),
            },
        );
    }

    fn import_listed_submodules(
        &mut self,
        pending_stars: &mut Vec<(String, String)>,
    ) -> Vec<String> {
        let mut importers = Vec::new();
        for star in pending_stars.clone() {
            let (importer, holder) = &star;
            if !self.modules.contains_key(holder) {
                continue;
            }
            let index = pending_stars
                .iter()
                .position(|pending| *pending == star)
                .expect("a pending star import is pending");
            pending_stars.remove(index);
            if !self.modules_declaring_all.contains(holder) {
                continue;
            }
            let file = self.modules[importer].file.clone();
            let names: Vec<String> = self.exports_by_module[holder].iter().cloned().collect();
            self.analysis.imports().set_current_mod(importer, &file);
            for name in names {
                self.analysis
                    .handle_import(&format!("{holder}.{name}"), 0, true);
            }
            importers.push(importer.clone());
        }
        importers
    }

    fn link_submodules(&mut self) {
        let mut names: FxHashSet<String> = self
            .analysis
            .imports()
            .import_graph()
            .keys()
            .cloned()
            .collect();
        for name in names.clone() {
            names.extend(self.analysis.imports().packages(&name));
        }
        let mut names: Vec<String> = names.into_iter().collect();
        names.sort();
        let mut submodules: Vec<(String, ObjId)> = Vec::new();
        for name in names {
            let module = self.analysis.module(&name);
            submodules.push((name, module));
        }
        let extensions: Vec<String> = self.extension_modules.keys().cloned().collect();
        for name in extensions {
            let module = self.analysis.external(&name, 0, false);
            submodules.push((name, module));
        }
        submodules.sort_by(|a, b| a.0.cmp(&b.0));
        for (name, module) in submodules {
            let Some((package, attribute)) = name.rsplit_once('.') else {
                continue;
            };
            let holder = self.analysis.module(package);
            add_once(self.analysis.module_defines(holder), attribute);
            let field = self.analysis.field(holder, attribute);
            self.analysis.add_object(field, module);
            if !attribute.starts_with('_') && !self.modules_declaring_all.contains(package) {
                self.exports_by_module
                    .entry(package.to_owned())
                    .or_default()
                    .insert(attribute.to_owned());
            }
        }
    }

    fn link_star_imports(&mut self) {
        self.link_outside_star_imports();
        let mut changed = true;
        while changed {
            changed = false;
            for (importer, holders) in &self.star_imported_modules_by_importer {
                if self.modules_declaring_all.contains(importer) {
                    continue;
                }
                for holder in holders {
                    let names: Vec<String> = self
                        .exports_by_module
                        .get(holder)
                        .into_iter()
                        .flatten()
                        .cloned()
                        .collect();
                    let exports = self
                        .exports_by_module
                        .get_mut(importer)
                        .expect("a built importer has exports");
                    for name in names {
                        changed |= exports.insert(name);
                    }
                }
            }
        }
        let stars: Vec<(String, Vec<String>)> = self
            .star_imported_modules_by_importer
            .iter()
            .map(|(importer, holders)| (importer.clone(), holders.clone()))
            .collect();
        for (importer, holders) in stars {
            let importer_module = self.analysis.module(&importer);
            for holder in holders {
                let holder_module = self.analysis.module(&holder);
                let names: Vec<String> = self
                    .exports_by_module
                    .get(&holder)
                    .into_iter()
                    .flatten()
                    .cloned()
                    .collect();
                for name in names {
                    add_once(self.analysis.module_defines(importer_module), &name);
                    let source = self.analysis.field(holder_module, &name);
                    let target = self.analysis.field(importer_module, &name);
                    self.analysis.add_edge(source, target);
                }
            }
        }
    }

    fn link_outside_star_imports(&mut self) {
        let stars: Vec<(String, Vec<String>)> = self
            .outside_star_imported_modules_by_importer
            .iter()
            .map(|(importer, holders)| (importer.clone(), holders.clone()))
            .collect();
        for (importer, holders) in stars {
            let importer_module = self.analysis.module(&importer);
            for holder in holders {
                for name in self.outside_exports(&holder) {
                    add_once(self.analysis.module_defines(importer_module), &name);
                    let source = self.analysis.imported_value(&format!("{holder}.{name}"));
                    let target = self.analysis.field(importer_module, &name);
                    self.analysis.add_edge(source, target);
                    if !self.modules_declaring_all.contains(&importer) {
                        self.exports_by_module
                            .get_mut(&importer)
                            .expect("a built importer has exports")
                            .insert(name);
                    }
                }
            }
        }
    }

    fn outside_exports(&mut self, holder: &str) -> Vec<String> {
        let Some(module) = self.stubs.module(holder) else {
            return Vec::new();
        };
        let data = self.stubs.module_data(module);
        match &data.all {
            Some(all) => all.iter().map(|name| name.to_string()).collect(),
            None => data
                .names
                .keys()
                .filter(|name| !name.starts_with('_'))
                .map(|name| name.to_string())
                .collect(),
        }
    }
}

fn add_once(defines: &mut Vec<Box<str>>, name: &str) {
    if !defines.iter().any(|defined| **defined == *name) {
        defines.push(name.into());
    }
}
