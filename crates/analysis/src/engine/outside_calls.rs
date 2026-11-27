use std::sync::Arc;

use pycg_solver::{NodeId, ObjId};
use pycg_stubs::{Decorator, Definition, DefinitionKind, Entry, ParameterKind, Type};
use rustc_hash::FxHashMap;

use crate::engine::hierarchy::{LookupAttr, LookupKey, Unless};
use crate::engine::library::deferred_result;
use crate::engine::objects::{Container, Function, Literal, Object};
use crate::engine::outside::outside_name;
use crate::engine::outside_types::TypeContext;
use crate::engine::rules::Rule;
use crate::engine::semantics::{Call, CallId, GroupId, Prefix, Role, SiteKey};
use crate::engine::symbols::Sym;
use crate::engine::trace::Trace;
use crate::engine::{Graph, OrderedMap, State, not_ported};
use crate::model::Signature;
use crate::models::{
    CACHED_FUNCTIONS, CALLS_BACK, CLOSURES, CONTAINER_CLASSES, HASHED_ARGUMENTS, KEY_WRAPPERS,
    KEYED_SEQUENCES, LENGTH_HINTS, LIBRARY_ITERATION, OPENERS, REFLECTION_CALLS, RETURNS_ARGUMENT,
    SPECIAL_METHOD_CALLS, function_model, lookup,
};

const STUB_BUILTINS_PREFIX: &str = "builtins.";
const OBJECT: &str = "builtins.object";
const SUBCLASSES: &str = "builtins.type.__subclasses__";
const METHOD_TYPE: &str = "types.MethodType";
const ORDERING_COMPARISON_BY_BUILTIN: &[(&str, &str)] = &[
    ("builtins.sorted", "__lt__"),
    ("builtins.list.sort", "__lt__"),
    ("builtins.min", "__lt__"),
    ("builtins.max", "__gt__"),
];
const ABSTRACT_ITERABLE_TYPES: &[&str] =
    &["typing.Iterable", "typing.Iterator", "typing.Collection"];

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct BoundId(u32);

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct PlanId(u32);

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Known {
    Stub,
    Name,
}

#[derive(Clone, Debug)]
pub struct Param {
    pub(crate) name: Box<str>,
    pub(crate) kind: ParameterKind,
    has_default: bool,
    pub(crate) annotation: Type,
}

#[derive(Clone, Debug)]
pub struct TypedResult {
    reduced: Type,
    bound: BoundId,
    parameters: Arc<[Param]>,
}

pub enum Bound {
    Late {
        call: CallId,
        signature: Signature,
        since: u32,
        supplied: Vec<Box<str>>,
        constants: Vec<(Box<str>, NodeId)>,
        nodes: FxHashMap<Box<str>, NodeId>,
    },
    Full {
        function: ObjId,
        supplied: Vec<Sym>,
        possible: Vec<Sym>,
    },
}

#[derive(Clone)]
pub(super) struct Overload {
    pub(super) parameters: Arc<[Param]>,
    pub(super) bound: BoundId,
}

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
enum ArgumentKey {
    Position(usize),
    Named(u8, Box<str>),
}

fn builtin_function_model(name: &str, steps: u32) -> Option<&'static crate::models::Model> {
    let rest = name.strip_prefix("<builtin>.")?;
    if steps > 1 {
        return None;
    }
    function_model(rest)
}

fn group_excluded(path: &str) -> bool {
    path == METHOD_TYPE
        || path == SUBCLASSES
        || lookup(CONTAINER_CLASSES, path).is_some()
        || lookup(HASHED_ARGUMENTS, path).is_some()
        || lookup(ORDERING_COMPARISON_BY_BUILTIN, path).is_some()
        || lookup(CALLS_BACK, path).is_some()
        || lookup(LENGTH_HINTS, path).is_some()
        || lookup(LIBRARY_ITERATION, path).is_some()
        || OPENERS.contains(&path)
        || lookup(CLOSURES, path).is_some()
        || lookup(REFLECTION_CALLS, path).is_some()
        || lookup(SPECIAL_METHOD_CALLS, path).is_some()
}

fn positional_kind(kind: ParameterKind) -> bool {
    matches!(
        kind,
        ParameterKind::PositionalOnly | ParameterKind::PositionalOrKeyword
    )
}

fn stub_signature(parameters: &[Param]) -> Signature {
    let positional: Vec<Box<str>> = parameters
        .iter()
        .filter(|parameter| positional_kind(parameter.kind))
        .map(|parameter| parameter.name.clone())
        .collect();
    let positional_only = parameters
        .iter()
        .filter(|parameter| parameter.kind == ParameterKind::PositionalOnly)
        .count();
    let named = |kind: ParameterKind| {
        parameters
            .iter()
            .find(|parameter| parameter.kind == kind)
            .map(|parameter| parameter.name.clone())
    };
    Signature::new(
        positional,
        positional_only,
        parameters
            .iter()
            .filter(|parameter| parameter.kind == ParameterKind::KeywordOnly)
            .map(|parameter| parameter.name.clone())
            .collect(),
        named(ParameterKind::VarPositional),
        named(ParameterKind::VarKeyword),
    )
}

fn arms(reduced: &Type) -> Vec<&Type> {
    match reduced {
        Type::Union(arms) => arms.iter().collect(),
        _ => vec![reduced],
    }
}

fn callable(reduced: &Type) -> bool {
    arms(reduced)
        .into_iter()
        .any(|arm| matches!(arm, Type::Callable { .. }))
}

pub(super) fn abstract_iterable(reduced: &Type) -> bool {
    match reduced {
        Type::Union(arms) => arms.iter().any(abstract_iterable),
        Type::Class(path) | Type::Generic(path, _) => ABSTRACT_ITERABLE_TYPES.contains(&&**path),
        _ => false,
    }
}

fn parameter_classes(reduced: &Type, classes: &mut Vec<String>) {
    let mut pending = vec![reduced];
    while let Some(current) = pending.pop() {
        let class = match current {
            Type::Union(arms) => {
                pending.extend(arms.iter().rev());
                continue;
            }
            Type::Variable {
                bound: Some(bound),
                constrained: false,
                ..
            } => {
                pending.push(bound);
                continue;
            }
            Type::Class(path) | Type::Generic(path, _) => path.to_string(),
            Type::Ellipsis => "...".to_string(),
            _ => continue,
        };
        if !classes.contains(&class) {
            classes.push(class);
        }
    }
}

impl<T: Trace> State<T> {
    pub(super) fn call_external(&mut self, graph: &mut Graph, external: ObjId, call: CallId) {
        if let Some(definitions) = self.stub_definitions(external) {
            self.call_outside(graph, external, &definitions, call);
            return;
        }
        let name = self
            .objects
            .external(external)
            .expect("an outside value")
            .name;
        self.add_external_call_edge(call, name, Known::Name);
        self.outside_result(graph, call);
    }

    pub(super) fn add_external_call_edge(&mut self, call: CallId, name: Sym, known: Known) {
        if self.calls[call.index()].implicit {
            return;
        }
        self.add_call_edge(call, name);
        if self.external_callees.get(&name) != Some(&Known::Stub) {
            self.external_callees.insert(name, known);
        }
    }

    fn call_outside(
        &mut self,
        graph: &mut Graph,
        external: ObjId,
        definitions: &[Definition],
        call: CallId,
    ) {
        let (base, receivers, group) = match self.prefixes.get(&call) {
            None => (call, Vec::new(), None),
            Some((base, Prefix::Receivers(receivers))) => (*base, receivers.clone(), None),
            Some((base, Prefix::Group(group))) => (*base, Vec::new(), Some(*group)),
        };
        assert!(
            group.is_none() || self.bound_in_group(external),
            "a group calls an outside function"
        );
        let found = self.objects.external(external).expect("an outside value");
        let (name, inexact, steps) = (found.name, found.inexact, found.steps);
        let text = self.symbols.text(name).to_string();
        if self.returns_argument(graph, external, call) {
            return;
        }
        let unknown = match group {
            Some(group) => self.group_records[group.0 as usize].unknown,
            None => receivers
                .first()
                .is_some_and(|&receiver| self.unknown_class(receiver)),
        };
        if !unknown {
            self.add_external_call_edge(call, name, Known::Stub);
            for definition in definitions {
                if let Some(&wrapper) = lookup(CACHED_FUNCTIONS, &*definition.path) {
                    let typed = self.typed(graph, wrapper);
                    let name = format!("{}.__call__", self.objects.name(typed, &self.symbols));
                    let name = self.symbols.intern(&name);
                    self.add_external_call_edge(call, name, Known::Stub);
                }
            }
        }
        let receiver = inexact.then_some(external);
        if let Some(&receiver) = receivers.first()
            && self.objects.is_class(receiver)
            && definitions
                .iter()
                .any(|definition| &*definition.path == SUBCLASSES)
        {
            self.subclasses(graph, receiver, call);
            return;
        }
        let dst = self.calls[call.index()].dst;
        for definition in definitions {
            if &*definition.path == METHOD_TYPE && dst.is_some() {
                self.make_method(graph, call);
            }
            if definition.kind == DefinitionKind::Class
                && let Some((_, model)) = lookup(CONTAINER_CLASSES, &*definition.path)
            {
                self.apply_rule(graph, model, call, receiver);
                return;
            }
        }
        if let Some(model) = builtin_function_model(&text, steps) {
            self.apply_rule(graph, model, call, receiver);
            if self.typed_callbacks.insert((base, external)) {
                let mut overloads = Vec::new();
                for definition in definitions {
                    if definition.kind == DefinitionKind::Function {
                        overloads.extend(self.bound_signatures(graph, definition, call));
                    } else {
                        assert_eq!(
                            definition.kind,
                            DefinitionKind::Class,
                            "{}",
                            definition.path
                        );
                        overloads.extend(self.constructor_signatures(graph, definition, call));
                    }
                }
                self.call_protocols(graph, base, &overloads, true);
            }
            return;
        }
        let mut builtins = Vec::new();
        let mut consuming = Vec::new();
        let mut calling = Vec::new();
        let mut hinting = Vec::new();
        let mut keyed = Vec::new();
        let mut library = Vec::new();
        for definition in definitions {
            let overloads = match definition.kind {
                DefinitionKind::Function => {
                    self.call_signatures(graph, definition, call, &receivers, group, external)
                }
                DefinitionKind::Class => {
                    let overloads = self.constructor_signatures(graph, definition, call);
                    if let Some(dst) = dst {
                        let context = TypeContext::of_call(call, self.calls[call.index()].origin);
                        self.add_instance(graph, &definition.path, &[], dst, &context, &[]);
                    }
                    overloads
                }
                _ => continue,
            };
            let path = &*definition.path;
            let builtin = path.starts_with(STUB_BUILTINS_PREFIX);
            if builtin {
                builtins.extend(overloads.iter().cloned());
            }
            if let Some(&hint) = lookup(LENGTH_HINTS, path) {
                hinting.extend(overloads.iter().map(|overload| (hint, overload.clone())));
            }
            if let Some(&name) = lookup(CALLS_BACK, path) {
                calling.extend(overloads.iter().map(|overload| (name, overload.clone())));
            }
            if let Some(&wholes) = lookup(KEYED_SEQUENCES, path) {
                keyed.extend(overloads.iter().map(|overload| (wholes, overload.clone())));
            }
            if let Some(&name) = lookup(KEY_WRAPPERS, path)
                && dst.is_some()
            {
                self.wrapped_key(graph, name, call, &overloads);
            }
            if let Some(&(path, _)) = LIBRARY_ITERATION.iter().find(|&&(known, _)| known == path) {
                library.push((path, overloads));
            } else if builtin {
                consuming.extend(
                    overloads
                        .into_iter()
                        .map(|overload| (Box::<str>::from(path), overload)),
                );
            }
        }
        let details = &self.calls[call.index()];
        if let (Some(dst), true, Some(Some(decorated))) =
            (details.dst, details.decorator, details.args.last())
        {
            let decorated = *decorated;
            self.add_edge(graph, decorated, dst);
        }
        if !self.typed_callbacks.insert((call, external)) {
            return;
        }
        if let Some(path) = definitions.iter().find_map(|definition| {
            HASHED_ARGUMENTS
                .iter()
                .find(|&&(known, _)| known == &*definition.path)
                .map(|&(known, _)| known)
        }) {
            self.hash_arguments(graph, path, call, &builtins, &receivers);
        }
        let comparison = definitions
            .iter()
            .find_map(|definition| lookup(ORDERING_COMPARISON_BY_BUILTIN, &definition.path));
        if let Some(&method) = comparison {
            self.call_protocols(graph, base, &builtins, true);
            self.compare_items(graph, method, call, &builtins);
        } else {
            self.call_back_builtin(graph, base, &builtins);
            self.call_protocols(graph, base, &builtins, false);
        }
        if !calling.is_empty() {
            self.call_back_library(graph, call, &calling);
        }
        if !keyed.is_empty() {
            self.call_sequence_key(graph, call, &keyed);
        }
        if !hinting.is_empty() {
            self.length_hints(graph, call, &hinting);
        }
        for (path, found) in &library {
            self.library_operation(graph, call, path, found);
        }
        if !consuming.is_empty() {
            self.consume_library(graph, call, &consuming);
        }
        for definition in definitions {
            let path = &*definition.path;
            if let Some(model) =
                lookup(REFLECTION_CALLS, path).or_else(|| lookup(SPECIAL_METHOD_CALLS, path))
            {
                self.apply_rule(graph, model, call, None);
            }
        }
    }

    pub(super) fn bound_in_group(&mut self, callee: ObjId) -> bool {
        if let Some(&found) = self.grouped_externals.get(&callee) {
            return found;
        }
        let found = self.find_bound_in_group(callee);
        self.grouped_externals.insert(callee, found);
        found
    }

    fn find_bound_in_group(&mut self, callee: ObjId) -> bool {
        let Object::External(external) = self.objects.get(callee) else {
            return false;
        };
        let steps = external.steps;
        let name = self.symbols.text(external.name).to_string();
        if RETURNS_ARGUMENT.iter().any(|&(model, _)| model == name)
            || builtin_function_model(&name, steps).is_some()
        {
            return false;
        }
        let Some(definitions) = self.stub_definitions(callee) else {
            return false;
        };
        !definitions.is_empty()
            && definitions.iter().all(|definition| {
                let path = &*definition.path;
                definition.kind == DefinitionKind::Function && !group_excluded(path)
            })
    }

    pub(super) fn group_width(&self, group: GroupId) -> usize {
        let call = self.group_records[group.0 as usize].call;
        let base = self
            .prefixes
            .get(&call)
            .map(|(base, _)| *base)
            .expect("a group base");
        self.calls[call.index()].args.len() - self.calls[base.index()].args.len()
    }

    pub(super) fn add_results_of(
        &mut self,
        graph: &mut Graph,
        call: CallId,
        typed: &[TypedResult],
        receivers: &[ObjId],
    ) {
        let details = &self.calls[call.index()];
        let dst = details.dst.expect("a typed result");
        let origin = details.origin;
        for result in typed {
            let context = TypeContext {
                receiver: receivers.first().copied(),
                binding: Some((result.bound, result.parameters.clone())),
                ..TypeContext::of_call(call, origin)
            };
            self.add_type(graph, &result.reduced, dst, &context, &[]);
        }
    }

    fn bound_signatures(
        &mut self,
        graph: &mut Graph,
        definition: &Definition,
        call: CallId,
    ) -> Vec<Overload> {
        let (signatures, _, _) = self.function_entry(definition);
        let mut overloads = Vec::new();
        for index in self.fitting(&signatures, 0, call) {
            let parameters: Arc<[Param]> = Arc::from(&signatures[index][..]);
            let bound = self.bind_stub(graph, call, &definition.path, index, &parameters);
            overloads.push(Overload { parameters, bound });
        }
        overloads
    }

    pub(super) fn unknown_class(&self, object: ObjId) -> bool {
        match self.objects.get(object) {
            Object::Typed { abstract_, .. } => *abstract_,
            Object::Container(container) if self.symbols.text(container.kind).contains('.') => {
                not_ported("containers: a container of an outside class")
            }
            _ => false,
        }
    }

    fn function_entry(
        &self,
        definition: &Definition,
    ) -> (Vec<Vec<Param>>, Vec<Type>, Option<Decorator>) {
        let entry = definition
            .entry
            .expect("a function definition has an entry");
        let Entry::Function(function) = self.stubs.entry(entry) else {
            panic!("{} is not a function of the stubs", definition.path)
        };
        let signatures = function
            .signatures
            .iter()
            .map(|signature| {
                signature
                    .parameters
                    .iter()
                    .map(|parameter| Param {
                        name: parameter.name.clone(),
                        kind: parameter.kind,
                        has_default: parameter.has_default,
                        annotation: parameter.annotation.clone(),
                    })
                    .collect()
            })
            .collect();
        let results = function
            .signatures
            .iter()
            .map(|signature| signature.result.clone())
            .collect();
        (signatures, results, function.decorator)
    }

    fn fitting(&self, signatures: &[Vec<Param>], skip: usize, call: CallId) -> Vec<usize> {
        let fitting: Vec<usize> = signatures
            .iter()
            .enumerate()
            .filter(|(_, parameters)| self.fits(&parameters[skip.min(parameters.len())..], call))
            .map(|(index, _)| index)
            .collect();
        if fitting.is_empty() {
            (0..signatures.len()).collect()
        } else {
            fitting
        }
    }

    fn fits(&self, parameters: &[Param], call: CallId) -> bool {
        let details = &self.calls[call.index()];
        let positional: Vec<&Param> = parameters
            .iter()
            .filter(|parameter| positional_kind(parameter.kind))
            .collect();
        let variadic = parameters
            .iter()
            .any(|parameter| parameter.kind == ParameterKind::VarPositional);
        let keywords_any = parameters
            .iter()
            .any(|parameter| parameter.kind == ParameterKind::VarKeyword);
        let count = details.args.len();
        if count > positional.len() && !variadic {
            return false;
        }
        let given: Vec<&str> = details
            .keywords
            .iter()
            .map(|&(name, _)| self.symbols.text(name))
            .collect();
        for name in &given {
            let parameter = parameters
                .iter()
                .find(|parameter| &*parameter.name == *name);
            let unnamed = parameter.is_none_or(|parameter| {
                matches!(
                    parameter.kind,
                    ParameterKind::PositionalOnly
                        | ParameterKind::VarPositional
                        | ParameterKind::VarKeyword
                )
            });
            if unnamed && !keywords_any {
                return false;
            }
        }
        if !details.star.is_empty() || !details.double_star.is_empty() {
            return true;
        }
        for (index, parameter) in positional.iter().enumerate() {
            if index >= count && !parameter.has_default && !given.contains(&&*parameter.name) {
                return false;
            }
        }
        for parameter in parameters {
            if parameter.kind == ParameterKind::KeywordOnly
                && !parameter.has_default
                && !given.contains(&&*parameter.name)
            {
                return false;
            }
        }
        true
    }

    fn call_signatures(
        &mut self,
        graph: &mut Graph,
        definition: &Definition,
        call: CallId,
        receivers: &[ObjId],
        group: Option<GroupId>,
        external: ObjId,
    ) -> Vec<Overload> {
        let (signatures, results, decorator) = self.function_entry(definition);
        let skip = usize::from(
            decorator == Some(Decorator::ClassMethod) && receivers.is_empty() && group.is_none(),
        );
        let mut receivers = receivers.to_vec();
        if skip == 1 && definition.owner.is_some() {
            receivers = vec![self.class_method_owner(graph, definition, external)];
        }
        let fitting = self.fitting(&signatures, skip, call);
        let dst = self.calls[call.index()].dst;
        let mut overloads = Vec::new();
        let mut typed = Vec::new();
        for index in fitting {
            let parameters: Arc<[Param]> =
                Arc::from(&signatures[index][skip.min(signatures[index].len())..]);
            let bound = self.bind_stub(graph, call, &definition.path, index, &parameters);
            if dst.is_some() {
                typed.push(TypedResult {
                    reduced: results[index].clone(),
                    bound,
                    parameters: parameters.clone(),
                });
            }
            overloads.push(Overload { parameters, bound });
        }
        if let Some(group) = group {
            if !typed.is_empty() {
                self.group_observe(group, call, typed);
            }
            return overloads;
        }
        let details = &self.calls[call.index()];
        let unpacked = !details.star.is_empty() || !details.double_star.is_empty();
        let origin = details.origin;
        let deferred = deferred_result(&definition.path);
        let typed_results: Vec<(Type, TypeContext)> = typed
            .into_iter()
            .map(|result| {
                let context = TypeContext {
                    receiver: receivers.first().copied(),
                    binding: Some((result.bound, result.parameters)),
                    deferred,
                    ..TypeContext::of_call(call, origin)
                };
                (result.reduced, context)
            })
            .collect();
        if !typed_results.is_empty() && OPENERS.contains(&&*definition.path) && !unpacked {
            self.open_file(graph, call, overloads[0].bound, typed_results);
        } else {
            let closure = lookup(CLOSURES, &*definition.path).copied();
            for (reduced, context) in typed_results {
                let dst = dst.expect("a typed result");
                if let (Some(closure), Type::Callable { result, .. }) = (closure, &reduced) {
                    let closure = self.closure(graph, closure, result);
                    self.add_object(graph, dst, closure);
                } else {
                    self.add_type(graph, &reduced, dst, &context, &[]);
                }
            }
        }
        let creates = self
            .fitting(&signatures, skip, call)
            .into_iter()
            .any(|index| results[index] == Type::SelfType);
        if creates && receivers.is_empty() && definition.path.ends_with(".__new__") {
            let details = &self.calls[call.index()];
            if details.dst.is_some() && matches!(details.args.first(), Some(Some(_))) {
                self.new_instance_of(graph, call);
            }
        }
        overloads
    }

    fn class_method_owner(
        &mut self,
        graph: &mut Graph,
        definition: &Definition,
        external: ObjId,
    ) -> ObjId {
        let name = self.external_name(external);
        let (holder, _) = name.rsplit_once('.').expect("a class method has a holder");
        let holder = self.external(graph, holder, 0, false);
        let found = self.stub_definitions(holder);
        if found.is_none_or(|found| found.iter().any(|d| d.kind == DefinitionKind::Class)) {
            return holder;
        }
        let owner = definition.owner.clone().expect("an owner");
        let public = outside_name(&self.stubs.public_name(&owner));
        self.external(graph, &public, 0, false)
    }

    fn constructor_signatures(
        &mut self,
        graph: &mut Graph,
        definition: &Definition,
        call: CallId,
    ) -> Vec<Overload> {
        let mut overloads = Vec::new();
        for name in ["__new__", "__init__"] {
            let members = self.stubs.member(&definition.path, name);
            for member in members.iter() {
                if member.kind != DefinitionKind::Function
                    || member.owner.as_deref() == Some(OBJECT)
                {
                    continue;
                }
                let (signatures, _, _) = self.function_entry(member);
                for index in self.fitting(&signatures, 1, call) {
                    let parameters: Arc<[Param]> =
                        Arc::from(&signatures[index][1.min(signatures[index].len())..]);
                    let bound = self.bind_stub(graph, call, &member.path, index, &parameters);
                    overloads.push(Overload { parameters, bound });
                }
            }
        }
        overloads
    }

    fn bind_stub(
        &mut self,
        graph: &mut Graph,
        call: CallId,
        path: &str,
        index: usize,
        parameters: &[Param],
    ) -> BoundId {
        let key = (call, Box::from(path), index);
        if let Some(&bound) = self.stub_bindings.get(&key) {
            return bound;
        }
        let signature = stub_signature(parameters);
        let bound = self.bind_signature(graph, call, signature, &[]);
        self.stub_bindings.insert(key, bound);
        bound
    }

    pub(super) fn bind_signature(
        &mut self,
        graph: &mut Graph,
        call: CallId,
        signature: Signature,
        constants: &[(Box<str>, Literal)],
    ) -> BoundId {
        let mut defaults = Vec::new();
        for (name, value) in constants {
            let object = self.const_object(graph, value);
            let node = self.constant(graph, object);
            defaults.push((name.clone(), node));
        }
        let details = self.calls[call.index()].clone();
        let count = details.args.len().min(signature.positional.len());
        let positional: Vec<Box<str>> = signature.positional[..count].to_vec();
        let keywords: Vec<Box<str>> = details
            .keywords
            .iter()
            .map(|&(name, _)| self.symbols.text(name))
            .filter(|name| signature.accepts_keyword(name))
            .map(Box::from)
            .collect();
        let mut distinct = keywords.clone();
        distinct.sort_unstable();
        distinct.dedup();
        let late = details.star.is_empty()
            && details.double_star.is_empty()
            && signature.vararg.is_none()
            && signature.kwarg.is_none()
            && !keywords.iter().any(|name| positional.contains(name))
            && distinct.len() == keywords.len();
        let bound = if late {
            let mut supplied = positional;
            supplied.extend(keywords);
            Bound::Late {
                call,
                signature,
                since: graph.phase,
                supplied,
                constants: defaults,
                nodes: FxHashMap::default(),
            }
        } else {
            let mut parameters = Vec::new();
            for name in signature.names() {
                let node = self.node(graph, None);
                parameters.push((self.symbols.intern(name), node));
            }
            let nothing = self.symbols.intern("None");
            let bound_defaults: Vec<(Sym, NodeId)> = defaults
                .iter()
                .map(|(name, node)| (self.symbols.intern(name), *node))
                .collect();
            let vararg = signature.vararg.is_some();
            let kwarg = signature.kwarg.is_some();
            let function = self.new_object(
                graph,
                Object::Function(Box::new(Function {
                    name: nothing,
                    module: nothing,
                    signature: signature.clone(),
                    parameters,
                    defaults: bound_defaults,
                    optional: Vec::new(),
                    return_node: None,
                    yield_node: None,
                    sent_node: None,
                    is_async: false,
                    varargs: None,
                    varkeywords: None,
                    passthrough: Vec::new(),
                    decorated: false,
                    lineno: None,
                    col_offset: None,
                    end_lineno: None,
                    end_col_offset: None,
                })),
            );
            for (present, kind) in [(vararg, "tuple"), (kwarg, "dict")] {
                if !present {
                    continue;
                }
                let container = Container {
                    kind: self.symbols.intern(kind),
                    site: details.site,
                    length: None,
                    exact: false,
                };
                let container = self.new_object(graph, Object::Container(container));
                let made = self.objects.function_mut(function);
                if kind == "tuple" {
                    made.varargs = Some(container);
                } else {
                    made.varkeywords = Some(container);
                }
            }
            let supplied = self.bind_arguments(graph, function, call, None);
            let mut possible = supplied.clone();
            if !details.star.is_empty() {
                for name in
                    &signature.positional[details.args.len().min(signature.positional.len())..]
                {
                    possible.push(self.symbols.intern(name));
                }
            }
            if !details.double_star.is_empty() {
                for name in signature.names() {
                    if signature.accepts_keyword(name) {
                        possible.push(self.symbols.intern(name));
                    }
                }
            }
            Bound::Full {
                function,
                supplied,
                possible,
            }
        };
        let id = BoundId(u32::try_from(self.bindings.len()).expect("fewer bindings"));
        self.bindings.push(bound);
        id
    }

    pub(super) fn bound_surely(&self, bound: BoundId, name: &str) -> bool {
        match &self.bindings[bound.0 as usize] {
            Bound::Late { supplied, .. } => supplied.iter().any(|given| &**given == name),
            Bound::Full { supplied, .. } => supplied
                .iter()
                .any(|&given| self.symbols.text(given) == name),
        }
    }

    pub(super) fn bound_has(&self, bound: BoundId, name: &str) -> bool {
        match &self.bindings[bound.0 as usize] {
            Bound::Late { signature, .. } => signature.names().contains(&name),
            Bound::Full { function, .. } => self
                .objects
                .function(*function)
                .signature
                .names()
                .contains(&name),
        }
    }

    pub(super) fn bound_varargs(&self, bound: BoundId) -> Option<ObjId> {
        match &self.bindings[bound.0 as usize] {
            Bound::Late { .. } => None,
            Bound::Full { function, .. } => self.objects.function(*function).varargs,
        }
    }

    pub(super) fn bound_varkeywords(&self, bound: BoundId) -> Option<ObjId> {
        match &self.bindings[bound.0 as usize] {
            Bound::Late { .. } => None,
            Bound::Full { function, .. } => self.objects.function(*function).varkeywords,
        }
    }

    pub(super) fn new_plan(&mut self, steps: Vec<(Sym, Unless)>) -> PlanId {
        let id = PlanId(u32::try_from(self.protocol_plans.len()).expect("fewer plans"));
        self.protocol_plans.push(steps);
        id
    }

    pub(super) fn bound_given(&self, bound: BoundId, name: &str) -> bool {
        match &self.bindings[bound.0 as usize] {
            Bound::Late { supplied, .. } => supplied.iter().any(|given| &**given == name),
            Bound::Full { possible, .. } => possible
                .iter()
                .any(|&given| self.symbols.text(given) == name),
        }
    }

    pub(super) fn bound_parameter(
        &mut self,
        graph: &mut Graph,
        bound: BoundId,
        name: &str,
    ) -> NodeId {
        match &self.bindings[bound.0 as usize] {
            Bound::Full { function, .. } => {
                let name = self.symbols.intern(name);
                self.objects.function(*function).parameter(name)
            }
            Bound::Late { nodes, .. } => {
                if let Some(&node) = nodes.get(name) {
                    return node;
                }
                let node = self.late_parameter(graph, bound, name);
                let Bound::Late { nodes, .. } = &mut self.bindings[bound.0 as usize] else {
                    panic!("a late binding")
                };
                nodes.insert(Box::from(name), node);
                node
            }
        }
    }

    fn late_parameter(&mut self, graph: &mut Graph, bound: BoundId, name: &str) -> NodeId {
        let Bound::Late {
            call,
            signature,
            since,
            supplied,
            constants,
            ..
        } = &self.bindings[bound.0 as usize]
        else {
            panic!("a late binding")
        };
        let constant = constants
            .iter()
            .find(|(constant, _)| &**constant == name)
            .map(|&(_, node)| node);
        let (call, since) = (*call, *since);
        assert!(signature.names().contains(&name), "{name} is a parameter");
        let details = &self.calls[call.index()];
        let count = details.args.len().min(signature.positional.len());
        let source = if let Some(position) = signature.positional[..count]
            .iter()
            .position(|parameter| &**parameter == name)
        {
            details.args[position]
        } else if supplied.iter().any(|given| &**given == name) {
            details
                .keywords
                .iter()
                .find(|&&(keyword, _)| self.symbols.text(keyword) == name)
                .and_then(|&(_, value)| value)
        } else {
            constant
        };
        match source {
            None => self.node(graph, None),
            Some(source) => self.follower(graph, source, since),
        }
    }

    pub(super) fn parameter_node(
        &mut self,
        graph: &mut Graph,
        bound: BoundId,
        parameter: &Param,
    ) -> Option<NodeId> {
        match parameter.kind {
            ParameterKind::VarPositional | ParameterKind::VarKeyword => {
                let Bound::Full { function, .. } = self.bindings[bound.0 as usize] else {
                    return None;
                };
                let made = self.objects.function(function);
                let container = match parameter.kind {
                    ParameterKind::VarPositional => made.varargs,
                    ParameterKind::VarKeyword => made.varkeywords,
                    _ => unreachable!("a variadic parameter"),
                }?;
                Some(self.every(graph, container))
            }
            _ => {
                if !self.bound_given(bound, &parameter.name) {
                    return None;
                }
                Some(self.bound_parameter(graph, bound, &parameter.name))
            }
        }
    }

    fn call_back_builtin(&mut self, graph: &mut Graph, call: CallId, overloads: &[Overload]) {
        let mut values = Vec::new();
        for overload in overloads {
            for parameter in overload.parameters.iter() {
                if callable(&parameter.annotation)
                    && let Some(node) = self.parameter_node(graph, overload.bound, parameter)
                    && !values.contains(&node)
                {
                    values.push(node);
                }
            }
        }
        if !values.is_empty() {
            self.call_back(graph, call, &values);
        }
    }

    pub(super) fn call_back(&mut self, graph: &mut Graph, call: CallId, values: &[NodeId]) {
        let origin = self.calls[call.index()].origin;
        let callback = match self.callbacks.get(&origin) {
            Some(&callback) => callback,
            None => {
                let details = &self.calls[call.index()];
                let made = Call {
                    caller: details.caller,
                    args: Vec::new(),
                    keywords: Vec::new(),
                    dst: None,
                    site: details.site,
                    origin,
                    star: Vec::new(),
                    double_star: Vec::new(),
                    implicit: true,
                    decorator: false,
                    applies: false,
                    rule: crate::engine::RuleId::PLACEHOLDER,
                };
                let callback = self.new_call(made, Some(origin));
                self.callbacks.insert(origin, callback);
                callback
            }
        };
        for &value in values {
            if self.callback_values.insert((callback, value)) {
                let rule = self.rule(Rule::CallBackObject { callback });
                self.attach(graph, value, rule);
            }
        }
    }

    fn call_protocols(
        &mut self,
        graph: &mut Graph,
        call: CallId,
        overloads: &[Overload],
        plain: bool,
    ) {
        let mut by_argument: OrderedMap<ArgumentKey, (Vec<NodeId>, Vec<String>)> =
            OrderedMap::default();
        for overload in overloads {
            let positions: Vec<&Param> = overload
                .parameters
                .iter()
                .filter(|parameter| positional_kind(parameter.kind))
                .collect();
            for parameter in overload.parameters.iter() {
                let Some(node) = self.parameter_node(graph, overload.bound, parameter) else {
                    continue;
                };
                let key = match positions
                    .iter()
                    .position(|position| std::ptr::eq(*position, parameter))
                {
                    Some(index) => ArgumentKey::Position(index),
                    None => ArgumentKey::Named(parameter.kind as u8, parameter.name.clone()),
                };
                let (nodes, protocols) = by_argument.entry(key).or_default();
                if !nodes.contains(&node) {
                    nodes.push(node);
                }
                parameter_classes(&parameter.annotation, protocols);
            }
        }
        for (nodes, protocols) in by_argument.into_values() {
            let mut plan: Vec<(Sym, Unless)> = Vec::new();
            let mut earlier: Vec<Sym> = Vec::new();
            for class in protocols {
                let names: Vec<Sym> = self
                    .protocol_methods(&class)
                    .into_iter()
                    .map(|name| self.symbols.intern(&name))
                    .filter(|name| !earlier.contains(name))
                    .collect();
                for &name in &names {
                    let unless = if earlier.is_empty() {
                        Unless::Nothing
                    } else {
                        Unless::Names(earlier.clone().into_boxed_slice())
                    };
                    plan.push((name, unless));
                }
                earlier.extend(names);
            }
            if plain {
                plan.retain(|&(name, _)| {
                    let text = self.symbols.text(name);
                    !(text.starts_with("__") && text.ends_with("__"))
                });
            }
            if plan.is_empty() {
                continue;
            }
            let id = self.new_plan(plan);
            let (caller, site) = (
                self.calls[call.index()].caller,
                self.calls[call.index()].site,
            );
            for node in nodes {
                let rule = self.rule(Rule::CallProtocol {
                    plan: id,
                    caller,
                    site,
                });
                self.attach(graph, node, rule);
            }
        }
    }

    fn protocol_methods(&mut self, class: &str) -> Vec<String> {
        let Some(definition) = self.stubs.definition(class) else {
            return Vec::new();
        };
        let protocol = matches!(
            definition.entry.map(|entry| self.stubs.entry(entry)),
            Some(Entry::Class(entry)) if entry.protocol
        );
        if !protocol {
            return Vec::new();
        }
        let mut names = Vec::new();
        for owner in self.stubs.mro(class).iter() {
            if &**owner == OBJECT {
                continue;
            }
            let Some(found) = self.stubs.definition(owner) else {
                continue;
            };
            let Some(Entry::Class(entry)) = found.entry.map(|entry| self.stubs.entry(entry)) else {
                continue;
            };
            for (name, &member) in &entry.members {
                if matches!(self.stubs.entry(member), Entry::Function(_))
                    && !names.iter().any(|known: &String| **known == **name)
                {
                    names.push(name.to_string());
                }
            }
        }
        names
    }

    pub(super) fn call_protocol(
        &mut self,
        graph: &mut Graph,
        object: ObjId,
        plan: PlanId,
        caller: Sym,
        site: Sym,
    ) {
        self.call_protocol_at(graph, object, plan, caller, site, false);
    }

    pub(super) fn call_protocol_at(
        &mut self,
        graph: &mut Graph,
        object: ObjId,
        plan: PlanId,
        caller: Sym,
        site: Sym,
        compare: bool,
    ) {
        let steps = self.protocol_plans[plan.0 as usize].clone();
        for (name, unless) in steps {
            let role = if compare {
                Role::Compare(name)
            } else {
                Role::Protocol(name)
            };
            let key = SiteKey {
                caller,
                site,
                role,
                implicit: true,
            };
            let implicit = self.site_call(graph, key, &[], None, None);
            if self.objects.is_class(object) {
                let rule = self.rule(Rule::MetaclassProtocol {
                    class: object,
                    name,
                    implicit,
                    unless,
                });
                let metaclass = self.objects.class(object).metaclass;
                self.attach(graph, metaclass, rule);
            } else {
                let text = self.symbols.text(name).to_string();
                self.call_dunder(graph, object, &text, implicit, None, unless);
            }
        }
    }

    pub(super) fn metaclass_protocol(
        &mut self,
        graph: &mut Graph,
        meta: ObjId,
        class: ObjId,
        name: Sym,
        implicit: CallId,
        unless: Unless,
    ) {
        if !self.objects.is_class(meta) {
            return;
        }
        let key = LookupKey {
            attr: LookupAttr::Name(name),
            receiver: Some(class),
            after: None,
            unless,
        };
        let found = self.lookup(graph, meta, key);
        let rule = self.rule(Rule::CallEach { call: implicit });
        self.attach(graph, found, rule);
    }
}
