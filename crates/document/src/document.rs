use std::collections::{BTreeMap, BTreeSet};

use num_bigint::BigInt;

use pycg_analysis::builder::calls::Analysis;
use pycg_analysis::program::Program;
use pycg_analysis::results::{
    AnalysisPart, ClassDefinition, Construct, FunctionDefinition, RolePart,
};

use crate::{Text, Value};

pub const FORMAT: &str = "pycg/1";
pub const TOOL_NAME: &str = "pycg";
pub const VERSION: &str = include_str!(concat!(env!("OUT_DIR"), "/version.txt"));
const BUILTIN_OBJECT: &str = "<builtin>.object";

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ProgramPart {
    pub modules: Vec<SourceModule>,
    pub extension_modules: BTreeMap<String, String>,
    pub shadows: BTreeMap<String, Vec<String>>,
}

impl ProgramPart {
    pub fn from_program<A: Analysis + Send>(program: &mut Program<A>) -> ProgramPart {
        let modules: Vec<SourceModule> = program
            .modules
            .iter()
            .map(|(name, module)| SourceModule {
                name: name.clone(),
                file: program.relative(&module.file),
                status: module.status.name().to_owned(),
                cause: module.cause.clone(),
                line_count: u64::try_from(module.line_count).expect("a line count fits u64"),
            })
            .collect();
        let extension_modules: BTreeMap<String, String> = program
            .extension_modules
            .iter()
            .map(|(name, file)| (name.clone(), program.relative(file)))
            .collect();
        let mut files: BTreeMap<String, String> = modules
            .iter()
            .map(|module| (module.name.clone(), module.file.clone()))
            .collect();
        files.extend(extension_modules.clone());
        let mut shadows = BTreeMap::new();
        for (name, file) in files {
            let joined = program.root.join(&file);
            let found: Vec<String> = program
                .shadowed(&name, &joined)
                .iter()
                .map(|other| program.relative(other))
                .collect();
            if !found.is_empty() {
                shadows.insert(name, found);
            }
        }
        ProgramPart {
            modules,
            extension_modules,
            shadows,
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct SourceModule {
    pub name: String,
    pub file: String,
    pub status: String,
    pub cause: Option<String>,
    pub line_count: u64,
}

pub fn build(
    program: &ProgramPart,
    analysis: &AnalysisPart,
    package_name: Option<&Text>,
    package_version: Option<&Text>,
) -> Value {
    let definitions = definitions(program, analysis);
    let calls = calls(program, analysis, &definitions);
    let mut callees = BTreeSet::new();
    for sites in calls.values() {
        for site in sites {
            callees.extend(site.callees.iter().cloned());
        }
    }
    let outside = callees
        .into_iter()
        .filter(|name| !definitions.contains_key(name))
        .map(|name| {
            let known = outside_known(&name, program, analysis);
            (name, object(vec![("known", text(&known))]))
        })
        .collect();
    object(vec![
        ("format", text(FORMAT)),
        (
            "tool",
            object(vec![
                ("name", text(TOOL_NAME)),
                ("version", text(VERSION)),
                ("typeshed", text(pycg_stubs::TYPESHED_COMMIT)),
                ("cap", analysis.cap.clone().map_or(Value::Null, Value::Int)),
            ]),
        ),
        (
            "package",
            object(vec![
                (
                    "name",
                    package_name.map_or(Value::Null, |name| Value::Str(name.clone())),
                ),
                (
                    "version",
                    package_version.map_or(Value::Null, |version| Value::Str(version.clone())),
                ),
            ]),
        ),
        ("modules", modules_section(program)),
        (
            "definitions",
            Value::Object(
                definitions
                    .into_iter()
                    .map(|(name, definition)| (name, definition.value()))
                    .collect(),
            ),
        ),
        ("exports", exports(program, analysis)),
        ("outside", Value::Object(outside)),
        (
            "calls",
            Value::Object(
                calls
                    .into_iter()
                    .map(|(caller, sites)| {
                        (
                            caller,
                            Value::Array(sites.iter().map(SiteRecord::value).collect()),
                        )
                    })
                    .collect(),
            ),
        ),
    ])
}

fn text(value: &str) -> Value {
    Value::Str(value.into())
}

fn int(number: u64) -> Value {
    Value::Int(BigInt::from(number))
}

fn object(fields: Vec<(&str, Value)>) -> Value {
    Value::Object(
        fields
            .into_iter()
            .map(|(key, field)| (key.to_owned(), field))
            .collect(),
    )
}

fn outside_known(name: &str, program: &ProgramPart, analysis: &AnalysisPart) -> String {
    let parts: Vec<&str> = name.split('.').collect();
    let extension = (1..parts.len()).any(|end| {
        program
            .extension_modules
            .contains_key(&parts[..end].join("."))
    });
    if extension {
        return "extension".to_owned();
    }
    analysis
        .external_callees
        .get(name)
        .cloned()
        .unwrap_or_else(|| "stub".to_owned())
}

pub fn modules_section(program: &ProgramPart) -> Value {
    let mut modules: BTreeMap<String, Vec<(&str, Value)>> = BTreeMap::new();
    for module in &program.modules {
        let mut fields = vec![
            ("file", text(&module.file)),
            ("kind", text("source")),
            ("status", text(&module.status)),
        ];
        if let Some(cause) = &module.cause {
            fields.push(("cause", text(cause)));
        }
        modules.insert(module.name.clone(), fields);
    }
    for (name, file) in &program.extension_modules {
        modules.insert(
            name.clone(),
            vec![("file", text(file)), ("kind", text("extension"))],
        );
    }
    Value::Object(
        modules
            .into_iter()
            .map(|(name, mut fields)| {
                if let Some(shadows) = program.shadows.get(&name) {
                    assert!(!shadows.is_empty(), "a module with shadows has some");
                    let mut sorted = shadows.clone();
                    sorted.sort();
                    fields.push((
                        "shadows",
                        Value::Array(sorted.iter().map(|shadow| text(shadow)).collect()),
                    ));
                }
                (name, object(fields))
            })
            .collect(),
    )
}

enum Definition {
    Module {
        module: String,
        lines: u64,
    },
    Function {
        module: String,
        lineno: u64,
        end_lineno: u64,
    },
    Class {
        module: String,
        lineno: u64,
        end_lineno: u64,
        mro: Vec<String>,
    },
}

impl Definition {
    fn module(&self) -> &str {
        match self {
            Definition::Module { module, .. }
            | Definition::Function { module, .. }
            | Definition::Class { module, .. } => module,
        }
    }

    fn value(self) -> Value {
        match self {
            Definition::Module { module, lines } => object(vec![
                ("kind", text("module")),
                ("module", text(&module)),
                ("lines", Value::Array(vec![int(lines.min(1)), int(lines)])),
            ]),
            Definition::Function {
                module,
                lineno,
                end_lineno,
            } => object(vec![
                ("kind", text("function")),
                ("module", text(&module)),
                ("lines", Value::Array(vec![int(lineno), int(end_lineno)])),
            ]),
            Definition::Class {
                module,
                lineno,
                end_lineno,
                mro,
            } => object(vec![
                ("kind", text("class")),
                ("module", text(&module)),
                ("lines", Value::Array(vec![int(lineno), int(end_lineno)])),
                (
                    "mro",
                    Value::Array(mro.iter().map(|name| text(name)).collect()),
                ),
            ]),
        }
    }
}

fn by_position(analysis: &AnalysisPart) -> Vec<&FunctionDefinition> {
    let mut functions: Vec<&FunctionDefinition> = analysis.functions.iter().collect();
    functions.sort_by(|left, right| {
        (&left.module, left.lineno, left.end_lineno, &left.name).cmp(&(
            &right.module,
            right.lineno,
            right.end_lineno,
            &right.name,
        ))
    });
    functions
}

pub fn module_definitions(program: &ProgramPart) -> Value {
    Value::Object(
        module_definition_entries(program)
            .into_iter()
            .map(|(name, definition)| (name, definition.value()))
            .collect(),
    )
}

fn module_definition_entries(program: &ProgramPart) -> BTreeMap<String, Definition> {
    let mut found = BTreeMap::new();
    for module in &program.modules {
        let previous = found.insert(
            module.name.clone(),
            Definition::Module {
                module: module.name.clone(),
                lines: module.line_count,
            },
        );
        assert!(previous.is_none(), "a module is listed once");
    }
    found
}

fn definitions(program: &ProgramPart, analysis: &AnalysisPart) -> BTreeMap<String, Definition> {
    let mut found = module_definition_entries(program);
    for function in by_position(analysis) {
        found
            .entry(function.name.clone())
            .or_insert_with(|| Definition::Function {
                module: function.module.clone(),
                lineno: function.lineno,
                end_lineno: function.end_lineno,
            });
    }
    let mut classes: Vec<&ClassDefinition> = analysis.classes.iter().collect();
    classes.sort_by(|left, right| (&left.module, left.index).cmp(&(&right.module, right.index)));
    for class in classes {
        found
            .entry(class.name.clone())
            .or_insert_with(|| Definition::Class {
                module: class.module.clone(),
                lineno: class.lineno,
                end_lineno: class.end_lineno,
                mro: mro(class),
            });
    }
    found
}

fn mro(class: &ClassDefinition) -> Vec<String> {
    if class.unknown {
        return vec![class.name.clone()];
    }
    let mut names: Vec<String> = class.mro.iter().map(|base| base.name.clone()).collect();
    if class.mro.iter().all(|base| base.analysed) {
        names.push(BUILTIN_OBJECT.to_owned());
    }
    names
}

fn exports(program: &ProgramPart, analysis: &AnalysisPart) -> Value {
    let mut exports = BTreeMap::new();
    for module in &program.modules {
        let Some(fields) = analysis.fields.get(&module.name) else {
            continue;
        };
        for (attribute, held) in fields {
            let path = format!("{}.{attribute}", module.name);
            let targets: BTreeSet<&String> = held.iter().filter(|name| **name != path).collect();
            if !targets.is_empty() {
                exports.insert(
                    path,
                    Value::Array(targets.into_iter().map(|name| text(name)).collect()),
                );
            }
        }
    }
    Value::Object(exports)
}

#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
struct Place {
    line: u64,
    column: u64,
}

struct Site {
    module: String,
    start: Place,
    end: Place,
}

fn site_parts(site: &str) -> Site {
    let (rest, suffix) = match site.rsplit_once('#') {
        Some((rest, suffix)) if digits(suffix) && tail(rest).is_some() => (rest, Some(suffix)),
        _ => (site, None),
    };
    assert!(
        suffix.is_none() || tail(site).is_none(),
        "{site} has one reading"
    );
    let (module, numbers) = tail(rest).unwrap_or_else(|| panic!("{site} is a site"));
    Site {
        module: module.to_owned(),
        start: Place {
            line: numbers[0],
            column: numbers[1],
        },
        end: Place {
            line: numbers[2],
            column: numbers[3],
        },
    }
}

fn digits(text: &str) -> bool {
    !text.is_empty() && text.bytes().all(|byte| byte.is_ascii_digit())
}

fn tail(text: &str) -> Option<(&str, [u64; 4])> {
    let (rest, end_column) = text.rsplit_once(':')?;
    let (rest, end_line) = rest.rsplit_once('#')?;
    let (rest, column) = rest.rsplit_once(':')?;
    let (module, line) = rest.rsplit_once(':')?;
    let parts = [line, column, end_line, end_column];
    if !parts.iter().all(|part| digits(part)) {
        return None;
    }
    let numbers = parts.map(|part| part.parse().expect("a site number fits u64"));
    Some((module, numbers))
}

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord)]
struct SiteKey {
    module: String,
    start: Place,
    end: Place,
    implicit: String,
}

struct SiteRecord {
    key: SiteKey,
    callees: BTreeSet<String>,
    cause: Option<String>,
}

impl SiteRecord {
    fn value(&self) -> Value {
        let mut fields = vec![
            ("line", int(self.key.start.line)),
            ("col", int(self.key.start.column)),
            (
                "end",
                Value::Array(vec![int(self.key.end.line), int(self.key.end.column)]),
            ),
            (
                "callees",
                Value::Array(self.callees.iter().map(|name| text(name)).collect()),
            ),
        ];
        if !self.key.implicit.is_empty() {
            fields.push(("implicit", text(&self.key.implicit)));
        } else if self.callees.is_empty() {
            fields.push((
                "unresolved",
                self.cause.as_deref().map_or(Value::Null, text),
            ));
        }
        if !self.key.module.is_empty() {
            fields.push(("module", text(&self.key.module)));
        }
        object(fields)
    }
}

type RecordKey = (String, String, Option<&'static str>);

type SiteCalls = BTreeMap<SiteKey, (BTreeSet<String>, Option<String>)>;

fn calls(
    program: &ProgramPart,
    analysis: &AnalysisPart,
    definitions: &BTreeMap<String, Definition>,
) -> BTreeMap<String, Vec<SiteRecord>> {
    let expressions: BTreeSet<(&str, &str)> = analysis
        .call_expressions
        .iter()
        .map(|(caller, site)| (caller.as_str(), site.as_str()))
        .collect();
    let mut records: Vec<(RecordKey, BTreeSet<String>)> = Vec::new();
    let mut record_index: BTreeMap<RecordKey, usize> = BTreeMap::new();
    let mut add = |key: RecordKey, callees: &[String]| {
        let index = *record_index.entry(key.clone()).or_insert_with(|| {
            records.push((key, BTreeSet::new()));
            records.len() - 1
        });
        records[index].1.extend(callees.iter().cloned());
    };
    for edge in &analysis.site_edges {
        let pair = (edge.caller.as_str(), edge.site.as_str());
        let implicit = implicit_construct(
            &edge.construct,
            expressions.contains(&pair),
            analysis
                .iterated_expressions
                .contains(&(edge.caller.clone(), edge.site.clone())),
        );
        add(
            (edge.caller.clone(), edge.site.clone(), implicit),
            &edge.callees,
        );
    }
    let causes: BTreeMap<(&str, &str), &str> = analysis
        .unresolved
        .iter()
        .map(|entry| {
            (
                (entry.caller.as_str(), entry.site.as_str()),
                entry.cause.as_str(),
            )
        })
        .collect();
    assert_eq!(
        causes.len(),
        analysis.unresolved.len(),
        "a site has one cause"
    );
    for entry in &analysis.unresolved {
        add((entry.caller.clone(), entry.site.clone(), None), &[]);
    }
    let mut functions: BTreeMap<&str, Vec<&FunctionDefinition>> = BTreeMap::new();
    for function in by_position(analysis) {
        functions.entry(&function.name).or_default().push(function);
    }
    let module_names: BTreeSet<&str> = program
        .modules
        .iter()
        .map(|module| module.name.as_str())
        .collect();
    let mut calls: BTreeMap<String, SiteCalls> = BTreeMap::new();
    for ((caller, site, implicit), callees) in records {
        let mut parts = site_parts(&site);
        if !caller_code_has_line(
            &caller,
            &parts.module,
            parts.start.line,
            &module_names,
            &functions,
        ) {
            let first = functions[caller.as_str()][0];
            parts = Site {
                module: first.module.clone(),
                start: Place {
                    line: first.lineno,
                    column: first.col_offset,
                },
                end: Place {
                    line: first.end_lineno,
                    column: first.end_col_offset,
                },
            };
        }
        let own = definitions
            .get(&caller)
            .unwrap_or_else(|| panic!("the caller {caller} is defined"))
            .module();
        let key = SiteKey {
            module: if parts.module == own {
                String::new()
            } else {
                parts.module
            },
            start: parts.start,
            end: parts.end,
            implicit: implicit.unwrap_or("").to_owned(),
        };
        let record = calls
            .entry(caller.clone())
            .or_default()
            .entry(key)
            .or_insert_with(|| (BTreeSet::new(), None));
        record.0.extend(callees);
        if let Some(cause) = causes.get(&(caller.as_str(), site.as_str())) {
            record.1 = Some((*cause).to_owned());
        }
    }
    calls
        .into_iter()
        .map(|(caller, sites)| {
            let records = sites
                .into_iter()
                .map(|(key, (callees, cause))| SiteRecord {
                    key,
                    callees,
                    cause,
                })
                .collect();
            (caller, records)
        })
        .collect()
}

fn caller_code_has_line(
    caller: &str,
    module: &str,
    line: u64,
    modules: &BTreeSet<&str>,
    functions: &BTreeMap<&str, Vec<&FunctionDefinition>>,
) -> bool {
    if modules.contains(caller) && module == caller {
        return true;
    }
    match functions.get(caller) {
        None => true,
        Some(found) => found.iter().any(|function| {
            function.module == module && function.lineno <= line && line <= function.end_lineno
        }),
    }
}

const ROLES_IMPLICIT_AT_CALL_EXPRESSION: &[&str] = &[
    "await",
    "class statement",
    "compare",
    "enter",
    "exit",
    "hash",
    "hash_eq",
    "init_subclass",
    "operator",
    "prepare",
    "raise",
    "set_name",
    "special",
    "subscript",
    "truth",
];

const ROLES_ITERATION: &[&str] = &["iterate", "index", "callable"];

const ROLES_ATTRIBUTE_ACCESS: &[&str] = &["accessor", "getattr", "hook", "property"];

fn implicit_construct(
    construct: &Construct,
    at_call_expression: bool,
    iterated: bool,
) -> Option<&'static str> {
    let parts = match construct {
        Construct::Call => return None,
        Construct::Decorator => return Some("decorator"),
        Construct::Role(parts) => parts,
    };
    let Some(RolePart::Text(role)) = parts.first() else {
        panic!("a role starts with its name")
    };
    let role = role.as_str();
    let iterated_by_statement = ROLES_ITERATION.contains(&role) && iterated;
    if at_call_expression
        && !ROLES_IMPLICIT_AT_CALL_EXPRESSION.contains(&role)
        && !iterated_by_statement
    {
        return None;
    }
    let second = parts.get(1);
    if parts.len() == 2
        && role == "subscript"
        && second == Some(&RolePart::Text("__delitem__".to_owned()))
    {
        return Some("delete");
    }
    if ROLES_ATTRIBUTE_ACCESS.contains(&role)
        && second == Some(&RolePart::Text("Delete".to_owned()))
    {
        return Some("delete");
    }
    implicit_construct_by_role(role)
}

fn implicit_construct_by_role(role: &str) -> Option<&'static str> {
    match role {
        "accessor" | "class get" | "getattr" | "hook" | "module getattr" | "named load"
        | "property" => Some("attribute"),
        "await" => Some("await"),
        "callable" | "index" | "iterate" => Some("iteration"),
        "class statement" | "init_subclass" | "prepare" | "set_name" => Some("class"),
        "compare" | "operator" => Some("operator"),
        "convert" | "format" => Some("format"),
        "enter" | "exit" => Some("with"),
        "hash" | "hash_eq" => Some("dict"),
        "raise" => Some("raise"),
        "special" => Some("match"),
        "subscript" => Some("subscript"),
        "truth" => Some("truth"),
        "call back" | "key" | "filter" | "map" | "protocol" | "reversed" | "type" => None,
        other => panic!("{other} is a role of an implicit call"),
    }
}

#[cfg(test)]
mod tests {
    use super::{ProgramPart, SourceModule, build, site_parts};
    use crate::dumps;
    use pycg_analysis::results::{
        AnalysisPart, Construct, FunctionDefinition, SiteEdge, Unresolved,
    };
    use std::collections::{BTreeMap, BTreeSet};

    fn program() -> ProgramPart {
        ProgramPart {
            modules: vec![SourceModule {
                name: "main".to_owned(),
                file: "main.py".to_owned(),
                status: "analysed".to_owned(),
                cause: None,
                line_count: 9,
            }],
            extension_modules: BTreeMap::from([("ext".to_owned(), "ext.so".to_owned())]),
            shadows: BTreeMap::new(),
        }
    }

    fn analysis() -> AnalysisPart {
        AnalysisPart {
            cap: None,
            functions: vec![FunctionDefinition {
                name: "main.f".to_owned(),
                module: "main".to_owned(),
                lineno: 2,
                end_lineno: 3,
                col_offset: 0,
                end_col_offset: 8,
            }],
            classes: vec![],
            fields: BTreeMap::new(),
            site_edges: vec![SiteEdge {
                caller: "main.f".to_owned(),
                site: "main:3:4#3:9".to_owned(),
                construct: Construct::Call,
                callees: vec!["ext.g".to_owned()],
            }],
            call_expressions: BTreeSet::from([
                ("main.f".to_owned(), "main:3:4#3:9".to_owned()),
                ("main".to_owned(), "main:5:0#5:3#2".to_owned()),
            ]),
            iterated_expressions: BTreeSet::new(),
            unresolved: vec![Unresolved {
                caller: "main".to_owned(),
                site: "main:5:0#5:3#2".to_owned(),
                cause: "no value".to_owned(),
            }],
            external_callees: BTreeMap::new(),
        }
    }

    #[test]
    fn a_site_reads_its_module_and_positions_with_or_without_a_count() {
        let plain = site_parts("pkg.mod:1:2#3:4");
        let counted = site_parts("pkg.mod:1:2#3:4#7");

        for site in [plain, counted] {
            assert_eq!(site.module, "pkg.mod");
            assert_eq!((site.start.line, site.start.column), (1, 2));
            assert_eq!((site.end.line, site.end.column), (3, 4));
        }
    }

    #[test]
    fn a_callee_under_an_extension_module_is_known_as_an_extension() {
        let document = dumps(&build(&program(), &analysis(), None, None));

        assert!(document.contains(r#""outside":{"ext.g":{"known":"extension"}}"#));
    }

    #[test]
    fn an_unresolved_call_records_its_cause() {
        let document = dumps(&build(&program(), &analysis(), None, None));

        assert!(document.contains(
            r#""main":[{"callees":[],"col":0,"end":[5,3],"line":5,"unresolved":"no value"}]"#
        ));
    }

    #[test]
    fn a_site_outside_the_code_of_its_caller_moves_to_the_definition() {
        let mut moved = analysis();
        moved.site_edges[0].site = "main:8:4#8:9".to_owned();

        let document = dumps(&build(&program(), &moved, None, None));

        assert!(
            document.contains(r#""main.f":[{"callees":["ext.g"],"col":0,"end":[3,8],"line":2}]"#)
        );
    }
}
