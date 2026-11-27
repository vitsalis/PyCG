use pycg_solver::{NodeId, ObjId};
use pycg_stubs::ParameterKind;
use rustc_hash::{FxHashMap, FxHashSet};

use crate::engine::containers::{
    ContainerOrigin, ContainerRule, IterationId, IterationName, Keeps, KeysConstruct,
};
use crate::engine::hierarchy::Unless;
use crate::engine::objects::{Kind, Literal, Object};
use crate::engine::outside_calls::{Overload, abstract_iterable};
use crate::engine::protocols::reflected_comparison;
use crate::engine::rules::Rule;
use crate::engine::semantics::{CallId, Origin, Role};
use crate::engine::symbols::Sym;
use crate::engine::trace::Trace;
use crate::engine::{Graph, OrderedMap, State};
use crate::models::{
    GROUPER, HASHED_ARGUMENTS, IterationMode, KEYED_OPERATIONS, LENGTH_HINT, LIBRARY_ITERATION,
    LIBRARY_VALUES, LengthPlan, LengthSource, NOT_CONSUMING, READS_TUPLES, REPEATS, Shape,
    TUPLE_STORAGE, lookup,
};

const LENGTH_SPECIAL_CALLS: LengthPlan = &[("__len__", &[])];
const TUPLE_STORAGE_LENGTH_HINT: LengthPlan = &[
    ("__len__", &[TUPLE_STORAGE]),
    ("__length_hint__", &["__len__", TUPLE_STORAGE]),
];
const CONSUMED_KINDS: &[Kind] = &[Kind::Container];
const ITERATOR_OF_KINDS: &[Kind] = &[Kind::Instance, Kind::Class, Kind::Container];

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub(crate) struct OperationId(u32);

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
struct SourcesId(u32);

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub(crate) enum Position {
    At(u32),
    Unknown,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub(crate) enum LibraryOrigin {
    Operation(Origin, &'static str),
    Tee(Origin),
    Group(Origin),
    Items(ObjId, &'static str, Option<u32>),
    ActivationItems(ObjId, Sym, Sym, Option<u32>),
    GroupPair(ObjId, Sym, Sym),
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub(crate) enum LibraryRule {
    Iterator {
        iteration: IterationId,
        dst: NodeId,
    },
    IteratorOf {
        call: CallId,
        iteration: IterationId,
        dst: NodeId,
    },
    Consume {
        call: CallId,
    },
}

impl LibraryRule {
    pub(crate) fn key(&self) -> &'static str {
        match self {
            LibraryRule::Iterator { .. } => "Each:Containers.iterator",
            LibraryRule::IteratorOf { .. } => "Each:BuiltinRules._iterator_of",
            LibraryRule::Consume { .. } => "Each:LibraryIteration._consume_library",
        }
    }

    pub(crate) fn kinds(&self) -> Option<&'static [Kind]> {
        match self {
            LibraryRule::Iterator { .. } => None,
            LibraryRule::IteratorOf { .. } => Some(ITERATOR_OF_KINDS),
            LibraryRule::Consume { .. } => Some(CONSUMED_KINDS),
        }
    }

    pub(crate) fn results(&self) -> Vec<NodeId> {
        match *self {
            LibraryRule::Iterator { dst, .. } | LibraryRule::IteratorOf { dst, .. } => vec![dst],
            LibraryRule::Consume { .. } => Vec::new(),
        }
    }
}

struct Activation {
    lazy: ObjId,
    caller: Sym,
    site: Sym,
    found: NodeId,
    items: OrderedMap<Position, NodeId>,
    made: Option<ObjId>,
    shapes: OrderedMap<Option<u32>, ObjId>,
}

struct Operation {
    path: &'static str,
    mode: IterationMode,
    values: Shape,
    caller: Sym,
    site: Sym,
    unless: Unless,
    arguments: OrderedMap<Position, NodeId>,
    sources: SourcesId,
    items: OrderedMap<Position, NodeId>,
    made: Option<ObjId>,
    values_as_given: Option<NodeId>,
    arities: OrderedMap<Option<u32>, ()>,
    shapes: OrderedMap<Option<u32>, ObjId>,
    key_is_item: bool,
    group: Option<ObjId>,
    activations: Vec<Activation>,
    key: Option<NodeId>,
}

#[derive(Default)]
pub(crate) struct Library {
    calls: FxHashMap<(Origin, &'static str), OperationId>,
    operations: Vec<Operation>,
    sources: Vec<OrderedMap<Position, NodeId>>,
    lazy: FxHashMap<ObjId, OperationId>,
    advances: FxHashMap<(ObjId, Sym, Sym), NodeId>,
    iterator_length_hints: FxHashSet<(Sym, Sym, NodeId)>,
}

fn lazy_mode(mode: IterationMode) -> bool {
    !matches!(
        mode,
        IterationMode::Eager | IterationMode::Materialize | IterationMode::Largest
    )
}

pub(crate) fn deferred_result(path: &str) -> bool {
    lookup(LIBRARY_ITERATION, path).is_some_and(|operation| lazy_mode(operation.mode))
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub(crate) enum LibraryRole {
    Tag {
        path: &'static str,
        position: Position,
        again: bool,
    },
    Position {
        position: Position,
        again: bool,
    },
    Inner,
    Bundle,
}

fn tag_role(path: &'static str, position: Position) -> LibraryRole {
    LibraryRole::Tag {
        path,
        position,
        again: false,
    }
}

fn again(role: LibraryRole) -> LibraryRole {
    match role {
        LibraryRole::Tag { path, position, .. } => LibraryRole::Tag {
            path,
            position,
            again: true,
        },
        LibraryRole::Position { position, .. } => LibraryRole::Position {
            position,
            again: true,
        },
        LibraryRole::Inner | LibraryRole::Bundle => panic!("{role:?} has no second pass"),
    }
}

impl<T: Trace> State<T> {
    fn operation(&self, id: OperationId) -> &Operation {
        &self.library.operations[id.0 as usize]
    }

    fn operation_mut(&mut self, id: OperationId) -> &mut Operation {
        &mut self.library.operations[id.0 as usize]
    }

    fn sources_of(&self, id: OperationId) -> Vec<Position> {
        let sources = self.operation(id).sources;
        self.library.sources[sources.0 as usize]
            .keys()
            .copied()
            .collect()
    }

    pub(super) fn library_operation(
        &mut self,
        graph: &mut Graph,
        call: CallId,
        path: &'static str,
        overloads: &[Overload],
    ) {
        let &operation = lookup(LIBRARY_ITERATION, path).expect("a library operation");
        let key = (self.calls[call.index()].origin, path);
        let state = match self.library.calls.get(&key) {
            Some(&state) => state,
            None => {
                let state = self.new_operation(graph, call, path);
                self.library.calls.insert(key, state);
                state
            }
        };
        let arguments = self.operation_arguments(graph, operation.roles, overloads, call);
        for &(position, node) in &arguments {
            let argument = self.argument(graph, state, position);
            self.add_edge(graph, node, argument);
        }
        let mut arity = None;
        if self.calls[call.index()].star.is_empty() {
            let highest = arguments
                .iter()
                .filter_map(|&(position, _)| match position {
                    Position::At(index) => Some(i64::from(index)),
                    Position::Unknown => None,
                })
                .max()
                .unwrap_or(-1);
            arity = Some(u32::try_from(highest + 1).expect("an arity fits u32"));
        }
        for overload in overloads {
            let bound = overload.bound;
            if let Some(&name) = lookup(LIBRARY_VALUES, path)
                && self.bound_given(bound, name)
            {
                let value = self.bound_parameter(graph, bound, name);
                let given = self.values_as_given_node(graph, state);
                self.add_edge(graph, value, given);
            }
            if let Some(&repeat) = lookup(REPEATS, path)
                && self.bound_given(bound, repeat)
            {
                arity = None;
            }
            if let Some(key) = self.operation(state).key
                && self.bound_given(bound, "key")
            {
                let given = self.bound_parameter(graph, bound, "key");
                self.add_edge(graph, given, key);
            }
            if operation.mode == IterationMode::Groupby
                && self.groupby_key_may_be_item(graph, call, overload)
            {
                self.make_groupby_key_the_item(graph, state);
            }
        }
        match operation.shape {
            Shape::Positions => self.arity(graph, state, arity),
            Shape::Tuples => self.arity(graph, state, None),
            _ => {}
        }
        if let (Some(dst), Some(made)) = (self.calls[call.index()].dst, self.operation(state).made)
        {
            self.add_object(graph, dst, made);
        }
    }

    fn new_operation(
        &mut self,
        graph: &mut Graph,
        call: CallId,
        path: &'static str,
    ) -> OperationId {
        let &operation = lookup(LIBRARY_ITERATION, path).expect("a library operation");
        let details = &self.calls[call.index()];
        let (caller, site, origin) = (details.caller, details.site, details.origin);
        let sources = SourcesId(u32::try_from(self.library.sources.len()).expect("fewer sources"));
        self.library.sources.push(OrderedMap::default());
        let unless = if READS_TUPLES.contains(&path) {
            Unless::Names(vec![self.symbols.intern(TUPLE_STORAGE)].into_boxed_slice())
        } else {
            Unless::Nothing
        };
        let key = KEYED_OPERATIONS
            .contains(&path)
            .then(|| self.node(graph, None));
        let mut state = Operation {
            path,
            mode: operation.mode,
            values: operation.shape,
            caller,
            site,
            unless,
            arguments: OrderedMap::default(),
            sources,
            items: OrderedMap::default(),
            made: None,
            values_as_given: None,
            arities: OrderedMap::default(),
            shapes: OrderedMap::default(),
            key_is_item: false,
            group: None,
            activations: Vec::new(),
            key,
        };
        let id =
            OperationId(u32::try_from(self.library.operations.len()).expect("fewer operations"));
        let library_origin = ContainerOrigin::Library(LibraryOrigin::Operation(origin, path));
        let mut grouper = None;
        match operation.mode {
            IterationMode::Materialize => {
                if let Some(kind) = operation.kind {
                    state.made =
                        Some(self.container_at(graph, kind, library_origin, site, None, false));
                }
            }
            IterationMode::Eager | IterationMode::Largest => {}
            mode => {
                let kind = operation.kind.expect("a lazy operation makes a container");
                let lazy = self.container_at(graph, kind, library_origin, site, None, false);
                self.library.lazy.insert(lazy, id);
                state.made = Some(lazy);
                if mode == IterationMode::Tee {
                    let origin = ContainerOrigin::Library(LibraryOrigin::Tee(origin));
                    let tee = self.container_at(graph, "tuple", origin, site, None, true);
                    state.made = Some(tee);
                    let unknown = self.unknown(graph, tee);
                    self.add_object(graph, unknown, lazy);
                } else if mode == IterationMode::Groupby {
                    let origin = ContainerOrigin::Library(LibraryOrigin::Group(origin));
                    let group = self.container_at(graph, GROUPER, origin, site, None, false);
                    grouper = Some(group);
                    state.group = Some(group);
                }
            }
        }
        self.library.operations.push(state);
        if let Some(group) = grouper {
            let grouped = OperationId(
                u32::try_from(self.library.operations.len()).expect("fewer operations"),
            );
            self.library.operations.push(Operation {
                path,
                mode: IterationMode::Lazy,
                values: Shape::Items,
                caller,
                site,
                unless: Unless::Nothing,
                arguments: OrderedMap::default(),
                sources,
                items: OrderedMap::default(),
                made: None,
                values_as_given: None,
                arities: OrderedMap::default(),
                shapes: OrderedMap::default(),
                key_is_item: false,
                group: None,
                activations: Vec::new(),
                key: None,
            });
            self.library.lazy.insert(group, grouped);
        }
        id
    }

    fn operation_arguments(
        &mut self,
        graph: &mut Graph,
        roles: &[&str],
        overloads: &[Overload],
        call: CallId,
    ) -> Vec<(Position, NodeId)> {
        let mut found = Vec::new();
        for overload in overloads {
            let bound = overload.bound;
            let chosen: Vec<_> = if roles == ["*"] {
                overload
                    .parameters
                    .iter()
                    .filter(|parameter| abstract_iterable(&parameter.annotation))
                    .cloned()
                    .collect()
            } else {
                roles
                    .iter()
                    .flat_map(|&name| {
                        overload
                            .parameters
                            .iter()
                            .filter(move |parameter| &*parameter.name == name)
                    })
                    .cloned()
                    .collect()
            };
            for (index, parameter) in chosen.iter().enumerate() {
                let index = u32::try_from(index).expect("an index fits u32");
                if parameter.kind == ParameterKind::VarPositional
                    && let Some(varargs) = self.bound_varargs(bound)
                {
                    if !self.calls[call.index()].star.is_empty() {
                        let every = self.every(graph, varargs);
                        found.push((Position::Unknown, every));
                        continue;
                    }
                    let count = u32::try_from(self.calls[call.index()].args.len())
                        .expect("a count fits u32");
                    for offset in 0..count.saturating_sub(index) {
                        let element = self.element(graph, varargs, &Literal::Int(offset.into()));
                        found.push((Position::At(index + offset), element));
                    }
                    continue;
                }
                if let Some(node) = self.parameter_node(graph, bound, parameter) {
                    found.push((Position::At(index), node));
                }
            }
        }
        found
    }

    fn argument(&mut self, graph: &mut Graph, state: OperationId, position: Position) -> NodeId {
        if let Some(&node) = self.operation(state).arguments.get(&position) {
            return node;
        }
        let node = self.node(graph, None);
        self.operation_mut(state).arguments.insert(position, node);
        let found = self.operation(state);
        let (caller, site, mode, path) = (found.caller, found.site, found.mode, found.path);
        let role = tag_role(path, position);
        match mode {
            IterationMode::Eager => {
                let dst = self.node(graph, None);
                self.library_iterate(graph, node, dst, caller, site, role, Unless::Nothing);
            }
            IterationMode::Materialize => {
                let items = self.node(graph, None);
                let unless = self.operation(state).unless.clone();
                let tuples = !matches!(unless, Unless::Nothing);
                self.library_iterate(graph, node, items, caller, site, role, unless);
                let plan = if tuples {
                    TUPLE_STORAGE_LENGTH_HINT
                } else {
                    LENGTH_HINT
                };
                self.add_length_hint(graph, node, caller, site, plan);
                self.operation_mut(state).items.insert(position, items);
                let shapes: Vec<_> = self
                    .operation(state)
                    .shapes
                    .iter()
                    .map(|(&arity, &shape)| (arity, shape))
                    .collect();
                for (arity, shape) in shapes {
                    self.shape_items(graph, items, shape, arity, position);
                }
            }
            IterationMode::Largest => {
                self.add_length_hint(graph, node, caller, site, LENGTH_SPECIAL_CALLS);
                let iterators = self.obtain(graph, node, caller, site, role);
                let again = self.obtain(graph, iterators, caller, site, again(role));
                let items = self.node(graph, None);
                self.library_advance(graph, again, items, caller, site, role);
                let key = self.operation(state).key;
                let path = self.symbols.intern(path);
                self.call_key(graph, key, items, caller, site, Role::LibraryKey(path));
            }
            _ => {
                let source = if matches!(mode, IterationMode::LazyAll | IterationMode::Merge) {
                    node
                } else {
                    let source = self.obtain(graph, node, caller, site, role);
                    if mode == IterationMode::Tee {
                        self.obtain(graph, source, caller, site, again(role))
                    } else {
                        source
                    }
                };
                let sources = self.operation(state).sources;
                self.library.sources[sources.0 as usize].insert(position, source);
                for activation in 0..self.operation(state).activations.len() {
                    self.wire(graph, state, activation, position);
                }
            }
        }
        node
    }

    fn values_as_given_node(&mut self, graph: &mut Graph, state: OperationId) -> NodeId {
        if let Some(node) = self.operation(state).values_as_given {
            return node;
        }
        let node = self.node(graph, None);
        self.operation_mut(state).values_as_given = Some(node);
        let found: Vec<NodeId> = self
            .operation(state)
            .activations
            .iter()
            .map(|activation| activation.found)
            .collect();
        for found in found {
            assert_ne!(
                self.operation(state).values,
                Shape::Positions,
                "{}",
                self.operation(state).path
            );
            self.add_edge(graph, node, found);
        }
        node
    }

    fn arity(&mut self, graph: &mut Graph, state: OperationId, arity: Option<u32>) {
        if self.operation(state).arities.contains_key(&arity) {
            return;
        }
        self.operation_mut(state).arities.insert(arity, ());
        let found = self.operation(state);
        if let (IterationMode::Materialize, Some(made)) = (found.mode, found.made) {
            let (path, site) = (found.path, found.site);
            let origin = ContainerOrigin::Library(LibraryOrigin::Items(made, path, arity));
            let shape = self.container_at(graph, "tuple", origin, site, arity, true);
            self.operation_mut(state).shapes.insert(arity, shape);
            let unknown = self.unknown(graph, made);
            self.add_object(graph, unknown, shape);
            let items: Vec<_> = self
                .operation(state)
                .items
                .iter()
                .map(|(&position, &items)| (position, items))
                .collect();
            for (position, items) in items {
                self.shape_items(graph, items, shape, arity, position);
            }
        }
        for activation in 0..self.operation(state).activations.len() {
            self.activation_shape(graph, state, activation, arity);
        }
    }

    fn activation_shape(
        &mut self,
        graph: &mut Graph,
        state: OperationId,
        activation: usize,
        arity: Option<u32>,
    ) {
        let found = &self.operation(state).activations[activation];
        let (lazy, caller, site, node) = (found.lazy, found.caller, found.site, found.found);
        let origin =
            ContainerOrigin::Library(LibraryOrigin::ActivationItems(lazy, caller, site, arity));
        let shape = self.container_at(graph, "tuple", origin, site, arity, true);
        self.operation_mut(state).activations[activation]
            .shapes
            .insert(arity, shape);
        self.add_object(graph, node, shape);
        let items: Vec<_> = self.operation(state).activations[activation]
            .items
            .iter()
            .map(|(&position, &items)| (position, items))
            .collect();
        for (position, items) in items {
            self.shape_items(graph, items, shape, arity, position);
        }
        if let Some(given) = self.operation(state).values_as_given {
            let unknown = self.unknown(graph, shape);
            self.add_edge(graph, given, unknown);
        }
    }

    fn shape_items(
        &mut self,
        graph: &mut Graph,
        items: NodeId,
        shape: ObjId,
        arity: Option<u32>,
        position: Position,
    ) {
        match (arity, position) {
            (None, _) => {
                let unknown = self.unknown(graph, shape);
                self.add_edge(graph, items, unknown);
            }
            (Some(arity), Position::At(index)) if index < arity => {
                let element = self.element(graph, shape, &Literal::Int(index.into()));
                self.add_edge(graph, items, element);
            }
            _ => {}
        }
    }

    fn call_key(
        &mut self,
        graph: &mut Graph,
        key: Option<NodeId>,
        items: NodeId,
        caller: Sym,
        site: Sym,
        role: Role,
    ) {
        let Some(key) = key else {
            return;
        };
        let role = self.site_key(caller, site, role);
        let back = self.site_call(graph, role, &[Some(items)], None, None);
        let callee = self.callee(graph, back);
        self.add_edge(graph, key, callee);
    }

    fn make_groupby_key_the_item(&mut self, graph: &mut Graph, state: OperationId) {
        if self.operation(state).key_is_item {
            return;
        }
        self.operation_mut(state).key_is_item = true;
        let pairs: Vec<(Vec<NodeId>, ObjId)> = self
            .operation(state)
            .activations
            .iter()
            .map(|activation| {
                (
                    activation.items.values().copied().collect(),
                    activation.made.expect("a group pair"),
                )
            })
            .collect();
        for (items, made) in pairs {
            for items in items {
                let first = self.element(graph, made, &Literal::Int(0.into()));
                self.add_edge(graph, items, first);
            }
        }
    }

    fn groupby_key_may_be_item(
        &mut self,
        graph: &mut Graph,
        call: CallId,
        overload: &Overload,
    ) -> bool {
        if !self.bound_surely(overload.bound, "key") {
            return true;
        }
        self.bound_parameter(graph, overload.bound, "key");
        if self.literal_none_keyword(call, "key") {
            return true;
        }
        overload
            .parameters
            .iter()
            .position(|parameter| &*parameter.name == "key")
            .is_some_and(|index| self.literal_none(call, index))
    }

    #[allow(clippy::too_many_arguments)]
    fn library_iterate(
        &mut self,
        graph: &mut Graph,
        node: NodeId,
        dst: NodeId,
        caller: Sym,
        site: Sym,
        role: LibraryRole,
        unless: Unless,
    ) {
        let name = IterationName::Library(role);
        let iteration = self.new_named_iteration(dst, caller, site, false, unless, name);
        let rule = self.rule(Rule::Container(ContainerRule::Iterate(iteration)));
        self.attach(graph, node, rule);
    }

    fn library_advance(
        &mut self,
        graph: &mut Graph,
        node: NodeId,
        dst: NodeId,
        caller: Sym,
        site: Sym,
        role: LibraryRole,
    ) {
        let name = IterationName::Library(role);
        let advance = self.new_named_iteration(dst, caller, site, false, Unless::Nothing, name);
        let rule = self.rule(Rule::Container(ContainerRule::NextElement(advance)));
        self.attach(graph, node, rule);
    }

    fn obtain(
        &mut self,
        graph: &mut Graph,
        node: NodeId,
        caller: Sym,
        site: Sym,
        role: LibraryRole,
    ) -> NodeId {
        let iterators = self.node(graph, None);
        let dst = self.node(graph, None);
        let name = IterationName::Library(role);
        let iteration = self.new_named_iteration(dst, caller, site, false, Unless::Nothing, name);
        let rule = self.rule(Rule::Library(LibraryRule::Iterator {
            iteration,
            dst: iterators,
        }));
        self.attach(graph, node, rule);
        iterators
    }

    pub(super) fn is_library(&self, container: ObjId) -> bool {
        self.library.lazy.contains_key(&container)
    }

    pub(super) fn advance_library(
        &mut self,
        graph: &mut Graph,
        object: ObjId,
        iteration: IterationId,
    ) {
        let found = *self.containers.iteration(iteration);
        let key = (object, found.caller, found.site);
        let node = match self.library.advances.get(&key) {
            Some(&node) => node,
            None => {
                let node = self.node(graph, None);
                self.library.advances.insert(key, node);
                let state = self.library.lazy[&object];
                let mut activation = Activation {
                    lazy: object,
                    caller: found.caller,
                    site: found.site,
                    found: node,
                    items: OrderedMap::default(),
                    made: None,
                    shapes: OrderedMap::default(),
                };
                if self.operation(state).mode == IterationMode::Groupby {
                    let origin = ContainerOrigin::Library(LibraryOrigin::GroupPair(
                        object,
                        found.caller,
                        found.site,
                    ));
                    let made = self.container_at(graph, "tuple", origin, found.site, Some(2), true);
                    activation.made = Some(made);
                    let second = self.element(graph, made, &Literal::Int(1.into()));
                    let group = self.operation(state).group.expect("a group");
                    self.add_object(graph, second, group);
                    self.add_object(graph, node, made);
                }
                self.operation_mut(state).activations.push(activation);
                let index = self.operation(state).activations.len() - 1;
                let arities: Vec<_> = self.operation(state).arities.keys().copied().collect();
                for arity in arities {
                    self.activation_shape(graph, state, index, arity);
                }
                for position in self.sources_of(state) {
                    self.wire(graph, state, index, position);
                }
                let found = self.operation(state);
                if let Some(given) = found.values_as_given
                    && found.values != Shape::Positions
                {
                    self.add_edge(graph, given, node);
                }
                node
            }
        };
        self.add_edge(graph, node, found.dst);
    }

    fn wire(
        &mut self,
        graph: &mut Graph,
        state: OperationId,
        activation: usize,
        position: Position,
    ) {
        let found = &self.operation(state).activations[activation];
        let (caller, site, node) = (found.caller, found.site, found.found);
        let sources = self.operation(state).sources;
        let source = self.library.sources[sources.0 as usize][&position];
        let role = LibraryRole::Position {
            position,
            again: false,
        };
        let (mode, path, values) = {
            let found = self.operation(state);
            (found.mode, found.path, found.values)
        };
        if mode == IterationMode::LazyAll {
            self.library_iterate(graph, source, node, caller, site, role, Unless::Nothing);
            return;
        }
        if mode == IterationMode::Merge {
            let tag = tag_role(path, position);
            let iterators = self.obtain(graph, source, caller, site, tag);
            let second = self.obtain(graph, iterators, caller, site, again(tag));
            self.library_advance(graph, iterators, node, caller, site, role);
            self.library_advance(graph, second, node, caller, site, again(role));
            let key = self.operation(state).key;
            let path = self.symbols.intern(path);
            self.call_key(graph, key, node, caller, site, Role::MergeKey(path));
            return;
        }
        let items = self.node(graph, None);
        self.operation_mut(state).activations[activation]
            .items
            .insert(position, items);
        self.library_advance(graph, source, items, caller, site, role);
        match mode {
            IterationMode::LazyOuter => {
                self.library_iterate(
                    graph,
                    items,
                    node,
                    caller,
                    site,
                    LibraryRole::Inner,
                    Unless::Nothing,
                );
            }
            IterationMode::Starmap => {
                let bundle = self.node(graph, None);
                self.library_iterate(
                    graph,
                    items,
                    bundle,
                    caller,
                    site,
                    LibraryRole::Bundle,
                    Unless::Nothing,
                );
                self.add_length_hint(graph, items, caller, site, LENGTH_HINT);
            }
            IterationMode::Groupby => {
                if self.operation(state).key_is_item {
                    let made = self.operation(state).activations[activation]
                        .made
                        .expect("a group pair");
                    let first = self.element(graph, made, &Literal::Int(0.into()));
                    self.add_edge(graph, items, first);
                }
            }
            _ if values == Shape::Items
                || (values == Shape::First && position == Position::At(0)) =>
            {
                self.add_edge(graph, items, node);
            }
            _ if matches!(values, Shape::Tuples | Shape::Positions) => {
                let shapes: Vec<_> = self.operation(state).activations[activation]
                    .shapes
                    .iter()
                    .map(|(&arity, &shape)| (arity, shape))
                    .collect();
                for (arity, shape) in shapes {
                    self.shape_items(graph, items, shape, arity, position);
                }
            }
            _ => {}
        }
    }

    pub(super) fn consume_library(
        &mut self,
        graph: &mut Graph,
        call: CallId,
        consuming: &[(Box<str>, Overload)],
    ) {
        for (path, overload) in consuming {
            if NOT_CONSUMING.contains(&&**path) {
                continue;
            }
            for parameter in overload.parameters.iter() {
                if !abstract_iterable(&parameter.annotation) {
                    continue;
                }
                if let Some(node) = self.parameter_node(graph, overload.bound, parameter) {
                    let rule = self.rule(Rule::Library(LibraryRule::Consume { call }));
                    self.attach(graph, node, rule);
                }
            }
        }
    }

    pub(super) fn library_apply(&mut self, graph: &mut Graph, rule: LibraryRule, object: ObjId) {
        match rule {
            LibraryRule::Iterator { iteration, dst } => {
                self.iterator(graph, object, iteration, dst)
            }
            LibraryRule::IteratorOf {
                call,
                iteration,
                dst,
            } => {
                if matches!(self.objects.get(object), Object::Container(_)) {
                    self.add_object(graph, dst, object);
                    return;
                }
                self.call_dunder(graph, object, "__iter__", call, Some(dst), Unless::Nothing);
                let types = self.types_node(graph, object);
                let rule = self.rule(Rule::Container(ContainerRule::SequenceType {
                    object,
                    iteration,
                    dst,
                }));
                self.attach(graph, types, rule);
            }
            LibraryRule::Consume { call } => {
                if !self.is_library(object) {
                    return;
                }
                let details = &self.calls[call.index()];
                let (caller, site) = (details.caller, details.site);
                let dst = self.node(graph, None);
                let consuming =
                    self.new_iteration(graph, dst, caller, site, false, Unless::Nothing, "consume");
                self.advance_library(graph, object, consuming);
            }
        }
    }

    pub(super) fn add_iterator_length_hint(
        &mut self,
        graph: &mut Graph,
        iterable: NodeId,
        caller: Sym,
        site: Sym,
    ) {
        if !self
            .library
            .iterator_length_hints
            .insert((caller, site, iterable))
        {
            return;
        }
        let iterators = self.node(graph, None);
        let name = self.symbols.intern("__iter__");
        let key = self.site_key(caller, site, Role::Protocol(name));
        let call = self.site_call(graph, key, &[], None, None);
        let dst = self.node(graph, None);
        let iteration =
            self.new_iteration(graph, dst, caller, site, false, Unless::Nothing, "length");
        let rule = self.rule(Rule::Library(LibraryRule::IteratorOf {
            call,
            iteration,
            dst: iterators,
        }));
        self.attach(graph, iterable, rule);
        self.add_length_hint(graph, iterators, caller, site, LENGTH_HINT);
    }

    pub(super) fn call_back_library(
        &mut self,
        graph: &mut Graph,
        call: CallId,
        calling: &[(&'static str, Overload)],
    ) {
        let details = &self.calls[call.index()];
        let (caller, site) = (details.caller, details.site);
        let key = self.site_key(caller, site, Role::CallBack);
        let back = self.site_call(graph, key, &[None], None, None);
        for (name, overload) in calling {
            for parameter in overload.parameters.iter() {
                let node = self.parameter_node(graph, overload.bound, parameter);
                if &*parameter.name == *name
                    && let Some(node) = node
                {
                    let callee = self.callee(graph, back);
                    self.add_edge(graph, node, callee);
                }
            }
        }
    }

    pub(super) fn wrapped_key(
        &mut self,
        graph: &mut Graph,
        name: &str,
        call: CallId,
        overloads: &[Overload],
    ) {
        let dst = self.calls[call.index()]
            .dst
            .expect("a wrapped key has a result");
        for overload in overloads {
            if self.bound_given(overload.bound, name) {
                let node = self.bound_parameter(graph, overload.bound, name);
                self.add_edge(graph, node, dst);
            }
        }
    }

    pub(super) fn call_sequence_key(
        &mut self,
        graph: &mut Graph,
        call: CallId,
        keyed: &[(&'static [&'static str], Overload)],
    ) {
        let details = &self.calls[call.index()];
        let (caller, site) = (details.caller, details.site);
        let items = self.node(graph, None);
        for (wholes, overload) in keyed {
            let bound = overload.bound;
            if !self.bound_given(bound, "key") {
                continue;
            }
            let key = self.bound_parameter(graph, bound, "key");
            if self.bound_given(bound, "a") {
                let sequence = self.bound_parameter(graph, bound, "a");
                let index = self.node(graph, None);
                self.add_subscript(
                    graph,
                    sequence,
                    Some(index),
                    Some(items),
                    None,
                    false,
                    caller,
                    site,
                );
            }
            for name in wholes.iter() {
                if self.bound_given(bound, name) {
                    let whole = self.bound_parameter(graph, bound, name);
                    self.add_edge(graph, whole, items);
                }
            }
            self.call_key(graph, Some(key), items, caller, site, Role::SequenceKey);
        }
    }

    pub(super) fn length_hints(
        &mut self,
        graph: &mut Graph,
        call: CallId,
        hinting: &[((&'static str, LengthPlan, LengthSource), Overload)],
    ) {
        let details = &self.calls[call.index()];
        let (caller, site) = (details.caller, details.site);
        for &((name, plan, how), ref overload) in hinting {
            for parameter in overload.parameters.iter() {
                let node = self.parameter_node(graph, overload.bound, parameter);
                let Some(node) = node.filter(|_| &*parameter.name == name) else {
                    continue;
                };
                match how {
                    LengthSource::Iterator => {
                        self.add_iterator_length_hint(graph, node, caller, site)
                    }
                    LengthSource::Argument => self.add_length_hint(graph, node, caller, site, plan),
                }
            }
        }
    }

    pub(super) fn hash_arguments(
        &mut self,
        graph: &mut Graph,
        path: &'static str,
        call: CallId,
        overloads: &[Overload],
        receivers: &[ObjId],
    ) {
        let &(parameter, iterable) = lookup(HASHED_ARGUMENTS, path).expect("a hashed argument");
        let details = &self.calls[call.index()];
        let (caller, site) = (details.caller, details.site);
        let mut given = self.node(graph, None);
        for overload in overloads {
            for each in overload.parameters.iter() {
                let node = self.parameter_node(graph, overload.bound, each);
                if &*each.name == parameter
                    && let Some(node) = node
                {
                    self.add_edge(graph, node, given);
                }
            }
        }
        let stored = self.node(graph, None);
        if let Some(&receiver) = receivers.first()
            && matches!(self.objects.get(receiver), Object::Container(_))
            && self.hashes_keys(receiver)
        {
            let elements = self.elements(graph, receiver);
            self.add_edge(graph, elements, stored);
        }
        if iterable {
            let construct = KeysConstruct::Arguments(call, path);
            let (hashed, kept) =
                self.entering_keys(graph, given, construct, caller, site, Keeps::Hashes);
            given = hashed;
            self.add_edge(graph, given, stored);
            self.add_edge(graph, kept, stored);
        }
        self.add_hash(graph, given, caller, site, Some(stored));
    }

    pub(super) fn compare_items(
        &mut self,
        graph: &mut Graph,
        method: &str,
        call: CallId,
        overloads: &[Overload],
    ) {
        let details = &self.calls[call.index()];
        let (caller, site) = (details.caller, details.site);
        let iterables = self.node(graph, None);
        let items = self.node(graph, None);
        let keys = self.node(graph, None);
        let compared = self.node(graph, None);
        let mut keyed = false;
        for overload in overloads {
            let positional: Vec<_> = overload
                .parameters
                .iter()
                .filter(|parameter| {
                    matches!(
                        parameter.kind,
                        ParameterKind::PositionalOnly
                            | ParameterKind::PositionalOrKeyword
                            | ParameterKind::VarPositional
                    )
                })
                .cloned()
                .collect();
            let target = if positional.len() == 1 {
                iterables
            } else {
                items
            };
            for parameter in &positional {
                if let Some(node) = self.parameter_node(graph, overload.bound, parameter) {
                    self.add_edge(graph, node, target);
                }
            }
            if self.bound_given(overload.bound, "key") {
                let key = self.bound_parameter(graph, overload.bound, "key");
                self.add_edge(graph, key, keys);
                keyed = keyed || self.bound_surely(overload.bound, "key");
            }
        }
        self.add_iteration(graph, iterables, items, caller, site, false);
        if !keyed {
            self.add_edge(graph, items, compared);
        }
        let key = self.site_key(caller, site, Role::Key);
        let by_key = self.site_call(graph, key, &[Some(items)], Some(compared), None);
        let callee = self.callee(graph, by_key);
        self.add_edge(graph, keys, callee);
        let method_sym = self.symbols.intern(method);
        let reflected = self.symbols.intern(reflected_comparison(method));
        let plan = self.new_plan(vec![
            (method_sym, Unless::Nothing),
            (reflected, Unless::Names(Box::from([method_sym]))),
        ]);
        let rule = self.rule(Rule::CallProtocol { plan, caller, site });
        self.attach(graph, compared, rule);
        self.compare_containers(graph, compared, method, caller, site);
    }
}

impl Library {
    pub(crate) fn table_sizes(&self, sizes: &mut Vec<(&'static str, usize)>) {
        let Library {
            calls: _,
            operations,
            sources: _,
            lazy: _,
            advances,
            iterator_length_hints: _,
        } = self;
        sizes.extend([
            ("library operations", operations.len()),
            ("library advances", advances.len()),
        ]);
    }
}
