use std::collections::VecDeque;

use indexmap::IndexMap;
use num_bigint::BigInt;
use pycg_solver::{NodeId, ObjId};
use pycg_stubs::DefinitionKind;
use rustc_hash::{FxHashMap, FxHashSet};

use crate::engine::arguments::{BindingId, SpreadId, Spreads};
use crate::engine::hierarchy::Unless;
use crate::engine::library::{LibraryOrigin, LibraryRole};
use crate::engine::objects::{Container, Kind, Literal, Object};
use crate::engine::outside_calls::BoundId;
use crate::engine::outside_types::TypeOrigin;
use crate::engine::protocols::OperatorId;
use crate::engine::rules::Rule;
use crate::engine::semantics::{CallId, Origin, Role, SiteKey};
use crate::engine::symbols::Sym;
use crate::engine::trace::Trace;
use crate::engine::{Graph, OrderedMap, State, not_ported};
use crate::model::constant_name;
use crate::models::{LENGTH_HINT, builtin_kind};

const SEQUENCES: [&str; 2] = ["list", "tuple"];
const COLLECTIONS: [&str; 5] = ["list", "tuple", "set", "frozenset", "dict"];
const HASHED: [&str; 3] = ["set", "frozenset", "dict"];

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub(crate) struct StorageId(pub(crate) u32);
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub(crate) struct GroupId(u32);
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub(crate) struct KeyedId(u32);
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub(crate) struct KeyedGroupId(u32);
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub(crate) struct KeyLookupId(u32);
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub(crate) struct IterationId(u32);
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub(crate) struct SubscriptId(u32);
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub(crate) struct SliceId(u32);
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub(crate) struct UnpackId(u32);
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub(crate) struct DictHubId(u32);
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub(crate) struct DictItemsId(u32);
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub(crate) struct SequencesId(u32);
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub(crate) struct IterationRoleId(u32);

fn index_of(id: u32) -> usize {
    id as usize
}

fn next_id(length: usize) -> u32 {
    u32::try_from(length).expect("fewer than 2^32 container records")
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub(crate) enum IterationName {
    Plain(Sym),
    Library(LibraryRole),
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub(super) enum ContainerOrigin {
    Rule(Origin, &'static str, Option<u32>),
    Object(ObjId, &'static str),
    Inexact(ObjId),
    ClassStatement(Sym),
    Slice(SliceId),
    Rest(Sym, Sym),
    Iterate(Sym, Sym, IterationRoleId),
    Iterator(ObjId),
    Operator(OperatorId),
    Stub(u32),
    Annotation(ObjId, Sym),
    Library(LibraryOrigin),
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub(crate) enum KeysConstruct {
    Builder(Sym, Sym),
    Bound(BoundId),
    Arguments(CallId, &'static str),
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub(crate) enum Keeps {
    Hashes,
    MappingHashes,
}

type ContainerKey = (Sym, ContainerOrigin, bool);

pub(crate) type Bounds = (Option<BigInt>, Option<BigInt>);

#[derive(Clone, Copy, Debug)]
pub(crate) enum Observer {
    CopyField { target: ObjId },
    ReadPattern { pattern: ObjId, dst: NodeId },
    BindUnpacked(BindingId),
    GatherSequence(SpreadId),
    GatherMapping(SpreadId),
    BindKeyword { function: ObjId, call: CallId },
}

#[derive(Default)]
struct Storage {
    fields: OrderedMap<Literal, NodeId>,
    observers: Vec<Observer>,
}

#[derive(Clone, Copy, Default)]
struct ContainerNodes {
    unknown: Option<NodeId>,
    every: Option<NodeId>,
    keys: Option<NodeId>,
    factory: Option<NodeId>,
    aliased: Option<NodeId>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub(crate) enum Keyable {
    Container(ObjId),
    Group(GroupId),
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum KeyAccess {
    Read,
    Write,
}

struct ContainerGroup {
    containers: Vec<ObjId>,
    hubs: FxHashMap<Option<ObjId>, NodeId>,
}

pub(crate) struct Keyed {
    access: KeyAccess,
    container: ObjId,
    node: NodeId,
    other_key: bool,
    pub(crate) result: Option<NodeId>,
}

pub(crate) struct KeyedGroup {
    access: KeyAccess,
    node: NodeId,
    pub(crate) result: Option<NodeId>,
    containers: Vec<Keyable>,
    keys: Vec<ObjId>,
    other_keys: FxHashSet<Keyable>,
}

struct KeyLookup {
    call: CallId,
    first: Option<ObjId>,
    many: bool,
    stored_keys: Option<OrderedMap<ObjId, ()>>,
    first_stored: bool,
}

#[derive(Clone, Copy)]
pub(crate) struct Iteration {
    pub(crate) dst: NodeId,
    pub(crate) caller: Sym,
    pub(crate) site: Sym,
    is_async: bool,
    role: IterationRoleId,
    iterators: Option<NodeId>,
    call: Option<CallId>,
    index_call: Option<CallId>,
    anext: Option<NodeId>,
    callable_call: Option<CallId>,
}

pub(crate) struct Subscript {
    key: Option<NodeId>,
    pub(crate) dst: Option<NodeId>,
    src: Option<NodeId>,
    delete: bool,
    caller: Sym,
    site: Sym,
    calls: FxHashMap<Sym, CallId>,
    reads: Option<KeyedGroupId>,
    writes: Option<KeyedGroupId>,
}

pub(crate) struct Slice {
    bounds: Option<Bounds>,
    pub(crate) dst: Option<NodeId>,
    src: Option<NodeId>,
    delete: bool,
    caller: Sym,
    site: Sym,
    calls: FxHashMap<Sym, CallId>,
}

pub(crate) struct Unpack {
    pub(crate) before: Vec<NodeId>,
    pub(crate) starred: Option<NodeId>,
    pub(crate) after: Vec<NodeId>,
    caller: Sym,
    site: Sym,
    rest: Option<ObjId>,
    iteration: Option<IterationId>,
}

struct DictHub {
    container: ObjId,
    hashed: NodeId,
    sources: OrderedMap<ObjId, ()>,
    targets: OrderedMap<(ObjId, Sym, Sym), ()>,
    sites: FxHashSet<(Sym, Sym)>,
    active: bool,
}

struct DictItems {
    target: ObjId,
    hub: DictHubId,
    caller: Sym,
    site: Sym,
    pairs: Option<IterationId>,
}

pub(crate) struct Sequences {
    iteration: IterationId,
    pub(crate) dst: NodeId,
    objects: Vec<ObjId>,
    found: bool,
    rule: Option<crate::engine::rules::RuleId>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
enum Subscription {
    CopyFields(ObjId, ObjId),
    ClassSubscript(ObjId, Access),
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
enum Iterated {
    Slice(SliceId),
    Keys(KeysConstruct),
}

#[derive(Default)]
pub(crate) struct Containers {
    containers: FxHashMap<ContainerKey, ObjId>,
    storages: Vec<Storage>,
    storage_of: FxHashMap<ObjId, StorageId>,
    nodes: FxHashMap<ObjId, ContainerNodes>,
    notices: VecDeque<(Observer, Literal, NodeId)>,
    notifying: bool,
    keyed: Vec<(NodeId, Keyable, NodeId, KeyAccess)>,
    completed_keys: usize,
    groups: Vec<ContainerGroup>,
    group_of: FxHashMap<Vec<ObjId>, GroupId>,
    keyed_rules: Vec<Keyed>,
    keyed_groups: Vec<KeyedGroup>,
    key_lookups: Vec<KeyLookup>,
    compared_keys: FxHashMap<CallId, FxHashSet<ObjId>>,
    subscript_keys: FxHashMap<(NodeId, Sym, Sym), KeyLookupId>,
    iterated: FxHashMap<Iterated, (NodeId, NodeId, Option<NodeId>)>,
    iterations: Vec<Iteration>,
    iteration_roles: IndexMap<(IterationName, bool, Unless), ()>,
    subscripts: Vec<Subscript>,
    slices: Vec<Slice>,
    unpacks: Vec<Unpack>,
    hubs: Vec<DictHub>,
    hub_of: FxHashMap<NodeId, DictHubId>,
    dict_items: Vec<DictItems>,
    sequences: Vec<Sequences>,
    sequences_of: FxHashMap<(ObjId, bool, IterationId, NodeId), SequencesId>,
    subscriptions: FxHashSet<Subscription>,
    pub(crate) spreads: Spreads,
}

impl Containers {
    pub(crate) fn keyed(&self, id: KeyedId) -> &Keyed {
        &self.keyed_rules[index_of(id.0)]
    }

    pub(crate) fn keyed_group(&self, id: KeyedGroupId) -> &KeyedGroup {
        &self.keyed_groups[index_of(id.0)]
    }

    pub(crate) fn iteration(&self, id: IterationId) -> &Iteration {
        &self.iterations[index_of(id.0)]
    }

    pub(crate) fn subscript(&self, id: SubscriptId) -> &Subscript {
        &self.subscripts[index_of(id.0)]
    }

    pub(crate) fn slice(&self, id: SliceId) -> &Slice {
        &self.slices[index_of(id.0)]
    }

    pub(crate) fn unpack(&self, id: UnpackId) -> &Unpack {
        &self.unpacks[index_of(id.0)]
    }

    pub(crate) fn sequences(&self, id: SequencesId) -> &Sequences {
        &self.sequences[index_of(id.0)]
    }

    pub(crate) fn iteration_role(&self, id: IterationRoleId) -> (IterationName, bool, &Unless) {
        let ((role, is_async, unless), ()) = self
            .iteration_roles
            .get_index(index_of(id.0))
            .expect("an interned iteration role");
        (*role, *is_async, unless)
    }
}

pub(super) fn is_sequence(kind: &str) -> bool {
    SEQUENCES.contains(&kind)
}

impl<T: Trace> State<T> {
    pub(super) fn add_inexact(&mut self, graph: &mut Graph, source: NodeId, dst: NodeId) {
        let rule = self.rule(Rule::AddInexact { dst });
        self.attach(graph, source, rule);
    }

    pub(super) fn inexact_object(&mut self, graph: &mut Graph, object: ObjId) -> ObjId {
        let inexact = match self.objects.get(object) {
            Object::Const { value, exact: true } => Object::Const {
                value: value.clone(),
                exact: false,
            },
            &Object::Generator {
                function,
                exact: true,
            } => Object::Generator {
                function,
                exact: false,
            },
            &Object::Coroutine {
                function,
                exact: true,
            } => Object::Coroutine {
                function,
                exact: false,
            },
            Object::Container(container) if container.exact => {
                return self.inexact_container(graph, object);
            }
            Object::Pattern {
                prefix,
                suffix,
                case,
                exact: true,
            } => {
                let (prefix, suffix, case) = (prefix.clone(), suffix.clone(), *case);
                return self.pattern(graph, &prefix, &suffix, case, false);
            }
            Object::Const { exact: false, .. }
            | Object::Generator { exact: false, .. }
            | Object::Coroutine { exact: false, .. }
            | Object::Container(_)
            | Object::Saturated
            | Object::Module(_)
            | Object::External(_)
            | Object::UnknownExternal(_)
            | Object::Function(_)
            | Object::Class(_)
            | Object::Instance { .. }
            | Object::BoundMethod { .. }
            | Object::Fallback { .. }
            | Object::Wrapper { .. }
            | Object::Super { .. }
            | Object::Typed { .. }
            | Object::Closure { .. }
            | Object::BuiltinMethod { .. }
            | Object::ReturnsArgument { .. }
            | Object::Pattern { exact: false, .. }
            | Object::TypeForm { .. } => return object,
        };
        if let Some(&found) = self.inexact.get(&object) {
            return found;
        }
        let found = self.new_object(graph, inexact);
        self.inexact.insert(object, found);
        found
    }

    pub(super) fn container_of(&self, object: ObjId) -> Option<&Container> {
        match self.objects.get(object) {
            Object::Container(container) => Some(container),
            _ => None,
        }
    }

    pub(super) fn container_kind(&self, container: ObjId) -> &str {
        self.kind_text(container)
    }

    fn kind_text(&self, container: ObjId) -> &str {
        let found = self.container_of(container).expect("a container");
        self.symbols.text(found.kind)
    }

    pub(super) fn hashes_keys(&self, container: ObjId) -> bool {
        HASHED.contains(&builtin_kind(self.kind_text(container)))
    }

    pub(super) fn container_factory(&self, container: ObjId) -> Option<NodeId> {
        self.container_nodes(container).factory
    }

    pub(super) fn is_dict(&self, container: ObjId) -> bool {
        builtin_kind(self.kind_text(container)) == "dict"
    }

    fn keeps_hashes(&self, container: ObjId) -> bool {
        HASHED.contains(&self.kind_text(container))
    }

    fn keeps_mapping_hashes(&self, container: ObjId) -> bool {
        self.is_dict(container) && self.kind_text(container) != "collections.OrderedDict"
    }

    fn container_label(&self, container: ObjId) -> String {
        self.objects.name(container, &self.symbols)
    }

    fn storage(&mut self, container: ObjId) -> StorageId {
        if let Some(&storage) = self.containers.storage_of.get(&container) {
            return storage;
        }
        let storage = StorageId(next_id(self.containers.storages.len()));
        self.containers.storages.push(Storage::default());
        self.containers.storage_of.insert(container, storage);
        storage
    }

    fn container_nodes(&self, container: ObjId) -> ContainerNodes {
        self.containers
            .nodes
            .get(&container)
            .copied()
            .unwrap_or_default()
    }

    fn set_container_nodes(&mut self, container: ObjId, nodes: ContainerNodes) {
        self.containers.nodes.insert(container, nodes);
    }

    pub(super) fn new_container(
        &mut self,
        graph: &mut Graph,
        kind: &str,
        site: &str,
        length: Option<u32>,
        exact: bool,
    ) -> ObjId {
        let container = Container {
            kind: self.symbols.intern(kind),
            site: self.symbols.intern(site),
            length,
            exact,
        };
        self.new_object(graph, Object::Container(container))
    }

    pub(super) fn container_at(
        &mut self,
        graph: &mut Graph,
        kind: &str,
        origin: ContainerOrigin,
        site: Sym,
        length: Option<u32>,
        exact: bool,
    ) -> ObjId {
        let kind = self.symbols.intern(kind);
        let key = (kind, origin, exact);
        if let Some(&found) = self.containers.containers.get(&key) {
            let existing = self.container_of(found).expect("a container");
            assert_eq!(existing.length, length, "{key:?} with another length");
            return found;
        }
        let container = Container {
            kind,
            site,
            length,
            exact,
        };
        let made = self.new_object(graph, Object::Container(container));
        self.containers.containers.insert(key, made);
        made
    }

    pub(super) fn inexact_container(&mut self, graph: &mut Graph, container: ObjId) -> ObjId {
        let source = *self.container_of(container).expect("a container");
        let key = (source.kind, ContainerOrigin::Inexact(container), false);
        if let Some(&alias) = self.containers.containers.get(&key) {
            return alias;
        }
        let unnamed = self.symbols.intern("");
        let alias = self.new_object(
            graph,
            Object::Container(Container {
                site: unnamed,
                exact: false,
                ..source
            }),
        );
        if let Object::Container(made) = self.objects.get_mut(alias) {
            made.site = source.site;
        }
        let storage = self.storage(container);
        self.containers.storage_of.insert(alias, storage);
        let unknown = self.unknown(graph, container);
        let every = self.every(graph, container);
        let keys = self.keys(graph, container);
        let factory = self.container_nodes(container).factory;
        let aliased = self.aliased(graph, container);
        self.set_container_nodes(
            alias,
            ContainerNodes {
                unknown: Some(unknown),
                every: Some(every),
                keys: Some(keys),
                factory,
                aliased: Some(aliased),
            },
        );
        self.containers.containers.insert(key, alias);
        alias
    }

    pub(super) fn element(&mut self, graph: &mut Graph, container: ObjId, key: &Literal) -> NodeId {
        let storage = self.storage(container);
        if let Some(&node) = self.containers.storages[index_of(storage.0)]
            .fields
            .get(key)
        {
            return node;
        }
        let label = format!(
            "{}[{}]",
            self.container_label(container),
            constant_name(&key.view())
        );
        let node = self.node(graph, Some(&label));
        self.containers.storages[index_of(storage.0)]
            .fields
            .insert(key.clone(), node);
        if let Some(every) = self.container_nodes(container).every {
            self.add_edge(graph, node, every);
        }
        let observers = self.containers.storages[index_of(storage.0)]
            .observers
            .clone();
        for observer in observers {
            self.notify(graph, observer, key.clone(), node);
        }
        node
    }

    pub(super) fn unknown(&mut self, graph: &mut Graph, container: ObjId) -> NodeId {
        let mut nodes = self.container_nodes(container);
        if let Some(unknown) = nodes.unknown {
            return unknown;
        }
        let label = format!("{}[?]", self.container_label(container));
        let unknown = self.node(graph, Some(&label));
        nodes.unknown = Some(unknown);
        self.set_container_nodes(container, nodes);
        if let Some(every) = nodes.every {
            self.add_edge(graph, unknown, every);
        }
        unknown
    }

    pub(super) fn every(&mut self, graph: &mut Graph, container: ObjId) -> NodeId {
        let mut nodes = self.container_nodes(container);
        if let Some(every) = nodes.every {
            return every;
        }
        let every = self.node(graph, None);
        nodes.every = Some(every);
        self.set_container_nodes(container, nodes);
        let storage = self.storage(container);
        let fields: Vec<NodeId> = self.containers.storages[index_of(storage.0)]
            .fields
            .values()
            .copied()
            .collect();
        for node in fields {
            self.add_edge(graph, node, every);
        }
        if let Some(unknown) = nodes.unknown {
            self.add_edge(graph, unknown, every);
        }
        every
    }

    fn labelled_container_node(
        &mut self,
        graph: &mut Graph,
        container: ObjId,
        suffix: &str,
        get: fn(&mut ContainerNodes) -> &mut Option<NodeId>,
    ) -> NodeId {
        let mut nodes = self.container_nodes(container);
        if let Some(node) = *get(&mut nodes) {
            return node;
        }
        let label = format!("{}.{suffix}", self.container_label(container));
        let node = self.node(graph, Some(&label));
        *get(&mut nodes) = Some(node);
        self.set_container_nodes(container, nodes);
        node
    }

    pub(super) fn keys(&mut self, graph: &mut Graph, container: ObjId) -> NodeId {
        self.labelled_container_node(graph, container, "<keys>", |nodes| &mut nodes.keys)
    }

    pub(super) fn aliased(&mut self, graph: &mut Graph, container: ObjId) -> NodeId {
        self.labelled_container_node(graph, container, "<aliased>", |nodes| &mut nodes.aliased)
    }

    pub(super) fn factory(&mut self, graph: &mut Graph, container: ObjId) -> NodeId {
        self.labelled_container_node(graph, container, "<factory>", |nodes| &mut nodes.factory)
    }

    pub(super) fn key_store(&mut self, graph: &mut Graph, container: ObjId) -> NodeId {
        if self.is_dict(container) {
            self.keys(graph, container)
        } else {
            self.unknown(graph, container)
        }
    }

    #[allow(clippy::too_many_arguments)]
    pub(super) fn add_keys(
        &mut self,
        graph: &mut Graph,
        target: ObjId,
        source: NodeId,
        construct: KeysConstruct,
        caller: Sym,
        site: Sym,
        keeps: Keeps,
    ) {
        let (hashed, kept) = self.entering_keys(graph, source, construct, caller, site, keeps);
        let store = self.key_store(graph, target);
        self.add_edge(graph, hashed, store);
        let store = self.key_store(graph, target);
        self.add_edge(graph, kept, store);
        let elements = self.elements(graph, target);
        self.add_hash(graph, hashed, caller, site, Some(elements));
    }

    pub(super) fn add_next(
        &mut self,
        graph: &mut Graph,
        iterator: NodeId,
        dst: NodeId,
        caller: Sym,
        site: Sym,
    ) {
        let iteration =
            self.new_iteration(graph, dst, caller, site, false, Unless::Nothing, "next");
        let rule = self.container_rule(ContainerRule::NextElement(iteration));
        self.attach(graph, iterator, rule);
    }

    pub(super) fn add_iter(
        &mut self,
        graph: &mut Graph,
        iterable: NodeId,
        dst: NodeId,
        caller: Sym,
        site: Sym,
    ) {
        let iteration =
            self.new_iteration(graph, dst, caller, site, false, Unless::Nothing, "iter");
        let rule = self.container_rule(ContainerRule::Iter { iteration, dst });
        self.attach(graph, iterable, rule);
    }

    fn iter_object(
        &mut self,
        graph: &mut Graph,
        object: ObjId,
        iteration: IterationId,
        dst: NodeId,
    ) {
        let mut object = object;
        if let Some(container) = self.container_of(object)
            && container.exact
            && COLLECTIONS.contains(&builtin_kind(self.symbols.text(container.kind)))
        {
            object = self.container_iterator(graph, object);
        }
        self.iterator(graph, object, iteration, dst);
    }

    pub(super) fn container_iterator(&mut self, graph: &mut Graph, container: ObjId) -> ObjId {
        let source = *self.container_of(container).expect("a container");
        let kind = format!("{}_iterator", builtin_kind(self.symbols.text(source.kind)));
        let kind = self.symbols.intern(&kind);
        let key = (kind, ContainerOrigin::Iterator(container), true);
        if let Some(&iterator) = self.containers.containers.get(&key) {
            return iterator;
        }
        let unnamed = self.symbols.intern("");
        let iterator = self.new_object(
            graph,
            Object::Container(Container {
                kind,
                site: unnamed,
                length: None,
                exact: true,
            }),
        );
        if let Object::Container(made) = self.objects.get_mut(iterator) {
            made.site = source.site;
        }
        self.containers.containers.insert(key, iterator);
        let elements = self.elements(graph, container);
        let unknown = self.unknown(graph, iterator);
        self.add_edge(graph, elements, unknown);
        iterator
    }

    pub(super) fn add_elements(
        &mut self,
        graph: &mut Graph,
        target: ObjId,
        source: NodeId,
        caller: Sym,
        site: Sym,
    ) {
        let unknown = self.unknown(graph, target);
        let iteration = self.new_iteration(
            graph,
            unknown,
            caller,
            site,
            false,
            Unless::Nothing,
            "elements",
        );
        let rule = self.container_rule(ContainerRule::CopyElements { target, iteration });
        self.attach(graph, source, rule);
    }

    fn copy_elements(
        &mut self,
        graph: &mut Graph,
        object: ObjId,
        target: ObjId,
        iteration: IterationId,
    ) {
        let both_sequences = self
            .container_of(object)
            .is_some_and(|container| is_sequence(self.symbols.text(container.kind)))
            && is_sequence(self.kind_text(target));
        if both_sequences {
            self.copy_range(graph, object, target, Some((Some(BigInt::ZERO), None)));
        } else {
            self.iterate(graph, object, iteration);
        }
    }

    pub(super) fn elements(&mut self, graph: &mut Graph, container: ObjId) -> NodeId {
        if self.is_dict(container) {
            self.keys(graph, container)
        } else {
            self.every(graph, container)
        }
    }

    fn observe(&mut self, graph: &mut Graph, container: ObjId, observer: Observer) {
        let storage = self.storage(container);
        self.observe_storage(graph, storage, observer);
    }

    pub(super) fn new_storage(&mut self) -> StorageId {
        let storage = StorageId(next_id(self.containers.storages.len()));
        self.containers.storages.push(Storage::default());
        storage
    }

    pub(super) fn observe_storage(
        &mut self,
        graph: &mut Graph,
        storage: StorageId,
        observer: Observer,
    ) {
        let entry = &mut self.containers.storages[index_of(storage.0)];
        entry.observers.push(observer);
        let fields: Vec<(Literal, NodeId)> = entry
            .fields
            .iter()
            .map(|(key, &node)| (key.clone(), node))
            .collect();
        for (key, node) in fields {
            self.notify(graph, observer, key, node);
        }
    }

    pub(super) fn storage_field(
        &mut self,
        graph: &mut Graph,
        storage: StorageId,
        key: &Literal,
    ) -> NodeId {
        if let Some(&node) = self.containers.storages[index_of(storage.0)]
            .fields
            .get(key)
        {
            return node;
        }
        let node = self.node(graph, None);
        self.containers.storages[index_of(storage.0)]
            .fields
            .insert(key.clone(), node);
        let observers = self.containers.storages[index_of(storage.0)]
            .observers
            .clone();
        for observer in observers {
            self.notify(graph, observer, key.clone(), node);
        }
        node
    }

    pub(super) fn container_storage(&mut self, container: ObjId) -> StorageId {
        self.storage(container)
    }

    fn notify(&mut self, graph: &mut Graph, observer: Observer, key: Literal, node: NodeId) {
        if self.containers.notifying {
            self.containers.notices.push_back((observer, key, node));
            return;
        }
        self.containers.notifying = true;
        if self.containers.notices.is_empty() {
            self.observed(graph, observer, &key, node);
        } else {
            self.containers.notices.push_back((observer, key, node));
        }
        while let Some((observer, key, node)) = self.containers.notices.pop_front() {
            self.observed(graph, observer, &key, node);
        }
        self.containers.notifying = false;
    }

    fn observed(&mut self, graph: &mut Graph, observer: Observer, key: &Literal, node: NodeId) {
        match observer {
            Observer::CopyField { target } => {
                let storage = self.storage(target);
                let existing = self.containers.storages[index_of(storage.0)]
                    .fields
                    .get(key)
                    .copied();
                let field = match existing {
                    Some(field) => field,
                    None => self.element(graph, target, key),
                };
                self.add_edge(graph, node, field);
            }
            Observer::ReadPattern { pattern, dst } => {
                if let Literal::Str(points) = key
                    && self.pattern_matches_points(pattern, points)
                {
                    self.add_edge(graph, node, dst);
                }
            }
            Observer::BindUnpacked(binding) => self.bind_unpacked_field(graph, binding, key, node),
            Observer::GatherSequence(spread) => {
                if let Literal::Int(value) = key
                    && *value >= BigInt::ZERO
                {
                    let field = self.spread_field(graph, spread, key);
                    self.add_edge(graph, node, field);
                }
            }
            Observer::GatherMapping(spread) => {
                if let Literal::Str(_) = key {
                    let field = self.spread_field(graph, spread, key);
                    self.add_edge(graph, node, field);
                }
            }
            Observer::BindKeyword { function, call } => {
                let Literal::Str(code_points) = key else {
                    unreachable!("a spread mapping is keyed by strings")
                };
                let name: String = code_points
                    .iter()
                    .map(|&point| {
                        char::from_u32(point)
                            .unwrap_or_else(|| not_ported("a keyword with a lone surrogate"))
                    })
                    .collect();
                let name = self.symbols.intern(&name);
                self.bind_keyword(graph, function, name, node, call);
            }
        }
    }

    fn field_key(&self, container: ObjId, key: &Literal) -> Option<Literal> {
        if self.is_dict(container) {
            return Some(key.clone());
        }
        let found = self.container_of(container).expect("a container");
        if !is_sequence(self.symbols.text(found.kind)) {
            return None;
        }
        if let Literal::Int(value) = key
            && *value < BigInt::ZERO
        {
            let length = BigInt::from(found.length?);
            if *value >= -length.clone() {
                return Some(Literal::Int(value + length));
            }
            return None;
        }
        Some(key.clone())
    }

    fn const_value(&self, object: ObjId) -> Option<(Literal, bool)> {
        match self.objects.get(object) {
            Object::Const { value, exact } => Some((value.clone(), *exact)),
            _ => None,
        }
    }

    fn read_key(&mut self, graph: &mut Graph, key: Option<ObjId>, container: ObjId, dst: NodeId) {
        if let Some((value, _)) = key.and_then(|key| self.const_value(key))
            && let Some(position) = self.field_key(container, &value)
        {
            let element = self.element(graph, container, &position);
            self.add_edge(graph, element, dst);
            let unknown = self.unknown(graph, container);
            self.add_edge(graph, unknown, dst);
            return;
        }
        if let Some(pattern) = key.filter(|&key| self.exact_pattern(key))
            && self.const_value(pattern).is_none()
            && self.is_dict(container)
        {
            let unknown = self.unknown(graph, container);
            self.add_edge(graph, unknown, dst);
            let aliased = self.aliased(graph, container);
            self.add_edge(graph, aliased, dst);
            self.observe(graph, container, Observer::ReadPattern { pattern, dst });
            return;
        }
        let every = self.every(graph, container);
        self.add_edge(graph, every, dst);
    }

    fn exact_pattern(&self, key: ObjId) -> bool {
        matches!(self.objects.get(key), Object::Pattern { exact: true, .. })
    }

    fn literal_key(&self, key: ObjId) -> bool {
        matches!(
            self.objects.get(key),
            Object::Const { .. } | Object::Pattern { .. }
        )
    }

    fn write_key(&mut self, graph: &mut Graph, key: Option<ObjId>, container: ObjId, src: NodeId) {
        if let Some((value, exact)) = key.and_then(|key| self.const_value(key))
            && let Some(position) = self.field_key(container, &value)
        {
            let element = self.element(graph, container, &position);
            self.add_edge(graph, src, element);
            if !exact && self.is_dict(container) {
                let aliased = self.aliased(graph, container);
                self.add_edge(graph, src, aliased);
            }
            return;
        }
        let unknown = self.unknown(graph, container);
        self.add_edge(graph, src, unknown);
    }

    fn access_key(
        &mut self,
        graph: &mut Graph,
        access: KeyAccess,
        key: Option<ObjId>,
        container: ObjId,
        node: NodeId,
    ) {
        match access {
            KeyAccess::Read => self.read_key(graph, key, container, node),
            KeyAccess::Write => self.write_key(graph, key, container, node),
        }
    }

    pub(super) fn site_key(&mut self, caller: Sym, site: Sym, role: Role) -> SiteKey {
        SiteKey {
            caller,
            site,
            role,
            implicit: true,
        }
    }

    pub(super) fn special_call(
        &mut self,
        graph: &mut Graph,
        value: NodeId,
        name: &str,
        call: CallId,
        unless: Unless,
    ) {
        let name = self.symbols.intern(name);
        let rule = self.container_rule(ContainerRule::SpecialCall { name, call, unless });
        self.attach(graph, value, rule);
    }

    pub(super) fn add_hash(
        &mut self,
        graph: &mut Graph,
        key: NodeId,
        caller: Sym,
        site: Sym,
        stored: Option<NodeId>,
    ) {
        let role = self.site_key(caller, site, Role::Hash);
        let call = self.site_call(graph, role, &[], None, None);
        self.special_call(graph, key, "__hash__", call, Unless::Nothing);
        if let Some(stored) = stored {
            self.compare_keys(graph, key, caller, site, stored);
        }
    }

    fn compare_keys(
        &mut self,
        graph: &mut Graph,
        key: NodeId,
        caller: Sym,
        site: Sym,
        stored: NodeId,
    ) {
        let pairing = self.key_lookup(graph, caller, site);
        let rule = self.container_rule(ContainerRule::KeyLookupKey(pairing));
        self.attach(graph, key, rule);
        let rule = self.container_rule(ContainerRule::KeyLookupStored(pairing));
        self.attach(graph, stored, rule);
    }

    fn key_lookup(&mut self, graph: &mut Graph, caller: Sym, site: Sym) -> KeyLookupId {
        let role = self.site_key(caller, site, Role::HashEq);
        let compare = self.site_call(graph, role, &[None], None, None);
        self.containers.compared_keys.entry(compare).or_default();
        let id = KeyLookupId(next_id(self.containers.key_lookups.len()));
        self.containers.key_lookups.push(KeyLookup {
            call: compare,
            first: None,
            many: false,
            stored_keys: Some(OrderedMap::default()),
            first_stored: false,
        });
        id
    }

    pub(super) fn key_lookup_key(&mut self, graph: &mut Graph, id: KeyLookupId, object: ObjId) {
        let lookup = &mut self.containers.key_lookups[index_of(id.0)];
        if lookup.many || lookup.first == Some(object) {
            return;
        }
        if lookup.first.is_none() {
            lookup.first = Some(object);
            let stored_keys = lookup
                .stored_keys
                .take()
                .expect("stored keys before the first");
            lookup.first_stored = stored_keys.contains_key(&object);
            for &stored in stored_keys.keys() {
                if stored != object && !self.opaque(stored) {
                    self.compare_stored(graph, id, stored);
                }
            }
            return;
        }
        lookup.many = true;
        if lookup.first_stored {
            let first = lookup.first.expect("a first key");
            if !self.opaque(first) {
                self.compare_stored(graph, id, first);
            }
        }
    }

    pub(super) fn key_lookup_stored(
        &mut self,
        graph: &mut Graph,
        id: KeyLookupId,
        instance: ObjId,
    ) {
        let lookup = &mut self.containers.key_lookups[index_of(id.0)];
        match lookup.first {
            None => {
                lookup
                    .stored_keys
                    .as_mut()
                    .expect("stored keys before the first")
                    .insert(instance, ());
            }
            Some(first) if lookup.many || instance != first => {
                self.compare_stored(graph, id, instance);
            }
            Some(_) => lookup.first_stored = true,
        }
    }

    fn compare_stored(&mut self, graph: &mut Graph, id: KeyLookupId, stored: ObjId) {
        let call = self.containers.key_lookups[index_of(id.0)].call;
        let compared = self
            .containers
            .compared_keys
            .get_mut(&call)
            .expect("the compared keys of a lookup");
        if compared.insert(stored) {
            self.call_dunder(graph, stored, "__eq__", call, None, Unless::Nothing);
        }
    }

    fn container_group(&mut self, containers: Vec<ObjId>) -> GroupId {
        let mut content = containers.clone();
        content.sort_by_key(|object| object.0);
        content.dedup();
        if let Some(&group) = self.containers.group_of.get(&content) {
            return group;
        }
        let group = GroupId(next_id(self.containers.groups.len()));
        self.containers.groups.push(ContainerGroup {
            containers,
            hubs: FxHashMap::default(),
        });
        self.containers.group_of.insert(content, group);
        group
    }

    fn read_group(&mut self, graph: &mut Graph, key: Option<ObjId>, group: GroupId, dst: NodeId) {
        let hub_key = key.filter(|&key| self.const_value(key).is_some() || self.exact_pattern(key));
        let existing = self.containers.groups[index_of(group.0)]
            .hubs
            .get(&hub_key)
            .copied();
        let hub = match existing {
            Some(hub) => hub,
            None => {
                let hub = self.node(graph, None);
                self.containers.groups[index_of(group.0)]
                    .hubs
                    .insert(hub_key, hub);
                let containers = self.containers.groups[index_of(group.0)].containers.clone();
                for container in containers {
                    self.read_key(graph, key, container, hub);
                }
                hub
            }
        };
        self.add_edge(graph, hub, dst);
    }

    fn new_keyed_group(
        &mut self,
        graph: &mut Graph,
        key: NodeId,
        access: KeyAccess,
        node: NodeId,
        result: Option<NodeId>,
    ) -> KeyedGroupId {
        let id = KeyedGroupId(next_id(self.containers.keyed_groups.len()));
        self.containers.keyed_groups.push(KeyedGroup {
            access,
            node,
            result,
            containers: Vec::new(),
            keys: Vec::new(),
            other_keys: FxHashSet::default(),
        });
        let rule = self.container_rule(ContainerRule::KeyedGroup(id));
        self.attach(graph, key, rule);
        id
    }

    fn keyed_group_add(&mut self, graph: &mut Graph, id: KeyedGroupId, container: Keyable) {
        let group = &mut self.containers.keyed_groups[index_of(id.0)];
        group.containers.push(container);
        let keys = group.keys.clone();
        for key in keys {
            self.keyed_pair(graph, id, key, container);
        }
    }

    pub(super) fn keyed_group_apply(&mut self, graph: &mut Graph, id: KeyedGroupId, key: ObjId) {
        if matches!(self.objects.get(key), Object::TypeForm { .. }) {
            return;
        }
        self.containers.keyed_groups[index_of(id.0)].keys.push(key);
        let containers = self.containers.keyed_groups[index_of(id.0)]
            .containers
            .clone();
        for container in containers {
            self.keyed_pair(graph, id, key, container);
        }
    }

    fn keyed_pair(&mut self, graph: &mut Graph, id: KeyedGroupId, key: ObjId, container: Keyable) {
        if !self.literal_key(key) {
            let group = &mut self.containers.keyed_groups[index_of(id.0)];
            if !group.other_keys.insert(container) {
                return;
            }
        }
        let group = &self.containers.keyed_groups[index_of(id.0)];
        let (access, node) = (group.access, group.node);
        match container {
            Keyable::Group(group) => self.read_group(graph, Some(key), group, node),
            Keyable::Container(container) => {
                self.access_key(graph, access, Some(key), container, node);
            }
        }
    }

    fn subscript_reads(&mut self, graph: &mut Graph, read: Keyable, id: SubscriptId) {
        let subscript = &self.containers.subscripts[index_of(id.0)];
        let key = subscript.key.expect("a keyed subscript");
        let dst = subscript.dst.expect("a subscript that reads");
        let reads = match subscript.reads {
            Some(reads) => reads,
            None => {
                let reads = self.new_keyed_group(graph, key, KeyAccess::Read, dst, Some(dst));
                self.containers.subscripts[index_of(id.0)].reads = Some(reads);
                reads
            }
        };
        self.keyed_group_add(graph, reads, read);
        self.containers
            .keyed
            .push((key, read, dst, KeyAccess::Read));
    }

    fn subscript_keyed(
        &mut self,
        graph: &mut Graph,
        container: ObjId,
        id: SubscriptId,
        read: bool,
    ) {
        let subscript = &self.containers.subscripts[index_of(id.0)];
        let (key, src, dst) = (
            subscript.key.expect("a keyed subscript"),
            subscript.src,
            subscript.dst,
        );
        if read && dst.is_some() {
            self.subscript_reads(graph, Keyable::Container(container), id);
        }
        if self.is_dict(container) {
            let keys = self.keys(graph, container);
            self.add_edge(graph, key, keys);
        }
        if let Some(src) = src {
            let writes = match self.containers.subscripts[index_of(id.0)].writes {
                Some(writes) => writes,
                None => {
                    let writes = self.new_keyed_group(graph, key, KeyAccess::Write, src, None);
                    self.containers.subscripts[index_of(id.0)].writes = Some(writes);
                    writes
                }
            };
            self.keyed_group_add(graph, writes, Keyable::Container(container));
            self.containers
                .keyed
                .push((key, Keyable::Container(container), src, KeyAccess::Write));
        }
    }

    fn hash_subscript_key(&mut self, graph: &mut Graph, id: SubscriptId, stored: NodeId) {
        let subscript = &self.containers.subscripts[index_of(id.0)];
        let (key, caller, site) = (
            subscript.key.expect("a keyed subscript"),
            subscript.caller,
            subscript.site,
        );
        let pairing = match self.containers.subscript_keys.get(&(key, caller, site)) {
            Some(&pairing) => pairing,
            None => {
                let role = self.site_key(caller, site, Role::Hash);
                let call = self.site_call(graph, role, &[], None, None);
                self.special_call(graph, key, "__hash__", call, Unless::Nothing);
                let pairing = self.key_lookup(graph, caller, site);
                self.containers
                    .subscript_keys
                    .insert((key, caller, site), pairing);
                let rule = self.container_rule(ContainerRule::KeyLookupKey(pairing));
                self.attach(graph, key, rule);
                pairing
            }
        };
        let rule = self.container_rule(ContainerRule::KeyLookupStored(pairing));
        self.attach(graph, stored, rule);
    }

    pub(super) fn entering_keys(
        &mut self,
        graph: &mut Graph,
        source: NodeId,
        construct: KeysConstruct,
        caller: Sym,
        site: Sym,
        keeps: Keeps,
    ) -> (NodeId, NodeId) {
        let key = Iterated::Keys(construct);
        if let Some(&(iterated, hashed, kept)) = self.containers.iterated.get(&key) {
            assert_eq!(iterated, source, "{construct:?} hashes another node");
            return (hashed, kept.expect("kept keys"));
        }
        let hashed = self.node(graph, None);
        let kept = self.node(graph, None);
        let iteration = self.new_iteration(
            graph,
            hashed,
            caller,
            site,
            false,
            Unless::Nothing,
            "elements",
        );
        let rule = self.container_rule(ContainerRule::EnterKeys {
            kept,
            iteration,
            keeps,
        });
        self.attach(graph, source, rule);
        self.containers
            .iterated
            .insert(key, (source, hashed, Some(kept)));
        (hashed, kept)
    }

    pub(super) fn enter_keys(
        &mut self,
        graph: &mut Graph,
        object: ObjId,
        kept: NodeId,
        iteration: IterationId,
        keeps: Keeps,
    ) {
        let kept_by_container = self.container_of(object).is_some()
            && match keeps {
                Keeps::Hashes => self.keeps_hashes(object),
                Keeps::MappingHashes => self.keeps_mapping_hashes(object),
            };
        if kept_by_container {
            let elements = self.elements(graph, object);
            self.add_edge(graph, elements, kept);
        } else {
            self.iterate(graph, object, iteration);
        }
    }

    pub(super) fn read_keyed(
        &mut self,
        graph: &mut Graph,
        container: ObjId,
        key: Option<NodeId>,
        dst: Option<NodeId>,
    ) {
        let Some(dst) = dst else {
            return;
        };
        let Some(key) = key else {
            let every = self.every(graph, container);
            self.add_edge(graph, every, dst);
            return;
        };
        self.new_keyed(graph, key, KeyAccess::Read, container, dst, Some(dst));
        self.containers
            .keyed
            .push((key, Keyable::Container(container), dst, KeyAccess::Read));
    }

    pub(super) fn write_keyed(
        &mut self,
        graph: &mut Graph,
        container: ObjId,
        key: Option<NodeId>,
        src: Option<NodeId>,
    ) {
        if let Some(key) = key
            && self.is_dict(container)
        {
            let keys = self.keys(graph, container);
            self.add_edge(graph, key, keys);
        }
        let Some(src) = src else {
            return;
        };
        let Some(key) = key else {
            let unknown = self.unknown(graph, container);
            self.add_edge(graph, src, unknown);
            return;
        };
        self.new_keyed(graph, key, KeyAccess::Write, container, src, None);
        self.containers
            .keyed
            .push((key, Keyable::Container(container), src, KeyAccess::Write));
    }

    fn new_keyed(
        &mut self,
        graph: &mut Graph,
        key: NodeId,
        access: KeyAccess,
        container: ObjId,
        node: NodeId,
        result: Option<NodeId>,
    ) {
        let id = KeyedId(next_id(self.containers.keyed_rules.len()));
        self.containers.keyed_rules.push(Keyed {
            access,
            container,
            node,
            other_key: false,
            result,
        });
        let rule = self.container_rule(ContainerRule::Keyed(id));
        self.attach(graph, key, rule);
    }

    pub(super) fn keyed_apply(&mut self, graph: &mut Graph, id: KeyedId, key: ObjId) {
        if matches!(self.objects.get(key), Object::TypeForm { .. }) {
            return;
        }
        let keyed = &mut self.containers.keyed_rules[index_of(id.0)];
        if !matches!(
            self.objects.get(key),
            Object::Const { .. } | Object::Pattern { .. }
        ) {
            if keyed.other_key {
                return;
            }
            keyed.other_key = true;
        }
        let (access, container, node) = (keyed.access, keyed.container, keyed.node);
        self.access_key(graph, access, Some(key), container, node);
    }

    pub(super) fn complete_keys(&mut self, graph: &mut Graph) -> bool {
        let mut added = false;
        let pending = self.containers.keyed[self.containers.completed_keys..].to_vec();
        for (key, container, node, access) in pending {
            if !self.objects_of(graph, key).is_empty() {
                continue;
            }
            match (container, access) {
                (Keyable::Group(group), _) => self.read_group(graph, None, group, node),
                (Keyable::Container(container), KeyAccess::Read) => {
                    let every = self.every(graph, container);
                    self.add_edge(graph, every, node);
                }
                (Keyable::Container(container), KeyAccess::Write) => {
                    let unknown = self.unknown(graph, container);
                    self.add_edge(graph, node, unknown);
                }
            }
            added = true;
        }
        self.containers.completed_keys = self.containers.keyed.len();
        added
    }

    pub(super) fn copy_range(
        &mut self,
        graph: &mut Graph,
        source: ObjId,
        target: ObjId,
        bounds: Option<Bounds>,
    ) {
        let length = self.container_of(source).expect("a container").length;
        match (bounds, length) {
            (Some(bounds), Some(length)) => {
                let (start, stop) = slice_indices(&bounds, length);
                for (offset, position) in (start..stop).enumerate() {
                    let from = self.element(graph, source, &Literal::Int(BigInt::from(position)));
                    let offset = i64::try_from(offset).expect("an offset fits i64");
                    let to = self.element(graph, target, &Literal::Int(BigInt::from(offset)));
                    self.add_edge(graph, from, to);
                }
                let from = self.unknown(graph, source);
                let to = self.unknown(graph, target);
                self.add_edge(graph, from, to);
            }
            _ => {
                let every = self.every(graph, source);
                let unknown = self.unknown(graph, target);
                self.add_edge(graph, every, unknown);
            }
        }
    }

    pub(super) fn copy_items(&mut self, graph: &mut Graph, source: ObjId, target: ObjId) {
        self.copy_fields(graph, source, target);
        let from = self.keys(graph, source);
        let to = self.keys(graph, target);
        self.add_edge(graph, from, to);
    }

    pub(super) fn copy_fields(&mut self, graph: &mut Graph, source: ObjId, target: ObjId) {
        if !self
            .containers
            .subscriptions
            .insert(Subscription::CopyFields(source, target))
        {
            return;
        }
        self.observe(graph, source, Observer::CopyField { target });
        let from = self.unknown(graph, source);
        let to = self.unknown(graph, target);
        self.add_edge(graph, from, to);
        if self.is_dict(source) && self.is_dict(target) {
            let from = self.aliased(graph, source);
            let to = self.aliased(graph, target);
            self.add_edge(graph, from, to);
        }
    }

    fn intern_iteration_role(
        &mut self,
        role: IterationName,
        is_async: bool,
        unless: Unless,
    ) -> IterationRoleId {
        let (index, _) = self
            .containers
            .iteration_roles
            .insert_full((role, is_async, unless), ());
        IterationRoleId(next_id(index))
    }

    #[allow(clippy::too_many_arguments)]
    pub(super) fn new_iteration(
        &mut self,
        _graph: &mut Graph,
        dst: NodeId,
        caller: Sym,
        site: Sym,
        is_async: bool,
        unless: Unless,
        role: &str,
    ) -> IterationId {
        let role = IterationName::Plain(self.symbols.intern(role));
        self.new_named_iteration(dst, caller, site, is_async, unless, role)
    }

    pub(super) fn new_named_iteration(
        &mut self,
        dst: NodeId,
        caller: Sym,
        site: Sym,
        is_async: bool,
        unless: Unless,
        role: IterationName,
    ) -> IterationId {
        let role = self.intern_iteration_role(role, is_async, unless);
        let id = IterationId(next_id(self.containers.iterations.len()));
        self.containers.iterations.push(Iteration {
            dst,
            caller,
            site,
            is_async,
            role,
            iterators: None,
            call: None,
            index_call: None,
            anext: None,
            callable_call: None,
        });
        id
    }

    fn iteration_call(&mut self, graph: &mut Graph, id: IterationId) -> CallId {
        let iteration = self.containers.iterations[index_of(id.0)];
        if let Some(call) = iteration.call {
            return call;
        }
        let key = self.site_key(
            iteration.caller,
            iteration.site,
            Role::Iterate(iteration.role),
        );
        let call = self.site_call(graph, key, &[], None, None);
        self.containers.iterations[index_of(id.0)].call = Some(call);
        call
    }

    fn iteration_index_call(&mut self, graph: &mut Graph, id: IterationId) -> CallId {
        let iteration = self.containers.iterations[index_of(id.0)];
        if let Some(call) = iteration.index_call {
            return call;
        }
        let key = self.site_key(
            iteration.caller,
            iteration.site,
            Role::Index(iteration.role),
        );
        let call = self.site_call(graph, key, &[None], None, None);
        self.containers.iterations[index_of(id.0)].index_call = Some(call);
        call
    }

    fn iteration_callable_call(&mut self, graph: &mut Graph, id: IterationId) -> CallId {
        let iteration = self.containers.iterations[index_of(id.0)];
        if let Some(call) = iteration.callable_call {
            return call;
        }
        let key = self.site_key(
            iteration.caller,
            iteration.site,
            Role::Callable(iteration.role),
        );
        let call = self.site_call(graph, key, &[], Some(iteration.dst), None);
        self.containers.iterations[index_of(id.0)].callable_call = Some(call);
        call
    }

    fn iteration_anext(&mut self, graph: &mut Graph, id: IterationId) -> NodeId {
        let iteration = self.containers.iterations[index_of(id.0)];
        if let Some(anext) = iteration.anext {
            return anext;
        }
        let anext = self.node(graph, None);
        self.containers.iterations[index_of(id.0)].anext = Some(anext);
        self.add_await(
            graph,
            anext,
            iteration.dst,
            iteration.caller,
            iteration.site,
        );
        anext
    }

    fn iteration_iterators(&mut self, graph: &mut Graph, id: IterationId) -> NodeId {
        let iteration = self.containers.iterations[index_of(id.0)];
        if let Some(iterators) = iteration.iterators {
            return iterators;
        }
        let iterators = self.node(graph, None);
        self.containers.iterations[index_of(id.0)].iterators = Some(iterators);
        let rule = self.container_rule(ContainerRule::NextElement(id));
        self.attach(graph, iterators, rule);
        iterators
    }

    #[allow(clippy::too_many_arguments)]
    pub(super) fn add_subscript(
        &mut self,
        graph: &mut Graph,
        base: NodeId,
        key: Option<NodeId>,
        dst: Option<NodeId>,
        src: Option<NodeId>,
        delete: bool,
        caller: Sym,
        site: Sym,
    ) {
        let id = SubscriptId(next_id(self.containers.subscripts.len()));
        self.containers.subscripts.push(Subscript {
            key,
            dst,
            src,
            delete,
            caller,
            site,
            calls: FxHashMap::default(),
            reads: None,
            writes: None,
        });
        let rule = self.container_rule(ContainerRule::Subscript(id));
        self.attach(graph, base, rule);
    }

    #[allow(clippy::too_many_arguments)]
    pub(super) fn add_slice(
        &mut self,
        graph: &mut Graph,
        base: NodeId,
        bounds: Option<Bounds>,
        dst: Option<NodeId>,
        src: Option<NodeId>,
        delete: bool,
        caller: Sym,
        site: Sym,
    ) {
        let id = SliceId(next_id(self.containers.slices.len()));
        self.containers.slices.push(Slice {
            bounds,
            dst,
            src,
            delete,
            caller,
            site,
            calls: FxHashMap::default(),
        });
        let rule = self.container_rule(ContainerRule::Slice(id));
        self.attach(graph, base, rule);
    }

    #[allow(clippy::too_many_arguments)]
    pub(super) fn add_unpack(
        &mut self,
        graph: &mut Graph,
        value: NodeId,
        before: &[NodeId],
        starred: Option<NodeId>,
        after: &[NodeId],
        caller: Sym,
        site: Sym,
    ) {
        let id = UnpackId(next_id(self.containers.unpacks.len()));
        self.containers.unpacks.push(Unpack {
            before: before.to_vec(),
            starred,
            after: after.to_vec(),
            caller,
            site,
            rest: None,
            iteration: None,
        });
        let rule = self.container_rule(ContainerRule::Unpack(id));
        self.attach(graph, value, rule);
    }

    pub(super) fn add_iteration(
        &mut self,
        graph: &mut Graph,
        iterable: NodeId,
        dst: NodeId,
        caller: Sym,
        site: Sym,
        is_async: bool,
    ) {
        let iteration =
            self.new_iteration(graph, dst, caller, site, is_async, Unless::Nothing, "for");
        let rule = self.container_rule(ContainerRule::Iterate(iteration));
        self.attach(graph, iterable, rule);
    }

    fn iterated_slice(
        &mut self,
        graph: &mut Graph,
        iterable: NodeId,
        slice: SliceId,
        caller: Sym,
        site: Sym,
    ) -> NodeId {
        let key = Iterated::Slice(slice);
        if let Some(&(iterated, node, _)) = self.containers.iterated.get(&key) {
            assert_eq!(iterated, iterable, "{key:?} iterates another node");
            return node;
        }
        let node = self.node(graph, None);
        self.containers.iterated.insert(key, (iterable, node, None));
        self.add_iteration(graph, iterable, node, caller, site, false);
        node
    }

    pub(super) fn add_yield_from(
        &mut self,
        graph: &mut Graph,
        iterable: NodeId,
        function: ObjId,
        dst: NodeId,
        caller: Sym,
        site: Sym,
    ) {
        let yield_node = self
            .objects
            .function(function)
            .yield_node
            .expect("a generator yields");
        self.add_iteration(graph, iterable, yield_node, caller, site, false);
        let rule = self.container_rule(ContainerRule::YieldFrom { function, dst });
        self.attach(graph, iterable, rule);
    }

    pub(super) fn yield_from(
        &mut self,
        graph: &mut Graph,
        object: ObjId,
        function: ObjId,
        dst: NodeId,
    ) {
        if let &Object::Generator {
            function: inner, ..
        } = self.objects.get(object)
        {
            let sent = self
                .objects
                .function(function)
                .sent_node
                .expect("a generator is sent to");
            let inner_sent = self
                .objects
                .function(inner)
                .sent_node
                .expect("a generator is sent to");
            self.add_edge(graph, sent, inner_sent);
            let returned = self
                .objects
                .function(inner)
                .return_node
                .expect("an analysed function returns");
            self.add_edge(graph, returned, dst);
        }
    }

    pub(super) fn add_dict_items(
        &mut self,
        graph: &mut Graph,
        target: ObjId,
        source: NodeId,
        caller: Sym,
        site: Sym,
    ) {
        let hub = match self.containers.hub_of.get(&source) {
            Some(&hub) => hub,
            None => {
                let site_text = self.symbols.text(site).to_owned();
                let container = self.new_container(graph, "dict", &site_text, None, false);
                let hashed = self.node(graph, None);
                let hub = DictHubId(next_id(self.containers.hubs.len()));
                self.containers.hubs.push(DictHub {
                    container,
                    hashed,
                    sources: OrderedMap::default(),
                    targets: OrderedMap::default(),
                    sites: FxHashSet::default(),
                    active: false,
                });
                self.containers.hub_of.insert(source, hub);
                hub
            }
        };
        let id = DictItemsId(next_id(self.containers.dict_items.len()));
        self.containers.dict_items.push(DictItems {
            target,
            hub,
            caller,
            site,
            pairs: None,
        });
        let rule = self.container_rule(ContainerRule::DictItems(id));
        self.attach(graph, source, rule);
    }

    pub(super) fn apply_subscripts(
        &mut self,
        graph: &mut Graph,
        objects: &[ObjId],
        id: SubscriptId,
    ) {
        let subscript = &self.containers.subscripts[index_of(id.0)];
        if subscript.key.is_none() || subscript.dst.is_none() {
            for &object in objects {
                self.apply_subscript(graph, object, id, true);
            }
            return;
        }
        let mut grouped = Vec::new();
        for &object in objects {
            if self.container_of(object).is_some() {
                grouped.push(object);
                self.apply_subscript(graph, object, id, false);
            } else {
                self.apply_subscript(graph, object, id, true);
            }
        }
        match grouped.as_slice() {
            [] => {}
            [one] => self.subscript_reads(graph, Keyable::Container(*one), id),
            _ => {
                let group = self.container_group(grouped);
                self.subscript_reads(graph, Keyable::Group(group), id);
            }
        }
    }

    pub(super) fn apply_subscript(
        &mut self,
        graph: &mut Graph,
        object: ObjId,
        id: SubscriptId,
        read: bool,
    ) {
        let subscript = &self.containers.subscripts[index_of(id.0)];
        let (key, dst, src) = (subscript.key, subscript.dst, subscript.src);
        let (caller, site) = (subscript.caller, subscript.site);
        let object = match self.objects.get(object) {
            Object::Const { .. } => match self.string_constant_value(graph, object) {
                Some(typed) => typed,
                None => return,
            },
            _ => object,
        };
        match self.objects.get(object) {
            Object::Typed { .. } => {
                let origin = TypeOrigin::Subscript { caller, site };
                self.typed_special(graph, object, "__getitem__", dst, origin);
            }
            Object::Container(_) => {
                match key {
                    None => {
                        self.read_keyed(graph, object, None, dst);
                        self.write_keyed(graph, object, None, src);
                    }
                    Some(_) => self.subscript_keyed(graph, object, id, read),
                }
                if self.is_dict(object) && key.is_some() {
                    let keys = self.keys(graph, object);
                    self.hash_subscript_key(graph, id, keys);
                }
                if self.container_nodes(object).factory.is_some() && dst.is_some() {
                    self.call_factory(graph, object, id);
                }
            }
            Object::Instance { .. } | Object::Class(_) => {
                self.subscript_object(graph, object, Access::Subscript(id), key);
            }
            Object::External(_) | Object::UnknownExternal(_) => {
                if let Some(dst) = dst {
                    self.add_object(graph, dst, object);
                }
            }
            Object::Saturated
            | Object::TypeForm { .. }
            | Object::Const { .. }
            | Object::Module(_)
            | Object::Function(_)
            | Object::BoundMethod { .. }
            | Object::Fallback { .. }
            | Object::Wrapper { .. }
            | Object::Super { .. }
            | Object::BuiltinMethod { .. }
            | Object::Generator { .. }
            | Object::Closure { .. }
            | Object::Coroutine { .. }
            | Object::ReturnsArgument { .. }
            | Object::Pattern { .. } => {}
        }
    }

    fn call_factory(&mut self, graph: &mut Graph, container: ObjId, id: SubscriptId) {
        let subscript = &self.containers.subscripts[index_of(id.0)];
        let key = self.site_key(subscript.caller, subscript.site, Role::SubscriptFactory);
        let call = self.site_call(graph, key, &[], None, None);
        let factory = self.container_nodes(container).factory.expect("a factory");
        let callee = self.callee(graph, call);
        self.add_edge(graph, factory, callee);
        let result = self.calls[call.index()]
            .dst
            .expect("a site call has a result");
        let unknown = self.unknown(graph, container);
        self.add_edge(graph, result, unknown);
    }

    fn access_call(
        &mut self,
        graph: &mut Graph,
        access: Access,
        name: &str,
        args: &[Option<NodeId>],
    ) -> CallId {
        let name = self.symbols.intern(name);
        let (calls, caller, site) = match access {
            Access::Subscript(id) => {
                let subscript = &self.containers.subscripts[index_of(id.0)];
                (&subscript.calls, subscript.caller, subscript.site)
            }
            Access::Slice(id) => {
                let slice = &self.containers.slices[index_of(id.0)];
                (&slice.calls, slice.caller, slice.site)
            }
        };
        if let Some(&call) = calls.get(&name) {
            return call;
        }
        let key = self.site_key(caller, site, Role::Subscript(name));
        let call = self.site_call(graph, key, args, None, None);
        match access {
            Access::Subscript(id) => {
                self.containers.subscripts[index_of(id.0)]
                    .calls
                    .insert(name, call);
            }
            Access::Slice(id) => {
                self.containers.slices[index_of(id.0)]
                    .calls
                    .insert(name, call);
            }
        }
        call
    }

    fn access_parts(&self, access: Access) -> (Option<NodeId>, Option<NodeId>, bool) {
        match access {
            Access::Subscript(id) => {
                let subscript = &self.containers.subscripts[index_of(id.0)];
                (subscript.dst, subscript.src, subscript.delete)
            }
            Access::Slice(id) => {
                let slice = &self.containers.slices[index_of(id.0)];
                (slice.dst, slice.src, slice.delete)
            }
        }
    }

    fn subscript_object(
        &mut self,
        graph: &mut Graph,
        object: ObjId,
        access: Access,
        key: Option<NodeId>,
    ) {
        let (dst, src, delete) = self.access_parts(access);
        if let Some(dst) = dst {
            let call = self.access_call(graph, access, "__getitem__", &[key]);
            self.call_dunder(
                graph,
                object,
                "__getitem__",
                call,
                Some(dst),
                Unless::Nothing,
            );
            if let Object::Class(class) = self.objects.get(object) {
                let metaclass = class.metaclass;
                let rule = self.container_rule(ContainerRule::MetaclassSubscript {
                    class: object,
                    access,
                    key,
                });
                self.attach(graph, metaclass, rule);
            } else {
                let missing = Unless::Names(Box::new([self.symbols.intern("__getitem__")]));
                self.call_dunder(graph, object, "__missing__", call, Some(dst), missing);
            }
        }
        if let Some(src) = src {
            let call = self.access_call(graph, access, "__setitem__", &[key, Some(src)]);
            self.call_dunder(graph, object, "__setitem__", call, None, Unless::Nothing);
        }
        if delete {
            let call = self.access_call(graph, access, "__delitem__", &[key]);
            self.call_dunder(graph, object, "__delitem__", call, None, Unless::Nothing);
        }
    }

    pub(super) fn metaclass_subscript(
        &mut self,
        graph: &mut Graph,
        meta: ObjId,
        class: ObjId,
        access: Access,
        key: Option<NodeId>,
    ) {
        match self.objects.get(meta) {
            Object::Class(_) => {
                let python = self.python_method(graph, meta, "__getitem__");
                let rule =
                    self.container_rule(ContainerRule::ClassSubscript { class, access, key });
                self.attach(graph, python, rule);
            }
            Object::External(_) | Object::UnknownExternal(_) => {
                let definitions = self.stub_definitions(meta);
                for definition in definitions.iter().flat_map(|found| found.iter()) {
                    if definition.kind == DefinitionKind::Class
                        && !self
                            .stubs
                            .member(&definition.path, "__getitem__")
                            .is_empty()
                    {
                        return;
                    }
                }
                self.class_subscript(graph, None, class, access, key);
            }
            Object::Typed { .. } => {
                not_ported("containers: subscripting a class whose metaclass is a typed value")
            }
            _ => not_ported(
                "containers: subscripting a class whose metaclass is not a class or an outside value",
            ),
        }
    }

    pub(super) fn class_subscript(
        &mut self,
        graph: &mut Graph,
        _python_method: Option<ObjId>,
        class: ObjId,
        access: Access,
        key: Option<NodeId>,
    ) {
        if !self
            .containers
            .subscriptions
            .insert(Subscription::ClassSubscript(class, access))
        {
            return;
        }
        let call = self.access_call(graph, access, "__class_getitem__", &[key]);
        let dst = self.access_parts(access).0.expect("an access that reads");
        let result = self.calls[call.index()]
            .dst
            .expect("a site call has a result");
        self.add_edge(graph, result, dst);
        let method = self.lookup_name(
            graph,
            class,
            "__class_getitem__",
            Some(class),
            None,
            Unless::Nothing,
        );
        let rule = self.container_rule(ContainerRule::ClassGetitem { call });
        self.attach(graph, method, rule);
        let alias = self.python_method(graph, class, "__class_getitem__");
        let rule = self.container_rule(ContainerRule::GenericAlias { class, dst });
        self.attach(graph, alias, rule);
    }

    pub(super) fn class_getitem(&mut self, graph: &mut Graph, method: ObjId, call: CallId) {
        if !matches!(
            self.objects.get(method),
            Object::External(_) | Object::UnknownExternal(_) | Object::Typed { .. }
        ) {
            self.call(graph, method, call);
        }
    }

    pub(super) fn apply_slice(&mut self, graph: &mut Graph, object: ObjId, id: SliceId) {
        let object = match self.objects.get(object) {
            Object::Const { .. } => match self.string_constant_value(graph, object) {
                Some(typed) => typed,
                None => return,
            },
            _ => object,
        };
        match self.objects.get(object) {
            Object::Typed { .. } => {
                let slice = &self.containers.slices[index_of(id.0)];
                let (dst, caller, site) = (slice.dst, slice.caller, slice.site);
                let origin = TypeOrigin::Slice { caller, site };
                self.typed_special(graph, object, "__getitem__", dst, origin);
            }
            Object::Instance { .. } | Object::Class(_) => {
                self.subscript_object(graph, object, Access::Slice(id), None);
            }
            Object::Container(container) if is_sequence(self.symbols.text(container.kind)) => {
                let container = *container;
                let slice = &self.containers.slices[index_of(id.0)];
                let (dst, src, bounds, caller, site) = (
                    slice.dst,
                    slice.src,
                    slice.bounds.clone(),
                    slice.caller,
                    slice.site,
                );
                if let Some(dst) = dst {
                    let kind = self.symbols.text(container.kind).to_owned();
                    let result = self.container_at(
                        graph,
                        &kind,
                        ContainerOrigin::Slice(id),
                        site,
                        None,
                        container.exact,
                    );
                    self.copy_range(graph, object, result, bounds);
                    self.add_object(graph, dst, result);
                }
                if let Some(src) = src {
                    let elements = self.iterated_slice(graph, src, id, caller, site);
                    let unknown = self.unknown(graph, object);
                    self.add_edge(graph, elements, unknown);
                }
            }
            Object::External(_) | Object::UnknownExternal(_) => {
                let dst = self.containers.slices[index_of(id.0)].dst;
                if let Some(dst) = dst {
                    self.add_object(graph, dst, object);
                }
            }
            Object::Container(_)
            | Object::Saturated
            | Object::TypeForm { .. }
            | Object::Const { .. }
            | Object::Module(_)
            | Object::Function(_)
            | Object::BoundMethod { .. }
            | Object::Fallback { .. }
            | Object::Wrapper { .. }
            | Object::Super { .. }
            | Object::BuiltinMethod { .. }
            | Object::Generator { .. }
            | Object::Closure { .. }
            | Object::Coroutine { .. }
            | Object::ReturnsArgument { .. }
            | Object::Pattern { .. } => {}
        }
    }

    pub(super) fn apply_unpacks(&mut self, graph: &mut Graph, objects: &[ObjId], id: UnpackId) {
        let mut sequences = Vec::new();
        for &object in objects {
            if self
                .container_of(object)
                .is_some_and(|container| is_sequence(self.symbols.text(container.kind)))
            {
                sequences.push(object);
            } else {
                let iteration = self.unpack_iteration(graph, id);
                self.iterate(graph, object, iteration);
            }
        }
        match sequences.as_slice() {
            [] => {}
            [one] => self.apply_unpack(graph, *one, id),
            _ => {
                let group = self.container_group(sequences);
                self.unpack_sequences(graph, group, id);
            }
        }
    }

    pub(super) fn apply_unpack(&mut self, graph: &mut Graph, object: ObjId, id: UnpackId) {
        let is_sequence_container = self
            .container_of(object)
            .is_some_and(|container| is_sequence(self.symbols.text(container.kind)));
        if !is_sequence_container {
            let iteration = self.unpack_iteration(graph, id);
            self.iterate(graph, object, iteration);
            return;
        }
        let unpack = &self.containers.unpacks[index_of(id.0)];
        let (before, after, starred) =
            (unpack.before.clone(), unpack.after.clone(), unpack.starred);
        for (index, dst) in before.iter().enumerate() {
            let key = self.index_const(graph, index_i64(index));
            self.read_key(graph, Some(key), object, *dst);
        }
        let count = index_i64(after.len());
        for (index, dst) in after.iter().enumerate() {
            let key = self.index_const(graph, index_i64(index) - count);
            self.read_key(graph, Some(key), object, *dst);
        }
        if starred.is_some() {
            let bounds = (
                Some(BigInt::from(before.len())),
                (count != 0).then(|| BigInt::from(-count)),
            );
            let rest = self.unpack_rest(graph, id);
            self.copy_range(graph, object, rest, Some(bounds));
        }
    }

    fn unpack_sequences(&mut self, graph: &mut Graph, group: GroupId, id: UnpackId) {
        let unpack = &self.containers.unpacks[index_of(id.0)];
        let (before, after, starred) =
            (unpack.before.clone(), unpack.after.clone(), unpack.starred);
        for (index, dst) in before.iter().enumerate() {
            let key = self.index_const(graph, index_i64(index));
            self.read_group(graph, Some(key), group, *dst);
        }
        let count = index_i64(after.len());
        for (index, dst) in after.iter().enumerate() {
            let key = self.index_const(graph, index_i64(index) - count);
            self.read_group(graph, Some(key), group, *dst);
        }
        if starred.is_some() {
            let bounds = (
                Some(BigInt::from(before.len())),
                (count != 0).then(|| BigInt::from(-count)),
            );
            let containers = self.containers.groups[index_of(group.0)].containers.clone();
            for object in containers {
                let rest = self.unpack_rest(graph, id);
                self.copy_range(graph, object, rest, Some(bounds.clone()));
            }
        }
    }

    fn index_const(&mut self, graph: &mut Graph, index: i64) -> ObjId {
        self.const_object(graph, &Literal::Int(BigInt::from(index)))
    }

    fn unpack_rest(&mut self, graph: &mut Graph, id: UnpackId) -> ObjId {
        let unpack = &self.containers.unpacks[index_of(id.0)];
        if let Some(rest) = unpack.rest {
            return rest;
        }
        let (caller, site, starred) = (unpack.caller, unpack.site, unpack.starred);
        let rest = self.container_at(
            graph,
            "list",
            ContainerOrigin::Rest(caller, site),
            site,
            None,
            true,
        );
        self.containers.unpacks[index_of(id.0)].rest = Some(rest);
        let starred = starred.expect("a starred target");
        self.add_object(graph, starred, rest);
        rest
    }

    fn unpack_iteration(&mut self, graph: &mut Graph, id: UnpackId) -> IterationId {
        let unpack = &self.containers.unpacks[index_of(id.0)];
        if let Some(iteration) = unpack.iteration {
            return iteration;
        }
        let (caller, site, starred) = (unpack.caller, unpack.site, unpack.starred);
        let targets: Vec<NodeId> = unpack.before.iter().chain(&unpack.after).copied().collect();
        let elements = self.node(graph, None);
        for dst in targets {
            self.add_edge(graph, elements, dst);
        }
        if starred.is_some() {
            let rest = self.unpack_rest(graph, id);
            let unknown = self.unknown(graph, rest);
            self.add_edge(graph, elements, unknown);
        }
        let iteration = self.new_iteration(
            graph,
            elements,
            caller,
            site,
            false,
            Unless::Nothing,
            "unpack",
        );
        self.containers.unpacks[index_of(id.0)].iteration = Some(iteration);
        if starred.is_some() {
            let iterators = self.iteration_iterators(graph, iteration);
            self.add_length_hint(graph, iterators, caller, site, LENGTH_HINT);
        }
        iteration
    }

    pub(super) fn iterate(&mut self, graph: &mut Graph, object: ObjId, iteration: IterationId) {
        let iterators = self.iteration_iterators(graph, iteration);
        self.iterator(graph, object, iteration, iterators);
    }

    pub(super) fn iterator(
        &mut self,
        graph: &mut Graph,
        object: ObjId,
        iteration: IterationId,
        dst: NodeId,
    ) {
        let object = match self.objects.get(object) {
            Object::Const { .. } => match self.string_constant_value(graph, object) {
                Some(typed) => typed,
                None => return,
            },
            _ => object,
        };
        match self.objects.get(object) {
            Object::Typed { .. } => {
                let found = &self.containers.iterations[index_of(iteration.0)];
                let (is_async, caller, site, role) =
                    (found.is_async, found.caller, found.site, found.role);
                let name = if is_async { "__aiter__" } else { "__iter__" };
                let origin = TypeOrigin::Iteration { caller, site, role };
                self.typed_special(graph, object, name, Some(dst), origin);
                return;
            }
            Object::Instance { .. } | Object::Class(_) => {}
            Object::Container(_)
            | Object::Generator { .. }
            | Object::External(_)
            | Object::UnknownExternal(_) => {
                self.add_object(graph, dst, object);
                return;
            }
            Object::Saturated
            | Object::TypeForm { .. }
            | Object::Const { .. }
            | Object::Module(_)
            | Object::Function(_)
            | Object::BoundMethod { .. }
            | Object::Fallback { .. }
            | Object::Wrapper { .. }
            | Object::Super { .. }
            | Object::BuiltinMethod { .. }
            | Object::Closure { .. }
            | Object::Coroutine { .. }
            | Object::ReturnsArgument { .. }
            | Object::Pattern { .. } => return,
        }
        let is_async = self.containers.iterations[index_of(iteration.0)].is_async;
        let role = self.containers.iterations[index_of(iteration.0)].role;
        let unless = self.containers.iteration_role(role).2.clone();
        let name = if is_async { "__aiter__" } else { "__iter__" };
        let call = self.iteration_call(graph, iteration);
        self.call_dunder(graph, object, name, call, Some(dst), unless);
        if !is_async {
            let types = self.types_node(graph, object);
            let rule = self.container_rule(ContainerRule::SequenceType {
                object,
                iteration,
                dst,
            });
            self.attach(graph, types, rule);
        }
    }

    pub(super) fn types_node(&mut self, graph: &mut Graph, object: ObjId) -> NodeId {
        match self.objects.get(object) {
            &Object::Instance { class, .. } => self.constant(graph, class),
            Object::Class(class) => class.metaclass,
            _ => unreachable!("only instances and classes have types"),
        }
    }

    pub(super) fn sequence_type(
        &mut self,
        graph: &mut Graph,
        class: ObjId,
        object: ObjId,
        iteration: IterationId,
        dst: NodeId,
    ) {
        if !matches!(self.objects.get(class), Object::Class(_)) {
            return;
        }
        let instance = matches!(self.objects.get(object), Object::Instance { .. });
        let key = (class, instance, iteration, dst);
        let sequences = match self.containers.sequences_of.get(&key) {
            Some(&sequences) => sequences,
            None => {
                let sequences = SequencesId(next_id(self.containers.sequences.len()));
                self.containers.sequences.push(Sequences {
                    iteration,
                    dst,
                    objects: Vec::new(),
                    found: false,
                    rule: None,
                });
                self.containers.sequences_of.insert(key, sequences);
                sequences
            }
        };
        let role = self.containers.iterations[index_of(iteration.0)].role;
        let mut names = vec![self.symbols.intern("__iter__")];
        match self.containers.iteration_role(role).2 {
            Unless::Nothing => {}
            Unless::Names(more) => names.extend(more.iter().copied()),
            other => not_ported(&format!("containers: an iteration unless {other:?}")),
        }
        let unless = Unless::Names(names.into_boxed_slice());
        let found = self.lookup_name(graph, class, "__getitem__", Some(object), None, unless);
        let rule = match self.containers.sequences[index_of(sequences.0)].rule {
            Some(rule) => rule,
            None => {
                let rule = self.container_rule(ContainerRule::Sequences(sequences));
                self.containers.sequences[index_of(sequences.0)].rule = Some(rule);
                rule
            }
        };
        self.attach(graph, found, rule);
        self.containers.sequences[index_of(sequences.0)]
            .objects
            .push(object);
        if self.containers.sequences[index_of(sequences.0)].found {
            self.sequences_iterate(graph, sequences, object);
        }
    }

    pub(super) fn sequences_apply(&mut self, graph: &mut Graph, id: SequencesId) {
        let sequences = &mut self.containers.sequences[index_of(id.0)];
        if sequences.found {
            return;
        }
        sequences.found = true;
        let objects = sequences.objects.clone();
        for object in objects {
            self.sequences_iterate(graph, id, object);
        }
    }

    fn sequences_iterate(&mut self, graph: &mut Graph, id: SequencesId, object: ObjId) {
        let sequences = &self.containers.sequences[index_of(id.0)];
        let (iteration, dst) = (sequences.iteration, sequences.dst);
        if self.opaque(object) {
            let saturated = self.saturated;
            self.add_object(graph, dst, saturated);
        } else {
            self.sequence_iterator(graph, object, iteration, dst);
        }
    }

    fn sequence_iterator(
        &mut self,
        graph: &mut Graph,
        object: ObjId,
        iteration: IterationId,
        dst: NodeId,
    ) {
        let found = self.containers.iterations[index_of(iteration.0)];
        let origin = ContainerOrigin::Iterate(found.caller, found.site, found.role);
        let iterator = self.container_at(graph, "iterator", origin, found.site, None, false);
        let source = self.keys(graph, iterator);
        self.add_object(graph, source, object);
        self.add_object(graph, dst, iterator);
    }

    pub(super) fn next_element(
        &mut self,
        graph: &mut Graph,
        object: ObjId,
        iteration: IterationId,
    ) {
        let found = self.containers.iterations[index_of(iteration.0)];
        match self.objects.get(object) {
            Object::Instance { .. } | Object::Class(_) => {
                let call = self.iteration_call(graph, iteration);
                if found.is_async {
                    let anext = self.iteration_anext(graph, iteration);
                    self.call_dunder(
                        graph,
                        object,
                        "__anext__",
                        call,
                        Some(anext),
                        Unless::Nothing,
                    );
                } else {
                    self.call_dunder(
                        graph,
                        object,
                        "__next__",
                        call,
                        Some(found.dst),
                        Unless::Nothing,
                    );
                }
            }
            Object::Container(_) if self.is_library(object) && !found.is_async => {
                self.advance_library(graph, object, iteration);
            }
            Object::Container(container) => match self.symbols.text(container.kind) {
                "iterator" => {
                    let source = self.keys(graph, object);
                    let rule = self.container_rule(ContainerRule::NextItem(iteration));
                    self.attach(graph, source, rule);
                }
                "callable_iterator" => {
                    let source = self.keys(graph, object);
                    let call = self.iteration_callable_call(graph, iteration);
                    let rule = self.calls[call.index()].rule;
                    self.attach(graph, source, rule);
                }
                _ => {
                    let elements = self.elements(graph, object);
                    self.add_edge(graph, elements, found.dst);
                }
            },
            &Object::Generator { function, .. } => {
                let yield_node = self
                    .objects
                    .function(function)
                    .yield_node
                    .expect("a generator yields");
                self.add_edge(graph, yield_node, found.dst);
            }
            Object::Typed { .. } => {
                let origin = TypeOrigin::Iteration {
                    caller: found.caller,
                    site: found.site,
                    role: found.role,
                };
                if found.is_async {
                    let anext = self.iteration_anext(graph, iteration);
                    self.typed_special(graph, object, "__anext__", Some(anext), origin);
                } else {
                    self.typed_special(graph, object, "__next__", Some(found.dst), origin);
                }
            }
            Object::External(_) | Object::UnknownExternal(_) => {
                self.add_object(graph, found.dst, object);
            }
            Object::Saturated
            | Object::TypeForm { .. }
            | Object::Module(_)
            | Object::Function(_)
            | Object::BoundMethod { .. }
            | Object::Fallback { .. }
            | Object::Wrapper { .. }
            | Object::Super { .. }
            | Object::BuiltinMethod { .. }
            | Object::Const { .. }
            | Object::Closure { .. }
            | Object::Coroutine { .. }
            | Object::ReturnsArgument { .. }
            | Object::Pattern { .. } => {}
        }
    }

    pub(super) fn next_item(&mut self, graph: &mut Graph, object: ObjId, iteration: IterationId) {
        let call = self.iteration_index_call(graph, iteration);
        let dst = self.containers.iterations[index_of(iteration.0)].dst;
        self.call_dunder(
            graph,
            object,
            "__getitem__",
            call,
            Some(dst),
            Unless::Nothing,
        );
    }

    pub(super) fn apply_dict_items(&mut self, graph: &mut Graph, object: ObjId, id: DictItemsId) {
        let is_dict = self.container_of(object).is_some() && self.is_dict(object);
        if !is_dict {
            let pairs = self.dict_items_pairs(graph, id);
            self.iterate(graph, object, pairs);
            return;
        }
        let items = &self.containers.dict_items[index_of(id.0)];
        let (hub, target, caller, site) = (items.hub, items.target, items.caller, items.site);
        let entry = &mut self.containers.hubs[index_of(hub.0)];
        let new_source = entry.sources.insert(object, ()).is_none();
        let active = entry.active;
        if new_source && active {
            self.enter_hub(graph, hub, object);
        }
        let entry = &mut self.containers.hubs[index_of(hub.0)];
        let new_target = entry.targets.insert((target, caller, site), ()).is_none();
        let active = entry.active;
        if new_target && active {
            self.leave_hub(graph, hub, target, caller, site);
        }
        if active {
            return;
        }
        if self.containers.hubs[index_of(hub.0)].sources.len() == 1 {
            self.copy_items(graph, object, target);
            if !self.keeps_mapping_hashes(object) {
                let keys = self.keys(graph, object);
                let stored = self.keys(graph, target);
                self.add_hash(graph, keys, caller, site, Some(stored));
            }
            return;
        }
        self.containers.hubs[index_of(hub.0)].active = true;
        let sources: Vec<ObjId> = self.containers.hubs[index_of(hub.0)]
            .sources
            .keys()
            .copied()
            .collect();
        for source in sources {
            self.enter_hub(graph, hub, source);
        }
        let targets: Vec<(ObjId, Sym, Sym)> = self.containers.hubs[index_of(hub.0)]
            .targets
            .keys()
            .copied()
            .collect();
        for (target, caller, site) in targets {
            self.leave_hub(graph, hub, target, caller, site);
        }
    }

    fn enter_hub(&mut self, graph: &mut Graph, hub: DictHubId, source: ObjId) {
        let container = self.containers.hubs[index_of(hub.0)].container;
        self.copy_items(graph, source, container);
        if !self.keeps_mapping_hashes(source) {
            let keys = self.keys(graph, source);
            let hashed = self.containers.hubs[index_of(hub.0)].hashed;
            self.add_edge(graph, keys, hashed);
        }
    }

    fn leave_hub(
        &mut self,
        graph: &mut Graph,
        hub: DictHubId,
        target: ObjId,
        caller: Sym,
        site: Sym,
    ) {
        let hashed = self.containers.hubs[index_of(hub.0)].hashed;
        if self.containers.hubs[index_of(hub.0)]
            .sites
            .insert((caller, site))
        {
            let key = self.site_key(caller, site, Role::Hash);
            let call = self.site_call(graph, key, &[], None, None);
            self.special_call(graph, hashed, "__hash__", call, Unless::Nothing);
        }
        let container = self.containers.hubs[index_of(hub.0)].container;
        self.copy_items(graph, container, target);
        let stored = self.keys(graph, target);
        self.compare_keys(graph, hashed, caller, site, stored);
    }

    fn dict_items_pairs(&mut self, graph: &mut Graph, id: DictItemsId) -> IterationId {
        let items = &self.containers.dict_items[index_of(id.0)];
        if let Some(pairs) = items.pairs {
            return pairs;
        }
        let (target, caller, site) = (items.target, items.caller, items.site);
        let pairs = self.node(graph, None);
        let key = self.node(graph, None);
        let value = self.node(graph, None);
        self.add_unpack(graph, pairs, &[key, value], None, &[], caller, site);
        self.write_keyed(graph, target, Some(key), Some(value));
        let stored = self.keys(graph, target);
        self.add_hash(graph, key, caller, site, Some(stored));
        let iteration =
            self.new_iteration(graph, pairs, caller, site, false, Unless::Nothing, "items");
        self.containers.dict_items[index_of(id.0)].pairs = Some(iteration);
        iteration
    }
}

const RECEIVER_KINDS: &[Kind] = &[Kind::Instance, Kind::Class];

#[derive(Clone, Debug)]
pub(crate) enum ContainerRule {
    SpecialCall {
        name: Sym,
        call: CallId,
        unless: Unless,
    },
    KeyLookupKey(KeyLookupId),
    KeyLookupStored(KeyLookupId),
    Keyed(KeyedId),
    KeyedGroup(KeyedGroupId),
    Subscript(SubscriptId),
    Slice(SliceId),
    Unpack(UnpackId),
    Iterate(IterationId),
    DictItems(DictItemsId),
    Sequences(SequencesId),
    EnterKeys {
        kept: NodeId,
        iteration: IterationId,
        keeps: Keeps,
    },
    Iter {
        iteration: IterationId,
        dst: NodeId,
    },
    CopyElements {
        target: ObjId,
        iteration: IterationId,
    },
    NextElement(IterationId),
    YieldFrom {
        function: ObjId,
        dst: NodeId,
    },
    MetaclassSubscript {
        class: ObjId,
        access: Access,
        key: Option<NodeId>,
    },
    ClassSubscript {
        class: ObjId,
        access: Access,
        key: Option<NodeId>,
    },
    ClassGetitem {
        call: CallId,
    },
    GenericAlias {
        class: ObjId,
        dst: NodeId,
    },
    SequenceType {
        object: ObjId,
        iteration: IterationId,
        dst: NodeId,
    },
    NextItem(IterationId),
    SpreadSequence {
        spread: SpreadId,
        iteration: IterationId,
    },
    SpreadMapping(SpreadId),
}

impl ContainerRule {
    pub(crate) fn key(&self) -> &'static str {
        match self {
            ContainerRule::SpecialCall { .. } => "Each:Analysis.call_dunder",
            ContainerRule::KeyLookupKey(_) => "Each:_KeyLookup.key",
            ContainerRule::KeyLookupStored(_) => "Each:_KeyLookup.stored",
            ContainerRule::Keyed(_) => "_Keyed",
            ContainerRule::KeyedGroup(_) => "_KeyedGroup",
            ContainerRule::Subscript(_) => "_Subscript",
            ContainerRule::Slice(_) => "_Slice",
            ContainerRule::Unpack(_) => "_Unpack",
            ContainerRule::Iterate(_) => "_Iterate",
            ContainerRule::DictItems(_) => "_DictItems",
            ContainerRule::Sequences(_) => "_Sequences",
            ContainerRule::EnterKeys { .. } => "Each:Containers._enter_keys",
            ContainerRule::Iter { .. } => "Each:Containers._iter",
            ContainerRule::CopyElements { .. } => "Each:Containers._copy_elements",
            ContainerRule::NextElement(_) => "Each:Containers.next_element",
            ContainerRule::YieldFrom { .. } => "Each:Containers._yield_from",
            ContainerRule::MetaclassSubscript { .. } => "Each:Containers._metaclass_subscript",
            ContainerRule::ClassSubscript { .. } => "Each:Containers._class_subscript",
            ContainerRule::ClassGetitem { .. } => "Each:Containers._class_getitem",
            ContainerRule::GenericAlias { .. } => "Each:Containers._generic_alias",
            ContainerRule::SequenceType { .. } => "Each:Containers._sequence_type",
            ContainerRule::NextItem(_) => "Each:Containers._next_item",
            ContainerRule::SpreadSequence { .. } => "Each:Arguments._spread_sequence",
            ContainerRule::SpreadMapping(_) => "Each:Arguments._spread_mapping",
        }
    }

    pub(crate) fn each(&self) -> bool {
        self.key().starts_with("Each:")
    }

    pub(crate) fn batches(&self) -> bool {
        matches!(self, ContainerRule::Subscript(_) | ContainerRule::Unpack(_))
    }

    pub(crate) fn kinds(&self) -> Option<&'static [Kind]> {
        match self {
            ContainerRule::SpecialCall { .. } | ContainerRule::KeyLookupStored(_) => {
                Some(RECEIVER_KINDS)
            }
            _ => None,
        }
    }

    pub(crate) fn captured(&self) -> Vec<ObjId> {
        match *self {
            ContainerRule::YieldFrom { function, .. } => vec![function],
            ContainerRule::CopyElements { target, .. } => vec![target],
            ContainerRule::MetaclassSubscript { class, .. }
            | ContainerRule::ClassSubscript { class, .. }
            | ContainerRule::GenericAlias { class, .. } => vec![class],
            ContainerRule::SequenceType { object, .. } => vec![object],
            _ => Vec::new(),
        }
    }
}

impl<T: Trace> State<T> {
    pub(super) fn container_rule(&mut self, rule: ContainerRule) -> crate::engine::rules::RuleId {
        self.rule(Rule::Container(rule))
    }

    pub(super) fn container_results(&self, rule: &ContainerRule) -> Vec<NodeId> {
        let containers = &self.containers;
        match *rule {
            ContainerRule::SpecialCall { .. }
            | ContainerRule::KeyLookupKey(_)
            | ContainerRule::KeyLookupStored(_)
            | ContainerRule::DictItems(_) => Vec::new(),
            ContainerRule::Keyed(id) => containers.keyed(id).result.into_iter().collect(),
            ContainerRule::KeyedGroup(id) => {
                containers.keyed_group(id).result.into_iter().collect()
            }
            ContainerRule::Subscript(id) => containers.subscript(id).dst.into_iter().collect(),
            ContainerRule::Slice(id) => containers.slice(id).dst.into_iter().collect(),
            ContainerRule::Unpack(id) => {
                let unpack = containers.unpack(id);
                let mut results: Vec<NodeId> =
                    unpack.before.iter().chain(&unpack.after).copied().collect();
                results.extend(unpack.starred);
                results
            }
            ContainerRule::Iterate(id)
            | ContainerRule::NextElement(id)
            | ContainerRule::NextItem(id) => vec![containers.iteration(id).dst],
            ContainerRule::Sequences(id) => vec![containers.sequences(id).dst],
            ContainerRule::EnterKeys {
                kept, iteration, ..
            } => {
                vec![containers.iteration(iteration).dst, kept]
            }
            ContainerRule::Iter { dst, .. } => vec![dst],
            ContainerRule::CopyElements { iteration, .. } => {
                vec![containers.iteration(iteration).dst]
            }
            ContainerRule::YieldFrom { dst, .. }
            | ContainerRule::GenericAlias { dst, .. }
            | ContainerRule::SequenceType { dst, .. } => vec![dst],
            ContainerRule::MetaclassSubscript { access, .. }
            | ContainerRule::ClassSubscript { access, .. } => {
                self.access_parts(access).0.into_iter().collect()
            }
            ContainerRule::ClassGetitem { call } => {
                self.calls[call.index()].dst.into_iter().collect()
            }
            ContainerRule::SpreadSequence { spread, .. } | ContainerRule::SpreadMapping(spread) => {
                vec![containers.spreads.unknown(spread)]
            }
        }
    }

    pub(super) fn container_apply(
        &mut self,
        graph: &mut Graph,
        rule: &ContainerRule,
        object: ObjId,
    ) {
        match *rule {
            ContainerRule::SpecialCall {
                name,
                call,
                ref unless,
            } => {
                let name = self.symbols.text(name).to_owned();
                self.call_dunder(graph, object, &name, call, None, unless.clone());
            }
            ContainerRule::KeyLookupKey(id) => self.key_lookup_key(graph, id, object),
            ContainerRule::KeyLookupStored(id) => self.key_lookup_stored(graph, id, object),
            ContainerRule::Keyed(id) => self.keyed_apply(graph, id, object),
            ContainerRule::KeyedGroup(id) => self.keyed_group_apply(graph, id, object),
            ContainerRule::Subscript(id) => self.apply_subscript(graph, object, id, true),
            ContainerRule::Slice(id) => self.apply_slice(graph, object, id),
            ContainerRule::Unpack(id) => self.apply_unpack(graph, object, id),
            ContainerRule::Iterate(id) => self.iterate(graph, object, id),
            ContainerRule::DictItems(id) => self.apply_dict_items(graph, object, id),
            ContainerRule::Sequences(id) => self.sequences_apply(graph, id),
            ContainerRule::EnterKeys {
                kept,
                iteration,
                keeps,
            } => self.enter_keys(graph, object, kept, iteration, keeps),
            ContainerRule::Iter { iteration, dst } => {
                self.iter_object(graph, object, iteration, dst)
            }
            ContainerRule::CopyElements { target, iteration } => {
                self.copy_elements(graph, object, target, iteration)
            }
            ContainerRule::NextElement(id) => self.next_element(graph, object, id),
            ContainerRule::YieldFrom { function, dst } => {
                self.yield_from(graph, object, function, dst)
            }
            ContainerRule::MetaclassSubscript { class, access, key } => {
                self.metaclass_subscript(graph, object, class, access, key)
            }
            ContainerRule::ClassSubscript { class, access, key } => {
                self.class_subscript(graph, Some(object), class, access, key)
            }
            ContainerRule::ClassGetitem { call } => self.class_getitem(graph, object, call),
            ContainerRule::GenericAlias { dst, .. } => {
                let class = match *rule {
                    ContainerRule::GenericAlias { class, .. } => class,
                    _ => unreachable!("a generic alias rule"),
                };
                self.add_object(graph, dst, class);
            }
            ContainerRule::SequenceType {
                object: owner,
                iteration,
                dst,
            } => self.sequence_type(graph, object, owner, iteration, dst),
            ContainerRule::NextItem(id) => self.next_item(graph, object, id),
            ContainerRule::SpreadSequence { spread, iteration } => {
                self.spread_sequence(graph, object, spread, iteration)
            }
            ContainerRule::SpreadMapping(spread) => self.spread_mapping(graph, object, spread),
        }
    }

    pub(super) fn container_apply_each(
        &mut self,
        graph: &mut Graph,
        rule: &ContainerRule,
        objects: &[ObjId],
    ) {
        match *rule {
            ContainerRule::Subscript(id) => self.apply_subscripts(graph, objects, id),
            ContainerRule::Unpack(id) => self.apply_unpacks(graph, objects, id),
            _ => unreachable!("only subscripts and unpacks apply in batches"),
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub(crate) enum Access {
    Subscript(SubscriptId),
    Slice(SliceId),
}

fn index_i64(index: usize) -> i64 {
    i64::try_from(index).expect("an index fits i64")
}

fn slice_indices(bounds: &Bounds, length: u32) -> (u32, u32) {
    let length = BigInt::from(length);
    let adjust = |bound: &Option<BigInt>, default: &BigInt| -> BigInt {
        match bound {
            None => default.clone(),
            Some(bound) if *bound < BigInt::ZERO => (bound + &length).max(BigInt::ZERO),
            Some(bound) => bound.clone().min(length.clone()),
        }
    };
    let start = adjust(&bounds.0, &BigInt::ZERO);
    let stop = adjust(&bounds.1, &length);
    let narrow = |value: BigInt| u32::try_from(value).expect("a clamped bound fits the length");
    (narrow(start), narrow(stop))
}

impl Containers {
    pub(crate) fn table_sizes(
        &self,
        iterated_nodes: usize,
        sizes: &mut Vec<(&'static str, usize)>,
    ) {
        let Containers {
            containers,
            storages: _,
            storage_of: _,
            nodes: _,
            notices: _,
            notifying: _,
            keyed: _,
            completed_keys: _,
            groups: _,
            group_of: _,
            keyed_rules: _,
            keyed_groups: _,
            key_lookups: _,
            compared_keys: _,
            subscript_keys: _,
            iterated,
            iterations: _,
            iteration_roles: _,
            subscripts: _,
            slices: _,
            unpacks: _,
            hubs: _,
            hub_of: _,
            dict_items: _,
            sequences: _,
            sequences_of: _,
            subscriptions: _,
            spreads,
        } = self;
        sizes.extend([
            ("containers containers", containers.len()),
            ("iterated", iterated.len() + iterated_nodes),
        ]);
        spreads.table_sizes(sizes);
    }
}
