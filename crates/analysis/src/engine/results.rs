use std::collections::{BTreeMap, BTreeSet};

use indexmap::IndexMap;
use num_bigint::BigInt;
use pycg_solver::ObjId;

use crate::engine::attributes::AccessKind;
use crate::engine::containers::{IterationName, IterationRoleId};
use crate::engine::hierarchy::Unless;
use crate::engine::library::{LibraryRole, Position};
use crate::engine::objects::Object;
use crate::engine::outside_calls::Known;
use crate::engine::semantics::{Construct, Role};
use crate::engine::{Engine, Graph, State};
use crate::results::{
    AnalysisPart, ClassDefinition, Construct as DocumentConstruct, FunctionDefinition, MroBase,
    RolePart, SiteEdge, Unresolved,
};

const SATURATED: &str = "saturated";
const COMPUTED_NAME: &str = "computed name";
const OUTSIDE_VALUE: &str = "outside value";
const NO_VALUE: &str = "no value";

impl Engine {
    pub fn results(&mut self, modules: &[String]) -> AnalysisPart {
        self.state.analysis_part(&mut self.graph, modules)
    }
}

impl State {
    fn analysis_part(&mut self, graph: &mut Graph, modules: &[String]) -> AnalysisPart {
        AnalysisPart {
            cap: graph.cap().map(BigInt::from),
            functions: self
                .functions
                .iter()
                .map(|&id| self.function_definition(id))
                .collect(),
            classes: self
                .classes
                .iter()
                .map(|&id| self.class_definition(id))
                .collect(),
            fields: self.module_fields(graph, modules),
            site_edges: self
                .site_edges
                .iter()
                .map(|(&(caller, site, construct), callees)| {
                    let mut callees: Vec<String> = callees
                        .iter()
                        .map(|&name| self.text(name).to_owned())
                        .collect();
                    callees.sort();
                    SiteEdge {
                        caller: self.text(caller).to_owned(),
                        site: self.text(site).to_owned(),
                        construct: self.document_construct(construct),
                        callees,
                    }
                })
                .collect(),
            call_expressions: self
                .call_expressions
                .iter()
                .map(|&(caller, site, _)| {
                    (self.text(caller).to_owned(), self.text(site).to_owned())
                })
                .collect(),
            iterated_expressions: self
                .tables
                .iterated_expressions
                .iter()
                .map(|(caller, site)| (caller.to_string(), site.to_string()))
                .collect(),
            unresolved: self.unresolved_calls(graph),
            external_callees: self
                .external_callees
                .iter()
                .map(|(&name, known)| {
                    let known = match known {
                        Known::Stub => "stub",
                        Known::Name => "name",
                    };
                    (self.text(name).to_owned(), known.to_owned())
                })
                .collect(),
        }
    }

    fn text(&self, sym: crate::engine::symbols::Sym) -> &str {
        self.symbols.text(sym)
    }

    fn function_definition(&self, id: ObjId) -> FunctionDefinition {
        let function = self.objects.function(id);
        let position = |value: Option<u32>| u64::from(value.expect("a function has its position"));
        FunctionDefinition {
            name: self.text(function.name).to_owned(),
            module: self.text(function.module).to_owned(),
            lineno: position(function.lineno),
            end_lineno: position(function.end_lineno),
            col_offset: position(function.col_offset),
            end_col_offset: position(function.end_col_offset),
        }
    }

    fn class_definition(&self, id: ObjId) -> ClassDefinition {
        let class = self.objects.class(id);
        let position = |value: Option<u32>| u64::from(value.expect("a class has its lines"));
        ClassDefinition {
            name: self.text(class.name).to_owned(),
            module: self.text(class.module).to_owned(),
            index: u64::from(class.index),
            lineno: position(class.lineno),
            end_lineno: position(class.end_lineno),
            unknown: class.unknown,
            mro: self
                .class_mro(id)
                .into_iter()
                .map(|base| MroBase {
                    analysed: matches!(self.objects.get(base), Object::Class(_)),
                    name: self
                        .definition_name(base)
                        .expect("a base of an MRO is a class or an outside class"),
                })
                .collect(),
        }
    }

    fn definition_name(&self, id: ObjId) -> Option<String> {
        let name = match self.objects.get(id) {
            Object::Module(module) => module.name,
            Object::Class(class) => class.name,
            Object::Function(function) => function.name,
            Object::External(external) | Object::UnknownExternal(external) => external.name,
            _ => return None,
        };
        Some(self.text(name).to_owned())
    }

    fn module_fields(
        &self,
        graph: &mut Graph,
        modules: &[String],
    ) -> BTreeMap<String, BTreeMap<String, Vec<String>>> {
        let mut found = BTreeMap::new();
        for (&name, &module) in &self.modules {
            if !modules.iter().any(|listed| listed == self.text(name)) {
                continue;
            }
            let Object::Module(object) = self.objects.get(module) else {
                unreachable!("a module of the program is a module object")
            };
            let fields = self.fields.get(&module);
            let mut attributes = BTreeMap::new();
            for &attribute in &object.defines {
                let held: BTreeSet<String> = fields
                    .and_then(|fields| fields.get(&attribute))
                    .map(|&node| graph.objects(node))
                    .unwrap_or_default()
                    .into_iter()
                    .filter_map(|held| self.definition_name(held))
                    .collect();
                attributes.insert(self.text(attribute).to_owned(), held.into_iter().collect());
            }
            if !attributes.is_empty() {
                found.insert(self.text(name).to_owned(), attributes);
            }
        }
        found
    }

    fn document_construct(&self, construct: Construct) -> DocumentConstruct {
        let text = |value: &str| RolePart::Text(value.to_owned());
        let named = |role: &str, sym| vec![text(role), RolePart::Text(self.text(sym).to_owned())];
        let accessed = |role: &str, kind: AccessKind, sym| {
            vec![
                text(role),
                text(kind.name()),
                RolePart::Text(self.text(sym).to_owned()),
            ]
        };
        match construct {
            Construct::Call => DocumentConstruct::Call,
            Construct::Decorator => DocumentConstruct::Decorator,
            Construct::Named(name) => DocumentConstruct::Role(vec![text(name)]),
            Construct::Role(role) => DocumentConstruct::Role(match role {
                Role::SetName(name) => named("set_name", name),
                Role::Getattr(kind, name) => accessed("getattr", kind, name),
                Role::Hook(kind, name) => accessed("hook", kind, name),
                Role::Accessor(kind, name) => accessed("accessor", kind, name),
                Role::ClassGet(name) => named("class get", name),
                Role::ModuleGetattr(name) => named("module getattr", name),
                Role::Protocol(name) => named("protocol", name),
                Role::Property(kind, accessor) => accessed("property", kind, accessor),
                Role::NamedLoad => vec![text("named load")],
                Role::Hash => vec![text("hash")],
                Role::HashEq => vec![text("hash_eq")],
                Role::Subscript(name) => named("subscript", name),
                Role::SubscriptFactory => vec![text("subscript"), text("factory")],
                Role::Iterate(id) => vec![text("iterate"), self.iteration_role(id)],
                Role::Index(id) => vec![text("index"), self.iteration_role(id)],
                Role::Callable(id) => vec![text("callable"), self.iteration_role(id)],
                Role::Map(width, rest) => vec![
                    text("map"),
                    RolePart::Number(i64::from(width)),
                    RolePart::Flag(rest),
                ],
                Role::Filter => vec![text("filter")],
                Role::Reversed => vec![text("reversed")],
                Role::ReversedLen => vec![text("reversed"), text("len")],
                Role::ReversedItem => vec![text("reversed"), text("item")],
                Role::Operator(method, is_left) => vec![
                    text("operator"),
                    RolePart::Text(self.text(method).to_owned()),
                    RolePart::Flag(is_left),
                ],
                Role::Compare(side) => named("compare", side),
                Role::Truth => vec![text("truth")],
                Role::Convert(kind) => named("convert", kind),
                Role::Format => vec![text("format")],
                Role::Await => vec![text("await")],
                Role::Enter => vec![text("enter")],
                Role::Exit => vec![text("exit")],
                Role::Raise => vec![text("raise")],
                Role::Special(name) => named("special", name),
                Role::TypeMetaclass => vec![text("type"), text("metaclass")],
                Role::CallBack => vec![text("call back")],
                Role::Key => vec![text("key")],
                Role::SequenceKey => vec![text("key"), text("sequence")],
                Role::LibraryKey(path) => named("key", path),
                Role::MergeKey(path) => vec![
                    text("iterate"),
                    text("key"),
                    RolePart::Text(self.text(path).to_owned()),
                ],
            }),
        }
    }

    fn iteration_role(&self, id: IterationRoleId) -> RolePart {
        let (role, is_async, unless) = self.containers.iteration_role(id);
        let unless = match unless {
            Unless::Nothing => Vec::new(),
            Unless::Names(names) => names
                .iter()
                .map(|&name| RolePart::Text(self.text(name).to_owned()))
                .collect(),
            other => vec![RolePart::Text(sentinel(other).to_owned())],
        };
        let role = match role {
            IterationName::Plain(role) => RolePart::Text(self.text(role).to_owned()),
            IterationName::Library(role) => library_role(role),
        };
        RolePart::Parts(vec![
            role,
            RolePart::Flag(is_async),
            RolePart::Parts(unless),
        ])
    }

    fn unresolved_calls(&mut self, graph: &mut Graph) -> Vec<Unresolved> {
        let resolved: BTreeSet<_> = self
            .site_edges
            .keys()
            .filter(|(_, _, construct)| *construct == Construct::Call)
            .map(|&(caller, site, _)| (caller, site))
            .collect();
        let computed = self.computed_name_nodes(graph);
        let mut causes: IndexMap<_, &'static str> = IndexMap::new();
        for &(caller, site, callee) in &self.call_expressions.clone() {
            if resolved.contains(&(caller, site)) {
                continue;
            }
            let objects = callee.map(|node| graph.objects(node)).unwrap_or_default();
            let known_opaque = objects
                .iter()
                .filter(|&&object| object != self.unknown_external)
                .all(|&object| self.opaque(object));
            if !known_opaque {
                continue;
            }
            let cause = if objects.iter().any(|&object| self.opaque(object)) {
                SATURATED
            } else if callee.is_some_and(|node| computed.contains(&node)) {
                COMPUTED_NAME
            } else if !objects.is_empty() {
                OUTSIDE_VALUE
            } else {
                NO_VALUE
            };
            causes.insert((caller, site), cause);
        }
        causes
            .into_iter()
            .map(|((caller, site), cause)| Unresolved {
                caller: self.text(caller).to_owned(),
                site: self.text(site).to_owned(),
                cause: cause.to_owned(),
            })
            .collect()
    }
}

fn sentinel(unless: &Unless) -> &'static str {
    match unless {
        Unless::Explicit => "<explicit>",
        Unless::PythonsOwn => "<python's own>",
        Unless::DescriptorItself => "<the descriptor itself>",
        Unless::DefaultMember => "<the default>",
        Unless::NewGivesTheClass => "<a __new__ that gives the class>",
        Unless::DescriptorDecides => "<a descriptor decides>",
        Unless::DataDescriptor => "<a data descriptor>",
        Unless::MayDerive => "<may derive>",
        Unless::MayLack => "<may lack>",
        Unless::MayLackMethod => "<may lack the method>",
        Unless::NotNominal => "<not nominal>",
        Unless::Nothing | Unless::Names(_) => unreachable!("an unless of names is its names"),
    }
}

fn library_role(role: LibraryRole) -> RolePart {
    let text = |value: &str| RolePart::Text(value.to_owned());
    let position = |position: Position| match position {
        Position::At(index) => RolePart::Number(i64::from(index)),
        Position::Unknown => text("*"),
    };
    let again = |again: bool| again.then(|| text("again"));
    RolePart::Parts(match role {
        LibraryRole::Tag {
            path,
            position: at,
            again: twice,
        } => {
            let mut tag = vec![text(path), position(at)];
            tag.extend(again(twice));
            vec![text("library"), RolePart::Parts(tag)]
        }
        LibraryRole::Position {
            position: at,
            again: twice,
        } => {
            let mut parts = vec![text("library"), position(at)];
            parts.extend(again(twice));
            parts
        }
        LibraryRole::Inner => vec![text("library"), text("inner")],
        LibraryRole::Bundle => vec![text("library"), text("bundle")],
    })
}
