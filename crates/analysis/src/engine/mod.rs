mod analysis;
mod annotations;
mod arguments;
mod attributes;
mod builtin_containers;
mod builtin_rules;
mod census;
mod chains;
mod containers;
mod fixpoint;
pub mod hierarchy;
mod library;
mod narrowing;
pub mod objects;
mod outside;
mod outside_calls;
mod outside_results;
mod outside_types;
mod patterns;
mod protocols;
mod reflection;
mod results;
mod rules;
mod semantics;
pub mod symbols;

use std::sync::Arc;

use indexmap::{IndexMap, IndexSet};
use pycg_solver::{NodeId, ObjId, Order, Solver, WatchId, Work};
use pycg_stubs::{Definition, Stubs};
use rustc_hash::{FxBuildHasher, FxHashMap, FxHashSet};

use crate::builder::calls::{BuilderTables, ClassFields, FunctionFields, MethodKind};
use crate::model::{BUILTIN_MODULE, Signature};
use crate::program::imports::ImportManager;
use attributes::{
    Access, AccessorEntry, AccessorHooks, Accessors, AccessorsId, Deliveries, DeliveriesId,
    FieldWrites, HookCalls, HookCallsId, HooksId, WritesId,
};
use builtin_containers::Iterated;
use builtin_rules::{DynamicAccess, WrapperKey};
use chains::{Chain, Chains};
use hierarchy::{LookupAttr, Namespace, Unless};
use objects::{Container, External, Function, Kind, Literal, Module, Object, Objects};
use outside_calls::{Bound, BoundId, Known};
pub use rules::RuleId;
use rules::{Rule, WaitingRule};
pub use semantics::CallId;
use semantics::{
    BoundGroup, Call, Construct, GroupId, Origin, Prefix, Receivers, Returned, ReturnedId, SiteKey,
};
use symbols::{Sym, Symbols};

pub(crate) type OrderedMap<K, V> = IndexMap<K, V, FxBuildHasher>;
pub(crate) type OrderedSet<K> = IndexSet<K, FxBuildHasher>;

pub const EXTERNAL_STEPS_PAST_ROOT_MAX: u32 = 2;

pub type Graph = Solver<RuleId>;

type Receiver = (NodeId, NodeId, ObjId, ObjId, Sym);

#[derive(Clone)]
enum BuilderFields {
    Function(FunctionFields),
    Class(ClassFields),
    Module(Vec<Box<str>>),
}

pub struct NotPorted(pub String);

pub fn not_ported(feature: &str) -> ! {
    std::panic::panic_any(NotPorted(feature.to_owned()))
}

pub struct Engine {
    graph: Graph,
    state: State,
}

struct State {
    symbols: Symbols,
    objects: Objects,
    saturated: ObjId,
    unknown_external: ObjId,
    labels: FxHashMap<NodeId, Box<str>>,
    named_nodes: Vec<NodeId>,
    fields: FxHashMap<ObjId, OrderedMap<Sym, NodeId>>,
    modules: OrderedMap<Sym, ObjId>,
    externals: FxHashMap<(Sym, u32, bool), ObjId>,
    consts: FxHashMap<Literal, ObjId>,
    constants: FxHashMap<ObjId, NodeId>,
    generators: FxHashMap<ObjId, ObjId>,
    coroutines: FxHashMap<ObjId, ObjId>,
    functions: Vec<ObjId>,
    completed_functions: usize,
    called: FxHashSet<ObjId>,
    rules: Vec<Rule>,
    released_rules: Vec<RuleId>,
    calls: Vec<Call>,
    receiver_calls: FxHashMap<(CallId, Receivers), CallId>,
    prefixes: FxHashMap<CallId, (CallId, Prefix)>,
    bound_groups: FxHashMap<(CallId, ObjId, usize, bool), Vec<GroupId>>,
    groups: FxHashMap<CallId, GroupId>,
    group_records: Vec<BoundGroup>,
    grouped_externals: FxHashMap<ObjId, bool>,
    site_edges: OrderedMap<(Sym, Sym, Construct), OrderedSet<Sym>>,
    call_expressions: Vec<(Sym, Sym, Option<NodeId>)>,
    classes: Vec<ObjId>,
    stubs: Stubs,
    imports: ImportManager,
    stub_definitions: FxHashMap<Sym, Option<Arc<[Definition]>>>,
    external_modules: FxHashSet<String>,
    watches: FxHashMap<(ObjId, LookupAttr, Option<ObjId>, Unless), WatchId>,
    waiting: FxHashMap<(WatchId, u32), Chain>,
    waiting_order: FxHashMap<WatchId, Vec<u32>>,
    chains: Chains,
    waiting_rules: OrderedSet<WaitingRule>,
    unlesses: OrderedSet<Unless>,
    watch_of_witness: FxHashMap<NodeId, WatchId>,
    metaclass_members: FxHashSet<(NodeId, Sym, NodeId)>,
    fallback_binds: FxHashSet<(NodeId, ObjId, NodeId)>,
    field_binds: FxHashMap<(NodeId, bool), hierarchy::BindsId>,
    binds: Vec<hierarchy::Binds>,
    shared: Vec<semantics::Shared>,
    shared_by_key: FxHashMap<(NodeId, semantics::SharedRule), semantics::SharedId>,
    fallback_nodes: FxHashMap<(ObjId, NodeId), NodeId>,
    families: FxHashMap<ObjId, NodeId>,
    namespace_nodes: FxHashMap<(ObjId, Namespace), NodeId>,
    classes_below: FxHashMap<String, OrderedSet<ObjId>>,
    below_nodes: FxHashMap<(String, bool), NodeId>,
    instances: FxHashMap<(ObjId, Option<Origin>), ObjId>,
    bound_methods: FxHashMap<(ObjId, ObjId), ObjId>,
    fallbacks: FxHashMap<ObjId, ObjId>,
    inexact: FxHashMap<ObjId, ObjId>,
    statement_calls: FxHashMap<ObjId, semantics::StatementCall>,
    statement_news: FxHashSet<ObjId>,
    made_classes: FxHashSet<ObjId>,
    new_results: FxHashMap<CallId, ReturnedId>,
    returned: Vec<Returned>,
    class_instances: FxHashMap<ObjId, FxHashSet<ObjId>>,
    roots: FxHashMap<CallId, CallId>,
    dunder_calls: FxHashMap<(Option<ObjId>, Sym, CallId, Unless), CallId>,
    dunder_owners: FxHashMap<CallId, FxHashSet<ObjId>>,
    site_calls: FxHashMap<SiteKey, CallId>,
    receivers: Vec<Receiver>,
    entry_receivers: Vec<Receiver>,
    completed_receivers: usize,
    accesses: Vec<Access>,
    accessor_hooks: Vec<AccessorHooks>,
    accessor_hooks_by_key: FxHashMap<(ObjId, Sym, Option<AccessorEntry>), HooksId>,
    accessor_hook_rules: FxHashMap<HooksId, RuleId>,
    accessors: Vec<Accessors>,
    accessor_receivers: FxHashMap<(NodeId, CallId, bool, u32), AccessorsId>,
    writes: Vec<FieldWrites>,
    field_writes: FxHashMap<NodeId, WritesId>,
    hook_calls: Vec<HookCalls>,
    hook_calls_by_lookup: FxHashMap<NodeId, HookCallsId>,
    deliveries: Vec<Deliveries>,
    deliveries_by_lookup: FxHashMap<NodeId, DeliveriesId>,
    descriptors_itself: FxHashSet<(ObjId, NodeId)>,
    store_names: FxHashSet<Sym>,
    class_store_names: FxHashMap<ObjId, FxHashSet<Sym>>,
    field_readers: FxHashMap<(ObjId, Sym), OrderedMap<NodeId, Vec<ObjId>>>,
    builder_fields: FxHashMap<ObjId, BuilderFields>,
    external_callees: FxHashMap<Sym, Known>,
    typed_callbacks: FxHashSet<(CallId, ObjId)>,
    stub_bindings: FxHashMap<(CallId, Box<str>, usize), BoundId>,
    bindings: Vec<Bound>,
    callbacks: FxHashMap<Origin, CallId>,
    callback_values: FxHashSet<(CallId, NodeId)>,
    protocol_plans: Vec<Vec<(Sym, Unless)>>,
    model_bindings: FxHashMap<(CallId, builtin_rules::BindingEntry), BoundId>,
    returning: FxHashMap<(Sym, bool), ObjId>,
    wrappers: FxHashMap<WrapperKey, ObjId>,
    builtin_methods: FxHashMap<(ObjId, Sym), ObjId>,
    none_arguments: FxHashMap<(Sym, Sym), Vec<u32>>,
    synced_none_arguments: usize,
    none_keywords: FxHashMap<(Sym, Sym), Vec<Sym>>,
    synced_none_keywords: usize,
    callees: FxHashMap<CallId, NodeId>,
    dynamic_accesses: Vec<DynamicAccess>,
    namespace_names_read: FxHashSet<Sym>,
    zero_argument_super: FxHashSet<Sym>,
    literal_imports: FxHashMap<Sym, NodeId>,
    synced_literal_imports: usize,
    read_namespaces: FxHashSet<Sym>,
    super_pairs: FxHashSet<(CallId, ObjId)>,
    super_accepted: FxHashMap<ObjId, FxHashSet<ObjId>>,
    supers: FxHashMap<(ObjId, ObjId), ObjId>,
    typed_objects: FxHashMap<String, ObjId>,
    iterated_nodes: FxHashMap<Iterated, (NodeId, NodeId)>,
    length_hints: FxHashSet<(Sym, Sym, NodeId, usize)>,
    length_plans: FxHashMap<usize, outside_calls::PlanId>,
    reverse_sequences: FxHashSet<(ObjId, NodeId, CallId)>,
    namespaces: FxHashSet<ObjId>,
    namespace_calls: FxHashSet<CallId>,
    getmembers: Vec<reflection::Getmembers>,
    getmembers_calls: FxHashSet<CallId>,
    members_listed: FxHashSet<(ObjId, reflection::GetmembersId)>,
    handed: Vec<ObjId>,
    tables: BuilderTables,
    containers: containers::Containers,
    protocols: protocols::Protocols,
    builder_calls: Vec<CallId>,
    patterns: patterns::Patterns,
    outside_types: outside_types::OutsideTypes,
    annotations: annotations::Annotations,
    outside_results: outside_results::OutsideResults,
    library: library::Library,
    class_tests: narrowing::ClassTests,
    census: census::Census,
}

impl State {
    fn table_sizes(&self) -> Vec<(&'static str, usize)> {
        let State {
            symbols: _,
            objects: _,
            saturated: _,
            unknown_external: _,
            labels: _,
            named_nodes,
            fields: _,
            modules: _,
            externals,
            consts,
            constants,
            generators,
            coroutines,
            functions: _,
            completed_functions: _,
            called: _,
            rules: _,
            released_rules: _,
            calls: _,
            receiver_calls,
            prefixes: _,
            bound_groups: _,
            groups: _,
            group_records: _,
            grouped_externals: _,
            site_edges: _,
            call_expressions: _,
            classes: _,
            stubs: _,
            imports: _,
            stub_definitions: _,
            external_modules: _,
            watches: _,
            waiting: _,
            waiting_order: _,
            chains: _,
            waiting_rules: _,
            unlesses: _,
            watch_of_witness: _,
            metaclass_members: _,
            fallback_binds: _,
            field_binds: _,
            binds: _,
            shared: _,
            shared_by_key: _,
            fallback_nodes,
            families,
            namespace_nodes,
            classes_below: _,
            below_nodes,
            instances,
            bound_methods,
            fallbacks,
            inexact: _,
            statement_calls: _,
            statement_news: _,
            made_classes: _,
            new_results: _,
            returned: _,
            class_instances: _,
            roots: _,
            dunder_calls,
            dunder_owners: _,
            site_calls,
            receivers: _,
            entry_receivers,
            completed_receivers: _,
            accesses: _,
            accessor_hooks: _,
            accessor_hooks_by_key: _,
            accessor_hook_rules: _,
            accessors: _,
            accessor_receivers: _,
            writes: _,
            field_writes: _,
            hook_calls: _,
            hook_calls_by_lookup: _,
            deliveries: _,
            deliveries_by_lookup: _,
            descriptors_itself: _,
            store_names: _,
            class_store_names: _,
            field_readers: _,
            builder_fields: _,
            external_callees: _,
            typed_callbacks: _,
            stub_bindings: _,
            bindings: _,
            callbacks,
            callback_values: _,
            protocol_plans: _,
            model_bindings,
            returning,
            wrappers,
            builtin_methods,
            none_arguments: _,
            synced_none_arguments: _,
            none_keywords: _,
            synced_none_keywords: _,
            callees,
            dynamic_accesses: _,
            namespace_names_read: _,
            zero_argument_super: _,
            literal_imports: _,
            synced_literal_imports: _,
            read_namespaces: _,
            super_pairs,
            super_accepted,
            supers,
            typed_objects,
            iterated_nodes,
            length_hints: _,
            length_plans: _,
            reverse_sequences: _,
            namespaces: _,
            namespace_calls: _,
            getmembers: _,
            getmembers_calls: _,
            members_listed: _,
            handed: _,
            tables: _,
            containers,
            protocols: _,
            builder_calls: _,
            patterns,
            outside_types: _,
            annotations: _,
            outside_results,
            library,
            class_tests,
            census: _,
        } = self;
        let mut sizes = vec![
            ("named_nodes", named_nodes.len()),
            ("externals", externals.len()),
            ("consts", consts.len()),
            ("constants", constants.len()),
            ("generators", generators.len()),
            ("coroutines", coroutines.len()),
            ("receiver_calls", receiver_calls.len()),
            ("fallback_nodes", fallback_nodes.len()),
            ("families", families.len()),
            ("namespace_nodes", namespace_nodes.len()),
            ("below_nodes", below_nodes.len()),
            ("instances", instances.len()),
            ("bound_methods", bound_methods.len()),
            ("fallbacks", fallbacks.len()),
            ("dunder_calls", dunder_calls.len()),
            ("site_calls", site_calls.len()),
            ("entry_receivers", entry_receivers.len()),
            ("callbacks", callbacks.len()),
            ("model_bindings", model_bindings.len()),
            ("returning", returning.len()),
            ("wrappers", wrappers.len()),
            ("builtin_methods", builtin_methods.len()),
            ("callees", callees.len()),
            ("super_pairs", super_pairs.len()),
            ("super_accepted", super_accepted.len()),
            ("supers", supers.len()),
            ("typed_objects", typed_objects.len()),
        ];
        containers.table_sizes(iterated_nodes.len(), &mut sizes);
        patterns.table_sizes(&mut sizes);
        class_tests.table_sizes(&mut sizes);
        outside_results.table_sizes(&mut sizes);
        library.table_sizes(&mut sizes);
        sizes
    }
}

impl Engine {
    pub fn table_sizes(&self) -> Vec<(&'static str, usize)> {
        self.state.table_sizes()
    }

    pub fn new(cap: Option<u32>, order: Order) -> Engine {
        let mut objects = Objects::default();
        let saturated = objects.push(Object::Saturated);
        let mut state = State {
            symbols: Symbols::default(),
            objects,
            saturated,
            unknown_external: saturated,
            labels: FxHashMap::default(),
            named_nodes: Vec::new(),
            fields: FxHashMap::default(),
            modules: OrderedMap::default(),
            externals: FxHashMap::default(),
            consts: FxHashMap::default(),
            constants: FxHashMap::default(),
            generators: FxHashMap::default(),
            coroutines: FxHashMap::default(),
            functions: Vec::new(),
            completed_functions: 0,
            called: FxHashSet::default(),
            rules: Vec::new(),
            released_rules: Vec::new(),
            calls: Vec::new(),
            receiver_calls: FxHashMap::default(),
            prefixes: FxHashMap::default(),
            bound_groups: FxHashMap::default(),
            groups: FxHashMap::default(),
            group_records: Vec::new(),
            grouped_externals: FxHashMap::default(),
            site_edges: OrderedMap::default(),
            call_expressions: Vec::new(),
            classes: Vec::new(),
            stubs: Stubs::new(),
            imports: ImportManager::default(),
            stub_definitions: FxHashMap::default(),
            external_modules: FxHashSet::default(),
            watches: FxHashMap::default(),
            waiting: FxHashMap::default(),
            waiting_order: FxHashMap::default(),
            chains: Chains::default(),
            waiting_rules: OrderedSet::default(),
            unlesses: OrderedSet::default(),
            watch_of_witness: FxHashMap::default(),
            metaclass_members: FxHashSet::default(),
            fallback_binds: FxHashSet::default(),
            field_binds: FxHashMap::default(),
            binds: Vec::new(),
            shared: Vec::new(),
            shared_by_key: FxHashMap::default(),
            fallback_nodes: FxHashMap::default(),
            families: FxHashMap::default(),
            namespace_nodes: FxHashMap::default(),
            classes_below: FxHashMap::default(),
            below_nodes: FxHashMap::default(),
            instances: FxHashMap::default(),
            bound_methods: FxHashMap::default(),
            fallbacks: FxHashMap::default(),
            inexact: FxHashMap::default(),
            statement_calls: FxHashMap::default(),
            statement_news: FxHashSet::default(),
            made_classes: FxHashSet::default(),
            new_results: FxHashMap::default(),
            returned: Vec::new(),
            class_instances: FxHashMap::default(),
            roots: FxHashMap::default(),
            dunder_calls: FxHashMap::default(),
            dunder_owners: FxHashMap::default(),
            site_calls: FxHashMap::default(),
            receivers: Vec::new(),
            entry_receivers: Vec::new(),
            completed_receivers: 0,
            accesses: Vec::new(),
            accessor_hooks: Vec::new(),
            accessor_hooks_by_key: FxHashMap::default(),
            accessor_hook_rules: FxHashMap::default(),
            accessors: Vec::new(),
            accessor_receivers: FxHashMap::default(),
            writes: Vec::new(),
            field_writes: FxHashMap::default(),
            hook_calls: Vec::new(),
            hook_calls_by_lookup: FxHashMap::default(),
            deliveries: Vec::new(),
            deliveries_by_lookup: FxHashMap::default(),
            descriptors_itself: FxHashSet::default(),
            store_names: FxHashSet::default(),
            class_store_names: FxHashMap::default(),
            field_readers: FxHashMap::default(),
            builder_fields: FxHashMap::default(),
            external_callees: FxHashMap::default(),
            typed_callbacks: FxHashSet::default(),
            stub_bindings: FxHashMap::default(),
            bindings: Vec::new(),
            callbacks: FxHashMap::default(),
            callback_values: FxHashSet::default(),
            protocol_plans: Vec::new(),
            model_bindings: FxHashMap::default(),
            returning: FxHashMap::default(),
            wrappers: FxHashMap::default(),
            builtin_methods: FxHashMap::default(),
            none_arguments: FxHashMap::default(),
            synced_none_arguments: 0,
            none_keywords: FxHashMap::default(),
            synced_none_keywords: 0,
            callees: FxHashMap::default(),
            dynamic_accesses: Vec::new(),
            namespace_names_read: FxHashSet::default(),
            zero_argument_super: FxHashSet::default(),
            literal_imports: FxHashMap::default(),
            synced_literal_imports: 0,
            read_namespaces: FxHashSet::default(),
            super_pairs: FxHashSet::default(),
            super_accepted: FxHashMap::default(),
            supers: FxHashMap::default(),
            typed_objects: FxHashMap::default(),
            iterated_nodes: FxHashMap::default(),
            length_hints: FxHashSet::default(),
            length_plans: FxHashMap::default(),
            reverse_sequences: FxHashSet::default(),
            namespaces: FxHashSet::default(),
            namespace_calls: FxHashSet::default(),
            getmembers: Vec::new(),
            getmembers_calls: FxHashSet::default(),
            members_listed: FxHashSet::default(),
            handed: Vec::new(),
            containers: containers::Containers::default(),
            protocols: protocols::Protocols::default(),
            builder_calls: Vec::new(),
            patterns: patterns::Patterns::default(),
            outside_types: outside_types::OutsideTypes::default(),
            annotations: annotations::Annotations::default(),
            outside_results: outside_results::OutsideResults::default(),
            library: library::Library::default(),
            class_tests: narrowing::ClassTests::default(),
            tables: BuilderTables::default(),
            census: census::Census::default(),
        };
        let mut graph = Solver::new(saturated, Kind::Saturated.mask(), cap, order);
        let name = state.symbols.intern("<unknown>");
        state.unknown_external = state.new_object(
            &mut graph,
            Object::UnknownExternal(External {
                name,
                steps: EXTERNAL_STEPS_PAST_ROOT_MAX,
                inexact: false,
            }),
        );
        Engine { graph, state }
    }

    pub fn intern(&mut self, text: &str) -> Sym {
        self.state.symbols.intern(text)
    }

    pub fn text(&self, sym: Sym) -> &str {
        self.state.symbols.text(sym)
    }

    pub fn object_name(&self, object: ObjId) -> String {
        self.state.objects.name(object, &self.state.symbols)
    }

    pub fn object(&self, object: ObjId) -> &Object {
        self.state.objects.get(object)
    }

    pub fn saturated(&self) -> ObjId {
        self.state.saturated
    }

    pub fn named_nodes(&self) -> &[NodeId] {
        &self.state.named_nodes
    }

    pub fn label(&self, node: NodeId) -> Option<&str> {
        self.state.labels.get(&node).map(|label| &**label)
    }

    pub fn held(&mut self, node: NodeId) -> Vec<ObjId> {
        self.graph.objects(node)
    }

    pub fn absorbed(&self) -> Vec<ObjId> {
        self.graph.absorbed()
    }

    pub fn work(&self) -> Work {
        self.graph.work()
    }

    pub fn phase(&self) -> u32 {
        self.graph.phase
    }

    pub fn solve(&mut self) {
        self.sync();
        self.state.census_dump(&self.graph, "start", false);
        self.state.solve(&mut self.graph);
        self.state.census_dump(&self.graph, "end", true);
    }
}

impl State {
    fn new_object(&mut self, graph: &mut Graph, object: Object) -> ObjId {
        let kind = object.kind();
        let id = self.objects.push(object);
        graph.declare(id, kind.mask());
        id
    }

    fn node(&mut self, graph: &mut Graph, label: Option<&str>) -> NodeId {
        let node = graph.node();
        if let Some(label) = label {
            self.labels.insert(node, label.into());
            self.named_nodes.push(node);
        }
        node
    }

    fn witness(&mut self, graph: &mut Graph, watch: WatchId) -> NodeId {
        let node = graph.witness(watch);
        self.watch_of_witness.insert(node, watch);
        node
    }

    fn objects_of(&mut self, graph: &mut Graph, node: NodeId) -> Vec<ObjId> {
        graph.objects(node)
    }

    fn follower(&mut self, graph: &mut Graph, source: NodeId, since: u32) -> NodeId {
        graph.follower(self, source, since)
    }

    fn is_saturated(&mut self, graph: &mut Graph, node: NodeId) -> bool {
        graph.is_saturated(node)
    }

    fn apply_now(&mut self, graph: &mut Graph, node: NodeId, rule: RuleId) {
        graph.apply_now(self, node, rule);
    }

    fn read_field(&mut self, graph: &mut Graph, instance: ObjId, name: Sym, dst: NodeId) {
        if let Some(&node) = self
            .fields
            .get(&instance)
            .and_then(|fields| fields.get(&name))
        {
            self.add_edge(graph, node, dst);
            return;
        }
        let &Object::Instance { class, .. } = self.objects.get(instance) else {
            panic!("a field read of an instance")
        };
        self.field_readers
            .entry((class, name))
            .or_default()
            .entry(dst)
            .or_default()
            .push(instance);
    }

    fn holds(&mut self, graph: &mut Graph, node: NodeId, object: ObjId) -> bool {
        graph.holds(node, object)
    }

    fn object_name(&self, object: ObjId) -> String {
        self.objects.name(object, &self.symbols)
    }

    fn constant(&mut self, graph: &mut Graph, object: ObjId) -> NodeId {
        if let Some(&node) = self.constants.get(&object) {
            return node;
        }
        let node = graph.constant(object);
        self.constants.insert(object, node);
        node
    }

    fn add_object(&mut self, graph: &mut Graph, node: NodeId, object: ObjId) {
        self.census.add_object += 1;
        self.census_step(graph);
        graph.add_object(self, node, object);
    }

    fn add_edge(&mut self, graph: &mut Graph, source: NodeId, target: NodeId) {
        self.census.add_edge += 1;
        self.census_step(graph);
        graph.add_edge(self, source, target);
    }

    fn attach(&mut self, graph: &mut Graph, node: NodeId, rule: RuleId) {
        graph.attach(self, node, rule);
    }

    fn field(&mut self, graph: &mut Graph, object: ObjId, name: Sym) -> NodeId {
        assert!(
            !matches!(self.objects.get(object), Object::Const { .. }),
            "a constant has no fields"
        );
        if let Some(&node) = self
            .fields
            .get(&object)
            .and_then(|fields| fields.get(&name))
        {
            return node;
        }
        let label = format!(
            "{}.{}",
            self.objects.name(object, &self.symbols),
            self.symbols.text(name)
        );
        let node = self.node(graph, Some(&label));
        self.fields.entry(object).or_default().insert(name, node);
        if let &Object::Instance { class, .. } = self.objects.get(object) {
            let readers: Vec<NodeId> = self
                .field_readers
                .get(&(class, name))
                .map(|readers| {
                    readers
                        .iter()
                        .filter(|(_, receivers)| receivers.contains(&object))
                        .map(|(&dst, _)| dst)
                        .collect()
                })
                .unwrap_or_default();
            for dst in readers {
                self.add_edge(graph, node, dst);
            }
        }
        node
    }

    fn module(&mut self, graph: &mut Graph, name: &str) -> ObjId {
        let name = self.symbols.intern(name);
        if let Some(&module) = self.modules.get(&name) {
            return module;
        }
        let module = self.new_object(
            graph,
            Object::Module(Module {
                name,
                defines: FxHashSet::default(),
            }),
        );
        self.modules.insert(name, module);
        module
    }

    fn external(&mut self, graph: &mut Graph, name: &str, steps: u32, inexact: bool) -> ObjId {
        let renamed;
        let name = match name.split_once('.') {
            Some(("builtins", rest)) => {
                renamed = format!("{BUILTIN_MODULE}.{rest}");
                &renamed
            }
            None if name == "builtins" => BUILTIN_MODULE,
            _ => name,
        };
        let name = self.symbols.intern(name);
        let key = (name, steps, inexact);
        if let Some(&external) = self.externals.get(&key) {
            return external;
        }
        let external = self.new_object(
            graph,
            Object::External(External {
                name,
                steps,
                inexact,
            }),
        );
        self.externals.insert(key, external);
        external
    }

    fn const_object(&mut self, graph: &mut Graph, value: &Literal) -> ObjId {
        if let Some(&object) = self.consts.get(value) {
            return object;
        }
        let object = self.new_object(
            graph,
            Object::Const {
                value: value.clone(),
                exact: true,
            },
        );
        self.consts.insert(value.clone(), object);
        object
    }

    fn function(
        &mut self,
        graph: &mut Graph,
        name: &str,
        module: &str,
        signature: &Signature,
        defaults: &[(Box<str>, Option<NodeId>)],
        generator: bool,
    ) -> ObjId {
        let mut parameters = Vec::new();
        for parameter in signature.names() {
            let node = self.node(graph, Some(&format!("{name}.{parameter}")));
            parameters.push((self.symbols.intern(parameter), node));
        }
        let return_node = self.node(graph, Some(&format!("{name}.<return>")));
        let optional = defaults
            .iter()
            .map(|(parameter, _)| self.symbols.intern(parameter))
            .collect();
        let given = defaults
            .iter()
            .filter_map(|(parameter, default)| {
                default.map(|default| (self.symbols.intern(parameter), default))
            })
            .collect();
        let function_name = self.symbols.intern(name);
        let module = self.symbols.intern(module);
        let function = self.new_object(
            graph,
            Object::Function(Box::new(Function {
                name: function_name,
                module,
                signature: signature.clone(),
                parameters,
                defaults: given,
                optional,
                return_node: Some(return_node),
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
        if generator {
            let yield_node = self.node(graph, Some(&format!("{name}.<yield>")));
            let sent_node = self.node(graph, Some(&format!("{name}.<sent>")));
            let made = self.objects.function_mut(function);
            made.yield_node = Some(yield_node);
            made.sent_node = Some(sent_node);
        }
        for (parameter, kind) in [(&signature.vararg, "tuple"), (&signature.kwarg, "dict")] {
            let Some(parameter) = parameter.as_deref().filter(|name| !name.is_empty()) else {
                continue;
            };
            let container = Container {
                kind: self.symbols.intern(kind),
                site: function_name,
                length: None,
                exact: true,
            };
            let container = self.new_object(graph, Object::Container(container));
            let made = self.objects.function_mut(function);
            if kind == "tuple" {
                made.varargs = Some(container);
            } else {
                made.varkeywords = Some(container);
            }
            let parameter = self.symbols.intern(parameter);
            let node = self.objects.function(function).parameter(parameter);
            self.add_object(graph, node, container);
        }
        self.functions.push(function);
        function
    }
}
