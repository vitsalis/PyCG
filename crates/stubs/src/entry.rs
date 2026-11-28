use std::collections::BTreeMap;
use std::fmt;

use serde_json::{Map, Value};

pub type Names = BTreeMap<Box<str>, EntryId>;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct EntryId(pub(crate) u32);

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct ModuleId(pub(crate) u32);

#[derive(Debug)]
pub struct Module {
    pub names: Names,
    pub all: Option<Box<[Box<str>]>>,
}

#[derive(Debug)]
pub enum Entry {
    Function(Function),
    Class(Class),
    Property(Property),
    Variable(Variable),
    Reference(Reference),
}

#[derive(Debug)]
pub struct Function {
    pub signatures: Box<[Signature]>,
    pub decorator: Option<Decorator>,
    pub abstract_: bool,
    pub also: Box<[Target]>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Decorator {
    ClassMethod,
    StaticMethod,
}

#[derive(Debug)]
pub struct Signature {
    pub parameters: Box<[Parameter]>,
    pub result: Type,
    pub coroutine: bool,
}

#[derive(Debug)]
pub struct Parameter {
    pub name: Box<str>,
    pub kind: ParameterKind,
    pub has_default: bool,
    pub annotation: Type,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ParameterKind {
    PositionalOnly,
    PositionalOrKeyword,
    VarPositional,
    KeywordOnly,
    VarKeyword,
}

#[derive(Debug)]
pub struct Class {
    pub bases: Box<[Type]>,
    pub members: Names,
    pub type_parameters: Box<[Box<str>]>,
    pub protocol: bool,
    pub final_: bool,
    pub type_check_only: bool,
    pub metaclass: Option<Type>,
    pub public_name: Option<Box<str>>,
    pub also: Box<[Target]>,
}

#[derive(Debug)]
pub struct Property {
    pub annotation: Type,
    pub setter: bool,
    pub abstract_: bool,
}

#[derive(Debug)]
pub struct Variable {
    pub annotation: Type,
    pub also: Box<[Target]>,
}

#[derive(Debug)]
pub struct Reference {
    pub to: Box<[Target]>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Target {
    pub module: Box<str>,
    pub qualname: Box<str>,
}

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub enum Type {
    Unknown,
    Class(Box<str>),
    Literal(Box<str>, Box<[LiteralValue]>),
    None,
    SelfType,
    Ellipsis,
    Generic(Box<str>, Box<[Type]>),
    Union(Box<[Type]>),
    TypeOf(Box<Type>),
    Callable {
        result: Box<Type>,
        parameters: Option<Box<[Type]>>,
    },
    Variable {
        name: Box<str>,
        bound: Option<Box<Type>>,
        constrained: bool,
    },
}

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub enum LiteralValue {
    Str(Box<str>),
    Int(i128),
}

impl Type {
    pub fn from_json(value: &Value) -> Result<Type, SchemaError> {
        decode_type(value, "type")
    }
}

impl Entry {
    pub fn to(&self) -> &[Target] {
        match self {
            Entry::Reference(reference) => &reference.to,
            _ => &[],
        }
    }

    pub fn also(&self) -> &[Target] {
        match self {
            Entry::Function(function) => &function.also,
            Entry::Class(class) => &class.also,
            Entry::Variable(variable) => &variable.also,
            Entry::Property(_) | Entry::Reference(_) => &[],
        }
    }

    pub fn is_abstract(&self) -> bool {
        match self {
            Entry::Function(function) => function.abstract_,
            Entry::Property(property) => property.abstract_,
            Entry::Class(_) | Entry::Variable(_) | Entry::Reference(_) => false,
        }
    }
}

const TYPE_NONE: &str = "*none";
const TYPE_SELF: &str = "*self";
const TYPE_ELLIPSIS: &str = "...";
const TYPE_UNION: &str = "|";
const TYPE_TYPE: &str = "*type";
const TYPE_CALL: &str = "*call";
const TYPE_VARIABLE: &str = "*var";
const TYPE_LITERAL: &str = "*lit";
const TYPE_VARIABLE_CONSTRAINED: &str = "c";
const SPECIAL_PREFIX: char = '*';

pub fn class_names(reduced: &Type) -> Vec<&str> {
    let mut names = Vec::new();
    let mut pending = vec![reduced];
    while let Some(current) = pending.pop() {
        match current {
            Type::Class(path) | Type::Literal(path, _) | Type::Generic(path, _) => {
                names.push(&**path)
            }
            Type::Ellipsis => names.push(TYPE_ELLIPSIS),
            Type::Union(arms) => pending.extend(arms.iter().rev()),
            Type::Unknown
            | Type::None
            | Type::SelfType
            | Type::TypeOf(_)
            | Type::Callable { .. }
            | Type::Variable { .. } => {}
        }
    }
    names
}

#[derive(Debug)]
pub struct SchemaError {
    pub location: String,
    pub problem: String,
}

impl fmt::Display for SchemaError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(formatter, "{}: {}", self.location, self.problem)
    }
}

pub(crate) struct Decoder<'a> {
    pub entries: &'a mut Vec<Entry>,
    pub modules: &'a mut Vec<Module>,
}

type Decoded<T> = Result<T, SchemaError>;

fn error<T>(location: &str, problem: impl Into<String>) -> Decoded<T> {
    Err(SchemaError {
        location: location.to_owned(),
        problem: problem.into(),
    })
}

fn object<'v>(value: &'v Value, location: &str) -> Decoded<&'v Map<String, Value>> {
    match value {
        Value::Object(map) => Ok(map),
        _ => error(location, "not an object"),
    }
}

fn array<'v>(value: &'v Value, location: &str) -> Decoded<&'v [Value]> {
    match value {
        Value::Array(items) => Ok(items),
        _ => error(location, "not an array"),
    }
}

fn string<'v>(value: &'v Value, location: &str) -> Decoded<&'v str> {
    match value {
        Value::String(text) => Ok(text),
        _ => error(location, "not a string"),
    }
}

fn required<'v>(map: &'v Map<String, Value>, key: &str, location: &str) -> Decoded<&'v Value> {
    match map.get(key) {
        Some(value) => Ok(value),
        None => error(location, format!("no key {key:?}")),
    }
}

fn flag(map: &Map<String, Value>, key: &str, location: &str) -> Decoded<bool> {
    match map.get(key) {
        None => Ok(false),
        Some(Value::Bool(value)) => Ok(*value),
        Some(Value::Number(number)) => match number.as_u64() {
            Some(0) => Ok(false),
            Some(1) => Ok(true),
            _ => error(location, format!("{key:?} is not 0 or 1")),
        },
        Some(_) => error(location, format!("{key:?} is not a flag")),
    }
}

fn known_keys(map: &Map<String, Value>, keys: &[&str], location: &str) -> Decoded<()> {
    for key in map.keys() {
        if !keys.contains(&key.as_str()) {
            return error(location, format!("unknown key {key:?}"));
        }
    }
    Ok(())
}

fn strings(value: &Value, location: &str) -> Decoded<Box<[Box<str>]>> {
    array(value, location)?
        .iter()
        .map(|item| string(item, location).map(Box::from))
        .collect()
}

impl Decoder<'_> {
    pub fn package(&mut self, value: &Value, top: &str) -> Decoded<BTreeMap<Box<str>, ModuleId>> {
        let map = object(value, top)?;
        known_keys(map, &["modules"], top)?;
        let mut modules = BTreeMap::new();
        for (name, module) in object(required(map, "modules", top)?, top)? {
            let id = self.module(module, name)?;
            modules.insert(Box::from(name.as_str()), id);
        }
        Ok(modules)
    }

    fn module(&mut self, value: &Value, location: &str) -> Decoded<ModuleId> {
        let map = object(value, location)?;
        known_keys(map, &["names", "all"], location)?;
        let names = self.names(required(map, "names", location)?, location)?;
        let all = match map.get("all") {
            None => None,
            Some(all) => Some(strings(all, location)?),
        };
        let id = ModuleId(u32::try_from(self.modules.len()).expect("module count fits u32"));
        self.modules.push(Module { names, all });
        Ok(id)
    }

    fn names(&mut self, value: &Value, location: &str) -> Decoded<Names> {
        let mut names = Names::new();
        for (name, entry) in object(value, location)? {
            let id = self.entry(entry, &format!("{location}.{name}"))?;
            names.insert(Box::from(name.as_str()), id);
        }
        Ok(names)
    }

    fn entry(&mut self, value: &Value, location: &str) -> Decoded<EntryId> {
        let map = object(value, location)?;
        let entry = match string(required(map, "k", location)?, location)? {
            "f" => {
                known_keys(map, &["k", "s", "d", "x", "also"], location)?;
                Entry::Function(Function {
                    signatures: array(required(map, "s", location)?, location)?
                        .iter()
                        .map(|signature| decode_signature(signature, location))
                        .collect::<Decoded<_>>()?,
                    decorator: match map.get("d") {
                        None => None,
                        Some(value) => Some(match string(value, location)? {
                            "classmethod" => Decorator::ClassMethod,
                            "staticmethod" => Decorator::StaticMethod,
                            other => return error(location, format!("decorator {other:?}")),
                        }),
                    },
                    abstract_: flag(map, "x", location)?,
                    also: targets(map.get("also"), location)?,
                })
            }
            "c" => {
                known_keys(
                    map,
                    &[
                        "k", "b", "m", "tp", "proto", "final", "tco", "meta", "pub", "also",
                    ],
                    location,
                )?;
                Entry::Class(Class {
                    bases: array(required(map, "b", location)?, location)?
                        .iter()
                        .map(|base| decode_type(base, location))
                        .collect::<Decoded<_>>()?,
                    members: self.names(required(map, "m", location)?, location)?,
                    type_parameters: match map.get("tp") {
                        None => Box::new([]),
                        Some(value) => strings(value, location)?,
                    },
                    protocol: flag(map, "proto", location)?,
                    final_: flag(map, "final", location)?,
                    type_check_only: flag(map, "tco", location)?,
                    metaclass: match map.get("meta") {
                        None => None,
                        Some(value) => Some(decode_type(value, location)?),
                    },
                    public_name: match map.get("pub") {
                        None => None,
                        Some(value) => Some(Box::from(string(value, location)?)),
                    },
                    also: targets(map.get("also"), location)?,
                })
            }
            "p" => {
                known_keys(map, &["k", "t", "set", "x"], location)?;
                Entry::Property(Property {
                    annotation: decode_type(required(map, "t", location)?, location)?,
                    setter: flag(map, "set", location)?,
                    abstract_: flag(map, "x", location)?,
                })
            }
            "v" => {
                known_keys(map, &["k", "t", "also"], location)?;
                Entry::Variable(Variable {
                    annotation: decode_type(required(map, "t", location)?, location)?,
                    also: targets(map.get("also"), location)?,
                })
            }
            "r" => {
                known_keys(map, &["k", "to"], location)?;
                Entry::Reference(Reference {
                    to: targets(Some(required(map, "to", location)?), location)?,
                })
            }
            other => return error(location, format!("kind {other:?}")),
        };
        let id = EntryId(u32::try_from(self.entries.len()).expect("entry count fits u32"));
        self.entries.push(entry);
        Ok(id)
    }
}

fn targets(value: Option<&Value>, location: &str) -> Decoded<Box<[Target]>> {
    let Some(value) = value else {
        return Ok(Box::new([]));
    };
    array(value, location)?
        .iter()
        .map(|target| match array(target, location)? {
            [module, qualname] => Ok(Target {
                module: Box::from(string(module, location)?),
                qualname: Box::from(string(qualname, location)?),
            }),
            _ => error(location, "a target is not [module, qualified name]"),
        })
        .collect()
}

fn decode_signature(value: &Value, location: &str) -> Decoded<Signature> {
    let map = object(value, location)?;
    known_keys(map, &["p", "r", "a"], location)?;
    Ok(Signature {
        parameters: array(required(map, "p", location)?, location)?
            .iter()
            .map(|parameter| decode_parameter(parameter, location))
            .collect::<Decoded<_>>()?,
        result: decode_type(required(map, "r", location)?, location)?,
        coroutine: flag(map, "a", location)?,
    })
}

fn decode_parameter(value: &Value, location: &str) -> Decoded<Parameter> {
    let [name, kind, default, annotation] = array(value, location)? else {
        return error(location, "a parameter is not [name, kind, default, type]");
    };
    Ok(Parameter {
        name: Box::from(string(name, location)?),
        kind: match string(kind, location)? {
            "/" => ParameterKind::PositionalOnly,
            "" => ParameterKind::PositionalOrKeyword,
            "*" => ParameterKind::VarPositional,
            "k" => ParameterKind::KeywordOnly,
            "**" => ParameterKind::VarKeyword,
            other => return error(location, format!("parameter kind {other:?}")),
        },
        has_default: match default.as_u64() {
            Some(0) => false,
            Some(1) => true,
            _ => return error(location, "a parameter default is not 0 or 1"),
        },
        annotation: decode_type(annotation, location)?,
    })
}

enum Pending<'v> {
    Decode(&'v Value),
    Build(&'v [Value], usize),
}

fn decode_type(value: &Value, location: &str) -> Decoded<Type> {
    let mut pending = vec![Pending::Decode(value)];
    let mut built: Vec<Type> = Vec::new();
    while let Some(step) = pending.pop() {
        match step {
            Pending::Decode(value) => match value {
                Value::Null => built.push(Type::Unknown),
                Value::String(text) => built.push(simple_type(text, location)?),
                Value::Array(items) => {
                    let children = type_children(items, location)?;
                    pending.push(Pending::Build(items, built.len()));
                    for child in children.iter().rev() {
                        pending.push(Pending::Decode(child));
                    }
                }
                _ => return error(location, "a type is not null, a string or a list"),
            },
            Pending::Build(items, start) => {
                let children: Vec<Type> = built.drain(start..).collect();
                built.push(compound_type(items, children, location)?);
            }
        }
    }
    let [single] = <[Type; 1]>::try_from(built).expect("one type decoded");
    Ok(single)
}

fn literal_value(value: &Value, location: &str) -> Decoded<LiteralValue> {
    match value {
        Value::String(text) => Ok(LiteralValue::Str(Box::from(text.as_str()))),
        Value::Number(number) => match number
            .as_i64()
            .map(i128::from)
            .or_else(|| number.as_u64().map(i128::from))
        {
            Some(value) => Ok(LiteralValue::Int(value)),
            None => error(location, format!("literal {number} is not an int")),
        },
        _ => error(location, "a literal is not a string or an int"),
    }
}

fn simple_type(text: &str, location: &str) -> Decoded<Type> {
    Ok(match text {
        TYPE_NONE => Type::None,
        TYPE_SELF => Type::SelfType,
        TYPE_ELLIPSIS => Type::Ellipsis,
        _ if text.starts_with(SPECIAL_PREFIX) => {
            return error(location, format!("type {text:?}"));
        }
        _ => Type::Class(Box::from(text)),
    })
}

fn type_children<'v>(items: &'v [Value], location: &str) -> Decoded<Vec<&'v Value>> {
    let Some((head, rest)) = items.split_first() else {
        return error(location, "an empty type list");
    };
    let head = string(head, location)?;
    Ok(match head {
        TYPE_UNION => rest.iter().collect(),
        TYPE_TYPE => match rest {
            [argument] => vec![argument],
            _ => return error(location, "*type takes one type"),
        },
        TYPE_CALL => match rest {
            [result, Value::Null] => vec![result],
            [result, Value::Array(parameters)] => {
                let mut children = vec![result];
                children.extend(parameters.iter());
                children
            }
            _ => return error(location, "*call takes a result and parameters"),
        },
        TYPE_VARIABLE => match rest {
            [Value::String(_)] => vec![],
            [Value::String(_), bound] => vec![bound],
            [Value::String(_), constraints, Value::String(marker)]
                if marker == TYPE_VARIABLE_CONSTRAINED =>
            {
                vec![constraints]
            }
            _ => return error(location, "*var takes a name and a bound or constraints"),
        },
        TYPE_LITERAL => match rest {
            [Value::String(_), Value::Array(_)] => vec![],
            _ => return error(location, "*lit takes a class and values"),
        },
        _ if head.starts_with(SPECIAL_PREFIX) => {
            return error(location, format!("type list {head:?}"));
        }
        _ => rest.iter().collect(),
    })
}

fn compound_type(items: &[Value], children: Vec<Type>, location: &str) -> Decoded<Type> {
    let head = string(&items[0], location)?;
    let mut children = children.into_iter();
    Ok(match head {
        TYPE_UNION => Type::Union(children.collect()),
        TYPE_TYPE => Type::TypeOf(Box::new(children.next().expect("the *type argument"))),
        TYPE_CALL => {
            let result = Box::new(children.next().expect("the *call result"));
            let parameters = match &items[2] {
                Value::Null => None,
                _ => Some(children.collect()),
            };
            Type::Callable { result, parameters }
        }
        TYPE_VARIABLE => {
            let name = Box::from(string(&items[1], location)?);
            let bound = children.next().map(Box::new);
            Type::Variable {
                name,
                bound,
                constrained: items.len() == 4,
            }
        }
        TYPE_LITERAL => {
            let class = Box::from(string(&items[1], location)?);
            let Value::Array(values) = &items[2] else {
                unreachable!("*lit values are a list");
            };
            let values = values
                .iter()
                .map(|value| literal_value(value, location))
                .collect::<Decoded<_>>()?;
            Type::Literal(class, values)
        }
        _ => Type::Generic(Box::from(head), children.collect()),
    })
}
