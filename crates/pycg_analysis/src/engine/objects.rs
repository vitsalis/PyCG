use num_bigint::BigInt;
use pycg_solver::{KindMask, NodeId, ObjId};
use rustc_hash::FxHashSet;

use crate::engine::symbols::{Sym, Symbols};
use crate::model::{
    ConstValue, Signature, bound_method_name, constant_name, container_name, coroutine_name,
    generator_name,
};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Kind {
    Object,
    Module,
    External,
    UnknownExternal,
    Saturated,
    Typed,
    Function,
    Class,
    Instance,
    BoundMethod,
    ReturnsArgument,
    Closure,
    Fallback,
    Wrapper,
    BuiltinMethod,
    Const,
    Container,
    Super,
    Generator,
    Coroutine,
    TypeForm,
    Pattern,
}

impl Kind {
    pub fn name(self) -> &'static str {
        match self {
            Kind::Object => "Object",
            Kind::Module => "Module",
            Kind::External => "External",
            Kind::UnknownExternal => "UnknownExternal",
            Kind::Saturated => "Saturated",
            Kind::Typed => "Typed",
            Kind::Function => "Function",
            Kind::Class => "Class",
            Kind::Instance => "Instance",
            Kind::BoundMethod => "BoundMethod",
            Kind::ReturnsArgument => "ReturnsArgument",
            Kind::Closure => "Closure",
            Kind::Fallback => "Fallback",
            Kind::Wrapper => "Wrapper",
            Kind::BuiltinMethod => "BuiltinMethod",
            Kind::Const => "Const",
            Kind::Container => "Container",
            Kind::Super => "Super",
            Kind::Generator => "Generator",
            Kind::Coroutine => "Coroutine",
            Kind::TypeForm => "TypeForm",
            Kind::Pattern => "Pattern",
        }
    }

    pub fn mro(self) -> &'static [Kind] {
        match self {
            Kind::Object => &[Kind::Object],
            Kind::UnknownExternal => &[Kind::UnknownExternal, Kind::External, Kind::Object],
            Kind::Module => &[Kind::Module, Kind::Object],
            Kind::External => &[Kind::External, Kind::Object],
            Kind::Saturated => &[Kind::Saturated, Kind::Object],
            Kind::Typed => &[Kind::Typed, Kind::Object],
            Kind::Function => &[Kind::Function, Kind::Object],
            Kind::Class => &[Kind::Class, Kind::Object],
            Kind::Instance => &[Kind::Instance, Kind::Object],
            Kind::BoundMethod => &[Kind::BoundMethod, Kind::Object],
            Kind::ReturnsArgument => &[Kind::ReturnsArgument, Kind::Object],
            Kind::Closure => &[Kind::Closure, Kind::Object],
            Kind::Fallback => &[Kind::Fallback, Kind::Object],
            Kind::Wrapper => &[Kind::Wrapper, Kind::Object],
            Kind::BuiltinMethod => &[Kind::BuiltinMethod, Kind::Object],
            Kind::Const => &[Kind::Const, Kind::Object],
            Kind::Container => &[Kind::Container, Kind::Object],
            Kind::Super => &[Kind::Super, Kind::Object],
            Kind::Generator => &[Kind::Generator, Kind::Object],
            Kind::Coroutine => &[Kind::Coroutine, Kind::Object],
            Kind::TypeForm => &[Kind::TypeForm, Kind::Object],
            Kind::Pattern => &[Kind::Pattern, Kind::Object],
        }
    }

    pub fn bit(self) -> KindMask {
        1 << (self as u32)
    }

    pub fn mask(self) -> KindMask {
        self.mro().iter().fold(0, |mask, kind| mask | kind.bit())
    }
}

pub fn kinds_mask(kinds: &[Kind]) -> KindMask {
    kinds.iter().fold(0, |mask, kind| mask | kind.bit())
}

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub enum Literal {
    Str(Box<[u32]>),
    Bytes(Box<[u8]>),
    Int(BigInt),
}

impl Literal {
    pub fn view(&self) -> ConstValue<'_> {
        match self {
            Literal::Str(code_points) => ConstValue::Str(code_points),
            Literal::Bytes(bytes) => ConstValue::Bytes(bytes),
            Literal::Int(value) => ConstValue::Int(value),
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Passthrough {
    Name(Sym),
    Element(Sym, i64),
}

pub struct Module {
    pub name: Sym,
    pub defines: FxHashSet<Sym>,
}

pub struct External {
    pub name: Sym,
    pub steps: u32,
    pub inexact: bool,
}

pub struct Function {
    pub name: Sym,
    pub module: Sym,
    pub signature: Signature,
    pub parameters: Vec<(Sym, NodeId)>,
    pub defaults: Vec<(Sym, NodeId)>,
    pub optional: Vec<Sym>,
    pub return_node: NodeId,
    pub yield_node: Option<NodeId>,
    pub sent_node: Option<NodeId>,
    pub is_async: bool,
    pub varargs: Option<ObjId>,
    pub varkeywords: Option<ObjId>,
    pub passthrough: Vec<Passthrough>,
    pub decorated: bool,
    pub lineno: Option<u32>,
    pub col_offset: Option<u32>,
    pub end_lineno: Option<u32>,
    pub end_col_offset: Option<u32>,
}

impl Function {
    pub fn parameter(&self, name: Sym) -> NodeId {
        self.parameters
            .iter()
            .find(|&&(parameter, _)| parameter == name)
            .map(|&(_, node)| node)
            .expect("a parameter of the function")
    }
}

pub struct Container {
    pub kind: Sym,
    pub site: Sym,
    pub length: Option<u32>,
    pub exact: bool,
}

pub enum Object {
    Saturated,
    Module(Module),
    External(External),
    UnknownExternal(External),
    Function(Box<Function>),
    BoundMethod { receiver: ObjId, function: ObjId },
    Const { value: Literal, exact: bool },
    Container(Container),
    Generator { function: ObjId, exact: bool },
    Coroutine { function: ObjId, exact: bool },
}

impl Object {
    pub fn kind(&self) -> Kind {
        match self {
            Object::Saturated => Kind::Saturated,
            Object::Module(_) => Kind::Module,
            Object::External(_) => Kind::External,
            Object::UnknownExternal(_) => Kind::UnknownExternal,
            Object::Function(_) => Kind::Function,
            Object::BoundMethod { .. } => Kind::BoundMethod,
            Object::Const { .. } => Kind::Const,
            Object::Container(_) => Kind::Container,
            Object::Generator { .. } => Kind::Generator,
            Object::Coroutine { .. } => Kind::Coroutine,
        }
    }
}

#[derive(Default)]
pub struct Objects {
    objects: Vec<Object>,
}

impl Objects {
    pub fn push(&mut self, object: Object) -> ObjId {
        let id = ObjId(u32::try_from(self.objects.len()).expect("fewer than 2^32 objects"));
        self.objects.push(object);
        id
    }

    pub fn get(&self, id: ObjId) -> &Object {
        &self.objects[id.index()]
    }

    pub fn get_mut(&mut self, id: ObjId) -> &mut Object {
        &mut self.objects[id.index()]
    }

    pub fn function(&self, id: ObjId) -> &Function {
        match self.get(id) {
            Object::Function(function) => function,
            _ => panic!("object {id:?} is not a function"),
        }
    }

    pub fn function_mut(&mut self, id: ObjId) -> &mut Function {
        match self.get_mut(id) {
            Object::Function(function) => function,
            _ => panic!("object {id:?} is not a function"),
        }
    }

    pub fn name(&self, id: ObjId, symbols: &Symbols) -> String {
        match self.get(id) {
            Object::Saturated => "<saturated>".to_string(),
            Object::Module(module) => symbols.text(module.name).to_string(),
            Object::External(external) | Object::UnknownExternal(external) => {
                symbols.text(external.name).to_string()
            }
            Object::Function(function) => symbols.text(function.name).to_string(),
            Object::BoundMethod { receiver, function } => bound_method_name(
                &self.name(*function, symbols),
                &self.name(*receiver, symbols),
            ),
            Object::Const { value, .. } => constant_name(&value.view()),
            Object::Container(container) => {
                container_name(symbols.text(container.kind), symbols.text(container.site))
            }
            Object::Generator { function, .. } => generator_name(&self.name(*function, symbols)),
            Object::Coroutine { function, .. } => coroutine_name(&self.name(*function, symbols)),
        }
    }
}
