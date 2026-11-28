use std::collections::BTreeMap;
use std::io::Write;
use std::path::Path;

use num_bigint::BigInt;
use pycg_document::{Value, dumps};
use pycg_syntax::parse::with_parsed;
use pycg_syntax::read::read_file;
use pycg_syntax::scopes::{ModuleScopes, ScopeId, ScopeKind, analyse_scopes};
use pycg_syntax::tree::{Field, Node, position, walk};
use ruff_python_ast::token::Tokens;
use ruff_source_file::LineIndex;

fn text(text: &str) -> Value {
    Value::Str(text.into())
}

fn optional(text: Option<&str>) -> Value {
    text.map_or(Value::Null, self::text)
}

fn int(number: usize) -> Value {
    Value::Int(BigInt::from(number))
}

fn strings<'s>(texts: impl Iterator<Item = &'s String>) -> Value {
    Value::Array(texts.map(|item| text(item)).collect())
}

fn sorted<'s>(texts: impl Iterator<Item = &'s String>) -> Value {
    let mut texts: Vec<&String> = texts.collect();
    texts.sort();
    strings(texts.into_iter())
}

fn object(fields: Vec<(&str, Value)>) -> Value {
    map(fields
        .into_iter()
        .map(|(key, field)| (key.to_owned(), field))
        .collect())
}

fn map(entries: Vec<(String, Value)>) -> Value {
    let count = entries.len();
    let fields: BTreeMap<String, Value> = entries.into_iter().collect();
    assert_eq!(fields.len(), count, "the keys of a record are distinct");
    Value::Object(fields)
}

fn dict(entries: Vec<Value>) -> Value {
    object(vec![("dict", Value::Array(entries))])
}

fn record(
    module: &str,
    mut fields: Vec<(&'static str, Value)>,
    out: &mut impl Write,
) -> std::io::Result<()> {
    fields.push(("module", text(module)));
    writeln!(out, "{}", dumps(&object(fields)))
}

fn status(module: &str, cause: Option<&str>, out: &mut impl Write) -> std::io::Result<()> {
    let status = if cause.is_some() {
        "failed"
    } else {
        "analysed"
    };
    let fields = vec![("cause", optional(cause)), ("status", text(status))];
    record(module, fields, out)
}

pub fn d1(path: &Path, module: &str, out: &mut (impl Write + Send)) -> std::io::Result<()> {
    let source = match read_file(path) {
        Ok(source) => source,
        Err(failure) => return status(module, Some(&failure.cause()), out),
    };
    with_parsed(&source, |parsed| {
        let parsed = match parsed {
            Ok(parsed) => parsed,
            Err(failure) => return status(module, Some(&failure.cause()), out),
        };
        status(module, None, out)?;
        let lines = LineIndex::from_source_text(&source);
        let tokens = parsed.tokens();
        for node in walk(parsed.syntax()) {
            if node.range(tokens).is_none() {
                continue;
            }
            let mut fields = vec![("position", ast_position(&node, tokens, &lines))];
            let identifiers: Vec<(&'static str, Value)> = node
                .identifiers(tokens, &source)
                .into_iter()
                .map(|(field, value)| match value {
                    Field::One(name) => (field, Value::Str(name.into())),
                    Field::Many(names) => (
                        field,
                        Value::Array(
                            names
                                .into_iter()
                                .map(|name| Value::Str(name.into()))
                                .collect(),
                        ),
                    ),
                })
                .collect();
            if !identifiers.is_empty() {
                fields.push(("identifiers", object(identifiers)));
            }
            record(module, fields, out)?;
        }
        let analysed = analyse_scopes(parsed.syntax(), module, tokens, &lines, &source);
        for &id in analysed.scopes() {
            let fields = vec![("scope", scope_record(&analysed, id, tokens, &lines))];
            record(module, fields, out)?;
        }
        for node in analysed.loop_nodes() {
            let bindings = analysed
                .loop_bindings(node)
                .iter()
                .map(|(name, unbinds)| Value::Array(vec![text(name), Value::Bool(*unbinds)]))
                .collect();
            let fields = vec![
                ("loop", ast_position(node, tokens, &lines)),
                ("bindings", dict(bindings)),
            ];
            record(module, fields, out)?;
        }
        let mut unread: Vec<(Position, Value)> = Vec::new();
        for node in walk(parsed.syntax()) {
            if let Node::Alias(alias) = node
                && analysed.is_unread_lazy(alias)
            {
                let range = node.range(tokens).expect("an alias has a position");
                let at = position(range, &lines);
                let key = (at.lineno, at.col_offset, at.end_lineno, at.end_col_offset);
                unread.push((key, ast_position(&node, tokens, &lines)));
            }
        }
        unread.sort_by_key(|(key, _)| *key);
        let unread = unread.into_iter().map(|(_, at)| at).collect();
        record(module, vec![("unread_lazy", Value::Array(unread))], out)
    })
}

type Position = (usize, usize, usize, usize);

fn ast_position(node: &Node<'_>, tokens: &Tokens, lines: &LineIndex) -> Value {
    let mut position_fields = vec![text(node.kind())];
    if let Some(range) = node.range(tokens) {
        let at = position(range, lines);
        position_fields.extend([
            int(at.lineno),
            int(at.col_offset),
            int(at.end_lineno),
            int(at.end_col_offset),
        ]);
    }
    Value::Array(position_fields)
}

fn kind_name(kind: ScopeKind) -> &'static str {
    match kind {
        ScopeKind::Module => "module",
        ScopeKind::Class => "class",
        ScopeKind::Function => "function",
        ScopeKind::Lambda => "lambda",
        ScopeKind::Comprehension => "comprehension",
    }
}

fn scope_record(
    scopes: &ModuleScopes<'_>,
    id: ScopeId,
    tokens: &Tokens,
    lines: &LineIndex,
) -> Value {
    let scope = scopes.scope(id);
    let imports = scope
        .imports
        .iter()
        .map(|(name, imported)| Value::Array(vec![text(name), optional(imported.as_deref())]))
        .collect();
    let definitions = scope
        .definitions
        .iter()
        .map(|(name, definition)| {
            let at = match definition.and_then(|key| scopes.scope_of_key(key)) {
                Some(defined) => object(vec![(
                    "ast",
                    ast_position(&scopes.scope(defined).node, tokens, lines),
                )]),
                None => Value::Null,
            };
            Value::Array(vec![text(name), at])
        })
        .collect();
    let reads = scope
        .reads
        .iter()
        .map(|name| {
            let binder = scopes.scope(scopes.resolve(id, name));
            (name.clone(), text(&binder.name))
        })
        .collect();
    let parent = scope
        .parent
        .map(|parent| scopes.scope(parent).name.as_str());
    object(vec![
        ("kind", text(kind_name(scope.kind))),
        ("name", text(&scope.name)),
        ("local_name", optional(scope.local_name.as_deref())),
        ("private_class", optional(scope.private_class.as_deref())),
        ("position", ast_position(&scope.node, tokens, lines)),
        ("parent", optional(parent)),
        ("generator", Value::Bool(scope.generator)),
        ("asynchronous", Value::Bool(scope.asynchronous)),
        ("star_import", Value::Bool(scope.star_import)),
        ("dynamic", Value::Bool(scope.dynamic)),
        ("bound", strings(scope.bound.iter())),
        ("defined", strings(scope.defined.iter())),
        ("globals", sorted(scope.globals.iter())),
        ("nonlocals", sorted(scope.nonlocals.iter())),
        ("rebound", sorted(scope.rebound.iter())),
        ("shared", sorted(scope.shared.iter())),
        ("imports", dict(imports)),
        ("definitions", dict(definitions)),
        ("reads", map(reads)),
    ])
}
