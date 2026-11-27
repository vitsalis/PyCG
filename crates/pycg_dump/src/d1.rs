use std::io::Write;
use std::path::Path;
use std::process::ExitCode;

use pycg_syntax::parse::with_parsed;
use pycg_syntax::read::read_file;
use pycg_syntax::scopes::{ModuleScopes, ScopeId, ScopeKind, analyse_scopes};
use pycg_syntax::tree::{Field, Node, position, walk};
use ruff_python_ast::token::Tokens;
use ruff_source_file::LineIndex;

pub fn run(arguments: &[String]) -> Option<ExitCode> {
    match arguments {
        [command, modules, out] if command == "d1" => {
            let listed = std::fs::read_to_string(modules).expect("the module list is readable");
            let file = std::fs::File::create(out).expect("the D1 dump can be created");
            let mut out = std::io::BufWriter::new(file);
            for line in listed.lines() {
                let (module, path) = line.split_once('\t').expect("a module and its file");
                d1(Path::new(path), module, &mut out).expect("the D1 dump takes the records");
            }
            out.flush().expect("the D1 dump is written");
            Some(ExitCode::SUCCESS)
        }
        _ => None,
    }
}

enum Json {
    Null,
    Bool(bool),
    Int(usize),
    Str(String),
    Array(Vec<Json>),
    Object(Vec<(&'static str, Json)>),
    Map(Vec<(String, Json)>),
}

impl Json {
    fn text(text: &str) -> Json {
        Json::Str(text.to_owned())
    }

    fn optional(text: Option<&str>) -> Json {
        text.map_or(Json::Null, Json::text)
    }

    fn strings<'s>(texts: impl Iterator<Item = &'s String>) -> Json {
        Json::Array(texts.map(|text| Json::text(text)).collect())
    }

    fn sorted<'s>(texts: impl Iterator<Item = &'s String>) -> Json {
        let mut texts: Vec<&String> = texts.collect();
        texts.sort();
        Json::strings(texts.into_iter())
    }

    fn dict(entries: Vec<Json>) -> Json {
        Json::Object(vec![("dict", Json::Array(entries))])
    }

    fn write(&self, out: &mut String) {
        match self {
            Json::Null => out.push_str("null"),
            Json::Bool(value) => out.push_str(if *value { "true" } else { "false" }),
            Json::Int(value) => out.push_str(&value.to_string()),
            Json::Str(text) => write_string(text, out),
            Json::Array(items) => {
                out.push('[');
                for (index, item) in items.iter().enumerate() {
                    if index > 0 {
                        out.push(',');
                    }
                    item.write(out);
                }
                out.push(']');
            }
            Json::Object(fields) => {
                let mut fields: Vec<(&str, &Json)> =
                    fields.iter().map(|(key, value)| (*key, value)).collect();
                write_object(&mut fields, out);
            }
            Json::Map(entries) => {
                let mut fields: Vec<(&str, &Json)> = entries
                    .iter()
                    .map(|(key, value)| (key.as_str(), value))
                    .collect();
                write_object(&mut fields, out);
            }
        }
    }
}

fn write_object(fields: &mut [(&str, &Json)], out: &mut String) {
    fields.sort_by(|left, right| left.0.cmp(right.0));
    out.push('{');
    for (index, (key, value)) in fields.iter().enumerate() {
        if index > 0 {
            out.push(',');
        }
        write_string(key, out);
        out.push(':');
        value.write(out);
    }
    out.push('}');
}

fn write_string(text: &str, out: &mut String) {
    out.push('"');
    for character in text.chars() {
        match character {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            '\u{8}' => out.push_str("\\b"),
            '\u{c}' => out.push_str("\\f"),
            ' '..='~' => out.push(character),
            _ => {
                let mut units = [0_u16; 2];
                for unit in character.encode_utf16(&mut units) {
                    out.push_str(&format!("\\u{unit:04x}"));
                }
            }
        }
    }
    out.push('"');
}

fn record(
    module: &str,
    mut fields: Vec<(&'static str, Json)>,
    out: &mut impl Write,
) -> std::io::Result<()> {
    fields.push(("module", Json::text(module)));
    let mut line = String::new();
    Json::Object(fields).write(&mut line);
    writeln!(out, "{line}")
}

fn status(module: &str, cause: Option<&str>, out: &mut impl Write) -> std::io::Result<()> {
    let status = if cause.is_some() {
        "failed"
    } else {
        "analysed"
    };
    let fields = vec![
        ("cause", Json::optional(cause)),
        ("status", Json::text(status)),
    ];
    record(module, fields, out)
}

fn d1(path: &Path, module: &str, out: &mut (impl Write + Send)) -> std::io::Result<()> {
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
            let identifiers: Vec<(&'static str, Json)> = node
                .identifiers(tokens, &source)
                .into_iter()
                .map(|(field, value)| match value {
                    Field::One(name) => (field, Json::Str(name)),
                    Field::Many(names) => (
                        field,
                        Json::Array(names.into_iter().map(Json::Str).collect()),
                    ),
                })
                .collect();
            if !identifiers.is_empty() {
                fields.push(("identifiers", Json::Object(identifiers)));
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
                .map(|(name, unbinds)| Json::Array(vec![Json::text(name), Json::Bool(*unbinds)]))
                .collect();
            let fields = vec![
                ("loop", ast_position(node, tokens, &lines)),
                ("bindings", Json::dict(bindings)),
            ];
            record(module, fields, out)?;
        }
        let mut unread: Vec<(Position, Json)> = Vec::new();
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
        record(module, vec![("unread_lazy", Json::Array(unread))], out)
    })
}

type Position = (usize, usize, usize, usize);

fn ast_position(node: &Node<'_>, tokens: &Tokens, lines: &LineIndex) -> Json {
    let mut position_fields = vec![Json::text(node.kind())];
    if let Some(range) = node.range(tokens) {
        let at = position(range, lines);
        position_fields.extend([
            Json::Int(at.lineno),
            Json::Int(at.col_offset),
            Json::Int(at.end_lineno),
            Json::Int(at.end_col_offset),
        ]);
    }
    Json::Array(position_fields)
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
) -> Json {
    let scope = scopes.scope(id);
    let imports = scope
        .imports
        .iter()
        .map(|(name, imported)| {
            Json::Array(vec![Json::text(name), Json::optional(imported.as_deref())])
        })
        .collect();
    let definitions = scope
        .definitions
        .iter()
        .map(|(name, definition)| {
            let at = match definition.and_then(|key| scopes.scope_of_key(key)) {
                Some(defined) => Json::Object(vec![(
                    "ast",
                    ast_position(&scopes.scope(defined).node, tokens, lines),
                )]),
                None => Json::Null,
            };
            Json::Array(vec![Json::text(name), at])
        })
        .collect();
    let reads = scope
        .reads
        .iter()
        .map(|name| {
            let binder = scopes.scope(scopes.resolve(id, name));
            (name.clone(), Json::text(&binder.name))
        })
        .collect();
    let parent = scope
        .parent
        .map(|parent| scopes.scope(parent).name.as_str());
    Json::Object(vec![
        ("kind", Json::text(kind_name(scope.kind))),
        ("name", Json::text(&scope.name)),
        ("local_name", Json::optional(scope.local_name.as_deref())),
        (
            "private_class",
            Json::optional(scope.private_class.as_deref()),
        ),
        ("position", ast_position(&scope.node, tokens, lines)),
        ("parent", Json::optional(parent)),
        ("generator", Json::Bool(scope.generator)),
        ("asynchronous", Json::Bool(scope.asynchronous)),
        ("star_import", Json::Bool(scope.star_import)),
        ("dynamic", Json::Bool(scope.dynamic)),
        ("bound", Json::strings(scope.bound.iter())),
        ("defined", Json::strings(scope.defined.iter())),
        ("globals", Json::sorted(scope.globals.iter())),
        ("nonlocals", Json::sorted(scope.nonlocals.iter())),
        ("rebound", Json::sorted(scope.rebound.iter())),
        ("shared", Json::sorted(scope.shared.iter())),
        ("imports", Json::dict(imports)),
        ("definitions", Json::dict(definitions)),
        ("reads", Json::Map(reads)),
    ])
}
