use std::collections::{BTreeMap, BTreeSet};
use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::ExitCode;

use num_bigint::BigInt;
use pycg_document::{
    AnalysisPart, ClassDefinition, Construct, FunctionDefinition, MroBase, ProgramPart, RolePart,
    SiteEdge, Unresolved, build, dumps,
};
use serde_json::{Map, Value};

const EXIT_FAILURE: u8 = 1;
const ORACLE_BUILDER: &str = "D4.jsonl";
const ANALYSIS_PART: &str = "D6in.json";
const RUN: &str = "run.json";
const DOCUMENT: &str = "D6.json";

pub fn run(oracle: &str, out: &str) -> ExitCode {
    let oracle = Path::new(oracle);
    let (run, analysis) = match read(&oracle.join(RUN)).and_then(|run| {
        let analysis = read(&oracle.join(ANALYSIS_PART)).and_then(|value| analysis_part(&value))?;
        Ok((run, analysis))
    }) {
        Ok(found) => found,
        Err(problem) => {
            eprintln!("pycg-dump: {}: {problem}", oracle.display());
            return ExitCode::from(EXIT_FAILURE);
        }
    };
    let (package, entry_points) = match run_paths(&run) {
        Ok(paths) => paths,
        Err(problem) => {
            eprintln!("pycg-dump: {}: {problem}", oracle.join(RUN).display());
            return ExitCode::from(EXIT_FAILURE);
        }
    };
    let out = Path::new(out);
    let mut program =
        crate::d4::discover(&oracle.join(ORACLE_BUILDER), out, &package, &entry_points);
    let program = ProgramPart::from_program(&mut program);
    let document = dumps(&build(&program, &analysis, None, None));
    let written = std::fs::File::create(out.join(DOCUMENT))
        .and_then(|mut file| file.write_all(document.as_bytes()));
    if let Err(error) = written {
        eprintln!(
            "pycg-dump: cannot write {}: {error}",
            out.join(DOCUMENT).display()
        );
        return ExitCode::from(EXIT_FAILURE);
    }
    ExitCode::SUCCESS
}

fn read(path: &Path) -> Parsed<Value> {
    let text = std::fs::read_to_string(path).map_err(|error| error.to_string())?;
    serde_json::from_str(&text).map_err(|error| error.to_string())
}

fn run_paths(run: &Value) -> Parsed<(PathBuf, Vec<PathBuf>)> {
    let record = object(run)?;
    let package = PathBuf::from(string(field(record, "package")?)?);
    let entry_points = strings(field(record, "entry_points")?)?
        .into_iter()
        .map(PathBuf::from)
        .collect();
    Ok((package, entry_points))
}

type Parsed<T> = Result<T, String>;

fn field<'v>(record: &'v Map<String, Value>, name: &str) -> Parsed<&'v Value> {
    record.get(name).ok_or_else(|| format!("no {name}"))
}

fn string(value: &Value) -> Parsed<String> {
    value
        .as_str()
        .map(str::to_owned)
        .ok_or_else(|| format!("{value} is not a string"))
}

fn number(value: &Value) -> Parsed<u64> {
    value
        .as_u64()
        .ok_or_else(|| format!("{value} is not a natural number"))
}

fn flag(value: &Value) -> Parsed<bool> {
    value
        .as_bool()
        .ok_or_else(|| format!("{value} is not a bool"))
}

fn array(value: &Value) -> Parsed<&Vec<Value>> {
    value
        .as_array()
        .ok_or_else(|| format!("{value} is not an array"))
}

fn object(value: &Value) -> Parsed<&Map<String, Value>> {
    value
        .as_object()
        .ok_or_else(|| format!("{value} is not an object"))
}

fn strings(value: &Value) -> Parsed<Vec<String>> {
    array(value)?.iter().map(string).collect()
}

fn string_map(value: &Value) -> Parsed<BTreeMap<String, String>> {
    object(value)?
        .iter()
        .map(|(key, item)| Ok((key.clone(), string(item)?)))
        .collect()
}

fn pairs(value: &Value) -> Parsed<BTreeSet<(String, String)>> {
    array(value)?
        .iter()
        .map(|pair| match array(pair)?.as_slice() {
            [first, second] => Ok((string(first)?, string(second)?)),
            _ => Err(format!("{pair} is not a pair")),
        })
        .collect()
}

fn analysis_part(value: &Value) -> Parsed<AnalysisPart> {
    let record = object(value)?;
    let cap = field(record, "cap")?;
    Ok(AnalysisPart {
        cap: if cap.is_null() {
            None
        } else {
            Some(BigInt::from(number(cap)?))
        },
        functions: array(field(record, "functions")?)?
            .iter()
            .map(function)
            .collect::<Parsed<_>>()?,
        classes: array(field(record, "classes")?)?
            .iter()
            .map(class)
            .collect::<Parsed<_>>()?,
        fields: object(field(record, "fields")?)?
            .iter()
            .map(|(module, attributes)| {
                let attributes = object(attributes)?
                    .iter()
                    .map(|(attribute, held)| Ok((attribute.clone(), strings(held)?)))
                    .collect::<Parsed<_>>()?;
                Ok((module.clone(), attributes))
            })
            .collect::<Parsed<_>>()?,
        site_edges: array(field(record, "site_edges")?)?
            .iter()
            .map(site_edge)
            .collect::<Parsed<_>>()?,
        call_expressions: pairs(field(record, "call_expressions")?)?,
        iterated_expressions: pairs(field(record, "iterated_expressions")?)?,
        unresolved: array(field(record, "unresolved")?)?
            .iter()
            .map(|entry| match array(entry)?.as_slice() {
                [caller, site, cause] => Ok(Unresolved {
                    caller: string(caller)?,
                    site: string(site)?,
                    cause: string(cause)?,
                }),
                _ => Err(format!("{entry} is not an unresolved call")),
            })
            .collect::<Parsed<_>>()?,
        external_callees: string_map(field(record, "external_callees")?)?,
    })
}

fn function(value: &Value) -> Parsed<FunctionDefinition> {
    let record = object(value)?;
    Ok(FunctionDefinition {
        name: string(field(record, "name")?)?,
        module: string(field(record, "module")?)?,
        lineno: number(field(record, "lineno")?)?,
        end_lineno: number(field(record, "end_lineno")?)?,
        col_offset: number(field(record, "col_offset")?)?,
        end_col_offset: number(field(record, "end_col_offset")?)?,
    })
}

fn class(value: &Value) -> Parsed<ClassDefinition> {
    let record = object(value)?;
    Ok(ClassDefinition {
        name: string(field(record, "name")?)?,
        module: string(field(record, "module")?)?,
        index: number(field(record, "index")?)?,
        lineno: number(field(record, "lineno")?)?,
        end_lineno: number(field(record, "end_lineno")?)?,
        unknown: flag(field(record, "unknown")?)?,
        mro: array(field(record, "mro")?)?
            .iter()
            .map(|base| match array(base)?.as_slice() {
                [analysed, name] => Ok(MroBase {
                    analysed: flag(analysed)?,
                    name: string(name)?,
                }),
                _ => Err(format!("{base} is not a base")),
            })
            .collect::<Parsed<_>>()?,
    })
}

fn site_edge(value: &Value) -> Parsed<SiteEdge> {
    match array(value)?.as_slice() {
        [caller, site, construct, callees] => Ok(SiteEdge {
            caller: string(caller)?,
            site: string(site)?,
            construct: match construct {
                Value::String(name) if name == "call" => Construct::Call,
                Value::String(name) if name == "decorator" => Construct::Decorator,
                Value::Array(parts) => Construct::Role(
                    parts
                        .iter()
                        .map(|part| match part {
                            Value::String(text) => RolePart::Text(text.clone()),
                            _ => RolePart::Other,
                        })
                        .collect(),
                ),
                other => return Err(format!("{other} is not a construct")),
            },
            callees: strings(callees)?,
        }),
        _ => Err(format!("{value} is not a site edge")),
    }
}
