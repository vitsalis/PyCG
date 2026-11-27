use std::sync::Arc;

use num_bigint::BigInt;
use pycg_solver::{NodeId, ObjId};
use pycg_stubs::{Definition, DefinitionKind, Entry, ParameterKind, Type};
use rustc_hash::FxHashMap;

use crate::engine::containers::{ContainerOrigin, IterationRoleId};
use crate::engine::objects::{Literal, Object};
use crate::engine::outside::{STUB_BUILTINS, outside_name};
use crate::engine::outside_calls::{BoundId, Param};
use crate::engine::rules::Rule;
use crate::engine::semantics::{CallId, Origin};
use crate::engine::symbols::Sym;
use crate::engine::trace::Trace;
use crate::engine::{Graph, State};
use crate::models::{
    CONCRETE_CLASSES, CONTAINER_CLASSES, STUB_RESULTS, VARIABLE_TYPES, builtin_kind, lookup,
};

const TYPES_SAYING_NOTHING: &[&str] = &["builtins.object"];
const TYPE_CALL: &str = "builtins.type.__call__";
const FUNCTION_TYPES: &[&str] = &[
    "builtins.function",
    "types.BuiltinFunctionType",
    "types.ClassMethodDescriptorType",
    "types.FunctionType",
    "types.MethodDescriptorType",
    "types.MethodType",
    "types.MethodWrapperType",
    "types.WrapperDescriptorType",
];
const BUILTIN_CONTAINERS: &[(&str, &str)] = &[
    ("builtins.list", "list"),
    ("builtins.tuple", "tuple"),
    ("builtins.set", "set"),
    ("builtins.frozenset", "frozenset"),
    ("builtins.dict", "dict"),
];
const ABSTRACT_ITERABLES: &[&str] = &[
    "typing.AbstractSet",
    "typing.AsyncGenerator",
    "typing.AsyncIterable",
    "typing.AsyncIterator",
    "typing.Collection",
    "typing.Generator",
    "typing.Iterable",
    "typing.Iterator",
    "typing.KeysView",
    "typing.MutableSequence",
    "typing.MutableSet",
    "typing.Reversible",
    "typing.Sequence",
    "typing.ValuesView",
];
const ABSTRACT_MAPPINGS: &[&str] = &["typing.Mapping", "typing.MutableMapping"];
const AWAITED_PARAMETERS: &[(&str, usize)] = &[
    ("typing.Awaitable", 0),
    ("typing.Coroutine", 2),
    ("typing.Generator", 2),
    ("_asyncio.Future", 0),
    ("_asyncio.Task", 0),
];
const ELEMENT_CONTAINERS: &[&str] = &[
    "builtins.list",
    "builtins.set",
    "builtins.frozenset",
    "builtins.tuple",
];

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub(crate) enum TypeOrigin {
    Call(Origin),
    Attribute(Box<str>),
    Iteration {
        caller: Sym,
        site: Sym,
        role: IterationRoleId,
    },
    Subscript {
        caller: Sym,
        site: Sym,
    },
    Slice {
        caller: Sym,
        site: Sym,
    },
}

#[derive(Clone, Debug)]
pub(crate) struct TypeContext {
    pub(crate) call: Option<CallId>,
    pub(crate) receiver: Option<ObjId>,
    pub(crate) binding: Option<(BoundId, Arc<[Param]>)>,
    pub(crate) origin: TypeOrigin,
    pub(crate) deferred: bool,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Binds {
    Value,
    Class,
    Elements,
    Awaited,
}

#[derive(Clone, Debug)]
pub(crate) enum OutsideRule {
    AddConstraint {
        constraints: Arc<[Type]>,
        dst: NodeId,
        context: Box<TypeContext>,
        position: Arc<[u32]>,
    },
    AddInstancesOf {
        dst: NodeId,
    },
}

impl OutsideRule {
    pub(crate) fn key(&self) -> &'static str {
        match self {
            OutsideRule::AddConstraint { .. } => "Each:Outside._add_constraint",
            OutsideRule::AddInstancesOf { .. } => "Each:Outside._add_instances_of",
        }
    }

    pub(crate) fn results(&self) -> Vec<NodeId> {
        match *self {
            OutsideRule::AddConstraint { dst, .. } | OutsideRule::AddInstancesOf { dst } => {
                vec![dst]
            }
        }
    }
}

type StubContainerKey = (TypeOrigin, Box<[u32]>, Box<[Type]>);

#[derive(Default)]
pub(crate) struct OutsideTypes {
    stub_containers: FxHashMap<StubContainerKey, u32>,
    concrete_typed: FxHashMap<String, ObjId>,
    elements: FxHashMap<(CallId, NodeId), NodeId>,
}

impl TypeContext {
    pub(crate) fn of_call(call: CallId, origin: Origin) -> TypeContext {
        TypeContext {
            call: Some(call),
            receiver: None,
            binding: None,
            origin: TypeOrigin::Call(origin),
            deferred: false,
        }
    }

    pub(crate) fn of_attribute(path: &str, receiver: Option<ObjId>) -> TypeContext {
        TypeContext {
            call: None,
            receiver,
            binding: None,
            origin: TypeOrigin::Attribute(path.into()),
            deferred: false,
        }
    }
}

pub(crate) fn named(definition: &Definition) -> bool {
    match definition.kind {
        DefinitionKind::Module | DefinitionKind::Class | DefinitionKind::Function => true,
        DefinitionKind::Property | DefinitionKind::Variable => {
            let module = definition
                .path
                .split('.')
                .next()
                .unwrap_or(&definition.path);
            module == "typing" || module == "typing_extensions"
        }
    }
}

fn constraints(reduced: &Type) -> Vec<Type> {
    match reduced {
        Type::Variable {
            bound: Some(bound),
            constrained: true,
            ..
        } => match &**bound {
            Type::Union(arms) => arms.to_vec(),
            single => vec![single.clone()],
        },
        _ => Vec::new(),
    }
}

fn mentions(reduced: &Type, name: &str) -> bool {
    match reduced {
        Type::Variable { name: variable, .. } => &**variable == name,
        Type::Union(parts) | Type::Generic(_, parts) => {
            parts.iter().any(|part| mentions(part, name))
        }
        Type::TypeOf(inner) => mentions(inner, name),
        Type::Callable { result, parameters } => {
            mentions(result, name)
                || parameters
                    .iter()
                    .flatten()
                    .any(|parameter| mentions(parameter, name))
        }
        Type::Unknown | Type::Class(_) | Type::None | Type::SelfType | Type::Ellipsis => false,
    }
}

fn variable_name(reduced: &Type) -> Option<&str> {
    match reduced {
        Type::Variable { name, .. } => Some(name),
        _ => None,
    }
}

fn binds(reduced: &Type, name: &str) -> Option<Binds> {
    match reduced {
        Type::Variable { name: variable, .. } if &**variable == name => Some(Binds::Value),
        Type::TypeOf(inner) if variable_name(inner) == Some(name) => Some(Binds::Class),
        Type::Union(arms) => arms.iter().find_map(|arm| binds(arm, name)),
        Type::Generic(class, arguments) => {
            let awaited = AWAITED_PARAMETERS
                .iter()
                .find(|&&(path, _)| path == &**class)
                .and_then(|&(_, position)| arguments.get(position))
                .and_then(variable_name);
            if awaited == Some(name) {
                return Some(Binds::Awaited);
            }
            let element =
                ELEMENT_CONTAINERS.contains(&&**class) || ABSTRACT_ITERABLES.contains(&&**class);
            (element && arguments.first().and_then(variable_name) == Some(name))
                .then_some(Binds::Elements)
        }
        _ => None,
    }
}

fn container_kind(class: &str) -> Option<&str> {
    if let Some(&(_, kind)) = BUILTIN_CONTAINERS.iter().find(|&&(path, _)| path == class) {
        return Some(kind);
    }
    let abstract_ = ABSTRACT_ITERABLES.contains(&class) || ABSTRACT_MAPPINGS.contains(&class);
    (abstract_ || lookup(CONTAINER_CLASSES, class).is_some()).then_some(class)
}

fn extended(position: &[u32], index: usize) -> Box<[u32]> {
    let mut extended = position.to_vec();
    extended.push(u32::try_from(index).expect("fewer arms than 2^32"));
    extended.into()
}

impl<T: Trace> State<T> {
    pub(super) fn variable_type(&self, definition: &Definition) -> Type {
        if let Some(&(_, class)) = VARIABLE_TYPES
            .iter()
            .find(|&&(path, _)| path == &*definition.path)
        {
            return Type::Class(class.into());
        }
        self.annotation_type(definition)
    }

    pub(super) fn annotation_type(&self, definition: &Definition) -> Type {
        let entry = definition.entry.expect("a typed definition has an entry");
        match self.stubs.entry(entry) {
            Entry::Variable(variable) => variable.annotation.clone(),
            Entry::Property(property) => property.annotation.clone(),
            _ => panic!("{} has no type", definition.path),
        }
    }

    fn context_site(&mut self, context: &TypeContext) -> Sym {
        match (context.call, &context.origin) {
            (Some(call), _) => self.calls[call.index()].site,
            (None, TypeOrigin::Attribute(path)) => self.symbols.intern(path),
            (
                None,
                &TypeOrigin::Iteration { site, .. }
                | &TypeOrigin::Subscript { site, .. }
                | &TypeOrigin::Slice { site, .. },
            ) => site,
            (None, TypeOrigin::Call(_)) => panic!("a call origin comes with its call"),
        }
    }

    pub(super) fn string_constant_value(
        &mut self,
        graph: &mut Graph,
        object: ObjId,
    ) -> Option<ObjId> {
        let class = match self.objects.get(object) {
            Object::Const {
                value: Literal::Str(_),
                ..
            } => "builtins.str",
            Object::Const {
                value: Literal::Bytes(_),
                ..
            } => "builtins.bytes",
            _ => return None,
        };
        Some(self.typed(graph, class))
    }

    pub(super) fn concrete_typed(&mut self, graph: &mut Graph, name: &str) -> ObjId {
        if let Some(&typed) = self.outside_types.concrete_typed.get(name) {
            return typed;
        }
        let &(_, class) = CONCRETE_CLASSES
            .iter()
            .find(|&&(concrete, _)| concrete == name)
            .expect("a concrete class");
        let object = Object::Typed {
            class: self.symbols.intern(class),
            name: self.symbols.intern(name),
            abstract_: false,
        };
        let typed = self.new_object(graph, object);
        self.outside_types
            .concrete_typed
            .insert(name.to_string(), typed);
        typed
    }

    pub(super) fn typed_special(
        &mut self,
        graph: &mut Graph,
        typed: ObjId,
        method: &str,
        dst: Option<NodeId>,
        origin: TypeOrigin,
    ) {
        let Some(dst) = dst else {
            return;
        };
        let class = self
            .stub_class(typed)
            .expect("a typed value has a stub class");
        for definition in self.stubs.member(&class, method).iter() {
            if definition.kind != DefinitionKind::Function {
                continue;
            }
            if let Some(&(_, result)) = STUB_RESULTS
                .iter()
                .find(|&&(path, _)| path == &*definition.path)
            {
                let concrete = self.concrete_typed(graph, result);
                self.add_object(graph, dst, concrete);
                continue;
            }
            let entry = definition.entry.expect("a function has an entry");
            let Entry::Function(function) = self.stubs.entry(entry) else {
                panic!("{} is not a function of the stubs", definition.path)
            };
            let results: Vec<Type> = function
                .signatures
                .iter()
                .map(|signature| signature.result.clone())
                .collect();
            for reduced in &results {
                let context = TypeContext {
                    call: None,
                    receiver: Some(typed),
                    binding: None,
                    origin: origin.clone(),
                    deferred: false,
                };
                self.add_type(graph, reduced, dst, &context, &[]);
            }
        }
    }

    pub(super) fn call_typed(&mut self, graph: &mut Graph, typed: ObjId, call: CallId) {
        let &Object::Typed { class, name, .. } = self.objects.get(typed) else {
            panic!("a typed value")
        };
        let class = self.symbols.text(class).to_string();
        let name = self.symbols.text(name).to_string();
        if FUNCTION_TYPES.contains(&&*class) {
            let unknown = self.unknown_external;
            self.call(graph, unknown, call);
            return;
        }
        for definition in self.stubs.member(&class, "__call__").iter() {
            if &*definition.path == TYPE_CALL {
                let unknown = self.unknown_external;
                self.call(graph, unknown, call);
            } else if definition.kind == DefinitionKind::Function {
                let method = self.external(graph, &format!("{name}.__call__"), 1, false);
                self.call_bound(graph, method, vec![typed], call);
            }
        }
    }

    pub(super) fn outside_instance_of(&mut self, graph: &mut Graph, external: ObjId) -> Vec<ObjId> {
        let Some(definitions) = self.stub_definitions(external) else {
            return vec![external];
        };
        let mut values = Vec::new();
        for definition in definitions.iter() {
            if definition.kind == DefinitionKind::Class {
                values.push(self.typed(graph, &definition.path));
            }
        }
        values
    }

    pub(super) fn add_type(
        &mut self,
        graph: &mut Graph,
        reduced: &Type,
        dst: NodeId,
        context: &TypeContext,
        position: &[u32],
    ) {
        match reduced {
            Type::Unknown | Type::Callable { .. } => {
                let unknown = self.unknown_external;
                self.add_object(graph, dst, unknown);
            }
            Type::None => {}
            Type::SelfType => self.add_receivers(graph, dst, context),
            Type::Class(class) => self.add_instance(graph, class, &[], dst, context, position),
            Type::Ellipsis => self.add_instance(graph, "...", &[], dst, context, position),
            Type::Generic(class, arguments) => {
                self.add_instance(graph, class, arguments, dst, context, position)
            }
            Type::Union(arms) => {
                for (index, arm) in arms.iter().enumerate() {
                    self.add_type(graph, arm, dst, context, &extended(position, index));
                }
            }
            Type::TypeOf(inner) => self.add_class(graph, inner, dst, context),
            Type::Variable { .. } => self.add_variable(graph, reduced, dst, context, position),
        }
    }

    pub(super) fn add_instance(
        &mut self,
        graph: &mut Graph,
        class: &str,
        arguments: &[Type],
        dst: NodeId,
        context: &TypeContext,
        position: &[u32],
    ) {
        if TYPES_SAYING_NOTHING.contains(&class) {
            let unknown = self.unknown_external;
            self.add_object(graph, dst, unknown);
        } else if let Some(kind) = container_kind(class) {
            let kind = kind.to_string();
            self.add_container(graph, &kind, arguments, dst, context, position);
        } else if self.stubs.definition(class).is_some() {
            let typed = self.typed(graph, class);
            self.add_object(graph, dst, typed);
        } else {
            let unknown = self.unknown_external;
            self.add_object(graph, dst, unknown);
        }
    }

    fn add_container(
        &mut self,
        graph: &mut Graph,
        kind: &str,
        arguments: &[Type],
        dst: NodeId,
        context: &TypeContext,
        position: &[u32],
    ) {
        let fixed =
            kind == "tuple" && !arguments.is_empty() && !arguments.contains(&Type::Ellipsis);
        let length = fixed.then(|| u32::try_from(arguments.len()).expect("a short tuple"));
        let key = (context.origin.clone(), position.into(), arguments.into());
        let next = u32::try_from(self.outside_types.stub_containers.len())
            .expect("fewer than 2^32 stub containers");
        let rule = *self
            .outside_types
            .stub_containers
            .entry(key)
            .or_insert(next);
        let site = self.context_site(context);
        let container = self.container_at(
            graph,
            kind,
            ContainerOrigin::Stub(rule),
            site,
            length,
            false,
        );
        self.add_object(graph, dst, container);
        if fixed {
            for (index, argument) in arguments.iter().enumerate() {
                let node = self.element(graph, container, &Literal::Int(BigInt::from(index)));
                self.add_type(graph, argument, node, context, &extended(position, index));
            }
        } else if builtin_kind(kind) == "dict" || ABSTRACT_MAPPINGS.contains(&kind) {
            if let Some(key) = arguments.first() {
                let keys = self.keys(graph, container);
                self.add_type(graph, key, keys, context, &extended(position, 0));
            }
            if let [_, value] = arguments {
                let values = self.unknown(graph, container);
                self.add_type(graph, value, values, context, &extended(position, 1));
            }
        } else if let Some(element) = arguments.first()
            && *element != Type::Ellipsis
        {
            let node = self.unknown(graph, container);
            self.add_type(graph, element, node, context, &extended(position, 0));
        }
    }

    fn add_receivers(&mut self, graph: &mut Graph, dst: NodeId, context: &TypeContext) {
        let Some(receiver) = context.receiver else {
            return;
        };
        match self.objects.get(receiver) {
            &Object::Instance { class, .. } => {
                self.add_object(graph, dst, receiver);
                let abstract_ = self.abstract_instance(graph, class);
                self.add_object(graph, dst, abstract_);
            }
            Object::Class(_) => {
                let abstract_ = self.abstract_instance(graph, receiver);
                self.add_object(graph, dst, abstract_);
            }
            Object::Const { value, .. } => {
                let class = format!(
                    "{STUB_BUILTINS}.{}",
                    crate::model::constant_type_name(&value.view())
                );
                let typed = self.typed(graph, &class);
                self.add_object(graph, dst, typed);
            }
            Object::External(_) | Object::UnknownExternal(_) => {
                for value in self.outside_instance_of(graph, receiver) {
                    self.add_object(graph, dst, value);
                }
            }
            _ => self.add_object(graph, dst, receiver),
        }
    }

    fn add_class(&mut self, graph: &mut Graph, reduced: &Type, dst: NodeId, context: &TypeContext) {
        match reduced {
            Type::SelfType => {
                if let Some(receiver) = context.receiver {
                    let class = self.class_object(graph, receiver);
                    self.add_object(graph, dst, class);
                }
            }
            Type::Class(class) => {
                if !TYPES_SAYING_NOTHING.contains(&&**class)
                    && self.stubs.definition(class).is_some()
                {
                    let public = outside_name(&self.stubs.public_name(class));
                    let external = self.external(graph, &public, 0, false);
                    self.add_object(graph, dst, external);
                }
            }
            Type::Union(arms) => {
                for arm in arms.iter() {
                    self.add_class(graph, arm, dst, context);
                }
            }
            Type::Variable { name, bound, .. } => {
                let bindings = self.bindings_of(graph, name, context);
                for &(node, how) in bindings.iter().flatten() {
                    if how == Binds::Class {
                        self.add_edge(graph, node, dst);
                    }
                }
                if bindings.is_none()
                    && let Some(bound) = bound
                {
                    self.add_class(graph, bound, dst, context);
                }
            }
            _ => {}
        }
    }

    fn add_variable(
        &mut self,
        graph: &mut Graph,
        reduced: &Type,
        dst: NodeId,
        context: &TypeContext,
        position: &[u32],
    ) {
        let Type::Variable { name, bound, .. } = reduced else {
            panic!("a type variable")
        };
        let constraints: Arc<[Type]> = constraints(reduced).into();
        let bindings = self.bindings_of(graph, name, context);
        for &(node, how) in bindings.iter().flatten() {
            match how {
                Binds::Value if !constraints.is_empty() => {
                    let rule = self.outside_rule(OutsideRule::AddConstraint {
                        constraints: constraints.clone(),
                        dst,
                        context: Box::new(context.clone()),
                        position: position.into(),
                    });
                    self.attach(graph, node, rule);
                }
                Binds::Value => self.add_edge(graph, node, dst),
                Binds::Class => {
                    let rule = self.outside_rule(OutsideRule::AddInstancesOf { dst });
                    self.attach(graph, node, rule);
                }
                Binds::Elements if context.deferred => {}
                Binds::Elements => {
                    let call = context.call.expect("elements are bound by a call");
                    let elements = self.elements_of(graph, call, node);
                    self.add_edge(graph, elements, dst);
                }
                Binds::Awaited => {
                    let call = context.call.expect("an awaited value is bound by a call");
                    let (caller, site) = {
                        let details = &self.calls[call.index()];
                        (details.caller, details.site)
                    };
                    self.add_await(graph, node, dst, caller, site);
                }
            }
        }
        if bindings.is_none() {
            let bound = bound.as_deref().unwrap_or(&Type::Unknown).clone();
            self.add_type(graph, &bound, dst, context, position);
        }
    }

    fn elements_of(&mut self, graph: &mut Graph, call: CallId, iterable: NodeId) -> NodeId {
        if let Some(&node) = self.outside_types.elements.get(&(call, iterable)) {
            return node;
        }
        let node = self.node(graph, None);
        self.outside_types.elements.insert((call, iterable), node);
        let (caller, site) = {
            let details = &self.calls[call.index()];
            (details.caller, details.site)
        };
        self.add_iteration(graph, iterable, node, caller, site, false);
        node
    }

    fn bindings_of(
        &mut self,
        graph: &mut Graph,
        name: &str,
        context: &TypeContext,
    ) -> Option<Vec<(NodeId, Binds)>> {
        let (bound, parameters) = context.binding.as_ref()?;
        let mut found = Vec::new();
        let mut passed = false;
        for parameter in parameters.iter() {
            if !mentions(&parameter.annotation, name) {
                continue;
            }
            let Some(node) = self.parameter_node(graph, *bound, parameter) else {
                continue;
            };
            passed = true;
            if let Some(how) = binds(&parameter.annotation, name)
                && parameter.kind != ParameterKind::VarKeyword
            {
                found.push((node, how));
            }
        }
        passed.then_some(found)
    }

    fn outside_rule(&mut self, rule: OutsideRule) -> crate::engine::rules::RuleId {
        self.rule(Rule::Outside(rule))
    }

    pub(super) fn outside_apply(&mut self, graph: &mut Graph, rule: &OutsideRule, object: ObjId) {
        match rule {
            OutsideRule::AddConstraint {
                constraints,
                dst,
                context,
                position,
            } => {
                let class = self.stub_class(object);
                let mro = match &class {
                    Some(class) => self.stubs.mro(class).to_vec(),
                    None => Vec::new(),
                };
                let matching: Vec<&Type> = constraints
                    .iter()
                    .filter(|constraint| match constraint {
                        Type::Class(path) => mro.contains(path),
                        _ => false,
                    })
                    .collect();
                let chosen: Vec<Type> = if matching.is_empty() {
                    constraints.to_vec()
                } else {
                    matching.into_iter().cloned().collect()
                };
                for constraint in &chosen {
                    self.add_type(graph, constraint, *dst, context, position);
                }
            }
            &OutsideRule::AddInstancesOf { dst } => match self.objects.get(object) {
                Object::Class(class) => {
                    let instances = class.instances;
                    self.add_edge(graph, instances, dst);
                }
                Object::External(_) | Object::UnknownExternal(_) => {
                    for value in self.outside_instance_of(graph, object) {
                        self.add_object(graph, dst, value);
                    }
                }
                _ => {}
            },
        }
    }

    fn stub_class(&mut self, object: ObjId) -> Option<String> {
        match self.objects.get(object) {
            &Object::Typed { class, .. } => Some(self.symbols.text(class).to_string()),
            Object::Const { value, .. } => Some(format!(
                "{STUB_BUILTINS}.{}",
                crate::model::constant_type_name(&value.view())
            )),
            Object::Container(container) => {
                let kind = self.symbols.text(container.kind).to_string();
                Some(self.kind_class(&kind).0)
            }
            _ => None,
        }
    }
}
