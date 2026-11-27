use std::io::Write;
use std::path::Path;
use std::process::ExitCode;

use pycg_syntax::parse::parse_source;
use pycg_syntax::read::read_file;
use pycg_syntax::scopes::{ModuleScopes, Scope, ScopeKind, analyse_scopes};
use pycg_syntax::tree::{Node, position, walk};
use ruff_source_file::LineIndex;

pub fn run(arguments: &[String]) -> Option<ExitCode> {
    match arguments {
        [command, file] if command == "d1-positions" => {
            let stdout = std::io::stdout();
            let mut out = stdout.lock();
            positions(Path::new(file), &mut out).expect("standard output takes the dump");
            Some(ExitCode::SUCCESS)
        }
        [command, file, module] if command == "d1-scopes" => {
            let stdout = std::io::stdout();
            let mut out = stdout.lock();
            scopes(Path::new(file), module, &mut out).expect("standard output takes the dump");
            Some(ExitCode::SUCCESS)
        }
        _ => None,
    }
}

fn positions(path: &Path, out: &mut impl Write) -> std::io::Result<()> {
    let source = match read_file(path) {
        Ok(source) => source,
        Err(failure) => return writeln!(out, "{{\"failed\":\"{}\"}}", failure.cause()),
    };
    let parsed = match parse_source(&source) {
        Ok(parsed) => parsed,
        Err(failure) => return writeln!(out, "{{\"failed\":\"{}\"}}", failure.cause()),
    };
    let lines = LineIndex::from_source_text(&source);
    for node in walk(parsed.syntax()) {
        let Some(range) = node.range(parsed.tokens()) else {
            continue;
        };
        let at = position(range, &lines);
        writeln!(
            out,
            "[\"{}\",{},{},{},{}]",
            node.kind(),
            at.lineno,
            at.col_offset,
            at.end_lineno,
            at.end_col_offset
        )?;
    }
    Ok(())
}

fn json_string(text: &str) -> String {
    let mut quoted = String::from("\"");
    for character in text.chars() {
        match character {
            '"' => quoted.push_str("\\\""),
            '\\' => quoted.push_str("\\\\"),
            ' '..='~' => quoted.push(character),
            _ => {
                let mut units = [0_u16; 2];
                for unit in character.encode_utf16(&mut units) {
                    quoted.push_str(&format!("\\u{unit:04x}"));
                }
            }
        }
    }
    quoted.push('"');
    quoted
}

fn json_strings<'s>(texts: impl Iterator<Item = &'s String>) -> String {
    let quoted: Vec<String> = texts.map(|text| json_string(text)).collect();
    format!("[{}]", quoted.join(","))
}

fn sorted<'s>(texts: impl Iterator<Item = &'s String>) -> Vec<&'s String> {
    let mut texts: Vec<&String> = texts.collect();
    texts.sort();
    texts
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

fn place(node: &Node<'_>, tokens: &ruff_python_ast::token::Tokens, lines: &LineIndex) -> String {
    match node.range(tokens) {
        Some(range) => {
            let at = position(range, lines);
            format!("[{},{}]", at.lineno, at.col_offset)
        }
        None => "null".to_owned(),
    }
}

fn scope_record(
    scopes: &ModuleScopes<'_>,
    scope: &Scope<'_>,
    id: pycg_syntax::scopes::ScopeId,
    tokens: &ruff_python_ast::token::Tokens,
    lines: &LineIndex,
) -> String {
    let flag = |value: bool| if value { "true" } else { "false" };
    let imports: Vec<String> = sorted(scope.imports.keys())
        .into_iter()
        .map(|name| match &scope.imports[name] {
            Some(imported) => format!("[{},{}]", json_string(name), json_string(imported)),
            None => format!("[{},null]", json_string(name)),
        })
        .collect();
    let definitions: Vec<String> = sorted(scope.definitions.keys())
        .into_iter()
        .map(|name| {
            let at = match scope.definitions[name].and_then(|key| scopes.scope_of_key(key)) {
                Some(defined) => place(&scopes.scope(defined).node, tokens, lines),
                None => "null".to_owned(),
            };
            format!("[{},{at}]", json_string(name))
        })
        .collect();
    let resolved: Vec<String> = sorted(scope.reads.iter())
        .into_iter()
        .map(|name| {
            let binder = scopes.scope(scopes.resolve(id, name));
            format!("[{},{}]", json_string(name), json_string(&binder.name))
        })
        .collect();
    let local = scope
        .local_name
        .as_ref()
        .map_or("null".to_owned(), |name| json_string(name));
    format!(
        "{{\"scope\":{},\"kind\":\"{}\",\"local\":{local},\"position\":{},\"generator\":{},\"async\":{},\"bound\":{},\"defined\":{},\"globals\":{},\"nonlocals\":{},\"rebound\":{},\"shared\":{},\"star_import\":{},\"dynamic\":{},\"imports\":[{}],\"definitions\":[{}],\"resolved\":[{}]}}",
        json_string(&scope.name),
        kind_name(scope.kind),
        place(&scope.node, tokens, lines),
        flag(scope.generator),
        flag(scope.asynchronous),
        json_strings(scope.bound.iter()),
        json_strings(scope.defined.iter()),
        json_strings(sorted(scope.globals.iter()).into_iter()),
        json_strings(sorted(scope.nonlocals.iter()).into_iter()),
        json_strings(sorted(scope.rebound.iter()).into_iter()),
        json_strings(sorted(scope.shared.iter()).into_iter()),
        flag(scope.star_import),
        flag(scope.dynamic),
        imports.join(","),
        definitions.join(","),
        resolved.join(","),
    )
}

fn scopes(path: &Path, module: &str, out: &mut impl Write) -> std::io::Result<()> {
    let source = match read_file(path) {
        Ok(source) => source,
        Err(failure) => return writeln!(out, "{{\"failed\":\"{}\"}}", failure.cause()),
    };
    let parsed = match parse_source(&source) {
        Ok(parsed) => parsed,
        Err(failure) => return writeln!(out, "{{\"failed\":\"{}\"}}", failure.cause()),
    };
    let lines = LineIndex::from_source_text(&source);
    let tokens = parsed.tokens();
    let analysed = analyse_scopes(parsed.syntax(), module, tokens, &lines, &source);
    for &id in analysed.scopes() {
        let record = scope_record(&analysed, analysed.scope(id), id, tokens, &lines);
        writeln!(out, "{record}")?;
    }
    let mut loops: Vec<((usize, usize), String, String)> = analysed
        .loop_nodes()
        .iter()
        .map(|node| {
            let names: Vec<String> = analysed
                .loop_bindings(node)
                .iter()
                .map(|(name, unbinds)| format!("[{},{unbinds}]", json_string(name)))
                .collect();
            let range = node.range(tokens).expect("a loop has a position");
            let at = position(range, &lines);
            (
                (at.lineno, at.col_offset),
                place(node, tokens, &lines),
                names.join(","),
            )
        })
        .collect();
    loops.sort();
    for (_, at, names) in loops {
        writeln!(out, "{{\"loop\":{at},\"names\":[{names}]}}")?;
    }
    let mut unread: Vec<String> = Vec::new();
    for node in walk(parsed.syntax()) {
        if let Node::Alias(alias) = node
            && analysed.is_unread_lazy(alias)
        {
            unread.push(place(&node, tokens, &lines));
        }
    }
    writeln!(out, "{{\"unread_lazy\":[{}]}}", unread.join(","))
}
