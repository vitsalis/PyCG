use std::path::{Path, PathBuf};

use indexmap::IndexSet;
use pycg_syntax::constants::{Constant, literal};
use pycg_syntax::names::{identifier, is_identifier};
use pycg_syntax::parse::with_parsed;
use pycg_syntax::read::read_file;
use pycg_syntax::scopes::analyse_scopes;
use pycg_syntax::tree::Node;
use ruff_python_ast::{Expr, ExprContext, ModModule, Stmt};
use ruff_source_file::LineIndex;
use rustc_hash::FxHashSet;

const SOURCE_SUFFIX: &str = ".py";

pub fn names_stored_by_name(root: &Path, entry_points: &[PathBuf]) -> FxHashSet<String> {
    let mut names = FxHashSet::default();
    for file in module_files(root, entry_points) {
        let Ok(source) = read_file(&file) else {
            continue;
        };
        let found = with_parsed(&source, |parsed| match parsed {
            Ok(parsed) => {
                let lines = LineIndex::from_source_text(&source);
                let scopes = analyse_scopes(parsed.syntax(), "", parsed.tokens(), &lines, &source);
                let rebound = |name: &str| {
                    scopes.scopes().iter().any(|&id| {
                        let scope = scopes.scope(id);
                        scope.bound_again.contains(name) || scope.shared.contains(name)
                    })
                };
                stored_names(parsed.syntax(), &source, &rebound)
            }
            Err(_) => Vec::new(),
        });
        names.extend(found);
    }
    names
}

fn module_files(root: &Path, entry_points: &[PathBuf]) -> IndexSet<PathBuf> {
    let mut files: IndexSet<PathBuf> = entry_points
        .iter()
        .filter(|path| path.is_file())
        .cloned()
        .collect();
    let mut visited: FxHashSet<PathBuf> = FxHashSet::default();
    let mut pending = vec![root.to_owned()];
    while let Some(directory) = pending.pop() {
        let Ok(canonical) = std::fs::canonicalize(&directory) else {
            continue;
        };
        if !visited.insert(canonical) {
            continue;
        }
        let Ok(entries) = std::fs::read_dir(&directory) else {
            continue;
        };
        for entry in entries.flatten() {
            let path = entry.path();
            let file_name = entry.file_name();
            let Some(name) = file_name.to_str() else {
                continue;
            };
            match name.strip_suffix(SOURCE_SUFFIX) {
                Some(stem) if is_identifier(stem) && path.is_file() => {
                    files.insert(path);
                }
                Some(_) => {}
                None if is_identifier(name) && path.is_dir() => pending.push(path),
                None => {}
            }
        }
    }
    files
}

fn stored_names(tree: &ModModule, source: &str, rebound: &dyn Fn(&str) -> bool) -> Vec<String> {
    let mut names = Vec::new();
    let mut pending: Vec<Node<'_>> = tree.body.iter().map(Node::Stmt).collect();
    while let Some(node) = pending.pop() {
        match &node {
            Node::Expr(Expr::Attribute(attribute))
                if matches!(attribute.ctx, ExprContext::Store | ExprContext::Del) =>
            {
                names.push(identifier(attribute.attr.as_str()).into_owned());
            }
            Node::Expr(expression @ Expr::StringLiteral(_)) => {
                if let Some(Constant::Str(text)) = literal(expression, source)
                    && let Some(name) = text
                        .code_points()
                        .iter()
                        .map(|&point| char::from_u32(point))
                        .collect::<Option<String>>()
                {
                    names.push(name);
                }
            }
            Node::Keyword(keyword) => {
                if let Some(argument) = &keyword.arg {
                    names.push(identifier(argument.as_str()).into_owned());
                }
            }
            Node::Stmt(Stmt::ImportFrom(import)) => {
                for alias in &import.names {
                    let member = identifier(alias.name.as_str()).into_owned();
                    let bound = alias.asname.as_ref().unwrap_or(&alias.name);
                    if rebound(&identifier(bound.as_str())) {
                        names.push(member);
                    }
                }
            }
            _ => {}
        }
        pending.extend(node.children());
    }
    names
}
