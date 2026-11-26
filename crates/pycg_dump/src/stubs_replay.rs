use std::io::{self, BufWriter, Write};
use std::process::ExitCode;

use pycg_stubs::{Definition, DefinitionKind, Stubs};
use serde_json::{Map, Value, json};

const EXIT_FAILURE: u8 = 1;

pub fn run(path: &str) -> ExitCode {
    let text = match std::fs::read_to_string(path) {
        Ok(text) => text,
        Err(error) => {
            eprintln!("pycg_dump: cannot read {path}: {error}");
            return ExitCode::from(EXIT_FAILURE);
        }
    };
    let mut stubs = Stubs::new();
    let mut out = BufWriter::new(io::stdout().lock());
    for (index, line) in text.lines().enumerate() {
        let record = match replay(&mut stubs, line) {
            Ok(record) => record,
            Err(problem) => {
                eprintln!("pycg_dump: {path}:{}: {problem}", index + 1);
                return ExitCode::from(EXIT_FAILURE);
            }
        };
        if let Err(error) = writeln!(out, "{}", python_json(&record)) {
            eprintln!("pycg_dump: cannot write: {error}");
            return ExitCode::from(EXIT_FAILURE);
        }
    }
    if let Err(error) = out.flush() {
        eprintln!("pycg_dump: cannot write: {error}");
        return ExitCode::from(EXIT_FAILURE);
    }
    ExitCode::SUCCESS
}

fn replay(stubs: &mut Stubs, line: &str) -> Result<Value, String> {
    let record: Value = serde_json::from_str(line).map_err(|error| error.to_string())?;
    let call = record["call"].as_str().ok_or("no call")?;
    let args = record["args"].as_array().ok_or("no args")?;
    let answer = answer(stubs, call, args)?;
    Ok(json!({"call": call, "args": args, "answer": answer}))
}

fn text(args: &[Value], index: usize) -> Result<&str, String> {
    args.get(index)
        .and_then(Value::as_str)
        .ok_or_else(|| format!("argument {index} is not a string"))
}

fn answer(stubs: &mut Stubs, call: &str, args: &[Value]) -> Result<Value, String> {
    Ok(match call {
        "module" => match stubs.module(text(args, 0)?) {
            None => Value::Null,
            Some(id) => {
                let module = stubs.module_data(id);
                json!({
                    "names": module.names.keys().map(|name| &**name).collect::<Vec<_>>(),
                    "all": module.all.as_ref().map(|all| all.iter().map(|name| &**name).collect::<Vec<_>>()),
                })
            }
        },
        "find" => definitions(&stubs.find(text(args, 0)?)),
        "attribute" => {
            let definition = argument_definition(stubs, args.first())?;
            definitions(&stubs.attribute(&definition, text(args, 1)?))
        }
        "metaclass_member" => definitions(&stubs.metaclass_member(text(args, 0)?, text(args, 1)?)),
        "metaclass" => json!(&*stubs.metaclass(text(args, 0)?)),
        "member" => definitions(&stubs.member(text(args, 0)?, text(args, 1)?)),
        "definition" => match stubs.definition(text(args, 0)?) {
            None => Value::Null,
            Some(found) => definition(&found),
        },
        "mro" => names(stubs.mro(text(args, 0)?).iter()),
        "abstract" => json!(stubs.is_abstract(text(args, 0)?)),
        "abstract_reach" => names(stubs.abstract_reach(text(args, 0)?).iter()),
        "abc_name" => json!(stubs.abc_name(text(args, 0)?).as_deref()),
        "public_name" => json!(&*stubs.public_name(text(args, 0)?)),
        other => return Err(format!("unknown call {other:?}")),
    })
}

fn names<'a>(items: impl Iterator<Item = &'a Box<str>>) -> Value {
    Value::Array(items.map(|name| Value::from(&**name)).collect())
}

fn definition(found: &Definition) -> Value {
    json!({"kind": found.kind.name(), "path": &*found.path, "owner": found.owner.as_deref()})
}

fn definitions(found: &[Definition]) -> Value {
    Value::Array(found.iter().map(definition).collect())
}

fn argument_definition(stubs: &mut Stubs, value: Option<&Value>) -> Result<Definition, String> {
    let map: &Map<String, Value> = value
        .and_then(Value::as_object)
        .ok_or("argument 0 is not a definition")?;
    let kind = map.get("kind").and_then(Value::as_str).ok_or("no kind")?;
    let path = map.get("path").and_then(Value::as_str).ok_or("no path")?;
    let owner = map.get("owner").and_then(Value::as_str);
    let found = if kind == DefinitionKind::Module.name() {
        Some(Definition {
            kind: DefinitionKind::Module,
            path: Box::from(path),
            entry: None,
            owner: None,
        })
    } else {
        stubs.definition(path)
    };
    match found {
        Some(found) if found.kind.name() == kind && found.owner.as_deref() == owner => Ok(found),
        _ => Err(format!("the definition {kind} {path} is not in the stubs")),
    }
}

fn python_json(value: &Value) -> String {
    let compact = value.to_string();
    let mut out = String::with_capacity(compact.len());
    for character in compact.chars() {
        if character.is_ascii() {
            out.push(character);
            continue;
        }
        let mut units = [0u16; 2];
        for unit in character.encode_utf16(&mut units) {
            out.push_str(&format!("\\u{unit:04x}"));
        }
    }
    out
}
